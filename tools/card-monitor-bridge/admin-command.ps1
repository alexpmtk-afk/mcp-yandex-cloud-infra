$ErrorActionPreference='Continue'
$root='C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
Write-Host '--- ACCEPTANCE_INSPECT ---'
foreach($p in @(
 (Join-Path $root 'acceptance-ozon\latest.json'),
 (Join-Path $root 'acceptance-wb\latest.json'),
 (Join-Path $root 'resolved-targets.json')
)){
 Write-Host "FILE=$p EXISTS=$(Test-Path $p)"
 if(Test-Path $p){
  try{
   $j=Get-Content $p -Raw -Encoding UTF8|ConvertFrom-Json
   if($j.results){
    foreach($r in $j.results){
     if($r.id -match 'cordiant|viatti'){
      $p1=if($r.price){$r.price.buyer_price_rub}else{$null};$p2=if($r.price){$r.price.secondary_price_rub}else{$null}
      Write-Host ("ID={0} STATUS={1} SKU={2} URL={3} PRICE={4}/{5} NAME_OK={6} REQ_OK={7} FORBID_OK={8} REGION={9} NAME={10}" -f $r.id,$r.status,$r.sku,$r.final_url,$p1,$p2,$r.name_ok,$r.required_ok,$r.forbidden_ok,$r.region_ok,$r.name)
      if($r.discovery){Write-Host ("DISCOVERY_STATUS={0} SOURCE={1} RAW={2} ERR={3}" -f $r.discovery.status,$r.discovery.discovery_source,$r.discovery.raw_product_links,$r.discovery.error)}
     }
    }
   } elseif($j -is [System.Array]) {
    foreach($r in $j){if($r.id -match 'cordiant|viatti'){Write-Host ("CACHE ID={0} MP={1} SKU={2} URL={3} SOURCE={4}" -f $r.id,$r.marketplace,$r.sku,$r.url,$r.source)}}
   }
  }catch{Write-Host "PARSE_ERROR=$($_.Exception.Message)"}
 }
}
Write-Host '--- HISTORICAL_MATCHES ---'
$files=Get-ChildItem -Path $root -Recurse -Filter '*.json' -File -ErrorAction SilentlyContinue | Where-Object {$_.FullName -match '\\runs\\'} | Sort-Object LastWriteTimeUtc -Descending
$seen=@{}
foreach($f in $files){
 try{
  $j=Get-Content $f.FullName -Raw -Encoding UTF8|ConvertFrom-Json
  $items=@()
  if($j.results){$items=@($j.results)}elseif($j.id){$items=@($j)}
  foreach($r in $items){
   if($r.id -match 'ozon-cordiant|ozon-viatti|wb-cordiant|wb-viatti'){
    $key="$($r.id)|$($r.sku)|$($r.final_url)"
    if(-not$seen.ContainsKey($key)){
     $seen[$key]=$true
     $p1=if($r.price){$r.price.buyer_price_rub}else{$null}
     Write-Host ("HIST ID={0} STATUS={1} SKU={2} URL={3} PRICE={4} FILE={5}" -f $r.id,$r.status,$r.sku,$r.final_url,$p1,$f.FullName)
    }
   }
  }
 }catch{}
}
exit 0
