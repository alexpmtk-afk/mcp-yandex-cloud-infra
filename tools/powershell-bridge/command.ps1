$ErrorActionPreference = 'Stop'

$runtimeRoot = 'C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
$taskName = 'MarketplaceCardMonitor-UserNode-Canonical'
$python = Join-Path $runtimeRoot '.venv\Scripts\python.exe'
$browser = 'C:\Program Files\Yandex\YandexBrowser\Application\browser.exe'
$collector = Join-Path $runtimeRoot 'card_collector.py'
$discovery = Join-Path $runtimeRoot 'target_discovery.py'
$batch = Join-Path $runtimeRoot 'batch_monitor.py'
$config = Join-Path $runtimeRoot 'tires-195-55-r16.json'
$launcher = Join-Path $runtimeRoot 'canonical-user-node-launcher.ps1'
$taskExitFile = Join-Path $runtimeRoot 'canonical-task-exit.json'
$latestFile = Join-Path $runtimeRoot 'latest.json'

if (-not (Test-Path $python)) { throw "Python not found: $python" }
if (-not (Test-Path $browser)) { throw "Yandex Browser not found: $browser" }

$downloads = @(
  @{ url='https://raw.githubusercontent.com/alexpmtk-afk/marketplace-card-monitor/implementation/ozon-user-node-gate/src/card_collector.py?token=CJWMU2T2PJZZXA7UMD5FBDDKT4DNNAA'; path=$collector },
  @{ url='https://raw.githubusercontent.com/alexpmtk-afk/marketplace-card-monitor/implementation/ozon-user-node-gate/src/target_discovery.py?token=CJWMU2XLBEBWE5XDPFNYYOTKT4DNNAA'; path=$discovery },
  @{ url='https://raw.githubusercontent.com/alexpmtk-afk/marketplace-card-monitor/implementation/ozon-user-node-gate/src/batch_monitor.py?token=CJWMU2S7AGCKLFNTFDQQIELKT4DNNAA'; path=$batch },
  @{ url='https://raw.githubusercontent.com/alexpmtk-afk/marketplace-card-monitor/implementation/ozon-user-node-gate/config/tires-195-55-r16.json?token=CJWMU2WZFCRCWOULKY7EGWTKT4DNVAA'; path=$config }
)

foreach ($item in $downloads) {
    Invoke-WebRequest -Uri $item.url -OutFile $item.path -UseBasicParsing
    if (-not (Test-Path $item.path)) { throw "Download missing: $($item.path)" }
    Write-Host "DEPLOYED=$($item.path) SIZE=$((Get-Item $item.path).Length)"
}

& $python -m py_compile $collector $discovery $batch
if ($LASTEXITCODE -ne 0) { throw "Python compile failed: $LASTEXITCODE" }
Write-Host 'PY_COMPILE=PASS'

$launcherCode = @'
$ErrorActionPreference = 'Continue'
$runtimeRoot = 'C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
$python = Join-Path $runtimeRoot '.venv\Scripts\python.exe'
$browser = 'C:\Program Files\Yandex\YandexBrowser\Application\browser.exe'
$batch = Join-Path $runtimeRoot 'batch_monitor.py'
$collector = Join-Path $runtimeRoot 'card_collector.py'
$discovery = Join-Path $runtimeRoot 'target_discovery.py'
$config = Join-Path $runtimeRoot 'tires-195-55-r16.json'
$taskExitFile = Join-Path $runtimeRoot 'canonical-task-exit.json'
$startedFile = Join-Path $runtimeRoot 'canonical-task.started'

"STARTED $(Get-Date -Format o) USER=$([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) SESSION=$((Get-Process -Id $PID).SessionId)" |
    Set-Content -Path $startedFile -Encoding UTF8

& $python $batch `
  --config $config `
  --runtime-root $runtimeRoot `
  --browser-path $browser `
  --collector $collector `
  --discovery $discovery `
  --base-port 9231 `
  --settle-seconds 12 `
  --discovery-settle-seconds 8

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

foreach ($path in @($taskExitFile, (Join-Path $runtimeRoot 'canonical-task.started'))) {
    if (Test-Path $path) { Remove-Item $path -Force }
}
$before = if (Test-Path $latestFile) { (Get-Item $latestFile).LastWriteTimeUtc } else { [datetime]::MinValue }

& schtasks.exe /Run /TN "\$taskName"
if ($LASTEXITCODE -ne 0) { throw "schtasks /Run failed: $LASTEXITCODE" }
Write-Host 'BATCH_TASK_TRIGGERED=YES'

$deadline = (Get-Date).AddMinutes(9)
while ((Get-Date) -lt $deadline) {
    $done = Test-Path $taskExitFile
    $fresh = (Test-Path $latestFile) -and ((Get-Item $latestFile).LastWriteTimeUtc -gt $before)
    if ($done -and $fresh) { break }
    Start-Sleep -Seconds 5
}

Write-Host '--- START_MARKER ---'
$startedFile = Join-Path $runtimeRoot 'canonical-task.started'
if (Test-Path $startedFile) { Get-Content $startedFile -Raw } else { Write-Host 'NOT_FOUND' }
Write-Host '--- TASK_EXIT ---'
if (Test-Path $taskExitFile) { Get-Content $taskExitFile -Raw -Encoding UTF8 } else { Write-Host 'NOT_FOUND' }
Write-Host '--- BATCH_SUMMARY ---'
if (Test-Path $latestFile) {
    $j = Get-Content $latestFile -Raw -Encoding UTF8 | ConvertFrom-Json
    Write-Host "SCHEMA=$($j.schema)"
    Write-Host "STATUS=$($j.status)"
    Write-Host "TOTAL=$($j.cards_total) PASS=$($j.cards_pass) FAIL=$($j.cards_fail)"
    foreach ($r in $j.results) {
      $p = $null
      if ($r.price) { $p = $r.price.buyer_price_rub }
      Write-Host ("CARD={0} MP={1} STATUS={2} SKU={3} PRICE={4} REGION={5} NAME={6}" -f $r.id,$r.marketplace,$r.status,$r.sku,$p,$r.region_ok,$r.name)
      if ($r.discovery -and $r.discovery.status) { Write-Host ("DISCOVERY={0}:{1}" -f $r.id,$r.discovery.status) }
    }
} else {
    Write-Host 'LATEST_NOT_FOUND'
}
