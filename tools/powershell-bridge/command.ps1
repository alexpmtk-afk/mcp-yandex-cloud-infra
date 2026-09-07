$ErrorActionPreference = 'Stop'

Write-Host '=== OZON_HOME_YANDEX_SMOKE_BEGIN ==='

$user = "$env:COMPUTERNAME\Win10_Game_OS"
$runtimeRoot = 'C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
$repoRoot = Join-Path $runtimeRoot 'repo'
$browser = 'C:\Program Files\Yandex\YandexBrowser\Application\browser.exe'
$launcher = Join-Path $runtimeRoot 'launch-ozon-yandex-smoke.ps1'
$taskName = 'MarketplaceCardMonitor-Ozon-Yandex-Smoke'

$exitFile = Join-Path $runtimeRoot 'task-exit.json'
$gateFile = Join-Path $runtimeRoot 'latest-gate.json'
$bootstrapFile = Join-Path $runtimeRoot 'bootstrap-status.json'
$logFile = Join-Path $runtimeRoot 'task-latest.log'

if (-not (Test-Path $browser)) {
    throw "Yandex Browser not found: $browser"
}

if (-not (Test-Path (Join-Path $repoRoot '.git'))) {
    throw "Marketplace Card Monitor repo not found: $repoRoot"
}

foreach ($path in @(
    $exitFile,
    $gateFile,
    $bootstrapFile,
    $logFile
)) {
    if (Test-Path $path) {
        Remove-Item $path -Force
    }
}

$script = @'
$ErrorActionPreference = 'Stop'
$env:GH_TOKEN = $null
$env:GITHUB_TOKEN = $null
$env:GIT_TERMINAL_PROMPT = '0'
$env:PYTHONUTF8 = '1'

$runtimeRoot = 'C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
$repoRoot = Join-Path $runtimeRoot 'repo'
$branch = 'implementation/ozon-user-node-gate'
$git = 'C:\Program Files\Git\cmd\git.exe'
$browser = 'C:\Program Files\Yandex\YandexBrowser\Application\browser.exe'

if (-not (Test-Path $git)) {
    throw "Git not found: $git"
}

if (-not (Test-Path $browser)) {
    throw "Yandex Browser not found: $browser"
}

& $git -C $repoRoot fetch origin $branch
if ($LASTEXITCODE -ne 0) {
    throw "git fetch failed: $LASTEXITCODE"
}

& $git -C $repoRoot checkout $branch
if ($LASTEXITCODE -ne 0) {
    throw "git checkout failed: $LASTEXITCODE"
}

& $git -C $repoRoot pull --ff-only origin $branch
if ($LASTEXITCODE -ne 0) {
    throw "git pull failed: $LASTEXITCODE"
}

$entry = Join-Path $repoRoot 'scripts\user_node_task_entry.ps1'
$config = Join-Path $repoRoot 'config\ozon-user-node-smoke-home-yandex.json'

if (-not (Test-Path $entry)) {
    throw "Task entry not found: $entry"
}

if (-not (Test-Path $config)) {
    throw "Yandex smoke config not found: $config"
}

& powershell.exe `
    -NoProfile `
    -ExecutionPolicy Bypass `
    -File $entry `
    -RepoRoot $repoRoot `
    -RuntimeRoot $runtimeRoot `
    -ConfigPath $config `
    -BrowserPath $browser `
    -Runs 1

$exit = $LASTEXITCODE
if ($null -eq $exit) {
    $exit = 0
}

exit $exit
'@

[IO.File]::WriteAllText(
    $launcher,
    $script,
    (New-Object Text.UTF8Encoding($false))
)

try {
    Unregister-ScheduledTask `
        -TaskName $taskName `
        -Confirm:$false `
        -ErrorAction SilentlyContinue
}
catch {}

$action = New-ScheduledTaskAction `
    -Execute 'powershell.exe' `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$launcher`""

$principal = New-ScheduledTaskPrincipal `
    -UserId $user `
    -LogonType Interactive `
    -RunLevel Limited

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 4) `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

try {
    Register-ScheduledTask `
        -TaskName $taskName `
        -Action $action `
        -Principal $principal `
        -Settings $settings `
        -Force | Out-Null

    Write-Host "TASK_REGISTERED=YES"
    Write-Host "TASK_USER=$user"
    Write-Host "BROWSER=$browser"

    Start-ScheduledTask -TaskName $taskName
    Write-Host 'TASK_STARTED=YES'

    $deadline = (Get-Date).AddMinutes(3)

    while (
        (Get-Date) -lt $deadline -and
        -not (Test-Path $exitFile)
    ) {
        Start-Sleep -Seconds 3
    }

    if (Test-Path $exitFile) {
        Write-Host '--- TASK_EXIT_JSON ---'
        Get-Content $exitFile -Raw
    }
    else {
        Write-Host 'TASK_EXIT_JSON=TIMEOUT'
    }

    if (Test-Path $bootstrapFile) {
        Write-Host '--- BOOTSTRAP_STATUS_JSON ---'
        Get-Content $bootstrapFile -Raw
    }

    if (Test-Path $gateFile) {
        Write-Host '--- LATEST_GATE_JSON ---'
        Get-Content $gateFile -Raw
    }
    else {
        Write-Host 'LATEST_GATE_JSON=NOT_FOUND'
    }

    if (Test-Path $logFile) {
        Write-Host '--- TASK_LOG_TAIL ---'
        Get-Content $logFile -Tail 160
    }
}
finally {
    Unregister-ScheduledTask `
        -TaskName $taskName `
        -Confirm:$false `
        -ErrorAction SilentlyContinue
}

Write-Host '=== OZON_HOME_YANDEX_SMOKE_END ==='
