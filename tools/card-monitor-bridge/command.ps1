$ErrorActionPreference = 'Continue'
$runtimeRoot = 'C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'

Write-Host '=== CARD_MONITOR_HANG_INSPECT_BEGIN ==='
Write-Host "BRIDGE_IDENTITY=$([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)"

Write-Host '--- LAUNCHER ---'
$p = Join-Path $runtimeRoot 'canonical-user-node-launcher.ps1'
if (Test-Path $p) { Get-Content $p -Raw }

Write-Host '--- PYTHON_MONITOR_PROCESSES ---'
Get-CimInstance Win32_Process | Where-Object {
  $_.Name -match 'python|powershell' -and $_.CommandLine -like '*marketplace-card-monitor*'
} | ForEach-Object {
  Write-Host ("PID={0} NAME={1} SESSION={2} CMD={3}" -f $_.ProcessId,$_.Name,$_.SessionId,$_.CommandLine)
}

Write-Host '--- RECENT_RUN_DIRS ---'
$runs = Join-Path $runtimeRoot 'runs'
if (Test-Path $runs) {
  Get-ChildItem $runs -Directory | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 5 | ForEach-Object {
    Write-Host ("RUN_DIR={0} UTC={1:o}" -f $_.FullName,$_.LastWriteTimeUtc)
    Get-ChildItem $_.FullName -File | Sort-Object LastWriteTimeUtc | ForEach-Object {
      Write-Host ("  FILE={0} SIZE={1} UTC={2:o}" -f $_.Name,$_.Length,$_.LastWriteTimeUtc)
    }
  }
}

Write-Host '--- NEWEST_PARTIAL_JSONS ---'
if (Test-Path $runs) {
  $newest = Get-ChildItem $runs -Directory | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
  if ($newest) {
    foreach ($f in (Get-ChildItem $newest.FullName -File -Filter '*.json' | Sort-Object LastWriteTimeUtc)) {
      Write-Host "### $($f.Name) ###"
      try {
        $j = Get-Content $f.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($j.status) { Write-Host "STATUS=$($j.status)" }
        if ($j.marketplace) { Write-Host "MARKETPLACE=$($j.marketplace)" }
        if ($j.query) { Write-Host "QUERY=$($j.query)" }
        if ($null -ne $j.raw_product_links) { Write-Host "RAW_PRODUCT_LINKS=$($j.raw_product_links)" }
        if ($j.error) { Write-Host "ERROR=$($j.error)" }
        if ($j.selected) { Write-Host ("SELECTED_SKU={0} URL={1}" -f $j.selected.sku,$j.selected.url) }
        if ($j.body_excerpt) { Write-Host ("BODY_EXCERPT=" + ([string]$j.body_excerpt).Substring(0,[Math]::Min(1200,([string]$j.body_excerpt).Length))) }
        if ($j.resource_samples) { Write-Host ("RESOURCES=" + (($j.resource_samples | Select-Object -First 12) -join ' | ')) }
      } catch { Write-Host "PARSE_ERROR=$($_.Exception.Message)" }
    }
  }
}
Write-Host '=== CARD_MONITOR_HANG_INSPECT_END ==='
exit 0
