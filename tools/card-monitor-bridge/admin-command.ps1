$ErrorActionPreference='Stop'
$root='C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
$repo=Join-Path $root 'repo'
$git='C:\Program Files\Git\cmd\git.exe'
$python=Join-Path $root '.venv\Scripts\python.exe'
$browser='C:\Program Files\Yandex\YandexBrowser\Application\browser.exe'
$taskName='MarketplaceCardMonitor-Direct10-Hidden-Acceptance'
$child=Join-Path $root 'direct10-hidden-acceptance.ps1'
$result=Join-Path $root 'direct10-hidden-acceptance.json'
$interactiveUser=(Get-CimInstance Win32_ComputerSystem -ErrorAction Stop).UserName
if([string]::IsNullOrWhiteSpace($interactiveUser)){throw 'No interactive user'}

function Get-MonitorBrowserProcesses {
  @(Get-CimInstance Win32_Process | Where-Object {
    ($_.Name -match '^(browser|yandex|chrome)\.exe$') -and
    ([string]$_.CommandLine).Contains('--user-data-dir=C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1')
  })
}
function Kill-MonitorBrowsers {
  Get-MonitorBrowserProcesses | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
  Start-Sleep -Milliseconds 500
}
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class Win32VisibleDirect10 {
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
}
'@
Kill-MonitorBrowsers
if(Test-Path $result){Remove-Item $result -Force}

$childCode=@'
$ErrorActionPreference='Stop'
$root='C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
$repo=Join-Path $root 'repo'
$git='C:\Program Files\Git\cmd\git.exe'
$python=Join-Path $root '.venv\Scripts\python.exe'
$browser='C:\Program Files\Yandex\YandexBrowser\Application\browser.exe'
$result=Join-Path $root 'direct10-hidden-acceptance.json'

function GitBytes([string]$spec,[string]$dest){
 $psi=New-Object Diagnostics.ProcessStartInfo;$psi.FileName=$git;$psi.Arguments="-C `"$repo`" show `"$spec`"";$psi.UseShellExecute=$false;$psi.RedirectStandardOutput=$true;$psi.RedirectStandardError=$true;$psi.CreateNoWindow=$true
 $p=[Diagnostics.Process]::Start($psi);$ms=New-Object IO.MemoryStream;$p.StandardOutput.BaseStream.CopyTo($ms);$err=$p.StandardError.ReadToEnd();$p.WaitForExit();if($p.ExitCode-ne 0){$ms.Dispose();throw $err};[IO.File]::WriteAllBytes($dest,$ms.ToArray());$ms.Dispose()
}

