$ErrorActionPreference = 'Stop'

Write-Host '=== OZON_HOME_YANDEX_CDP_V2_BEGIN ==='

$user = "$env:COMPUTERNAME\Win10_Game_OS"
$runtimeRoot = 'C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
$repoRoot = Join-Path $runtimeRoot 'repo'
$browser = 'C:\Program Files\Yandex\YandexBrowser\Application\browser.exe'
$powershell = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'

$sanityTask = 'MarketplaceCardMonitor-Interactive-Sanity'
$sanityScript = Join-Path $runtimeRoot 'interactive-sanity.ps1'
$sanityResult = Join-Path $runtimeRoot 'interactive-sanity.json'

$cdpTask = 'MarketplaceCardMonitor-Ozon-Yandex-CDP-V2'
$cdpLauncher = Join-Path $runtimeRoot 'launch-ozon-yandex-cdp-v2.ps1'
$cdpStarted = Join-Path $runtimeRoot 'plain-cdp-v2.started'
$cdpStatus = Join-Path $runtimeRoot 'plain-cdp-v2-launcher-status.json'
$cdpResult = Join-Path $runtimeRoot 'plain-cdp-v2.json'
$cdpScreenshot = Join-Path $runtimeRoot 'plain-cdp-v2.png'
$cdpLog = Join-Path $runtimeRoot 'plain-cdp-v2.log'

New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null
& icacls.exe $runtimeRoot /grant "${user}:(OI)(CI)M" /T /C | Out-Null

foreach ($path in @(
    $sanityResult,
    $cdpStarted,
    $cdpStatus,
    $cdpResult,
    $cdpScreenshot,
    $cdpLog
)) {
    if (Test-Path $path) {
        Remove-Item $path -Force
    }
}

if (-not (Test-Path $browser)) {
    throw "Yandex Browser not found: $browser"
}

if (-not (Test-Path (Join-Path $repoRoot '.git'))) {
    throw "Marketplace Card Monitor repo not found: $repoRoot"
}

Write-Host '--- PHASE_1_INTERACTIVE_SANITY ---'

$sanityCode = @'
$ErrorActionPreference = 'Stop'

$resultPath = 'C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1\interactive-sanity.json'

$result = [ordered]@{
    timestamp = (Get-Date).ToString('o')
    user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    session_id = (Get-Process -Id $PID).SessionId
    profile = $env:USERPROFILE
}

$result |
    ConvertTo-Json -Depth 4 |
    Set-Content -Path $resultPath -Encoding UTF8

exit 0
'@

[IO.File]::WriteAllText(
    $sanityScript,
    $sanityCode,
    (New-Object System.Text.UnicodeEncoding($false,$true))
)

try {
    Unregister-ScheduledTask `
        -TaskName $sanityTask `
        -Confirm:$false `
        -ErrorAction SilentlyContinue
}
catch {}

$sanityAction = New-ScheduledTaskAction `
    -Execute $powershell `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$sanityScript`"" `
    -WorkingDirectory $runtimeRoot

$principal = New-ScheduledTaskPrincipal `
    -UserId $user `
    -LogonType Interactive `
    -RunLevel Limited

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 2) `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

Register-ScheduledTask `
    -TaskName $sanityTask `
    -Action $sanityAction `
    -Principal $principal `
    -Settings $settings `
    -Force | Out-Null

Write-Host 'SANITY_TASK_REGISTERED=YES'

Start-ScheduledTask -TaskName $sanityTask
Write-Host 'SANITY_TASK_STARTED=YES'

$sanityDeadline = (Get-Date).AddSeconds(45)

while (
    (Get-Date) -lt $sanityDeadline -and
    -not (Test-Path $sanityResult)
) {
    Start-Sleep -Seconds 2
}

if (-not (Test-Path $sanityResult)) {
    Write-Host 'SANITY_RESULT=TIMEOUT'

    try {
        $info = Get-ScheduledTaskInfo `
            -TaskName $sanityTask `
            -ErrorAction Stop

        Write-Host "SANITY_LAST_RESULT=$($info.LastTaskResult)"
        Write-Host "SANITY_LAST_RUN=$($info.LastRunTime)"
    }
    catch {
        Write-Host "SANITY_TASK_INFO_ERROR=$($_.Exception.Message)"
    }

    Write-Host '--- SANITY_SCHTASKS ---'
    & schtasks.exe /Query /TN $sanityTask /V /FO LIST 2>&1 |
        ForEach-Object { Write-Host $_ }

    exit 31
}

Write-Host '--- SANITY_RESULT ---'
Get-Content $sanityResult -Raw

