# ADMIN_ROUTE=codex-bridge-admin
$ErrorActionPreference = 'Stop'

Write-Host '=== MARKETPLACES_NATIVE_E2E_SERVICE_BEGIN ==='

$interactiveUser = (Get-CimInstance Win32_ComputerSystem -ErrorAction Stop).UserName
if ([string]::IsNullOrWhiteSpace($interactiveUser)) { throw 'No interactive Windows user is logged on.' }
Write-Host "INTERACTIVE_USER=$interactiveUser"
Write-Host "BRIDGE_IDENTITY=$([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)"
Write-Host "COMPUTER=$env:COMPUTERNAME"

$runtimeRoot = Join-Path $env:ProgramData 'ChatGPT-PK\marketplaces-native-e2e'
New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null
$childScript = Join-Path $runtimeRoot 'run.ps1'
$resultPath = Join-Path $runtimeRoot 'result.txt'
$taskName = 'ChatGPT-Marketplaces-Native-E2E-Once'
if (Test-Path $resultPath) { Remove-Item $resultPath -Force }

$child = @'
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$resultPath = 'C:\ProgramData\ChatGPT-PK\marketplaces-native-e2e\result.txt'
$lines = New-Object System.Collections.Generic.List[string]
function Add-Line([string]$s) { $lines.Add($s) }
function Flush-Result {
    $safe = $lines -join "`r`n"
    $token = [Environment]::GetEnvironmentVariable('MARKETPLACES_MCP_TOKEN','User')
    if (-not [string]::IsNullOrWhiteSpace($token)) { $safe = $safe.Replace($token, '[REDACTED_MARKETPLACES_MCP_TOKEN]') }
    [IO.File]::WriteAllText($resultPath, $safe, (New-Object Text.UTF8Encoding($false)))
}
try {
    Add-Line "EXEC_IDENTITY=$([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)"
    Add-Line "EXEC_SESSION=$((Get-Process -Id $PID).SessionId)"
    $token = [Environment]::GetEnvironmentVariable('MARKETPLACES_MCP_TOKEN','User')
    Add-Line ("TOKEN_USER_ENV_PRESENT=" + [bool](-not [string]::IsNullOrWhiteSpace($token)))

    $globalConfig = Join-Path $HOME '.codex\config.toml'
    Add-Line "GLOBAL_CODEX_CONFIG_EXISTS=$(Test-Path $globalConfig)"
    if (Test-Path $globalConfig) {
        $cfg = Get-Content -Raw -LiteralPath $globalConfig
        Add-Line ("GLOBAL_HAS_MARKETPLACES_YANDEX=" + [bool]($cfg -match '(?m)^\[mcp_servers\.marketplaces-yandex\]'))
        Add-Line ("GLOBAL_USES_TOKEN_ENV=" + [bool]($cfg -match 'bearer_token_env_var\s*=\s*"MARKETPLACES_MCP_TOKEN"'))
        Add-Line ("GLOBAL_REMOTE_HTTPS=" + [bool]($cfg -match '(?ms)\[mcp_servers\.marketplaces-yandex\].*?url\s*=\s*"https://'))
        Add-Line ("GLOBAL_REMOTE_REQUIRED=" + [bool]($cfg -match '(?ms)\[mcp_servers\.marketplaces-yandex\].*?required\s*=\s*true'))
    }

    $candidates = @(
        'G:\Мой диск\Marketplaces\MCP отчеты МП\marketplaces-mcp-only',
        'G:\My Drive\Marketplaces\MCP отчеты МП\marketplaces-mcp-only',
        (Join-Path $HOME 'My Drive\Marketplaces\MCP отчеты МП\marketplaces-mcp-only'),
        (Join-Path $HOME 'Google Drive\My Drive\Marketplaces\MCP отчеты МП\marketplaces-mcp-only')
    )
    $project = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $project) {
        foreach ($drive in (Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Root })) {
            foreach ($name in @('Мой диск','My Drive')) {
                $p = Join-Path $drive.Root "$name\Marketplaces\MCP отчеты МП\marketplaces-mcp-only"
                if (Test-Path $p) { $project = $p; break }
            }
            if ($project) { break }
        }
    }
    Add-Line "PROJECT_FOUND=$([bool]$project)"
    if (-not $project) { throw 'marketplaces-mcp-only project was not found on synchronized Google Drive.' }
    Add-Line "PROJECT_PATH=$project"

    $agents = Join-Path $project 'AGENTS.md'
    Add-Line "AGENTS_EXISTS=$(Test-Path $agents)"
    if (Test-Path $agents) {
        $a = Get-Content -Raw -LiteralPath $agents
        Add-Line ("AGENTS_MCP_ONLY=" + [bool]($a -match 'marketplaces-yandex'))
        Add-Line ("AGENTS_FAIL_CLOSED=" + [bool]($a -match '(?i)fail-closed'))
    }

    $projectCfg = Join-Path $project '.codex\config.toml'
    Add-Line "PROJECT_CODEX_CONFIG_EXISTS=$(Test-Path $projectCfg)"
    if (Test-Path $projectCfg) {
        $pc = Get-Content -Raw -LiteralPath $projectCfg
        Add-Line ("PROJECT_REMOTE_ENABLED=" + [bool]($pc -match '(?ms)\[mcp_servers\.marketplaces-yandex\].*?enabled\s*=\s*true'))
        Add-Line ("PROJECT_WB_LOCAL_DISABLED=" + [bool]($pc -match '(?ms)\[mcp_servers\.wildberries\].*?enabled\s*=\s*false'))
        Add-Line ("PROJECT_OZON_LOCAL_DISABLED=" + [bool]($pc -match '(?ms)\[mcp_servers\.ozon\].*?enabled\s*=\s*false'))
        Add-Line ("PROJECT_OZON_PERF_LOCAL_DISABLED=" + [bool]($pc -match '(?ms)\[mcp_servers\.ozon-perf\].*?enabled\s*=\s*false'))
    }

    $codex = Get-Command codex -ErrorAction SilentlyContinue
    if (-not $codex) {
        $possible = @((Join-Path $HOME 'AppData\Roaming\npm\codex.cmd'),(Join-Path $HOME 'AppData\Local\Programs\codex\codex.exe')) | Where-Object { Test-Path $_ } | Select-Object -First 1
        if ($possible) { $codexPath = $possible } else { throw 'Codex CLI was not found for interactive user.' }
    } else { $codexPath = $codex.Source }
    Add-Line 'CODEX_FOUND=True'
    Add-Line "CODEX_PATH=$codexPath"
    $ver = (& $codexPath --version 2>&1 | Out-String).Trim(); Add-Line "CODEX_VERSION=$ver"

    Push-Location $project
    try {
        $prompt = 'Покажи один существующий товар Ozon из моего кабинета. Используй только разрешённый remote MCP marketplaces-yandex. Не используй локальные wildberries, ozon или ozon-perf. В конце коротко укажи фактически использованные MCP server и tool.'
        Add-Line 'PROMPT=Покажи один существующий товар Ozon из моего кабинета.'
        $output = & $codexPath exec --skip-git-repo-check --sandbox read-only --color never $prompt 2>&1 | Out-String
        $exit = $LASTEXITCODE; if ($null -eq $exit) { $exit = 0 }
        Add-Line "CODEX_EXIT=$exit"
        Add-Line '--- CODEX_OUTPUT_BEGIN ---'; Add-Line $output.Trim(); Add-Line '--- CODEX_OUTPUT_END ---'
        Add-Line ("OUTPUT_MENTIONS_MARKETPLACES_YANDEX=" + [bool]($output -match 'marketplaces-yandex'))
        Add-Line ("OUTPUT_MENTIONS_OZON_GET_PRODUCTS=" + [bool]($output -match 'ozon_get_products'))
        Add-Line ("OUTPUT_LOOKS_SUCCESSFUL=" + [bool]($exit -eq 0 -and $output -notmatch '(?i)error|ошибк|failed'))
        if ($exit -ne 0) { throw "Codex exec failed with exit code $exit." }
        if ($output -notmatch 'marketplaces-yandex') { throw 'Codex output did not identify marketplaces-yandex.' }
        if ($output -notmatch 'ozon_get_products') { throw 'Codex output did not identify ozon_get_products.' }
    } finally { Pop-Location }
    Add-Line 'END_TO_END_ACCEPTANCE=PASS'
} catch {
    Add-Line 'END_TO_END_ACCEPTANCE=FAIL'; Add-Line "ERROR=$($_.Exception.Message)"
} finally { Flush-Result }
'@

