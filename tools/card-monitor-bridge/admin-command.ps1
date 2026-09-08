$ErrorActionPreference='Stop'
$root='C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
$repo=Join-Path $root 'repo'
$git='C:\Program Files\Git\cmd\git.exe'
$python=Join-Path $root '.venv\Scripts\python.exe'
$browser='C:\Program Files\Yandex\YandexBrowser\Application\browser.exe'
$taskName='MarketplaceCardMonitor-Daily-OnDemand-Hidden'
$child=Join-Path $root 'daily-ondemand-hidden.ps1'
$result=Join-Path $root 'daily-history\latest.json'
$interactiveUser=(Get-CimInstance Win32_ComputerSystem -ErrorAction Stop).UserName
if([string]::IsNullOrWhiteSpace($interactiveUser)){throw 'No interactive user'}
function Get-MonitorBrowserProcesses {@(Get-CimInstance Win32_Process|Where-Object{($_.Name-match'^(browser|yandex|chrome)\.exe$')-and([string]$_.CommandLine).Contains('--user-data-dir=C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1')})}
function Kill-MonitorBrowsers {Get-MonitorBrowserProcesses|ForEach-Object{Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue};Start-Sleep -Milliseconds 500}
Add-Type @'
using System;using System.Runtime.InteropServices;public static class Win32VisibleDaily2{[DllImport("user32.dll")]public static extern bool IsWindowVisible(IntPtr hWnd);}
'@
Kill-MonitorBrowsers
$before=if(Test-Path $result){(Get-Item $result).LastWriteTimeUtc}else{[datetime]::MinValue}
$childCode=@'
$ErrorActionPreference='Stop'
$root='C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
$repo=Join-Path $root 'repo';$git='C:\Program Files\Git\cmd\git.exe';$python=Join-Path $root '.venv\Scripts\python.exe';$browser='C:\Program Files\Yandex\YandexBrowser\Application\browser.exe'
function GitBytes([string]$spec,[string]$dest){$psi=New-Object Diagnostics.ProcessStartInfo;$psi.FileName=$git;$psi.Arguments="-C `"$repo`" show `"$spec`"";$psi.UseShellExecute=$false;$psi.RedirectStandardOutput=$true;$psi.RedirectStandardError=$true;$psi.CreateNoWindow=$true;$p=[Diagnostics.Process]::Start($psi);$ms=New-Object IO.MemoryStream;$p.StandardOutput.BaseStream.CopyTo($ms);$err=$p.StandardError.ReadToEnd();$p.WaitForExit();if($p.ExitCode-ne0){$ms.Dispose();throw$err};[IO.File]::WriteAllBytes($dest,$ms.ToArray());$ms.Dispose()}
& $git -C $repo fetch origin implementation/ozon-user-node-gate --prune;if($LASTEXITCODE-ne0){throw "git fetch failed: $LASTEXITCODE"}
$ref='origin/implementation/ozon-user-node-gate'
$map=@{'src/browser_lifecycle.py'='browser_lifecycle.py';'src/card_collector.py'='card_collector.py';'src/target_discovery.py'='target_discovery.py';'src/direct_acceptance.py'='direct_acceptance.py';'src/daily_monitor.py'='daily_monitor.py';'config/direct-acceptance-5x2.json'='direct-acceptance-5x2.json';'config/history-seed-2026-09-07.json'='history-seed-2026-09-07.json'}
foreach($e in $map.GetEnumerator()){GitBytes "$ref`:$($e.Key)" (Join-Path $root $e.Value)}
& $python -m py_compile (Join-Path $root 'browser_lifecycle.py') (Join-Path $root 'card_collector.py') (Join-Path $root 'target_discovery.py') (Join-Path $root 'direct_acceptance.py') (Join-Path $root 'daily_monitor.py');if($LASTEXITCODE-ne0){throw "compile failed: $LASTEXITCODE"}
$history=Join-Path $root 'daily-history';New-Item -ItemType Directory -Path $history -Force|Out-Null
& $python (Join-Path $root 'daily_monitor.py') --config (Join-Path $root 'direct-acceptance-5x2.json') --acceptance (Join-Path $root 'direct_acceptance.py') --collector (Join-Path $root 'card_collector.py') --discovery (Join-Path $root 'target_discovery.py') --browser-path $browser --runtime-root $root --history-root $history --seed-file (Join-Path $root 'history-seed-2026-09-07.json') --timeout-seconds 65 --discovery-timeout-seconds 75 --settle-seconds 9
exit $LASTEXITCODE
'@
[IO.File]::WriteAllText($child,$childCode,(New-Object Text.UTF8Encoding($false)))
try{Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue}catch{}
$action=New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$child`""
$principal=New-ScheduledTaskPrincipal -UserId $interactiveUser -LogonType Interactive -RunLevel Limited
$settings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 12) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $taskName -Action $action -Principal $principal -Settings $settings -Force|Out-Null
$maxProc=0;$maxVisible=0;Start-ScheduledTask -TaskName $taskName;$deadline=(Get-Date).AddMinutes(12)
while((Get-Date)-lt$deadline){$fresh=(Test-Path $result)-and((Get-Item $result).LastWriteTimeUtc-gt$before);if($fresh){break};$procs=Get-MonitorBrowserProcesses;if($procs.Count-gt$maxProc){$maxProc=$procs.Count};$vis=0;foreach($p in $procs){try{$gp=Get-Process -Id $p.ProcessId -ErrorAction Stop;if($gp.MainWindowHandle-ne0-and[Win32VisibleDaily2]::IsWindowVisible($gp.MainWindowHandle)){$vis++}}catch{}};if($vis-gt$maxVisible){$maxVisible=$vis};Start-Sleep -Milliseconds 350}
if(-not((Test-Path $result)-and((Get-Item $result).LastWriteTimeUtc-gt$before))){throw 'daily snapshot timeout'}
Start-Sleep -Seconds 2;Kill-MonitorBrowsers;$remaining=(Get-MonitorBrowserProcesses).Count;$j=Get-Content $result -Raw -Encoding UTF8|ConvertFrom-Json
Write-Host '--- DAILY_SNAPSHOT_RETRY ---';Write-Host "RUN_ID=$($j.run_id) DAY=$($j.local_day) STATUS=$($j.status) OZON=$($j.ozon_valid_price_count) WB=$($j.wb_valid_price_count) FRESH=$($j.fresh_valid_count) REPLACED=$($j.same_day_replaced_count) HISTORY_TOTAL=$($j.history_total_records)";Write-Host "MAX_VISIBLE=$maxVisible REMAINING=$remaining"
foreach($r in $j.rows){Write-Host ("ROW={0} MP={1} STATUS={2} SOURCE={3} CONFIG_SKU={4} RESOLVED_SKU={5} PRICE={6} PREV={7} CHANGE={8} CHANGE_PCT={9} REGION={10} VALID={11}" -f $r.id,$r.marketplace,$r.status,$r.target_source,$r.configured_sku,$r.resolved_sku,$r.buyer_price_rub,$r.previous_price_rub,$r.change_rub,$r.change_pct,$r.region_ok,$r.valid_price)}
try{Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue}catch{};Remove-Item $child -Force -ErrorAction SilentlyContinue
if($remaining-ne0){exit 9};if($maxVisible-ne0){exit 8};exit 0
