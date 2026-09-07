$ErrorActionPreference='Continue'
$p='C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1\wb-network-discovery.json'
Write-Host '=== WB_NETWORK_DISCOVERY_INSPECT ==='
if(-not(Test-Path $p)){Write-Host 'NOT_FOUND';exit 0}
$j=Get-Content $p -Raw -Encoding UTF8|ConvertFrom-Json
Write-Host "STATUS=$($j.status) SOURCE=$($j.discovery_source) ERROR=$($j.error) RAW=$($j.raw_product_links)"
Write-Host '--- RESOURCES ---'
foreach($r in $j.resource_samples){Write-Host $r}
Write-Host '--- BODY ---'
if($j.body_excerpt){$b=[string]$j.body_excerpt;Write-Host $b.Substring(0,[Math]::Min(5000,$b.Length))}
Write-Host '--- CANDIDATES ---'
foreach($c in $j.candidates){Write-Host ("SKU={0} SOURCE={1} SCORE={2} TEXT={3}" -f $c.sku,$c.source,$c.score,$c.text)}
exit 0
