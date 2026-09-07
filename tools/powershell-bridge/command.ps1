$ErrorActionPreference = 'Stop'
$runtimeRoot='C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
$taskName='MarketplaceCardMonitor-UserNode-Canonical'
$python=Join-Path $runtimeRoot '.venv\Scripts\python.exe'
$browser='C:\Program Files\Yandex\YandexBrowser\Application\browser.exe'
$collector=Join-Path $runtimeRoot 'card_collector.py'
$discovery=Join-Path $runtimeRoot 'target_discovery.py'
$batch=Join-Path $runtimeRoot 'batch_monitor.py'
$config=Join-Path $runtimeRoot 'tires-195-55-r16.json'
$launcher=Join-Path $runtimeRoot 'canonical-user-node-launcher.ps1'
$taskExitFile=Join-Path $runtimeRoot 'canonical-task-exit.json'
$latestFile=Join-Path $runtimeRoot 'latest.json'

$downloads=@(
 @{url='https://raw.githubusercontent.com/alexpmtk-afk/marketplace-card-monitor/implementation/ozon-user-node-gate/src/card_collector.py?token=CJWMU2X34EUODZGSJIY6V3DKT4EM7AA';path=$collector},
 @{url='https://raw.githubusercontent.com/alexpmtk-afk/marketplace-card-monitor/implementation/ozon-user-node-gate/src/target_discovery.py?token=CJWMU2SQ3LKZYWO7RLGBNGTKT4EM7AA';path=$discovery},
 @{url='https://raw.githubusercontent.com/alexpmtk-afk/marketplace-card-monitor/implementation/ozon-user-node-gate/src/batch_monitor.py?token=CJWMU2QYBQ36BMXEYHNJKADKT4EM7AA';path=$batch},
 @{url='https://raw.githubusercontent.com/alexpmtk-afk/marketplace-card-monitor/implementation/ozon-user-node-gate/config/tires-195-55-r16.json?token=CJWMU2WTM5ZY3PVCA2KW6MTKT4EOBAA';path=$config}
)
foreach($item in $downloads){Invoke-WebRequest -Uri $item.url -OutFile $item.path -UseBasicParsing; Write-Host "DEPLOYED=$($item.path) SIZE=$((Get-Item $item.path).Length)"}
& $python -m py_compile $collector $discovery $batch
if($LASTEXITCODE -ne 0){throw "PY_COMPILE_FAIL=$LASTEXITCODE"}
Write-Host 'PY_COMPILE=PASS'

# Purge only invalid pre-fix observations; run evidence folders remain preserved.
$history=Join-Path $runtimeRoot 'history'
if(Test-Path $history){Remove-Item $history -Recurse -Force}
Write-Host 'INVALID_HISTORY_PURGED=YES'

$launcherCode=@'
$ErrorActionPreference='Continue'
$runtimeRoot='C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
$python=Join-Path $runtimeRoot '.venv\Scripts\python.exe'
$browser='C:\Program Files\Yandex\YandexBrowser\Application\browser.exe'
$batch=Join-Path $runtimeRoot 'batch_monitor.py'
$collector=Join-Path $runtimeRoot 'card_collector.py'
$discovery=Join-Path $runtimeRoot 'target_discovery.py'
$config=Join-Path $runtimeRoot 'tires-195-55-r16.json'
$exitFile=Join-Path $runtimeRoot 'canonical-task-exit.json'
"STARTED $(Get-Date -Format o) USER=$([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) SESSION=$((Get-Process -Id $PID).SessionId)" | Set-Content (Join-Path $runtimeRoot 'canonical-task.started') -Encoding UTF8
& $python $batch --config $config --runtime-root $runtimeRoot --browser-path $browser --collector $collector --discovery $discovery --base-port 9231 --settle-seconds 12 --discovery-settle-seconds 10
$ec=$LASTEXITCODE;if($null -eq $ec){$ec=0}
[ordered]@{timestamp=(Get-Date).ToString('o');exit_code=$ec;user=[System.Security.Principal.WindowsIdentity]::GetCurrent().Name;session_id=(Get-Process -Id $PID).SessionId}|ConvertTo-Json|Set-Content $exitFile -Encoding UTF8
exit $ec
'@
[IO.File]::WriteAllText($launcher,$launcherCode,(New-Object System.Text.UnicodeEncoding($false,$true)))
foreach($p in @($taskExitFile,(Join-Path $runtimeRoot 'canonical-task.started'))){if(Test-Path $p){Remove-Item $p -Force}}
$before=if(Test-Path $latestFile){(Get-Item $latestFile).LastWriteTimeUtc}else{[datetime]::MinValue}
& schtasks.exe /Run /TN "\$taskName"
if($LASTEXITCODE -ne 0){throw "TASK_TRIGGER_FAIL=$LASTEXITCODE"}
Write-Host 'BATCH_TASK_TRIGGERED=YES'
$deadline=(Get-Date).AddMinutes(9)
while((Get-Date)-lt $deadline){$done=Test-Path $taskExitFile;$fresh=(Test-Path $latestFile)-and((Get-Item $latestFile).LastWriteTimeUtc -gt $before);if($done-and$fresh){break};Start-Sleep 5}
Write-Host '--- BATCH_SUMMARY ---'
$j=Get-Content $latestFile -Raw -Encoding UTF8|ConvertFrom-Json
Write-Host "STATUS=$($j.status) TOTAL=$($j.cards_total) PASS=$($j.cards_pass) FAIL=$($j.cards_fail)"
foreach($r in $j.results){$price=if($r.price){$r.price.buyer_price_rub}else{$null};$raw=if($r.discovery){$r.discovery.raw_product_links}else{$null};Write-Host ("CARD={0} MP={1} STATUS={2} SKU={3} PRICE={4} REGION={5} RAWLINKS={6} NAME={7}" -f $r.id,$r.marketplace,$r.status,$r.sku,$price,$r.region_ok,$raw,$r.name);if($r.discovery){Write-Host ("DISCOVERY={0}:{1}" -f $r.id,$r.discovery.status)}}
Write-Host '--- TASK_EXIT ---'
Get-Content $taskExitFile -Raw -Encoding UTF8
