$ErrorActionPreference='Stop'
$runtimeRoot='C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
$repoRoot=Join-Path $runtimeRoot 'repo'
$taskName='MarketplaceCardMonitor-WB-Network-Probe-Once'
$child=Join-Path $runtimeRoot 'wb-network-probe.ps1'
$result=Join-Path $runtimeRoot 'wb-network-probe-result.txt'
$interactiveUser=(Get-CimInstance Win32_ComputerSystem -ErrorAction Stop).UserName
if([string]::IsNullOrWhiteSpace($interactiveUser)){throw 'No interactive user'}
if(Test-Path $result){Remove-Item $result -Force}
$childCode=@'
$ErrorActionPreference='Stop'
$root='C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
$repo=Join-Path $root 'repo'
$git='C:\Program Files\Git\cmd\git.exe'
$python=Join-Path $root '.venv\Scripts\python.exe'
$result=Join-Path $root 'wb-network-probe-result.txt'
function GitBytes([string]$spec,[string]$dest){
 $psi=New-Object Diagnostics.ProcessStartInfo;$psi.FileName=$git;$psi.Arguments="-C `"$repo`" show `"$spec`"";$psi.UseShellExecute=$false;$psi.RedirectStandardOutput=$true;$psi.RedirectStandardError=$true;$psi.CreateNoWindow=$true
 $p=[Diagnostics.Process]::Start($psi);$ms=New-Object IO.MemoryStream;$p.StandardOutput.BaseStream.CopyTo($ms);$err=$p.StandardError.ReadToEnd();$p.WaitForExit();if($p.ExitCode-ne 0){throw $err};[IO.File]::WriteAllBytes($dest,$ms.ToArray());$ms.Dispose()
}
& $git -C $repo fetch origin implementation/ozon-user-node-gate --prune
if($LASTEXITCODE-ne 0){throw 'git fetch failed'}
$ref='origin/implementation/ozon-user-node-gate'
GitBytes "$ref`:src/target_discovery.py" (Join-Path $root 'target_discovery.py')
& $python -m py_compile (Join-Path $root 'target_discovery.py')
if($LASTEXITCODE-ne 0){throw 'compile failed'}
$probe=Join-Path $root 'wb-network-probe.py'
$code=@"
import json,pathlib,subprocess,sys,shutil
r=pathlib.Path(r'$root')
c=json.loads((r/'tires-195-55-r16.json').read_text(encoding='utf-8'))
card=next(x for x in c['cards'] if x['id']=='wb-cordiant-snow-cross-2')
p=r/'profiles'/'Wildberries-Network-Probe'
shutil.rmtree(p,ignore_errors=True)
out=r/'wb-network-discovery.json'
cmd=[sys.executable,str(r/'target_discovery.py'),'--browser-path',r'C:\Program Files\Yandex\YandexBrowser\Application\browser.exe','--profile-dir',str(p),'--marketplace','wildberries','--query',card['query'],'--output',str(out),'--port','9350','--settle-seconds','10']
for k,a in [('required_tokens','--required'),('preferred_tokens','--preferred'),('forbidden_tokens','--forbidden')]:
 for t in card.get(k,[]): cmd += [a,str(t)]
cp=subprocess.run(cmd,capture_output=True,text=True,timeout=100)
j=json.loads(out.read_text(encoding='utf-8')) if out.exists() else {}
s=j.get('selected') or {}
(r/'wb-network-probe-result.txt').write_text(f"EXIT={cp.returncode} STATUS={j.get('status')} SOURCE={j.get('discovery_source')} RAW={j.get('raw_product_links')} SKU={s.get('sku')} URL={s.get('url')} TEXT={s.get('text')} ERR={j.get('error')}",encoding='utf-8')
"@
[IO.File]::WriteAllText($probe,$code,(New-Object Text.UTF8Encoding($false)))
& $python $probe
'@
[IO.File]::WriteAllText($child,$childCode,(New-Object Text.UTF8Encoding($false)))
try{Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue}catch{}
$action=New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$child`""
$principal=New-ScheduledTaskPrincipal -UserId $interactiveUser -LogonType Interactive -RunLevel Limited
$settings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 4) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $taskName -Action $action -Principal $principal -Settings $settings -Force|Out-Null
Start-ScheduledTask -TaskName $taskName
$deadline=(Get-Date).AddMinutes(4);while((Get-Date)-lt $deadline -and -not(Test-Path $result)){Start-Sleep 3}
if(-not(Test-Path $result)){throw 'probe timeout'}
Get-Content $result -Raw
try{Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue}catch{}
