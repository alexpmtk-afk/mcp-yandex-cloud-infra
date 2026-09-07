$ErrorActionPreference='Stop'
$root='C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
$repo=Join-Path $root 'repo'
$git='C:\Program Files\Git\cmd\git.exe'
$python=Join-Path $root '.venv\Scripts\python.exe'
$browser='C:\Program Files\Yandex\YandexBrowser\Application\browser.exe'
$taskName='MarketplaceCardMonitor-Full-Hidden-Acceptance'
$child=Join-Path $root 'full-hidden-acceptance.ps1'
$result=Join-Path $root 'full-hidden-acceptance.json'
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
public static class Win32VisibleFull {
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
$result=Join-Path $root 'full-hidden-acceptance.json'

function GitBytes([string]$spec,[string]$dest){
 $psi=New-Object Diagnostics.ProcessStartInfo
 $psi.FileName=$git
 $psi.Arguments="-C `"$repo`" show `"$spec`""
 $psi.UseShellExecute=$false;$psi.RedirectStandardOutput=$true;$psi.RedirectStandardError=$true;$psi.CreateNoWindow=$true
 $p=[Diagnostics.Process]::Start($psi);$ms=New-Object IO.MemoryStream
 $p.StandardOutput.BaseStream.CopyTo($ms);$err=$p.StandardError.ReadToEnd();$p.WaitForExit()
 if($p.ExitCode-ne 0){$ms.Dispose();throw $err}
 [IO.File]::WriteAllBytes($dest,$ms.ToArray());$ms.Dispose()
}

try {
 & $git -C $repo fetch origin implementation/ozon-user-node-gate --prune
 if($LASTEXITCODE-ne 0){throw "git fetch failed: $LASTEXITCODE"}
 $ref='origin/implementation/ozon-user-node-gate'
 $sha=(& $git -C $repo rev-parse $ref).Trim()
 $files=@{
  'src/browser_lifecycle.py'=(Join-Path $root 'browser_lifecycle.py')
  'src/card_collector.py'=(Join-Path $root 'card_collector.py')
  'src/target_discovery.py'=(Join-Path $root 'target_discovery.py')
  'src/batch_monitor.py'=(Join-Path $root 'batch_monitor.py')
  'config/tires-195-55-r16.json'=(Join-Path $root 'tires-195-55-r16.json')
 }
 foreach($e in $files.GetEnumerator()){GitBytes ("{0}:{1}" -f $ref,$e.Key) $e.Value}
 & $python -m py_compile (Join-Path $root 'browser_lifecycle.py') (Join-Path $root 'card_collector.py') (Join-Path $root 'target_discovery.py') (Join-Path $root 'batch_monitor.py')
 if($LASTEXITCODE-ne 0){throw "py_compile failed: $LASTEXITCODE"}

 $ozRoot=Join-Path $root 'acceptance-ozon'
 $wbRoot=Join-Path $root 'acceptance-wb'
 foreach($d in @($ozRoot,$wbRoot)){New-Item -ItemType Directory -Path $d -Force|Out-Null}
 $fullCfg=Join-Path $root 'tires-195-55-r16.json'
 $ozCfg=Join-Path $ozRoot 'config.json';$wbCfg=Join-Path $wbRoot 'config.json'
 & $python -c "import json,sys; p=json.load(open(sys.argv[1],encoding='utf-8')); q=dict(p); q['cards']=[x for x in p['cards'] if x['marketplace']=='ozon']; json.dump(q,open(sys.argv[2],'w',encoding='utf-8'),ensure_ascii=False,indent=2); q=dict(p); q['cards']=[x for x in p['cards'] if x['marketplace']=='wildberries']; json.dump(q,open(sys.argv[3],'w',encoding='utf-8'),ensure_ascii=False,indent=2)" $fullCfg $ozCfg $wbCfg
 if($LASTEXITCODE-ne 0){throw 'split config failed'}

 # Seed each isolated run with the last verified address cache. Live collectors
 # still revalidate identity and read fresh prices.
 $cache=Join-Path $root 'resolved-targets.json'
 if(Test-Path $cache){
  & $python -c "import json,sys,pathlib; p=json.load(open(sys.argv[1],encoding='utf-8')); [pathlib.Path(sys.argv[2]).write_text(json.dumps([x for x in p if x.get('marketplace')=='ozon'],ensure_ascii=False,indent=2),encoding='utf-8'),pathlib.Path(sys.argv[3]).write_text(json.dumps([x for x in p if x.get('marketplace')=='wildberries'],ensure_ascii=False,indent=2),encoding='utf-8')]" $cache (Join-Path $ozRoot 'resolved-targets.json') (Join-Path $wbRoot 'resolved-targets.json')
 }

 $batch=Join-Path $root 'batch_monitor.py';$collector=Join-Path $root 'card_collector.py';$discovery=Join-Path $root 'target_discovery.py'
 function StartBatch([string]$cfg,[string]$rt,[int]$port){
  $psi=New-Object Diagnostics.ProcessStartInfo
  $psi.FileName=$python
  $psi.Arguments="`"$batch`" --config `"$cfg`" --runtime-root `"$rt`" --browser-path `"$browser`" --collector `"$collector`" --discovery `"$discovery`" --base-port $port --settle-seconds 9 --discovery-settle-seconds 8 --collector-timeout-seconds 60 --discovery-timeout-seconds 55"
  $psi.UseShellExecute=$false;$psi.RedirectStandardOutput=$true;$psi.RedirectStandardError=$true;$psi.CreateNoWindow=$true
  return [Diagnostics.Process]::Start($psi)
 }
 $oz=StartBatch $ozCfg $ozRoot 9410
 $wb=StartBatch $wbCfg $wbRoot 9510
 $deadline=(Get-Date).AddMinutes(9)
 while((Get-Date)-lt $deadline -and (-not $oz.HasExited -or -not $wb.HasExited)){Start-Sleep -Seconds 1}
 if(-not $oz.HasExited){try{$oz.Kill()}catch{}}
 if(-not $wb.HasExited){try{$wb.Kill()}catch{}}
 try{$oz.WaitForExit()}catch{};try{$wb.WaitForExit()}catch{}
 $ozOut=$oz.StandardOutput.ReadToEnd();$ozErr=$oz.StandardError.ReadToEnd();$wbOut=$wb.StandardOutput.ReadToEnd();$wbErr=$wb.StandardError.ReadToEnd()
 $ozLatest=Join-Path $ozRoot 'latest.json';$wbLatest=Join-Path $wbRoot 'latest.json'
 if(-not(Test-Path $ozLatest)){throw "Ozon latest missing: $ozErr"}
 if(-not(Test-Path $wbLatest)){throw "WB latest missing: $wbErr"}
 $oj=Get-Content $ozLatest -Raw -Encoding UTF8|ConvertFrom-Json
 $wj=Get-Content $wbLatest -Raw -Encoding UTF8|ConvertFrom-Json
 $ozPrices=@($oj.results|Where-Object{$_.price -and $_.price.buyer_price_rub -ne $null})
 $wbPrices=@($wj.results|Where-Object{$_.price -and $_.price.buyer_price_rub -ne $null})
 [ordered]@{
  ok=$true;source_sha=$sha
  ozon=[ordered]@{batch_status=$oj.status;total=$oj.cards_total;pass=$oj.cards_pass;price_count=$ozPrices.Count;results=$oj.results}
  wildberries=[ordered]@{batch_status=$wj.status;total=$wj.cards_total;pass=$wj.cards_pass;price_count=$wbPrices.Count;results=$wj.results}
 }|ConvertTo-Json -Depth 30|Set-Content -LiteralPath $result -Encoding UTF8
} catch {
 [ordered]@{ok=$false;error=$_.Exception.Message}|ConvertTo-Json -Depth 5|Set-Content -LiteralPath $result -Encoding UTF8
}
'@
[IO.File]::WriteAllText($child,$childCode,(New-Object Text.UTF8Encoding($false)))
try{Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue}catch{}
$action=New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$child`""
$principal=New-ScheduledTaskPrincipal -UserId $interactiveUser -LogonType Interactive -RunLevel Limited
$settings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $taskName -Action $action -Principal $principal -Settings $settings -Force|Out-Null

$maxProc=0;$maxVisible=0
Start-ScheduledTask -TaskName $taskName
$deadline=(Get-Date).AddMinutes(10)
while((Get-Date)-lt $deadline -and -not(Test-Path $result)){
 $procs=Get-MonitorBrowserProcesses
 if($procs.Count-gt$maxProc){$maxProc=$procs.Count}
 $vis=0
 foreach($p in $procs){try{$gp=Get-Process -Id $p.ProcessId -ErrorAction Stop;if($gp.MainWindowHandle-ne 0 -and [Win32VisibleFull]::IsWindowVisible($gp.MainWindowHandle)){$vis++}}catch{}}
 if($vis-gt$maxVisible){$maxVisible=$vis}
 Start-Sleep -Milliseconds 300
}
if(-not(Test-Path $result)){throw 'full acceptance timeout'}
Start-Sleep -Seconds 2
Kill-MonitorBrowsers
$remaining=(Get-MonitorBrowserProcesses).Count
$j=Get-Content $result -Raw -Encoding UTF8|ConvertFrom-Json
Write-Host '--- FULL_HIDDEN_ACCEPTANCE ---'
Write-Host "OK=$($j.ok) SOURCE_SHA=$($j.source_sha)"
Write-Host "MAX_MONITOR_PROCESSES=$maxProc MAX_VISIBLE_MONITOR_WINDOWS=$maxVisible REMAINING_MONITOR_PROCESSES=$remaining"
if($j.ok){
 Write-Host "OZON_TOTAL=$($j.ozon.total) OZON_PASS=$($j.ozon.pass) OZON_PRICE_COUNT=$($j.ozon.price_count)"
 foreach($r in $j.ozon.results){$p1=if($r.price){$r.price.buyer_price_rub}else{$null};$p2=if($r.price){$r.price.secondary_price_rub}else{$null};Write-Host ("OZON {0} STATUS={1} SKU={2} PRICE={3}/{4} REGION={5} SOURCE={6}" -f $r.model,$r.status,$r.sku,$p1,$p2,$r.region_ok,$r.target_source)}
 Write-Host "WB_TOTAL=$($j.wildberries.total) WB_PASS=$($j.wildberries.pass) WB_PRICE_COUNT=$($j.wildberries.price_count)"
 foreach($r in $j.wildberries.results){$p1=if($r.price){$r.price.buyer_price_rub}else{$null};$p2=if($r.price){$r.price.secondary_price_rub}else{$null};Write-Host ("WB {0} STATUS={1} SKU={2} PRICE={3}/{4} REGION={5} SOURCE={6}" -f $r.model,$r.status,$r.sku,$p1,$p2,$r.region_ok,$r.target_source)}
}else{Write-Host "ERROR=$($j.error)"}
try{Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue}catch{}
Remove-Item $child -Force -ErrorAction SilentlyContinue
if($remaining-ne 0){exit 9};if($maxVisible-ne 0){exit 8};if(-not$j.ok){exit 7}
if($j.ozon.price_count-lt 5 -or $j.wildberries.price_count-lt 5){exit 6}
exit 0
