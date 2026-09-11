param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('safe', 'write', 'dangerous')]
    [string]$Mode,

    [Parameter(Mandatory = $true)]
    [string]$ScriptPath
)

$ErrorActionPreference = 'Stop'

function Deny([string]$Reason) {
    Write-Host "BRIDGE_GUARD=DENY"
    Write-Host "BRIDGE_GUARD_REASON=$Reason"
    exit 93
}

if (-not (Test-Path -LiteralPath $ScriptPath -PathType Leaf)) {
    Deny 'command file is missing'
}

$content = Get-Content -LiteralPath $ScriptPath -Raw
$bytes = [Text.Encoding]::UTF8.GetByteCount($content)
if ($bytes -gt 65536) { Deny 'command exceeds 64 KiB limit' }
if ([string]::IsNullOrWhiteSpace($content)) { Deny 'command is empty' }

if ($Mode -eq 'dangerous') {
    Deny 'dangerous mode is intentionally fail-closed; use a separately approved maintenance path'
}

# Secrets must never travel through Git history or Actions logs.
$secretLiteralPatterns = @(
    '(?i)-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----',
    '(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{24,}',
    '(?i)\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b',
    '(?i)(password|passwd|api[_-]?key|client[_-]?secret|access[_-]?token|refresh[_-]?token)\s*=\s*["''][^"'']{8,}["'']'
)
foreach ($pattern in $secretLiteralPatterns) {
    if ($content -match $pattern) { Deny 'possible literal secret detected in command' }
}

# Dynamic execution bypasses static policy and is never allowed.
$alwaysDenied = @(
    '(?i)\bInvoke-Expression\b|\biex\b',
    '(?i)-EncodedCommand\b|-EncodedArguments\b',
    '(?i)\bAdd-Type\b',
    '(?i)\bDownloadString\s*\(|\bDownloadFile\s*\(',
    '(?i)\bFromBase64String\s*\(',
    '(?i)\bStart-Job\b|\bInvoke-Command\b|\bEnter-PSSession\b|\bNew-PSSession\b',
    '(?i)\byc\s+lockbox\s+payload\s+get\b',
    '(?i)(Get-Content|gc|type)\b[^\r\n]*(\.env\b|cabinets\.json\b|\\\.ssh\\|credentials|secrets?|tokens?|passwords?|\.pem\b|\.pfx\b|\.p12\b|\.key\b)',
    '(?i)\$env:[A-Za-z0-9_]*(TOKEN|SECRET|PASSWORD|PASSWD|API_KEY|PRIVATE_KEY)[A-Za-z0-9_]*'
)
foreach ($pattern in $alwaysDenied) {
    if ($content -match $pattern) { Deny "blocked sensitive or dynamic pattern: $pattern" }
}

$tokens = $null
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    $ScriptPath,
    [ref]$tokens,
    [ref]$parseErrors
)
if ($parseErrors.Count -gt 0) {
    Deny ('PowerShell parse error: ' + $parseErrors[0].Message)
}

