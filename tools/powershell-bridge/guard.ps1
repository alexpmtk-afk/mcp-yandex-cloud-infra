param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('safe', 'write', 'dangerous')]
    [string]$Mode,

    [Parameter(Mandatory = $true)]
    [string]$ScriptPath
)

$ErrorActionPreference = 'Stop'

function Deny([string]$Reason) {
    Write-Host 'GUARD_RESULT=BLOCK'
    Write-Host 'BRIDGE_GUARD=DENY'
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

$secretLiteralPatterns = @(
    '(?i)-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----',
    '(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{24,}',
    '(?i)\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b',
    '(?i)(password|passwd|api[_-]?key|client[_-]?secret|access[_-]?token|refresh[_-]?token)\s*=\s*["''][^"'']{8,}["'']'
)
foreach ($pattern in $secretLiteralPatterns) {
    if ($content -match $pattern) { Deny 'possible literal secret detected in command' }
}

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

$safeAllowed = @{
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

function Check-ReadonlyExternal([string]$Base, [string]$Text) {
    if ($Base -in @('git', 'git.exe')) {
        if ($Text -notmatch '(?i)^\s*(?:[^\s]*\\)?git(?:\.exe)?\s+(status|log|diff|show|rev-parse|ls-files|ls-tree|remote\s+-v)\b') {
            Deny "git operation is not read-only: $Text"
        }
    }
    if ($Base -in @('yc', 'yc.exe')) {
        if ($Text -match '(?i)\b(create|update|delete|set|add|remove|start|stop|restart|attach|detach|apply|add-version)\b') {
            Deny "yc mutating operation is not allowed: $Text"
        }
        if ($Text -notmatch '(?i)\b(list|get|describe|version)\b') {
            Deny "yc operation is not recognized as read-only: $Text"
        }
    }
    if ($Base -eq 'sc.exe' -and $Text -notmatch '(?i)\b(query|queryex|qc|qfailure|qfailureflag)\b') {
        Deny "sc.exe operation is not read-only: $Text"
    }
}

if ($Mode -eq 'safe') {
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
        if (-not $safeAllowed.ContainsKey($base)) {
            Deny "command '$name' is not in SAFE allowlist"
        }
        Check-ReadonlyExternal $base $command.Extent.Text
    }
}

function Get-LiteralParameterValue($Command, [string[]]$Names) {
    $elements = $Command.CommandElements
    for ($i = 1; $i -lt $elements.Count; $i++) {
        $element = $elements[$i]
        if ($element -is [System.Management.Automation.Language.CommandParameterAst]) {
            $parameterName = $element.ParameterName.ToLowerInvariant()
            if ($Names -contains $parameterName) {
                $argument = $element.Argument
                if ($null -eq $argument) {
                    if (($i + 1) -ge $elements.Count) { Deny "missing argument for -$parameterName" }
                    $argument = $elements[$i + 1]
                }
                if ($argument -is [System.Management.Automation.Language.StringConstantExpressionAst]) {
                    return [string]$argument.Value
                }
                Deny "WRITE requires literal string argument for -$parameterName"
            }
        }
    }
    return $null
}

function Assert-AllowedWritePath([string]$Path) {
    if ([string]::IsNullOrWhiteSpace($Path)) { Deny 'WRITE command is missing explicit -Path/-LiteralPath' }
    if ($Path -match '(^|[\\/])\.\.([\\/]|$)') { Deny 'WRITE path traversal is forbidden' }

    try {
        $full = [IO.Path]::GetFullPath($Path)
        $root = [IO.Path]::GetFullPath('C:\ProgramData\ChatGPT-PK').TrimEnd('\')
    }
    catch {
        Deny 'WRITE path could not be canonicalized'
    }

    $inside = $full.Equals($root, [StringComparison]::OrdinalIgnoreCase) -or
              $full.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase)
    if (-not $inside) {
        Deny "WRITE path is outside allowlisted root C:\ProgramData\ChatGPT-PK: $full"
    }
}

if ($Mode -eq 'write') {
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

    $invokeMembers = $ast.FindAll({ param($n)
        $n -is [System.Management.Automation.Language.InvokeMemberExpressionAst]
    }, $true)
    if ($invokeMembers.Count -gt 0) { Deny 'WRITE mode forbids .NET/member method invocation' }

    $redirections = $ast.FindAll({ param($n)
        $n -is [System.Management.Automation.Language.FileRedirectionAst]
    }, $true)
    if ($redirections.Count -gt 0) { Deny 'WRITE mode forbids file redirection; use approved file cmdlets' }

    $writeAllowed = @{}
    foreach ($key in $safeAllowed.Keys) { $writeAllowed[$key] = $true }
    $writeAllowed['new-item'] = $true
    $writeAllowed['set-content'] = $true
    $writeAllowed['add-content'] = $true

    $commands = $ast.FindAll({ param($n)
        $n -is [System.Management.Automation.Language.CommandAst]
    }, $true)
    foreach ($command in $commands) {
        $name = $command.GetCommandName()
        if ([string]::IsNullOrWhiteSpace($name)) { Deny 'WRITE mode forbids dynamic command names' }
        $base = [IO.Path]::GetFileName($name).ToLowerInvariant()
        if (-not $writeAllowed.ContainsKey($base)) {
            Deny "command '$name' is not in WRITE allowlist"
        }

        if ($safeAllowed.ContainsKey($base)) {
            Check-ReadonlyExternal $base $command.Extent.Text
        }

        if ($base -in @('new-item', 'set-content', 'add-content')) {
            $path = Get-LiteralParameterValue $command @('literalpath', 'path')
            Assert-AllowedWritePath $path
        }

        if ($base -eq 'new-item') {
            $itemType = Get-LiteralParameterValue $command @('itemtype')
            if ($itemType -notin @('Directory', 'File')) {
                Deny 'New-Item in WRITE mode requires -ItemType Directory or File'
            }
        }
    }
}

Write-Host 'GUARD_RESULT=PASS'
Write-Host 'BRIDGE_GUARD=PASS'
Write-Host "BRIDGE_MODE=$Mode"
Write-Host "BRIDGE_COMMAND_BYTES=$bytes"
exit 0