[IO.File]::WriteAllText($childScript, $child, (New-Object Text.UTF8Encoding($false)))
try { Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue } catch {}
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$childScript`""
$principal = New-ScheduledTaskPrincipal -UserId $interactiveUser -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 8) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
try {
    Register-ScheduledTask -TaskName $taskName -Action $action -Principal $principal -Settings $settings -Force | Out-Null
    Write-Host 'TASK_REGISTERED=YES'; Start-ScheduledTask -TaskName $taskName; Write-Host 'TASK_STARTED=YES'
    $deadline = (Get-Date).AddMinutes(8)
    while ((Get-Date) -lt $deadline -and -not (Test-Path $resultPath)) { Start-Sleep -Seconds 3 }
    if (-not (Test-Path $resultPath)) { throw 'Timed out waiting for native Codex E2E result.' }
    Write-Host '--- NATIVE_E2E_RESULT_BEGIN ---'; Get-Content -Raw -LiteralPath $resultPath; Write-Host '--- NATIVE_E2E_RESULT_END ---'
} finally {
    try { Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue } catch {}
    Remove-Item $childScript -Force -ErrorAction SilentlyContinue
    Remove-Item $resultPath -Force -ErrorAction SilentlyContinue
    try { Remove-Item $runtimeRoot -Force -ErrorAction SilentlyContinue } catch {}
}
Write-Host '=== MARKETPLACES_NATIVE_E2E_SERVICE_END ==='
