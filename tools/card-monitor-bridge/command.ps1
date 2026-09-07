$ErrorActionPreference = 'Continue'
$runtimeRoot = 'C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
$runs = Join-Path $runtimeRoot 'runs'
Write-Host '=== CARD_MONITOR_RESULT_INSPECT_BEGIN ==='
$newest = Get-ChildItem $runs -Directory | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
Write-Host "RUN=$($newest.FullName)"
$targets = @('ozon-cordiant-snow-cross-2.json','wb-cordiant-snow-cross-2.json','wb-formula-ice.json')
foreach ($name in $targets) {
  $p = Join-Path $newest.FullName $name
  Write-Host "### $name ###"
  if (-not (Test-Path $p)) { Write-Host 'NOT_FOUND'; continue }
  try {
    $j = Get-Content $p -Raw -Encoding UTF8 | ConvertFrom-Json
    Write-Host "STATUS=$($j.status)"
    Write-Host "NAME=$($j.name)"
    Write-Host "SKU=$($j.sku)"
    Write-Host "REGION_OK=$($j.region_ok)"
    Write-Host "NAME_OK=$($j.name_ok)"
    Write-Host "REQUIRED_OK=$($j.required_ok)"
    Write-Host "FORBIDDEN_OK=$($j.forbidden_ok)"
    Write-Host "BLOCKED=$($j.blocked)"
    Write-Host "AVAILABILITY=$($j.availability)"
    Write-Host "SELLER=$($j.seller)"
    if ($j.price) {
      Write-Host "PRICE_BUYER=$($j.price.buyer_price_rub)"
      Write-Host "PRICE_SECONDARY=$($j.price.secondary_price_rub)"
      Write-Host "PRICE_METHOD=$($j.price.method)"
      Write-Host ("PRICE_CANDIDATES=" + (($j.price.candidates_rub | Select-Object -First 15) -join ','))
    }
    if ($j.required_text) { Write-Host ("REQUIRED_TEXT_COUNT=" + $j.required_text.Count) }
    if ($j.forbidden_text) { Write-Host ("FORBIDDEN_TEXT_COUNT=" + $j.forbidden_text.Count) }
    if ($j.evidence -and $j.evidence.body_excerpt) {
      $b = [string]$j.evidence.body_excerpt
      Write-Host ("BODY_LEN=" + $b.Length)
      Write-Host ("BODY_HEAD=" + $b.Substring(0,[Math]::Min(5000,$b.Length)))
    }
  } catch { Write-Host "PARSE_ERROR=$($_.Exception.Message)" }
}
Write-Host '=== CARD_MONITOR_RESULT_INSPECT_END ==='
exit 0
