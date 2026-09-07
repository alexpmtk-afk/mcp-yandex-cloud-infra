$ErrorActionPreference = 'Stop'

Write-Host '=== OZON_HOME_YANDEX_PLAIN_CDP_BEGIN ==='

$user = "$env:COMPUTERNAME\Win10_Game_OS"
$runtimeRoot = 'C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
$repoRoot = Join-Path $runtimeRoot 'repo'
$browser = 'C:\Program Files\Yandex\YandexBrowser\Application\browser.exe'
$profile = Join-Path $runtimeRoot 'profiles\MarketplaceMonitor\Ozon-Yandex-CDP'
$launcher = Join-Path $runtimeRoot 'launch-ozon-yandex-cdp.ps1'
$resultPath = Join-Path $runtimeRoot 'plain-cdp-probe.json'
$screenshotPath = Join-Path $runtimeRoot 'plain-cdp-probe.png'
$startedPath = Join-Path $runtimeRoot 'plain-cdp-probe.started'
$taskName = 'MarketplaceCardMonitor-Ozon-Yandex-CDP'

foreach ($path in @($resultPath,$screenshotPath,$startedPath)) {
    if (Test-Path $path) {
        Remove-Item $path -Force
    }
}

if (-not (Test-Path $browser)) {
    throw "Yandex Browser not found: $browser"
}

$script = @'
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$env:PYTHONUTF8 = '1'
$env:GIT_TERMINAL_PROMPT = '0'

$runtimeRoot = 'C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
$repoRoot = Join-Path $runtimeRoot 'repo'
$browser = 'C:\Program Files\Yandex\YandexBrowser\Application\browser.exe'
$profile = Join-Path $runtimeRoot 'profiles\MarketplaceMonitor\Ozon-Yandex-CDP'
$resultPath = Join-Path $runtimeRoot 'plain-cdp-probe.json'
$screenshotPath = Join-Path $runtimeRoot 'plain-cdp-probe.png'
$startedPath = Join-Path $runtimeRoot 'plain-cdp-probe.started'
$branch = 'implementation/ozon-user-node-gate'
$git = 'C:\Program Files\Git\cmd\git.exe'

"STARTED $(Get-Date -Format o) USER=$([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) SESSION=$((Get-Process -Id $PID).SessionId)" |
    Set-Content -Path $startedPath -Encoding UTF8

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

$venvPython = Join-Path $runtimeRoot '.venv\Scripts\python.exe'

if (-not (Test-Path $venvPython)) {
    throw "Venv Python not found: $venvPython"
}

& $venvPython -m pip install -r (Join-Path $repoRoot 'requirements.txt') --disable-pip-version-check
if ($LASTEXITCODE -ne 0) {
    throw "pip install failed: $LASTEXITCODE"
}

$probe = Join-Path $repoRoot 'src\ozon_plain_cdp_probe.py'

if (-not (Test-Path $probe)) {
    throw "CDP probe not found: $probe"
}

& $venvPython `
    $probe `
    --browser-path $browser `
    --profile-dir $profile `
    --target-url 'https://www.ozon.ru/product/nippel-dlya-beskamernyh-shin-ventil-sosok-avtomobilnyy-rezinovyy-1420875699/' `
    --expected-sku '1420875699' `
    --expected-region 'Воронеж' `
    --output $resultPath `
    --screenshot $screenshotPath `
    --port 9227 `
    --settle-seconds 18

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

& icacls.exe $runtimeRoot /grant "${user}:(OI)(CI)M" /T /C | Out-Null

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
    -ExecutionTimeLimit (New-TimeSpan -Minutes 3) `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Principal $principal `
    -Settings $settings `
    -Force | Out-Null

Write-Host 'TASK_REGISTERED=YES'
Write-Host "TASK_USER=$user"

Start-ScheduledTask -TaskName $taskName
Write-Host 'TASK_START_REQUESTED=YES'

$deadline = (Get-Date).AddSeconds(100)

while (
    (Get-Date) -lt $deadline -and
    -not (Test-Path $resultPath)
) {
    Start-Sleep -Seconds 2
}

Write-Host '--- START_MARKER ---'
if (Test-Path $startedPath) {
    Get-Content $startedPath -Raw
}
else {
    Write-Host 'NOT_FOUND'
}

Write-Host '--- CDP_RESULT ---'
if (Test-Path $resultPath) {
    Get-Content $resultPath -Raw
}
else {
    Write-Host 'NOT_FOUND'
}

Write-Host "SCREENSHOT_EXISTS=$(Test-Path $screenshotPath)"

try {
    Unregister-ScheduledTask `
        -TaskName $taskName `
        -Confirm:$false `
        -ErrorAction SilentlyContinue
}
catch {}

Write-Host '=== OZON_HOME_YANDEX_PLAIN_CDP_END ==='
