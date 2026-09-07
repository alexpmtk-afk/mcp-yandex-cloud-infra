$ErrorActionPreference = 'Stop'

$runtimeRoot = 'C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
$probe = Join-Path $runtimeRoot 'ozon-plain-cdp-frozen.py'
$launcher = Join-Path $runtimeRoot 'canonical-user-node-launcher.ps1'
$launcherBackup = Join-Path $runtimeRoot ('canonical-user-node-launcher.backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.ps1')
$python = Join-Path $runtimeRoot '.venv\Scripts\python.exe'
$browser = 'C:\Program Files\Yandex\YandexBrowser\Application\browser.exe'
$profile = Join-Path $runtimeRoot 'profiles\MarketplaceMonitor\Ozon-Yandex-CDP-Canonical'
$startedFile = Join-Path $runtimeRoot 'canonical-task.started'
$taskExitFile = Join-Path $runtimeRoot 'canonical-task-exit.json'
$resultFile = Join-Path $runtimeRoot 'plain-cdp-canonical.json'
$screenshotFile = Join-Path $runtimeRoot 'plain-cdp-canonical.png'
$taskName = 'MarketplaceCardMonitor-UserNode-Canonical'
$payloadPath = 'tools/powershell-bridge/payloads/ozon_plain_cdp_probe_25af2c9.py'

if (-not (Test-Path $python)) { throw "Python not found: $python" }
if (-not (Test-Path $browser)) { throw "Yandex Browser not found: $browser" }

$uri = "https://api.github.com/repos/$env:GITHUB_REPOSITORY/contents/$payloadPath?ref=$env:GITHUB_SHA"
$headers = @{
    Authorization = "Bearer $env:GH_TOKEN"
    Accept = 'application/vnd.github+json'
    'X-GitHub-Api-Version' = '2022-11-28'
    'User-Agent' = 'powershell-bridge'
}
$resp = Invoke-RestMethod -Uri $uri -Headers $headers -Method Get
$raw = ($resp.content -replace '\s','')
[IO.File]::WriteAllBytes($probe, [Convert]::FromBase64String($raw))

if (Test-Path $launcher) {
    Copy-Item $launcher $launcherBackup -Force
}

$launcherCode = @'
$ErrorActionPreference = 'Continue'
$runtimeRoot = 'C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
$python = Join-Path $runtimeRoot '.venv\Scripts\python.exe'
$probe = Join-Path $runtimeRoot 'ozon-plain-cdp-frozen.py'
$browser = 'C:\Program Files\Yandex\YandexBrowser\Application\browser.exe'
$profile = Join-Path $runtimeRoot 'profiles\MarketplaceMonitor\Ozon-Yandex-CDP-Canonical'
$startedFile = Join-Path $runtimeRoot 'canonical-task.started'
$taskExitFile = Join-Path $runtimeRoot 'canonical-task-exit.json'
$resultFile = Join-Path $runtimeRoot 'plain-cdp-canonical.json'
$screenshotFile = Join-Path $runtimeRoot 'plain-cdp-canonical.png'
$expectedRegion = ([string][char]0x0412) + ([string][char]0x043E) + ([string][char]0x0440) + ([string][char]0x043E) + ([string][char]0x043D) + ([string][char]0x0435) + ([string][char]0x0436)

"STARTED $(Get-Date -Format o) USER=$([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) SESSION=$((Get-Process -Id $PID).SessionId)" |
    Set-Content -Path $startedFile -Encoding UTF8

& $python `
    $probe `
    --browser-path $browser `
    --profile-dir $profile `
    --target-url 'https://www.ozon.ru/product/nippel-dlya-beskamernyh-shin-ventil-sosok-avtomobilnyy-rezinovyy-1420875699/' `
    --expected-sku '1420875699' `
    --expected-region $expectedRegion `
    --output $resultFile `
    --screenshot $screenshotFile `
    --port 9231 `
    --settle-seconds 18

$exitCode = $LASTEXITCODE
if ($null -eq $exitCode) { $exitCode = 0 }
[ordered]@{
    timestamp = (Get-Date).ToString('o')
    exit_code = $exitCode
    user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    session_id = (Get-Process -Id $PID).SessionId
} | ConvertTo-Json -Depth 4 | Set-Content -Path $taskExitFile -Encoding UTF8
exit $exitCode
'@

[IO.File]::WriteAllText($launcher, $launcherCode, (New-Object System.Text.UnicodeEncoding($false, $true)))

foreach ($path in @($startedFile, $taskExitFile, $resultFile, $screenshotFile)) {
    if (Test-Path $path) { Remove-Item $path -Force }
}

& schtasks.exe /Run /TN "\$taskName"
if ($LASTEXITCODE -ne 0) { throw "schtasks /Run failed: $LASTEXITCODE" }

$deadline = (Get-Date).AddSeconds(120)
while ((Get-Date) -lt $deadline -and -not (Test-Path $taskExitFile)) {
    Start-Sleep -Seconds 2
}

Write-Host '--- START_MARKER ---'
if (Test-Path $startedFile) { Get-Content $startedFile -Raw } else { Write-Host 'NOT_FOUND' }
Write-Host '--- TASK_EXIT ---'
if (Test-Path $taskExitFile) { Get-Content $taskExitFile -Raw } else { Write-Host 'NOT_FOUND' }
Write-Host '--- CDP_RESULT ---'
if (Test-Path $resultFile) { Get-Content $resultFile -Raw } else { Write-Host 'NOT_FOUND' }
Write-Host "SCREENSHOT_EXISTS=$(Test-Path $screenshotFile)"
Write-Host "LAUNCHER_BACKUP=$launcherBackup"
