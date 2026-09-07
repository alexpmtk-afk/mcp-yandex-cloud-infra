$ErrorActionPreference='Stop'
$runtimeRoot='C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
$repoRoot=Join-Path $runtimeRoot 'repo'
$taskName='MarketplaceCardMonitor-Hidden-Smoke-Once'
$child=Join-Path $runtimeRoot 'hidden-smoke-once.ps1'
$result=Join-Path $runtimeRoot 'hidden-smoke-result.json'
$interactiveUser=(Get-CimInstance Win32_ComputerSystem -ErrorAction Stop).UserName
if([string]::IsNullOrWhiteSpace($interactiveUser)){throw 'No interactive user'}

function Get-MonitorBrowserProcesses {
  @(Get-CimInstance Win32_Process | Where-Object {
    ($_.Name -match '^(browser|yandex|chrome)\.exe$') -and
    ([string]$_.CommandLine).Contains('marketplace-card-monitor\user-node-v1\profiles')
  })
}
function Kill-MonitorBrowsers {
  Get-MonitorBrowserProcesses | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
  Start-Sleep -Milliseconds 500
}

Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class Win32Visible {
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
$result=Join-Path $root 'hidden-smoke-result.json'
$smoke=Join-Path $root 'hidden-smoke-4.json'

function GitBytes([string]$spec,[string]$dest){
 $psi=New-Object Diagnostics.ProcessStartInfo
 $psi.FileName=$git
 $psi.Arguments="-C `"$repo`" show `"$spec`""
 $psi.UseShellExecute=$false
 $psi.RedirectStandardOutput=$true
 $psi.RedirectStandardError=$true
 $psi.CreateNoWindow=$true
 $p=[Diagnostics.Process]::Start($psi)
 $ms=New-Object IO.MemoryStream
 $p.StandardOutput.BaseStream.CopyTo($ms)
 $err=$p.StandardError.ReadToEnd()
 $p.WaitForExit()
 if($p.ExitCode-ne 0){$ms.Dispose();throw $err}
 [IO.File]::WriteAllBytes($dest,$ms.ToArray())
 $ms.Dispose()
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

  & $python -c "import json,sys; p=json.load(open(sys.argv[1],encoding='utf-8')); ids={'ozon-cordiant-snow-cross-2','wb-cordiant-snow-cross-2','ozon-formula-ice','wb-formula-ice'}; p['cards']=[x for x in p['cards'] if x['id'] in ids]; json.dump(p,open(sys.argv[2],'w',encoding='utf-8'),ensure_ascii=False,indent=2)" (Join-Path $root 'tires-195-55-r16.json') $smoke
  if($LASTEXITCODE-ne 0){throw 'smoke config failed'}

  & $python (Join-Path $root 'batch_monitor.py') --config $smoke --runtime-root $root --browser-path $browser --collector (Join-Path $root 'card_collector.py') --discovery (Join-Path $root 'target_discovery.py') --base-port 9380 --settle-seconds 10 --discovery-settle-seconds 10 --collector-timeout-seconds 70 --discovery-timeout-seconds 75
  $ec=$LASTEXITCODE
  $latest=Get-Content (Join-Path $root 'latest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
  [ordered]@{
    ok=$true
    source_sha=$sha
    batch_exit=$ec
    run_id=$latest.run_id
    batch_status=$latest.status
    total=$latest.cards_total
    pass=$latest.cards_pass
    fail=$latest.cards_fail
    results=$latest.results
  } | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $result -Encoding UTF8
} catch {
  [ordered]@{ok=$false;error=$_.Exception.Message} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $result -Encoding UTF8
}
'@
[IO.File]::WriteAllText($child,$childCode,(New-Object Text.UTF8Encoding($false)))

try{Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue}catch{}
$action=New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$child`""
$principal=New-ScheduledTaskPrincipal -UserId $interactiveUser -LogonType Interactive -RunLevel Limited
$settings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 8) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $taskName -Action $action -Principal $principal -Settings $settings -Force|Out-Null

$maxMonitorProcesses=0
$maxVisibleWindows=0
Start-ScheduledTask -TaskName $taskName
$deadline=(Get-Date).AddMinutes(8)
while((Get-Date)-lt $deadline -and -not(Test-Path $result)){
  $procs=Get-MonitorBrowserProcesses
  if($procs.Count -gt $maxMonitorProcesses){$maxMonitorProcesses=$procs.Count}
  $visible=0
  foreach($p in $procs){
    try{
      $gp=Get-Process -Id $p.ProcessId -ErrorAction Stop
      if($gp.MainWindowHandle -ne 0 -and [Win32Visible]::IsWindowVisible($gp.MainWindowHandle)){$visible++}
    }catch{}
  }
  if($visible -gt $maxVisibleWindows){$maxVisibleWindows=$visible}
  Start-Sleep -Milliseconds 400
}
if(-not(Test-Path $result)){throw 'hidden smoke timeout'}

Start-Sleep -Seconds 2
Kill-MonitorBrowsers
$remaining=(Get-MonitorBrowserProcesses).Count
$j=Get-Content $result -Raw -Encoding UTF8 | ConvertFrom-Json
Write-Host '--- HIDDEN_SMOKE ---'
Write-Host "OK=$($j.ok) SOURCE_SHA=$($j.source_sha) BATCH=$($j.batch_status) TOTAL=$($j.total) PASS=$($j.pass) FAIL=$($j.fail)"
Write-Host "MAX_MONITOR_PROCESSES=$maxMonitorProcesses"
Write-Host "MAX_VISIBLE_MONITOR_WINDOWS=$maxVisibleWindows"
Write-Host "REMAINING_MONITOR_PROCESSES=$remaining"
if($j.results){
 foreach($r in $j.results){
  $p1=$null;$p2=$null;$m=$null
  if($r.price){$p1=$r.price.buyer_price_rub;$p2=$r.price.secondary_price_rub;$m=$r.price.method}
  Write-Host ("CARD={0} MP={1} STATUS={2} SKU={3} PRICE={4}/{5} METHOD={6} REGION={7} NAME={8}" -f $r.id,$r.marketplace,$r.status,$r.sku,$p1,$p2,$m,$r.region_ok,$r.name)
 }
}
try{Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue}catch{}
Remove-Item $child -Force -ErrorAction SilentlyContinue
if($remaining -ne 0){exit 9}
if($maxVisibleWindows -ne 0){exit 8}
exit 0
