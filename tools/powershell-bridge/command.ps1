# SERVICE_ROUTE=codex-bridge-service
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

Write-Host '=== MARKETPLACES_NATIVE_E2E_CLONED_TASK_BEGIN ==='
Write-Host "COMPUTER=$env:COMPUTERNAME"
Write-Host "BRIDGE_IDENTITY=$([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)"

$canonicalTaskName = 'MarketplaceCardMonitor-UserNode-Canonical'
$tempTaskName = 'ChatGPT-Marketplaces-Native-E2E-Cloned'
$runtimeRoot = Join-Path $env:ProgramData 'ChatGPT-PK\marketplaces-native-e2e'
$childScript = Join-Path $runtimeRoot 'run.ps1'
$resultPath = Join-Path $runtimeRoot 'result.txt'
$startedPath = Join-Path $runtimeRoot 'started.txt'
New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null
foreach ($p in @($resultPath,$startedPath)) { if (Test-Path $p) { Remove-Item $p -Force } }

$canonical = Get-ScheduledTask -TaskName $canonicalTaskName -ErrorAction Stop
$canonicalInfo = Get-ScheduledTaskInfo -TaskName $canonicalTaskName -ErrorAction Stop
Write-Host "CANONICAL_TASK_FOUND=YES"
Write-Host "CANONICAL_STATE=$($canonical.State)"
Write-Host "CANONICAL_LAST_RESULT=$($canonicalInfo.LastTaskResult)"
Write-Host "CANONICAL_USER=$($canonical.Principal.UserId)"
Write-Host "CANONICAL_LOGON_TYPE=$($canonical.Principal.LogonType)"
Write-Host "CANONICAL_RUN_LEVEL=$($canonical.Principal.RunLevel)"

$child = @'
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$runtimeRoot = 'C:\ProgramData\ChatGPT-PK\marketplaces-native-e2e'
$resultPath = Join-Path $runtimeRoot 'result.txt'
$startedPath = Join-Path $runtimeRoot 'started.txt'
$lines = New-Object System.Collections.Generic.List[string]
function Add-Line([string]$s) { $lines.Add($s) }
function Flush-Result {
    $safe = $lines -join "`r`n"
    $token = [Environment]::GetEnvironmentVariable('MARKETPLACES_MCP_TOKEN','User')
    if (-not [string]::IsNullOrWhiteSpace($token)) { $safe = $safe.Replace($token, '[REDACTED_MARKETPLACES_MCP_TOKEN]') }
    [IO.File]::WriteAllText($resultPath, $safe, (New-Object Text.UTF8Encoding($false)))
}

"STARTED $(Get-Date -Format o) USER=$([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) SESSION=$((Get-Process -Id $PID).SessionId)" |
    Set-Content -LiteralPath $startedPath -Encoding UTF8

