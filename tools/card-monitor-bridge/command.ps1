$ErrorActionPreference = 'Continue'
$runtimeRoot = 'C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
$taskName = '\MarketplaceCardMonitor-UserNode-Canonical'

Write-Host '=== CARD_MONITOR_STATE_BEGIN ==='
Write-Host "BRIDGE_IDENTITY=$([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)"
Write-Host "COMPUTER=$env:COMPUTERNAME"

Write-Host '--- TASK_QUERY ---'
& schtasks.exe /Query /TN $taskName /V /FO LIST
Write-Host "TASK_QUERY_EXIT=$LASTEXITCODE"

Write-Host '--- TASK_XML ---'
& schtasks.exe /Query /TN $taskName /XML
Write-Host "TASK_XML_EXIT=$LASTEXITCODE"

Write-Host '--- RUNTIME_FILES ---'
$names = @('canonical-user-node-launcher.ps1','canonical-task.started','canonical-task-exit.json','latest.json','resolved-targets.json','card_collector.py','target_discovery.py','batch_monitor.py','tires-195-55-r16.json')
foreach ($name in $names) {
  $p = Join-Path $runtimeRoot $name
  if (Test-Path $p) {
    $i = Get-Item $p
    Write-Host ("FILE={0} SIZE={1} UTC={2:o}" -f $name,$i.Length,$i.LastWriteTimeUtc)
  } else { Write-Host "FILE=$name NOT_FOUND" }
}

Write-Host '--- START_MARKER ---'
$p = Join-Path $runtimeRoot 'canonical-task.started'
if (Test-Path $p) { Get-Content $p -Raw }
Write-Host '--- TASK_EXIT ---'
$p = Join-Path $runtimeRoot 'canonical-task-exit.json'
if (Test-Path $p) { Get-Content $p -Raw -Encoding UTF8 }

Write-Host '--- LATEST_SUMMARY ---'
$p = Join-Path $runtimeRoot 'latest.json'
if (Test-Path $p) {
  try {
    $j = Get-Content $p -Raw -Encoding UTF8 | ConvertFrom-Json
    Write-Host ("RUN_ID={0} STATUS={1} TOTAL={2} PASS={3} FAIL={4} FINISHED={5}" -f $j.run_id,$j.status,$j.cards_total,$j.cards_pass,$j.cards_fail,$j.finished_at)
    foreach ($r in $j.results) {
      $price = $null; if ($r.price) { $price = $r.price.buyer_price_rub }
      $ds = $null; $raw = $null; if ($r.discovery) { $ds = $r.discovery.status; $raw = $r.discovery.raw_product_links }
      Write-Host ("CARD={0} MP={1} STATUS={2} SKU={3} PRICE={4} DISC={5} RAWLINKS={6}" -f $r.id,$r.marketplace,$r.status,$r.sku,$price,$ds,$raw)
    }
  } catch { Write-Host "LATEST_PARSE_ERROR=$($_.Exception.Message)" }
}

Write-Host '--- RESOLVED_TARGETS ---'
$p = Join-Path $runtimeRoot 'resolved-targets.json'
if (Test-Path $p) { Get-Content $p -Raw -Encoding UTF8 }

Write-Host '--- YANDEX_MONITOR_PROCESSES ---'
Get-CimInstance Win32_Process -Filter "Name='browser.exe'" | Where-Object { $_.CommandLine -like '*marketplace-card-monitor*' } | ForEach-Object {
  Write-Host ("PID={0} CMD={1}" -f $_.ProcessId,$_.CommandLine)
}
Write-Host '=== CARD_MONITOR_STATE_END ==='
exit 0
