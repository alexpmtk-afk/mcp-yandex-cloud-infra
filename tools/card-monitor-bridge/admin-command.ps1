$ErrorActionPreference='Stop'
$root='C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
$repo=Join-Path $root 'repo'
$git='C:\Program Files\Git\cmd\git.exe'
$python=Join-Path $root '.venv\Scripts\python.exe'
$browser='C:\Program Files\Yandex\YandexBrowser\Application\browser.exe'
$taskName='MarketplaceCardMonitor-Parallel5x2-Hidden-Acceptance'
$child=Join-Path $root 'parallel5x2-hidden-acceptance.ps1'
$result=Join-Path $root 'parallel5x2-hidden-acceptance.json'
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
public static class Win32Visible5x2 {
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
$result=Join-Path $root 'parallel5x2-hidden-acceptance.json'
function GitBytes([string]$spec,[string]$dest){
 $psi=New-Object Diagnostics.ProcessStartInfo;$psi.FileName=$git;$psi.Arguments="-C `"$repo`" show `"$spec`"";$psi.UseShellExecute=$false;$psi.RedirectStandardOutput=$true;$psi.RedirectStandardError=$true;$psi.CreateNoWindow=$true
 $p=[Diagnostics.Process]::Start($psi);$ms=New-Object IO.MemoryStream;$p.StandardOutput.BaseStream.CopyTo($ms);$err=$p.StandardError.ReadToEnd();$p.WaitForExit();if($p.ExitCode-ne 0){$ms.Dispose();throw $err};[IO.File]::WriteAllBytes($dest,$ms.ToArray());$ms.Dispose()
}
try{
 & $git -C $repo fetch origin implementation/ozon-user-node-gate --prune
 if($LASTEXITCODE-ne 0){throw "git fetch failed: $LASTEXITCODE"}
 $ref='origin/implementation/ozon-user-node-gate';$sha=(& $git -C $repo rev-parse $ref).Trim()
 GitBytes "$ref`:src/browser_lifecycle.py" (Join-Path $root 'browser_lifecycle.py')
 GitBytes "$ref`:src/card_collector.py" (Join-Path $root 'card_collector.py')
 GitBytes "$ref`:src/direct_acceptance.py" (Join-Path $root 'direct_acceptance.py')
 GitBytes "$ref`:config/direct-acceptance-5x2.json" (Join-Path $root 'direct-acceptance-5x2.json')
 & $python -m py_compile (Join-Path $root 'browser_lifecycle.py') (Join-Path $root 'card_collector.py') (Join-Path $root 'direct_acceptance.py')
 if($LASTEXITCODE-ne 0){throw "compile failed: $LASTEXITCODE"}
 & $python (Join-Path $root 'direct_acceptance.py') --config (Join-Path $root 'direct-acceptance-5x2.json') --collector (Join-Path $root 'card_collector.py') --browser-path $browser --runtime-root $root --output $result --timeout-seconds 65 --settle-seconds 9
 $ec=$LASTEXITCODE
 if(-not(Test-Path $result)){throw "acceptance result missing, exit=$ec"}
}catch{
 [ordered]@{schema='DIRECT_CARD_ACCEPTANCE_V1';error=$_.Exception.Message;ozon_valid_price_count=0;wb_valid_price_count=0;rows=@()}|ConvertTo-Json -Depth 10|Set-Content -LiteralPath $result -Encoding UTF8
}
'@
[IO.File]::WriteAllText($child,$childCode,(New-Object Text.UTF8Encoding($false)))
try{Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue}catch{}
$action=New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$child`""
$principal=New-ScheduledTaskPrincipal -UserId $interactiveUser -LogonType Interactive -RunLevel Limited
$settings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 7) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $taskName -Action $action -Principal $principal -Settings $settings -Force|Out-Null
$maxProc=0;$maxVisible=0
Start-ScheduledTask -TaskName $taskName
$deadline=(Get-Date).AddMinutes(7)
while((Get-Date)-lt$deadline -and -not(Test-Path $result)){
 $procs=Get-MonitorBrowserProcesses;if($procs.Count-gt$maxProc){$maxProc=$procs.Count}
 $vis=0;foreach($p in $procs){try{$gp=Get-Process -Id $p.ProcessId -ErrorAction Stop;if($gp.MainWindowHandle-ne 0 -and [Win32Visible5x2]::IsWindowVisible($gp.MainWindowHandle)){$vis++}}catch{}}
 if($vis-gt$maxVisible){$maxVisible=$vis};Start-Sleep -Milliseconds 300
}
if(-not(Test-Path $result)){throw 'parallel5x2 timeout'}
Start-Sleep -Seconds 2;Kill-MonitorBrowsers;$remaining=(Get-MonitorBrowserProcesses).Count
$j=Get-Content $result -Raw -Encoding UTF8|ConvertFrom-Json
Write-Host '--- PARALLEL5X2_HIDDEN_ACCEPTANCE ---'
Write-Host "OZON_VALID=$($j.ozon_valid_price_count) WB_VALID=$($j.wb_valid_price_count)"
Write-Host "MAX_MONITOR_PROCESSES=$maxProc MAX_VISIBLE_MONITOR_WINDOWS=$maxVisible REMAINING_MONITOR_PROCESSES=$remaining"
if($j.rows){foreach($r in $j.rows){Write-Host ("CARD={0} MP={1} STATUS={2} SKU={3} PRICE={4}/{5} REGION={6} NAME_OK={7} VALID={8} NAME={9}" -f $r.id,$r.marketplace,$r.status,$r.sku,$r.buyer_price_rub,$r.secondary_price_rub,$r.region_ok,$r.name_ok,$r.valid_price,$r.name)}}else{Write-Host "ERROR=$($j.error)"}
try{Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue}catch{}
Remove-Item $child -Force -ErrorAction SilentlyContinue
if($remaining-ne 0){exit 9};if($maxVisible-ne 0){exit 8};if($j.ozon_valid_price_count-lt5 -or $j.wb_valid_price_count-lt5){exit 6};exit 0