try {
    Add-Line "EXEC_IDENTITY=$([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)"
    Add-Line "EXEC_SESSION=$((Get-Process -Id $PID).SessionId)"
    Add-Line "HOME=$HOME"

    $token = [Environment]::GetEnvironmentVariable('MARKETPLACES_MCP_TOKEN','User')
    Add-Line ("TOKEN_USER_ENV_PRESENT=" + [bool](-not [string]::IsNullOrWhiteSpace($token)))

    $globalConfig = Join-Path $HOME '.codex\config.toml'
    Add-Line "GLOBAL_CODEX_CONFIG_EXISTS=$(Test-Path $globalConfig)"
    if (Test-Path $globalConfig) {
        $cfg = Get-Content -Raw -LiteralPath $globalConfig
        Add-Line ("GLOBAL_HAS_MARKETPLACES_YANDEX=" + [bool]($cfg -match '(?m)^\[mcp_servers\.marketplaces-yandex\]'))
        Add-Line ("GLOBAL_USES_TOKEN_ENV=" + [bool]($cfg -match 'bearer_token_env_var\s*=\s*"MARKETPLACES_MCP_TOKEN"'))
        Add-Line ("GLOBAL_REMOTE_HTTPS=" + [bool]($cfg -match '(?ms)\[mcp_servers\.marketplaces-yandex\].*?url\s*=\s*"https://'))
    }

    $candidates = @(
        'G:\Мой диск\Marketplaces\MCP отчеты МП\marketplaces-mcp-only',
        'G:\My Drive\Marketplaces\MCP отчеты МП\marketplaces-mcp-only'
    )
    $project = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $project -and (Test-Path 'G:\')) {
        $project = Get-ChildItem -LiteralPath 'G:\' -Directory -Recurse -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -eq 'marketplaces-mcp-only' } |
            Select-Object -First 1 -ExpandProperty FullName
    }
    Add-Line "PROJECT_FOUND=$([bool]$project)"
    if (-not $project) { throw 'marketplaces-mcp-only project was not found.' }
    Add-Line "PROJECT_PATH=$project"

    $agents = Join-Path $project 'AGENTS.md'
    Add-Line "AGENTS_EXISTS=$(Test-Path -LiteralPath $agents)"
    if (Test-Path -LiteralPath $agents) {
        $a = Get-Content -Raw -LiteralPath $agents
        Add-Line ("AGENTS_MCP_ONLY=" + [bool]($a -match 'marketplaces-yandex'))
        Add-Line ("AGENTS_FAIL_CLOSED=" + [bool]($a -match '(?i)fail-closed'))
    }

    $projectCfg = Join-Path $project '.codex\config.toml'
    Add-Line "PROJECT_CODEX_CONFIG_EXISTS=$(Test-Path -LiteralPath $projectCfg)"
    if (Test-Path -LiteralPath $projectCfg) {
        $pc = Get-Content -Raw -LiteralPath $projectCfg
        Add-Line ("PROJECT_REMOTE_ENABLED=" + [bool]($pc -match '(?ms)\[mcp_servers\.marketplaces-yandex\].*?enabled\s*=\s*true'))
        Add-Line ("PROJECT_WB_LOCAL_DISABLED=" + [bool]($pc -match '(?ms)\[mcp_servers\.wildberries\].*?enabled\s*=\s*false'))
        Add-Line ("PROJECT_OZON_LOCAL_DISABLED=" + [bool]($pc -match '(?ms)\[mcp_servers\.ozon\].*?enabled\s*=\s*false'))
        Add-Line ("PROJECT_OZON_PERF_LOCAL_DISABLED=" + [bool]($pc -match '(?ms)\[mcp_servers\.ozon-perf\].*?enabled\s*=\s*false'))
    }

    $codex = Get-Command codex -ErrorAction SilentlyContinue
    if ($codex) { $codexPath = $codex.Source }
    else {
        $possible = @(
            (Join-Path $HOME 'AppData\Roaming\npm\codex.cmd'),
            (Join-Path $HOME 'AppData\Local\Programs\codex\codex.exe')
        ) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
        if (-not $possible) { throw 'Codex CLI was not found for interactive user.' }
        $codexPath = $possible
    }
    Add-Line 'CODEX_FOUND=True'
    Add-Line "CODEX_PATH=$codexPath"
    $ver = (& $codexPath --version 2>&1 | Out-String).Trim()
    Add-Line "CODEX_VERSION=$ver"

    Push-Location $project
    try {
        $prompt = 'Покажи один существующий товар Ozon из моего кабинета. Используй только разрешённый remote MCP marketplaces-yandex. Не используй локальные wildberries, ozon или ozon-perf. В конце коротко укажи фактически использованные MCP server и tool.'
        Add-Line 'PROMPT=Покажи один существующий товар Ozon из моего кабинета.'
        $output = & $codexPath exec --skip-git-repo-check --sandbox read-only --color never $prompt 2>&1 | Out-String
        $exit = $LASTEXITCODE
        if ($null -eq $exit) { $exit = 0 }
        Add-Line "CODEX_EXIT=$exit"
        Add-Line '--- CODEX_OUTPUT_BEGIN ---'
        Add-Line $output.Trim()
        Add-Line '--- CODEX_OUTPUT_END ---'
        Add-Line ("OUTPUT_MENTIONS_MARKETPLACES_YANDEX=" + [bool]($output -match 'marketplaces-yandex'))
        Add-Line ("OUTPUT_MENTIONS_OZON_GET_PRODUCTS=" + [bool]($output -match 'ozon_get_products'))
        Add-Line ("OUTPUT_LOOKS_SUCCESSFUL=" + [bool]($exit -eq 0 -and $output -notmatch '(?i)failed|fatal|ошибка'))
        if ($exit -ne 0) { throw "Codex exec failed with exit code $exit." }
        if ($output -notmatch 'marketplaces-yandex') { throw 'Codex output did not identify marketplaces-yandex.' }
        if ($output -notmatch 'ozon_get_products') { throw 'Codex output did not identify ozon_get_products.' }
    }
    finally { Pop-Location }

    Add-Line 'END_TO_END_ACCEPTANCE=PASS'
}
catch {
    Add-Line 'END_TO_END_ACCEPTANCE=FAIL'
    Add-Line "ERROR=$($_.Exception.Message)"
}
finally {
    Flush-Result
}
'@

