$ErrorActionPreference = 'Continue'
$runtimeRoot = 'C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
$p = Join-Path $runtimeRoot 'wb-profile-probe-fresh.json'
Write-Host '=== WB_FRESH_DISCOVERY_INSPECT_BEGIN ==='
if (-not (Test-Path $p)) { Write-Host 'NOT_FOUND'; exit 0 }
try {
  $j = Get-Content $p -Raw -Encoding UTF8 | ConvertFrom-Json
  Write-Host "STATUS=$($j.status)"
  Write-Host "RAW_PRODUCT_LINKS=$($j.raw_product_links)"
  Write-Host "SEARCH_URL=$($j.search_url)"
  if ($j.body_excerpt) {
    $b = [string]$j.body_excerpt
    Write-Host "BODY_LEN=$($b.Length)"
    Write-Host ("BODY=" + $b.Substring(0,[Math]::Min(9000,$b.Length)))
  }
  Write-Host '--- RESOURCES ---'
  foreach ($r in $j.resource_samples) { Write-Host $r }
  Write-Host '--- CANDIDATES ---'
  foreach ($c in $j.candidates) { Write-Host ("SKU={0} SCORE={1} URL={2} TEXT={3}" -f $c.sku,$c.score,$c.url,$c.text) }
} catch { Write-Host "PARSE_ERROR=$($_.Exception.Message)" }
Write-Host '=== WB_FRESH_DISCOVERY_INSPECT_END ==='
exit 0
