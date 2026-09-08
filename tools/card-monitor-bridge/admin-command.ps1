$ErrorActionPreference='Stop'
$root='C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
$repo=Join-Path $root 'repo'
$git='C:\Program Files\Git\cmd\git.exe'
$python=Join-Path $root '.venv\Scripts\python.exe'
$browser='C:\Program Files\Yandex\YandexBrowser\Application\browser.exe'
$taskName='MarketplaceCardMonitor-WB-Inspect-Hidden'
$child=Join-Path $root 'wb-inspect-hidden.ps1'
$result=Join-Path $root 'wb-inspect-hidden.json'
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
public static class Win32VisibleWBInspect {
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
$result=Join-Path $root 'wb-inspect-hidden.json'
function GitBytes([string]$spec,[string]$dest){
 $psi=New-Object Diagnostics.ProcessStartInfo;$psi.FileName=$git;$psi.Arguments="-C `"$repo`" show `"$spec`"";$psi.UseShellExecute=$false;$psi.RedirectStandardOutput=$true;$psi.RedirectStandardError=$true;$psi.CreateNoWindow=$true
 $p=[Diagnostics.Process]::Start($psi);$ms=New-Object IO.MemoryStream;$p.StandardOutput.BaseStream.CopyTo($ms);$err=$p.StandardError.ReadToEnd();$p.WaitForExit();if($p.ExitCode-ne 0){$ms.Dispose();throw $err};[IO.File]::WriteAllBytes($dest,$ms.ToArray());$ms.Dispose()
}
try{
 & $git -C $repo fetch origin implementation/ozon-user-node-gate --prune
 if($LASTEXITCODE-ne 0){throw "git fetch failed: $LASTEXITCODE"}
 $ref='origin/implementation/ozon-user-node-gate'
 foreach($f in @('src/browser_lifecycle.py','src/target_discovery.py','src/wb_region_probe.py')){GitBytes "$ref`:$f" (Join-Path $root ([IO.Path]::GetFileName($f)))}
 & $python -m py_compile (Join-Path $root 'browser_lifecycle.py') (Join-Path $root 'target_discovery.py') (Join-Path $root 'wb_region_probe.py')
 if($LASTEXITCODE-ne 0){throw "compile failed: $LASTEXITCODE"}
 $profile=Join-Path $root 'profiles\Wildberries'
 $probe=Join-Path $root 'wb-region-probe.json'
 & $python (Join-Path $root 'wb_region_probe.py') --browser-path $browser --profile-dir $profile --output $probe --port 9891 --settle-seconds 7
 $probeEc=$LASTEXITCODE
 $kumho=Join-Path $root 'wb-discovery-kumho.json'
 & $python (Join-Path $root 'target_discovery.py') --browser-path $browser --profile-dir $profile --marketplace wildberries --query 'Kumho WinterCraft Ice Wi32 195/55 R16' --required Kumho --required WinterCraft --required Wi32 --required 195/55 --required R16 --forbidden 'БУ' --output $kumho --port 9892 --settle-seconds 10
 $kumhoEc=$LASTEXITCODE
 $viatti=Join-Path $root 'wb-discovery-viatti.json'
 & $python (Join-Path $root 'target_discovery.py') --browser-path $browser --profile-dir $profile --marketplace wildberries --query 'Viatti Nordico 2 V-528 195/55 R16' --required Viatti --required 'Nordico 2' --required 195/55 --required R16 --preferred V-528 --forbidden 'БУ' --output $viatti --port 9893 --settle-seconds 10
 $viattiEc=$LASTEXITCODE
 [ordered]@{
   ok=$true
   probe_exit=$probeEc
   kumho_exit=$kumhoEc
   viatti_exit=$viattiEc
   probe=(Get-Content $probe -Raw -Encoding UTF8|ConvertFrom-Json)
   kumho=(Get-Content $kumho -Raw -Encoding UTF8|ConvertFrom-Json)
   viatti=(Get-Content $viatti -Raw -Encoding UTF8|ConvertFrom-Json)
 }|ConvertTo-Json -Depth 30|Set-Content -LiteralPath $result -Encoding UTF8
}catch{
 [ordered]@{ok=$false;error=$_.Exception.Message}|ConvertTo-Json -Depth 5|Set-Content -LiteralPath $result -Encoding UTF8
}
'@
[IO.File]::WriteAllText($child,$childCode,(New-Object Text.UTF8Encoding($false)))
try{Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue}catch{}
$action=New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$child`""
$principal=New-ScheduledTaskPrincipal -UserId $interactiveUser -LogonType Interactive -RunLevel Limited
$settings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 6) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $taskName -Action $action -Principal $principal -Settings $settings -Force|Out-Null
$maxProc=0;$maxVisible=0
Start-ScheduledTask -TaskName $taskName
$deadline=(Get-Date).AddMinutes(6)
while((Get-Date)-lt$deadline -and -not(Test-Path $result)){
 $procs=Get-MonitorBrowserProcesses;if($procs.Count-gt$maxProc){$maxProc=$procs.Count}
 $vis=0;foreach($p in $procs){try{$gp=Get-Process -Id $p.ProcessId -ErrorAction Stop;if($gp.MainWindowHandle-ne 0 -and [Win32VisibleWBInspect]::IsWindowVisible($gp.MainWindowHandle)){$vis++}}catch{}}
 if($vis-gt$maxVisible){$maxVisible=$vis};Start-Sleep -Milliseconds 300
}
if(-not(Test-Path $result)){throw 'wb inspect timeout'}
Start-Sleep -Seconds 2;Kill-MonitorBrowsers;$remaining=(Get-MonitorBrowserProcesses).Count
$j=Get-Content $result -Raw -Encoding UTF8|ConvertFrom-Json
Write-Host '--- WB_INSPECT ---'
Write-Host "OK=$($j.ok) MAX_VISIBLE=$maxVisible REMAINING=$remaining"
if($j.ok){
 Write-Host "PROBE_STATUS=$($j.probe.status)"
 if($j.probe.before){Write-Host ('BEFORE_BODY=' + (($j.probe.before.body -replace "`r|`n",' ') -replace '\s+',' ').Substring(0,[Math]::Min(1200,(($j.probe.before.body -replace "`r|`n",' ') -replace '\s+',' ').Length)))}
 if($j.probe.after_click){Write-Host ('AFTER_BODY=' + (($j.probe.after_click.body -replace "`r|`n",' ') -replace '\s+',' ').Substring(0,[Math]::Min(2200,(($j.probe.after_click.body -replace "`r|`n",' ') -replace '\s+',' ').Length)));foreach($i in $j.probe.after_click.inputs){Write-Host ("INPUT placeholder={0} value={1} aria={2} cls={3}" -f $i.placeholder,$i.value,$i.aria,$i.cls)}}
 foreach($name in @('kumho','viatti')){$d=$j.$name;Write-Host ("DISCOVERY {0} STATUS={1} SOURCE={2} RAW={3}" -f $name,$d.status,$d.discovery_source,$d.raw_product_links);foreach($c in @($d.candidates|Select-Object -First 8)){Write-Host ("CAND {0} SKU={1} SCORE={2} URL={3} TEXT={4}" -f $name,$c.sku,$c.score,$c.url,(($c.text -replace "`r|`n",' ') -replace '\s+',' '))}}
}else{Write-Host "ERROR=$($j.error)"}
try{Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue}catch{}
Remove-Item $child -Force -ErrorAction SilentlyContinue
if($remaining-ne 0){exit 9};if($maxVisible-ne 0){exit 8};exit 0