[IO.File]::WriteAllText($childScript, $child, (New-Object System.Text.UnicodeEncoding($false, $true)))

try {
    Unregister-ScheduledTask -TaskName $tempTaskName -Confirm:$false -ErrorAction SilentlyContinue

    [xml]$xml = Export-ScheduledTask -TaskName $canonicalTaskName -ErrorAction Stop
    $exec = $xml.Task.Actions.Exec
    if ($null -eq $exec) { throw 'Canonical task does not have an Exec action.' }
    $exec.Command = 'powershell.exe'
    $exec.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$childScript`""
    if ($xml.Task.RegistrationInfo.URI) { $xml.Task.RegistrationInfo.URI = "\$tempTaskName" }
    if ($xml.Task.Triggers) { $xml.Task.RemoveChild($xml.Task.Triggers) | Out-Null }

    Register-ScheduledTask -TaskName $tempTaskName -Xml $xml.OuterXml -Force | Out-Null
    $temp = Get-ScheduledTask -TaskName $tempTaskName
    Write-Host 'CLONED_TASK_REGISTERED=YES'
    Write-Host "CLONED_USER=$($temp.Principal.UserId)"
    Write-Host "CLONED_LOGON_TYPE=$($temp.Principal.LogonType)"
    Write-Host "CLONED_RUN_LEVEL=$($temp.Principal.RunLevel)"

    & schtasks.exe /Run /TN "\$tempTaskName" | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "schtasks /Run failed: $LASTEXITCODE" }
    Write-Host 'CLONED_TASK_TRIGGERED=YES'

    $startDeadline = (Get-Date).AddSeconds(45)
    while ((Get-Date) -lt $startDeadline -and -not (Test-Path $startedPath)) { Start-Sleep -Seconds 2 }
    Write-Host '--- START_MARKER ---'
    if (Test-Path $startedPath) { Get-Content -Raw -LiteralPath $startedPath } else { Write-Host 'NOT_FOUND' }

    $deadline = (Get-Date).AddMinutes(8)
    while ((Get-Date) -lt $deadline -and -not (Test-Path $resultPath)) { Start-Sleep -Seconds 3 }

    if (-not (Test-Path $resultPath)) {
        $ti = Get-ScheduledTaskInfo -TaskName $tempTaskName
        $ts = Get-ScheduledTask -TaskName $tempTaskName
        Write-Host "CLONED_TASK_STATE=$($ts.State)"
        Write-Host "CLONED_TASK_LAST_RESULT=$($ti.LastTaskResult)"
        throw 'Timed out waiting for cloned-task Codex E2E result.'
    }

    Write-Host '--- NATIVE_E2E_RESULT_BEGIN ---'
    Get-Content -Raw -LiteralPath $resultPath
    Write-Host '--- NATIVE_E2E_RESULT_END ---'
}
finally {
    try { Unregister-ScheduledTask -TaskName $tempTaskName -Confirm:$false -ErrorAction SilentlyContinue } catch {}
    Remove-Item $childScript -Force -ErrorAction SilentlyContinue
    Remove-Item $resultPath -Force -ErrorAction SilentlyContinue
    Remove-Item $startedPath -Force -ErrorAction SilentlyContinue
    try { Remove-Item $runtimeRoot -Force -ErrorAction SilentlyContinue } catch {}
}

Write-Host '=== MARKETPLACES_NATIVE_E2E_CLONED_TASK_END ==='
