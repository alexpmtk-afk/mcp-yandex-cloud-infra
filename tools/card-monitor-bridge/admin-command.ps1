$ErrorActionPreference='Continue'
$root='C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
foreach($p in @((Join-Path $root 'acceptance-ozon\latest.json'),(Join-Path $root 'acceptance-wb\latest.json'))){
 Write-Host "FILE=$p"
 if(Test-Path $p){
  $j=Get-Content $p -Raw -Encoding UTF8|ConvertFrom-Json
  foreach($r in $j.results){
   $p1=if($r.price){$r.price.buyer_price_rub}else{$null};$p2=if($r.price){$r.price.secondary_price_rub}else{$null}
   Write-Host ("ID={0} STATUS={1} SKU={2} URL={3} PRICE={4}/{5} REGION={6} NAME={7}" -f $r.id,$r.status,$r.sku,$r.final_url,$p1,$p2,$r.region_ok,$r.name)
  }
 }
}
exit 0
