# Card Monitor admin deploy/smoke command. Source files are copied byte-exact.
$ErrorActionPreference = 'Stop'
$runtimeRoot = 'C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
$repoRoot = Join-Path $runtimeRoot 'repo'
$taskName = 'MarketplaceCardMonitor-Deploy-Smoke-Once'
$child = Join-Path $runtimeRoot 'deploy-smoke-once.ps1'
$result = Join-Path $runtimeRoot 'deploy-smoke-result.txt'

$interactiveUser = (Get-CimInstance Win32_ComputerSystem -ErrorAction Stop).UserName
if ([string]::IsNullOrWhiteSpace($interactiveUser)) { throw 'No interactive Windows user is logged on.' }
if (-not (Test-Path (Join-Path $repoRoot '.git'))) { throw "Repo not found: $repoRoot" }
if (Test-Path $result) { Remove-Item $result -Force }

$childCode = @'
$ErrorActionPreference = 'Stop'
$runtimeRoot = 'C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
$repoRoot = Join-Path $runtimeRoot 'repo'
$result = Join-Path $runtimeRoot 'deploy-smoke-result.txt'
$smokeConfig = Join-Path $runtimeRoot 'smoke-4.json'
$python = Join-Path $runtimeRoot '.venv\Scripts\python.exe'
$browser = 'C:\Program Files\Yandex\YandexBrowser\Application\browser.exe'
$git = 'C:\Program Files\Git\cmd\git.exe'
$lines = New-Object System.Collections.Generic.List[string]
function Add-Line([string]$s) { $lines.Add($s) }
function Flush { [IO.File]::WriteAllText($result, ($lines -join "`r`n"), (New-Object Text.UTF8Encoding($false))) }
function Write-GitObjectBytes([string]$spec, [string]$destination) {
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $git
  $psi.Arguments = "-C `"$repoRoot`" show `"$spec`""
  $psi.UseShellExecute = $false
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  $psi.CreateNoWindow = $true
  $p = [System.Diagnostics.Process]::Start($psi)
  $ms = New-Object System.IO.MemoryStream
  $p.StandardOutput.BaseStream.CopyTo($ms)
  $stderr = $p.StandardError.ReadToEnd()
  $p.WaitForExit()
  if ($p.ExitCode -ne 0) { $ms.Dispose(); throw "git show failed for $spec : $stderr" }
  [IO.File]::WriteAllBytes($destination, $ms.ToArray())
  $ms.Dispose()
}
try {
  Add-Line "USER=$([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)"
  Add-Line "SESSION=$((Get-Process -Id $PID).SessionId)"
  & $git -C $repoRoot fetch origin implementation/ozon-user-node-gate --prune
  if ($LASTEXITCODE -ne 0) { throw "git fetch failed: $LASTEXITCODE" }
  $ref = 'origin/implementation/ozon-user-node-gate'
  $sha = (& $git -C $repoRoot rev-parse $ref).Trim()
  Add-Line "SOURCE_SHA=$sha"
  $files = @{
    'src/card_collector.py' = (Join-Path $runtimeRoot 'card_collector.py')
    'src/target_discovery.py' = (Join-Path $runtimeRoot 'target_discovery.py')
    'src/batch_monitor.py' = (Join-Path $runtimeRoot 'batch_monitor.py')
    'config/tires-195-55-r16.json' = (Join-Path $runtimeRoot 'tires-195-55-r16.json')
  }
  foreach ($entry in $files.GetEnumerator()) {
    Write-GitObjectBytes ("{0}:{1}" -f $ref,$entry.Key) $entry.Value
    Add-Line "DEPLOYED=$($entry.Key)"
  }
  & $python -m py_compile (Join-Path $runtimeRoot 'card_collector.py') (Join-Path $runtimeRoot 'target_discovery.py') (Join-Path $runtimeRoot 'batch_monitor.py')
  if ($LASTEXITCODE -ne 0) { throw "py_compile failed: $LASTEXITCODE" }
  Add-Line 'PY_COMPILE=PASS'

  $full = Join-Path $runtimeRoot 'tires-195-55-r16.json'
  & $python -c "import json,sys; p=json.load(open(sys.argv[1],encoding='utf-8')); ids={'ozon-cordiant-snow-cross-2','wb-cordiant-snow-cross-2','ozon-formula-ice','wb-formula-ice'}; p['cards']=[x for x in p['cards'] if x['id'] in ids]; json.dump(p,open(sys.argv[2],'w',encoding='utf-8'),ensure_ascii=False,indent=2)" $full $smokeConfig
  if ($LASTEXITCODE -ne 0) { throw "smoke config failed: $LASTEXITCODE" }

  & $python (Join-Path $runtimeRoot 'batch_monitor.py') --config $smokeConfig --runtime-root $runtimeRoot --browser-path $browser --collector (Join-Path $runtimeRoot 'card_collector.py') --discovery (Join-Path $runtimeRoot 'target_discovery.py') --base-port 9260 --settle-seconds 10 --discovery-settle-seconds 8 --collector-timeout-seconds 60 --discovery-timeout-seconds 75
  $batchExit = $LASTEXITCODE
  Add-Line "BATCH_EXIT=$batchExit"
  $latest = Get-Content (Join-Path $runtimeRoot 'latest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
  Add-Line "RUN_ID=$($latest.run_id)"
  Add-Line "BATCH_STATUS=$($latest.status) TOTAL=$($latest.cards_total) PASS=$($latest.cards_pass) FAIL=$($latest.cards_fail)"
  foreach ($r in $latest.results) {
    $p1=$null;$p2=$null;$method=$null
    if ($r.price) { $p1=$r.price.buyer_price_rub;$p2=$r.price.secondary_price_rub;$method=$r.price.method }
    $disc=$null;$selected=$null
    if ($r.discovery) { $disc=$r.discovery.status; if($r.discovery.selected){$selected=$r.discovery.selected.sku} }
    Add-Line ("CARD={0} MP={1} STATUS={2} SKU={3} PRICE={4}/{5} METHOD={6} SELLER={7} REGION={8} DISC={9} SELECTED={10} NAME={11}" -f $r.id,$r.marketplace,$r.status,$r.sku,$p1,$p2,$method,$r.seller,$r.region_ok,$disc,$selected,$r.name)
  }
  Add-Line 'DEPLOY_SMOKE=DONE'
} catch {
  Add-Line 'DEPLOY_SMOKE=FAIL'
  Add-Line "ERROR=$($_.Exception.Message)"
} finally { Flush }
'@
[IO.File]::WriteAllText($child, $childCode, (New-Object Text.UTF8Encoding($false)))
try { Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue } catch {}
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$child`""
$principal = New-ScheduledTaskPrincipal -UserId $interactiveUser -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 8) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $taskName -Action $action -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
$deadline = (Get-Date).AddMinutes(8)
while ((Get-Date) -lt $deadline -and -not (Test-Path $result)) { Start-Sleep -Seconds 3 }
if (-not (Test-Path $result)) { throw 'Timed out waiting for deploy smoke result.' }
Write-Host '--- CARD_MONITOR_DEPLOY_SMOKE_RESULT ---'
Get-Content -Raw -LiteralPath $result
try { Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue } catch {}
Remove-Item $child -Force -ErrorAction SilentlyContinue