Unregister-ScheduledTask `
    -TaskName $sanityTask `
    -Confirm:$false `
    -ErrorAction SilentlyContinue

Write-Host 'SANITY_PASS=YES'

Write-Host '--- PHASE_2_YANDEX_CDP ---'

$launcherCode = @'
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$env:PYTHONUTF8 = '1'
$env:GIT_TERMINAL_PROMPT = '0'

$runtimeRoot = 'C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
$repoRoot = Join-Path $runtimeRoot 'repo'
$browser = 'C:\Program Files\Yandex\YandexBrowser\Application\browser.exe'
$profile = Join-Path $runtimeRoot 'profiles\MarketplaceMonitor\Ozon-Yandex-CDP-V2'

$startedPath = Join-Path $runtimeRoot 'plain-cdp-v2.started'
$statusPath = Join-Path $runtimeRoot 'plain-cdp-v2-launcher-status.json'
$resultPath = Join-Path $runtimeRoot 'plain-cdp-v2.json'
$screenshotPath = Join-Path $runtimeRoot 'plain-cdp-v2.png'
$logPath = Join-Path $runtimeRoot 'plain-cdp-v2.log'

$branch = 'implementation/ozon-user-node-gate'
$git = 'C:\Program Files\Git\cmd\git.exe'
$venvPython = Join-Path $runtimeRoot '.venv\Scripts\python.exe'

function Write-LauncherStatus(
    [string]$Status,
    [string]$Message = ''
) {
    $obj = [ordered]@{
        timestamp = (Get-Date).ToString('o')
        status = $Status
        message = $Message
        user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
        session_id = (Get-Process -Id $PID).SessionId
    }

    $obj |
        ConvertTo-Json -Depth 4 |
        Set-Content -Path $statusPath -Encoding UTF8
}

try {
    Start-Transcript -Path $logPath -Force | Out-Null
}
catch {}

try {
    "STARTED $(Get-Date -Format o) USER=$([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) SESSION=$((Get-Process -Id $PID).SessionId)" |
        Set-Content -Path $startedPath -Encoding UTF8

    Write-LauncherStatus 'STARTED'

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

    Write-LauncherStatus 'REPO_UPDATED'

    if (-not (Test-Path $venvPython)) {
        throw "Venv Python not found: $venvPython"
    }

    & $venvPython `
        -m pip install `
        -r (Join-Path $repoRoot 'requirements.txt') `
        --disable-pip-version-check

    if ($LASTEXITCODE -ne 0) {
        throw "pip install failed: $LASTEXITCODE"
    }

    Write-LauncherStatus 'DEPENDENCIES_READY'

    $probe = Join-Path $repoRoot 'src\ozon_plain_cdp_probe.py'

    if (-not (Test-Path $probe)) {
        throw "CDP probe not found: $probe"
    }

    Write-LauncherStatus 'CDP_STARTING'

    & $venvPython `
        $probe `
        --browser-path $browser `
        --profile-dir $profile `
        --target-url 'https://www.ozon.ru/product/nippel-dlya-beskamernyh-shin-ventil-sosok-avtomobilnyy-rezinovyy-1420875699/' `
        --expected-sku '1420875699' `
        --expected-region 'Воронеж' `
        --output $resultPath `
        --screenshot $screenshotPath `
        --port 9228 `
        --settle-seconds 18

    $exit = $LASTEXITCODE

    if ($null -eq $exit) {
        $exit = 0
    }

    Write-LauncherStatus 'FINISHED' "exit=$exit"

    try {
        Stop-Transcript | Out-Null
    }
    catch {}

    exit $exit
}
catch {
    Write-LauncherStatus 'ERROR' $_.Exception.Message
    Write-Host "LAUNCHER_ERROR=$($_.Exception.Message)"

    try {
        Stop-Transcript | Out-Null
    }
    catch {}

    exit 91
}
'@

[IO.File]::WriteAllText(
    $cdpLauncher,
    $launcherCode,
    (New-Object System.Text.UnicodeEncoding($false,$true))
)

try {
    Unregister-ScheduledTask `
        -TaskName $cdpTask `
        -Confirm:$false `
        -ErrorAction SilentlyContinue
}
catch {}

$cdpAction = New-ScheduledTaskAction `
    -Execute $powershell `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$cdpLauncher`"" `
    -WorkingDirectory $runtimeRoot

Register-ScheduledTask `
    -TaskName $cdpTask `
    -Action $cdpAction `
    -Principal $principal `
    -Settings $settings `
    -Force | Out-Null

Write-Host 'CDP_TASK_REGISTERED=YES'
Write-Host "CDP_TASK_USER=$user"

Start-ScheduledTask -TaskName $cdpTask
Write-Host 'CDP_TASK_STARTED=YES'

$deadline = (Get-Date).AddSeconds(150)

while (
    (Get-Date) -lt $deadline -and
    -not (Test-Path $cdpResult)
) {
    Start-Sleep -Seconds 2
}

Write-Host '--- CDP_START_MARKER ---'

if (Test-Path $cdpStarted) {
    Get-Content $cdpStarted -Raw
}
else {
    Write-Host 'NOT_FOUND'
}

Write-Host '--- CDP_LAUNCHER_STATUS ---'

if (Test-Path $cdpStatus) {
    Get-Content $cdpStatus -Raw
}
else {
    Write-Host 'NOT_FOUND'
}

Write-Host '--- CDP_RESULT ---'

if (Test-Path $cdpResult) {
    Get-Content $cdpResult -Raw
}
else {
    Write-Host 'NOT_FOUND'
}

Write-Host "CDP_SCREENSHOT_EXISTS=$(Test-Path $cdpScreenshot)"

Write-Host '--- CDP_TASK_INFO ---'

try {
    $task = Get-ScheduledTask `
        -TaskName $cdpTask `
        -ErrorAction Stop

    $info = Get-ScheduledTaskInfo `
        -TaskName $cdpTask `
        -ErrorAction Stop

    Write-Host "CDP_TASK_FOUND=YES"
    Write-Host "CDP_TASK_STATE=$($task.State)"
    Write-Host "CDP_TASK_LAST_RESULT=$($info.LastTaskResult)"
    Write-Host "CDP_TASK_LAST_RUN=$($info.LastRunTime)"
}
catch {
    Write-Host 'CDP_TASK_FOUND=NO'
    Write-Host "CDP_TASK_INFO_ERROR=$($_.Exception.Message)"
}

if (Test-Path $cdpLog) {
    Write-Host '--- CDP_LOG_TAIL ---'
    Get-Content $cdpLog -Tail 160
}

Write-Host 'CDP_TASK_LEFT_REGISTERED=YES'
Write-Host '=== OZON_HOME_YANDEX_CDP_V2_END ==='
