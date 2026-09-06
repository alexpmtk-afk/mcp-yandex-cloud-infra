$ErrorActionPreference='Stop'
Write-Host '=== INTERACTIVE_OZON_CDP_DEBUG_BEGIN ==='
$root='C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\interactive-gate'
$user=(Get-CimInstance Win32_ComputerSystem).UserName
if(-not $user){throw 'NO_INTERACTIVE_USER'}
$browserCandidates=@(
 'C:\Users\Win10_Game_OS\AppData\Local\Yandex\YandexBrowser\Application\browser.exe',
 'C:\Program Files\Yandex\YandexBrowser\Application\browser.exe',
 'C:\Program Files (x86)\Yandex\YandexBrowser\Application\browser.exe',
 'C:\Program Files\Google\Chrome\Application\chrome.exe'
)
$browser=$browserCandidates|Where-Object{Test-Path $_}|Select-Object -First 1
if(-not $browser){throw 'BROWSER_NOT_FOUND'}
$runner=Join-Path $root 'interactive-ozon-test.ps1'
$result=Join-Path $root 'result.json'
$trace=Join-Path $root 'trace.txt'
$profile=Join-Path $root 'profile'
$ozon='https://www.ozon.ru/product/nippel-dlya-beskamernyh-shin-ventil-sosok-avtomobilnyy-rezinovyy-1420875699/'
$script=@"
`$ErrorActionPreference='Continue'
`$browser='$($browser.Replace("'","''"))'
`$profile='$($profile.Replace("'","''"))'
`$result='$($result.Replace("'","''"))'
`$trace='$($trace.Replace("'","''"))'
`$url='$ozon'
Remove-Item `$result,`$trace -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path `$profile|Out-Null
Start-Process -FilePath `$browser -ArgumentList @('--remote-debugging-port=9223','--remote-allow-origins=*','--no-first-run','--no-default-browser-check',"--user-data-dir=`$profile",'--lang=ru-RU','--new-window',`$url)|Out-Null
`$deadline=(Get-Date).AddSeconds(45);`$targets=`$null
while((Get-Date)-lt `$deadline){try{`$targets=Invoke-RestMethod 'http://127.0.0.1:9223/json' -TimeoutSec 2;if(`$targets){break}}catch{};Start-Sleep -Milliseconds 500}
if(-not `$targets){[IO.File]::WriteAllText(`$result,'{"status":"NO_CDP"}');exit 0}
`$t=`$targets|Where-Object{`$_.type -eq 'page' -and `$_.url -like 'https://www.ozon.ru/*'}|Select-Object -First 1
if(-not `$t){`$t=`$targets|Where-Object{`$_.type -eq 'page'}|Select-Object -First 1}
if(-not `$t){[IO.File]::WriteAllText(`$result,'{"status":"NO_PAGE"}');exit 0}
[IO.File]::WriteAllText(`$trace,("TARGET_URL="+`$t.url+"`r`nWS="+`$t.webSocketDebuggerUrl+"`r`n"),(New-Object Text.UTF8Encoding(`$false)))
Add-Type -AssemblyName System.Net.WebSockets.Client
`$ws=New-Object System.Net.WebSockets.ClientWebSocket
`$cts=New-Object Threading.CancellationTokenSource
`$cts.CancelAfter(20000)
`$ws.ConnectAsync([Uri]`$t.webSocketDebuggerUrl,`$cts.Token).Wait()
function SendMsg([string]`$json){`$bytes=[Text.Encoding]::UTF8.GetBytes(`$json);`$seg=New-Object ArraySegment[byte] -ArgumentList (,`$bytes);`$ws.SendAsync(`$seg,[Net.WebSockets.WebSocketMessageType]::Text,`$true,`$cts.Token).Wait()}
function ReceiveMsg(){
  `$ms=New-Object IO.MemoryStream
  do{`$buf=New-Object byte[] 65536;`$seg=New-Object ArraySegment[byte] -ArgumentList (,`$buf);`$r=`$ws.ReceiveAsync(`$seg,`$cts.Token).Result;if(`$r.Count -gt 0){`$ms.Write(`$buf,0,`$r.Count)}}while(-not `$r.EndOfMessage)
  `$txt=[Text.Encoding]::UTF8.GetString(`$ms.ToArray());`$ms.Dispose();return `$txt
}
Start-Sleep -Seconds 6
`$expr="JSON.stringify({title:document.title,url:location.href,body:document.body?document.body.innerText.slice(0,15000):''})"
`$cmd=@{id=101;method='Runtime.evaluate';params=@{expression=`$expr;returnByValue=`$true}}|ConvertTo-Json -Compress -Depth 6
SendMsg `$cmd
`$resp=`$null
for(`$i=0;`$i -lt 50;`$i++){
  try{`$txt=ReceiveMsg()}catch{break}
  if(`$i -lt 8){[IO.File]::AppendAllText(`$trace,("MSG"+`$i+"="+`$txt+"`r`n"),(New-Object Text.UTF8Encoding(`$false)))}
  try{`$o=`$txt|ConvertFrom-Json;if(`$o.id -eq 101){`$resp=`$o;break}}catch{}
}
if(`$resp -and `$resp.result.result.value){`$payload=[string]`$resp.result.result.value}else{`$payload='{"status":"NO_EVAL"}'}
[IO.File]::WriteAllText(`$result,`$payload,(New-Object Text.UTF8Encoding(`$false)))
try{SendMsg '{"id":102,"method":"Browser.close","params":{}}'}catch{}
try{`$ws.Dispose()}catch{}
"@
[IO.File]::WriteAllText($runner,$script,(New-Object Text.UTF8Encoding($false)))
$taskName='MarketplaceMonitor-Interactive-Ozon-Gate'
$action=New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$runner`""
$principal=New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings=New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 2)
Register-ScheduledTask -TaskName $taskName -Action $action -Principal $principal -Settings $settings -Force|Out-Null
Remove-Item $result,$trace -Force -ErrorAction SilentlyContinue
Start-ScheduledTask -TaskName $taskName
$deadline=(Get-Date).AddSeconds(75)
while((Get-Date)-lt $deadline -and -not(Test-Path $result)){Start-Sleep -Seconds 1}
if(Test-Path $result){$raw=Get-Content $result -Raw -Encoding UTF8;Write-Host "RESULT_LEN=$($raw.Length)";try{$o=$raw|ConvertFrom-Json;if($o.status){Write-Host "STATUS=$($o.status)"};if($o.title){Write-Host "TITLE_B64=$([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes([string]$o.title)))"};if($o.url){Write-Host "URL=$($o.url)"};if($o.body){Write-Host "HAS_SKU=$([bool]($o.body -match '1420875699'))";Write-Host "BODY_B64=$([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes(([string]$o.body).Substring(0,[Math]::Min(1800,([string]$o.body).Length)))))"}}catch{Write-Host "PARSE_ERROR=$($_.Exception.Message)"}}else{Write-Host 'RESULT_MISSING=YES'}
if(Test-Path $trace){$tr=Get-Content $trace -Raw -Encoding UTF8;if($tr.Length -gt 5000){$tr=$tr.Substring(0,5000)};Write-Host "TRACE_B64=$([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($tr)))"}
Write-Host '=== INTERACTIVE_OZON_CDP_DEBUG_END ==='