try {
 & $git -C $repo fetch origin implementation/ozon-user-node-gate --prune
 if($LASTEXITCODE-ne 0){throw "git fetch failed: $LASTEXITCODE"}
 $ref='origin/implementation/ozon-user-node-gate';$sha=(& $git -C $repo rev-parse $ref).Trim()
 GitBytes "$ref`:src/browser_lifecycle.py" (Join-Path $root 'browser_lifecycle.py')
 GitBytes "$ref`:src/card_collector.py" (Join-Path $root 'card_collector.py')
 & $python -m py_compile (Join-Path $root 'browser_lifecycle.py') (Join-Path $root 'card_collector.py')
 if($LASTEXITCODE-ne 0){throw "compile failed: $LASTEXITCODE"}

 $targets=@(
  @{id='ozon-cordiant';mp='ozon';sku='3215740356';name='Snow Cross 2';url='https://www.ozon.ru/product/cordiant-snow-cross-2-shiny-zimnie-195-55-r16-91t-shipovannye-3215740356/'},
  @{id='ozon-formula';mp='ozon';sku='1713084818';name='Formula Ice';url='https://www.ozon.ru/product/formula-formula-ice-shiny-zimnie-195-55-r16-91t-shipovannye-1713084818/'},
  @{id='ozon-ikon';mp='ozon';sku='1873541922';name='Character Ice 7';url='https://www.ozon.ru/product/ikon-tyres-ikon-character-ice-7-shiny-zimnie-195-55-r16-91t-shipovannye-1873541922/'},
  @{id='ozon-nexen';mp='ozon';sku='1271999893';name='Winguard WinSpike 3';url='https://www.ozon.ru/product/nexen-winguard-winspike-3-shiny-zimnie-195-55-r16-91t-shipovannye-1271999893/'},
  @{id='ozon-kumho';mp='ozon';sku='572748589';name='WinterCraft Ice WI32';url='https://www.ozon.ru/product/kumho-wintercraft-ice-wi32-shiny-zimnie-195-55-r16-91t-shipovannye-572748589/'},
  @{id='wb-cordiant';mp='wildberries';sku='448889876';name='Snow cross 2';url='https://www.wildberries.ru/catalog/448889876/detail.aspx'},
  @{id='wb-formula';mp='wildberries';sku='445155828';name='Formula ice';url='https://www.wildberries.ru/catalog/445155828/detail.aspx'},
  @{id='wb-ikon';mp='wildberries';sku='1304585260';name='Character Ice 7';url='https://www.wildberries.ru/catalog/1304585260/detail.aspx'},
  @{id='wb-nexen';mp='wildberries';sku='1284571224';name='WinSpike 3';url='https://www.wildberries.ru/catalog/1284571224/detail.aspx'},
  @{id='wb-kumho';mp='wildberries';sku='895872553';name='Wintercraft Ice WI32';url='https://www.wildberries.ru/catalog/895872553/detail.aspx'}
 )
 $collector=Join-Path $root 'card_collector.py';$outDir=Join-Path $root ('direct10-'+(Get-Date -Format 'yyyyMMdd-HHmmss'));New-Item -ItemType Directory -Path $outDir -Force|Out-Null
 $rows=@();$i=0
 foreach($t in $targets){
  $i++
  $profile=Join-Path $root ('profiles\'+$(if($t.mp-eq'ozon'){'Ozon'}else{'Wildberries'}))
  $out=Join-Path $outDir ($t.id+'.json');$shot=Join-Path $outDir ($t.id+'.png')
  $port=9600+$i
  & $python $collector --browser-path $browser --profile-dir $profile --target-url $t.url --expected-sku $t.sku --expected-region 'Воронеж' --expected-name $t.name --output $out --screenshot $shot --port $port --settle-seconds 9
  $ec=$LASTEXITCODE
  if(Test-Path $out){$j=Get-Content $out -Raw -Encoding UTF8|ConvertFrom-Json}else{$j=[pscustomobject]@{status='NO_RESULT'}}
  $p1=if($j.price){$j.price.buyer_price_rub}else{$null};$p2=if($j.price){$j.price.secondary_price_rub}else{$null}
  $identityOk=($j.sku-eq$t.sku)-and($j.name_ok-eq$true)
  $valid=($identityOk-and$p1-ne$null-and($j.status-eq'CARD_PASS'-or$j.status-eq'REGION_UNRESOLVED'))
  $rows+=[pscustomobject]@{id=$t.id;marketplace=$t.mp;status=$j.status;sku=$j.sku;price1=$p1;price2=$p2;region_ok=$j.region_ok;name=$j.name;name_ok=$j.name_ok;identity_ok=$identityOk;valid_price=$valid;exit_code=$ec}
 }
 $ozValid=@($rows|Where-Object{$_.marketplace-eq'ozon'-and$_.valid_price}).Count
 $wbValid=@($rows|Where-Object{$_.marketplace-eq'wildberries'-and$_.valid_price}).Count
 [ordered]@{ok=$true;source_sha=$sha;ozon_valid_price_count=$ozValid;wb_valid_price_count=$wbValid;rows=$rows}|ConvertTo-Json -Depth 20|Set-Content -LiteralPath $result -Encoding UTF8
}catch{
 [ordered]@{ok=$false;error=$_.Exception.Message}|ConvertTo-Json -Depth 5|Set-Content -LiteralPath $result -Encoding UTF8
}
'@
[IO.File]::WriteAllText($child,$childCode,(New-Object Text.UTF8Encoding($false)))
try{Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue}catch{}
$action=New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$child`""
$principal=New-ScheduledTaskPrincipal -UserId $interactiveUser -LogonType Interactive -RunLevel Limited
$settings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 8) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $taskName -Action $action -Principal $principal -Settings $settings -Force|Out-Null
$maxProc=0;$maxVisible=0
Start-ScheduledTask -TaskName $taskName
$deadline=(Get-Date).AddMinutes(8)
while((Get-Date)-lt$deadline -and -not(Test-Path $result)){
 $procs=Get-MonitorBrowserProcesses;if($procs.Count-gt$maxProc){$maxProc=$procs.Count}
 $vis=0;foreach($p in $procs){try{$gp=Get-Process -Id $p.ProcessId -ErrorAction Stop;if($gp.MainWindowHandle-ne 0 -and [Win32VisibleDirect10]::IsWindowVisible($gp.MainWindowHandle)){$vis++}}catch{}}
 if($vis-gt$maxVisible){$maxVisible=$vis};Start-Sleep -Milliseconds 300
}
if(-not(Test-Path $result)){throw 'direct10 timeout'}
Start-Sleep -Seconds 2;Kill-MonitorBrowsers;$remaining=(Get-MonitorBrowserProcesses).Count
$j=Get-Content $result -Raw -Encoding UTF8|ConvertFrom-Json
Write-Host '--- DIRECT10_HIDDEN_ACCEPTANCE ---'
Write-Host "OK=$($j.ok) SOURCE_SHA=$($j.source_sha) OZON_VALID=$($j.ozon_valid_price_count) WB_VALID=$($j.wb_valid_price_count)"
Write-Host "MAX_MONITOR_PROCESSES=$maxProc MAX_VISIBLE_MONITOR_WINDOWS=$maxVisible REMAINING_MONITOR_PROCESSES=$remaining"
if($j.rows){foreach($r in $j.rows){Write-Host ("CARD={0} MP={1} STATUS={2} SKU={3} PRICE={4}/{5} REGION={6} NAME_OK={7} VALID={8} NAME={9}" -f $r.id,$r.marketplace,$r.status,$r.sku,$r.price1,$r.price2,$r.region_ok,$r.name_ok,$r.valid_price,$r.name)}}else{Write-Host "ERROR=$($j.error)"}
try{Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue}catch{}
Remove-Item $child -Force -ErrorAction SilentlyContinue
if($remaining-ne 0){exit 9};if($maxVisible-ne 0){exit 8};if(-not$j.ok){exit 7};if($j.ozon_valid_price_count-lt5 -or $j.wb_valid_price_count-lt5){exit 6};exit 0
