$ErrorActionPreference='Continue'
$root='C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
Write-Host '--- DAILY_FAILURE_INSPECT ---'
$evidence=Join-Path $root 'daily-history\runs\20260908T151601Z\raw-evidence'
foreach($name in @('ozon-cordiant.json','ozon-nexen.json')){
 $p=Join-Path $evidence $name
 Write-Host "FILE=$p EXISTS=$(Test-Path $p)"
 if(Test-Path $p){
  try{$j=Get-Content $p -Raw -Encoding UTF8|ConvertFrom-Json;$p1=if($j.price){$j.price.buyer_price_rub}else{$null};$p2=if($j.price){$j.price.secondary_price_rub}else{$null};Write-Host ("STATUS={0} ERROR={1} FINAL={2} SKU={3} PRICE={4}/{5} REGION={6} NAME_OK={7} REQUIRED_OK={8} FORBIDDEN_OK={9} BLOCKED={10} NAME={11}" -f $j.status,$j.error,$j.final_url,$j.sku,$p1,$p2,$j.region_ok,$j.name_ok,$j.required_ok,$j.forbidden_ok,$j.blocked,$j.name);if($j.evidence){Write-Host ('BODY=' + (($j.evidence.body_excerpt -replace "`r|`n",' ') -replace '\s+',' ').Substring(0,[Math]::Min(2500,(($j.evidence.body_excerpt -replace "`r|`n",' ') -replace '\s+',' ').Length)))}}catch{Write-Host "PARSE_ERROR=$($_.Exception.Message)"}
 }
}
Write-Host '--- WB_PARTIAL_FILES ---'
foreach($name in @('wb-region-probe.json','wb-discovery-kumho.json','wb-discovery-viatti.json')){
 $p=Join-Path $root $name;Write-Host "FILE=$name EXISTS=$(Test-Path $p)"
 if(Test-Path $p){try{$j=Get-Content $p -Raw -Encoding UTF8|ConvertFrom-Json;Write-Host "STATUS=$($j.status) SOURCE=$($j.discovery_source) RAW=$($j.raw_product_links) ERROR=$($j.error)";if($name-eq'wb-region-probe.json'){if($j.before){Write-Host ('BEFORE='+(($j.before.body-replace"`r|`n",' ')-replace'\s+',' ').Substring(0,[Math]::Min(1800,(($j.before.body-replace"`r|`n",' ')-replace'\s+',' ').Length)))};if($j.after_click){Write-Host ('AFTER='+(($j.after_click.body-replace"`r|`n",' ')-replace'\s+',' ').Substring(0,[Math]::Min(3000,(($j.after_click.body-replace"`r|`n",' ')-replace'\s+',' ').Length)));foreach($i in $j.after_click.inputs){Write-Host ("INPUT placeholder={0} value={1} aria={2} cls={3}"-f$i.placeholder,$i.value,$i.aria,$i.cls)}}}else{foreach($c in @($j.candidates|Select-Object -First 10)){Write-Host ("CAND SKU={0} SCORE={1} URL={2} TEXT={3}"-f$c.sku,$c.score,$c.url,(($c.text-replace"`r|`n",' ')-replace'\s+',' '))}}}catch{Write-Host "PARSE_ERROR=$($_.Exception.Message)"}}
}
exit 0