if ($Mode -eq 'safe') {
    # SAFE is intentionally narrow: diagnostics and inspection only.
    $allowed = @{
        'write-host' = $true; 'write-output' = $true
        'get-date' = $true; 'get-command' = $true; 'get-location' = $true
        'get-process' = $true; 'get-service' = $true
        'get-childitem' = $true; 'get-item' = $true; 'get-itemproperty' = $true
        'get-content' = $true; 'get-filehash' = $true; 'get-acl' = $true
        'test-path' = $true; 'resolve-path' = $true
        'select-object' = $true; 'where-object' = $true; 'foreach-object' = $true
        'measure-object' = $true; 'sort-object' = $true; 'group-object' = $true
        'format-table' = $true; 'format-list' = $true; 'out-string' = $true
        'convertto-json' = $true; 'convertfrom-json' = $true
        'get-ciminstance' = $true; 'get-wmiobject' = $true
        'get-scheduledtask' = $true; 'get-scheduledtaskinfo' = $true
        'get-nettcpconnection' = $true; 'get-netipconfiguration' = $true
        'get-netipaddress' = $true; 'get-netroute' = $true
        'get-dnsclientserveraddress' = $true; 'test-netconnection' = $true
        'whoami.exe' = $true; 'hostname.exe' = $true; 'ipconfig.exe' = $true
        'netstat.exe' = $true; 'nslookup.exe' = $true; 'ping.exe' = $true
        'tasklist.exe' = $true; 'sc.exe' = $true
        'git' = $true; 'git.exe' = $true; 'yc' = $true; 'yc.exe' = $true
    }

    $invokeMembers = $ast.FindAll({ param($n)
        $n -is [System.Management.Automation.Language.InvokeMemberExpressionAst]
    }, $true)
    if ($invokeMembers.Count -gt 0) { Deny 'SAFE mode forbids .NET/member method invocation' }

    $redirections = $ast.FindAll({ param($n)
        $n -is [System.Management.Automation.Language.FileRedirectionAst]
    }, $true)
    if ($redirections.Count -gt 0) { Deny 'SAFE mode forbids file redirection' }

    $assignments = $ast.FindAll({ param($n)
        $n -is [System.Management.Automation.Language.AssignmentStatementAst]
    }, $true)
    foreach ($assignment in $assignments) {
        if (-not ($assignment.Left -is [System.Management.Automation.Language.VariableExpressionAst])) {
            Deny 'SAFE mode permits assignment only to local variables'
        }
    }

    $commands = $ast.FindAll({ param($n)
        $n -is [System.Management.Automation.Language.CommandAst]
    }, $true)
    foreach ($command in $commands) {
        $name = $command.GetCommandName()
        if ([string]::IsNullOrWhiteSpace($name)) { Deny 'SAFE mode forbids dynamic command names' }
        $base = [IO.Path]::GetFileName($name).ToLowerInvariant()
        if (-not $allowed.ContainsKey($base)) {
            Deny "command '$name' is not in SAFE allowlist"
        }

        $text = $command.Extent.Text
        if ($base -in @('git', 'git.exe')) {
            if ($text -notmatch '(?i)^\s*(?:[^\s]*\\)?git(?:\.exe)?\s+(status|log|diff|show|rev-parse|ls-files|ls-tree|remote\s+-v)\b') {
                Deny "git operation is not read-only: $text"
            }
        }
        if ($base -in @('yc', 'yc.exe')) {
            if ($text -match '(?i)\b(create|update|delete|set|add|remove|start|stop|restart|attach|detach|apply|add-version)\b') {
                Deny "yc mutating operation is not allowed in SAFE mode: $text"
            }
            if ($text -notmatch '(?i)\b(list|get|describe|version)\b') {
                Deny "yc operation is not recognized as read-only: $text"
            }
        }
        if ($base -eq 'sc.exe' -and $text -notmatch '(?i)\b(query|queryex|qc)\b') {
            Deny "sc.exe operation is not read-only: $text"
        }
    }
}

if ($Mode -eq 'write') {
    # WRITE permits ordinary file/repository/application changes, but blocks
    # destructive OS/admin/cloud operations. NETWORK SERVICE remains the OS sandbox.
    $dangerPatterns = @(
        '(?i)\bRemove-Item\b|\bClear-Content\b|\bFormat-Volume\b|\bClear-Disk\b|\bInitialize-Disk\b',
        '(?i)\bStop-Computer\b|\bRestart-Computer\b|\bshutdown(?:\.exe)?\b|\bbcdedit(?:\.exe)?\b|\bdiskpart(?:\.exe)?\b',
        '(?i)\bSet-Acl\b|\btakeown(?:\.exe)?\b|\bicacls(?:\.exe)?\b',
        '(?i)\bNew-LocalUser\b|\bSet-LocalUser\b|\bRemove-LocalUser\b|\bAdd-LocalGroupMember\b|\bRemove-LocalGroupMember\b',
        '(?i)\bRegister-ScheduledTask\b|\bUnregister-ScheduledTask\b|\bSet-Service\b|\bStop-Service\b|\bRestart-Service\b',
        '(?i)\bNew-NetFirewallRule\b|\bSet-NetFirewallRule\b|\bRemove-NetFirewallRule\b',
        '(?i)\bSet-MpPreference\b|\bAdd-MpPreference\b|\bRemove-MpPreference\b',
        '(?i)\breg(?:\.exe)?\s+(delete|add)\b',
        '(?i)\bsc(?:\.exe)?\s+(delete|config|stop)\b',
        '(?i)\bschtasks(?:\.exe)?\s+/delete\b',
        '(?i)\bgit(?:\.exe)?\s+(reset\s+--hard|clean\s+-|checkout\s+--\s+\.|restore\s+--source)\b',
        '(?i)\bterraform(?:\.exe)?\s+(destroy|apply)\b',
        '(?i)\byc\b[^\r\n]*\b(delete|remove)\b'
    )
    foreach ($pattern in $dangerPatterns) {
        if ($content -match $pattern) { Deny "WRITE mode blocked destructive pattern: $pattern" }
    }
}

Write-Host 'BRIDGE_GUARD=PASS'
Write-Host "BRIDGE_MODE=$Mode"
Write-Host "BRIDGE_COMMAND_BYTES=$bytes"
exit 0
