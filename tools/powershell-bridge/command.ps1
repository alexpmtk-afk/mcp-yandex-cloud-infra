$ErrorActionPreference = 'Stop'

$runtimeRoot = 'C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
$repoRoot = Join-Path $runtimeRoot 'repo'
$git = 'C:\Program Files\Git\cmd\git.exe'

$commit = '25af2c9b30f25a0a1c9c822642185977faa2f901'
$sourcePath = 'src/ozon_plain_cdp_probe.py'

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

if (-not (Test-Path $git)) { throw "Git not found: $git" }
if (-not (Test-Path (Join-Path $repoRoot '.git'))) { throw "Repo not found: $repoRoot" }
if (-not (Test-Path $python)) { throw "Python not found: $python" }
if (-not (Test-Path $browser)) { throw "Yandex Browser not found: $browser" }

& $git -C $repoRoot cat-file -e "$commit`:$sourcePath"
if ($LASTEXITCODE -ne 0) { throw "Frozen probe not found in local git object: $commit`:$sourcePath" }

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $git
$psi.Arguments = "-C `"$repoRoot`" show $commit`:$sourcePath"
$psi.UseShellExecute = $false
$psi.RedirectStandardOutput = $true
$psi.CreateNoWindow = $true

$p = [System.Diagnostics.Process]::Start($psi)
$ms = New-Object System.IO.MemoryStream
$p.StandardOutput.BaseStream.CopyTo($ms)
$p.WaitForExit()

if ($p.ExitCode -ne 0) { throw "git show failed: $($p.ExitCode)" }

[System.IO.File]::WriteAllBytes($probe, $ms.ToArray())
$ms.Dispose()

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

"STARTED $(Get-Date -Format o) USER=$([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) SESSION=$((Get-Process -Id $PID).SessionId)" |
    Set-Content -Path $startedFile -Encoding UTF8

& $python `
    $probe `
    --browser-path $browser `
    --profile-dir $profile `
    --target-url 'https://www.ozon.ru/product/nippel-dlya-beskamernyh-shin-ventil-sosok-avtomobilnyy-rezinovyy-1420875699/' `
    --expected-sku '1420875699' `
    --expected-region 'Воронеж' `
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

[System.IO.File]::WriteAllText(
    $launcher,
    $launcherCode,
    (New-Object System.Text.UnicodeEncoding($false, $true))
)

foreach ($path in @($startedFile, $taskExitFile, $resultFile, $screenshotFile)) {
    if (Test-Path $path) { Remove-Item $path -Force }
}

& schtasks.exe /Run /TN "\$taskName"
if ($LASTEXITCODE -ne 0) { throw "schtasks /Run failed: $LASTEXITCODE" }

$deadline = (Get-Date).AddSeconds(90)

while ((Get-Date) -lt $deadline -and -not (Test-Path $resultFile)) {
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
