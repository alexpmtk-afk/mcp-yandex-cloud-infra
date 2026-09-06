$ErrorActionPreference='Stop'
Write-Host '=== INTERACTIVE_OZON_GATE_SETUP_BEGIN ==='
$root='C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\interactive-gate'
New-Item -ItemType Directory -Force -Path $root | Out-Null
$user=(Get-CimInstance Win32_ComputerSystem).UserName
Write-Host "INTERACTIVE_USER=$user"
if(-not $user){throw 'NO_INTERACTIVE_USER'}
$browserCandidates=@(
 'C:\Users\Win10_Game_OS\AppData\Local\Yandex\YandexBrowser\Application\browser.exe',
 'C:\Program Files\Yandex\YandexBrowser\Application\browser.exe',
 'C:\Program Files (x86)\Yandex\YandexBrowser\Application\browser.exe',
 'C:\Program Files\Google\Chrome\Application\chrome.exe',
 'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe'
)
$browser=$browserCandidates|Where-Object{Test-Path $_}|Select-Object -First 1
if(-not $browser){throw 'BROWSER_NOT_FOUND'}
Write-Host "BROWSER=$browser"
$runner=Join-Path $root 'interactive-ozon-test.ps1'
$result=Join-Path $root 'result.json'
$profile=Join-Path $root 'profile'
$ozon='https://www.ozon.ru/product/nippel-dlya-beskamernyh-shin-ventil-sosok-avtomobilnyy-rezinovyy-1420875699/'
$script=@"
`$ErrorActionPreference='Continue'
`$browser='$($browser.Replace("'","''"))'
`$profile='$($profile.Replace("'","''"))'
`$result='$($result.Replace("'","''"))'
`$url='$ozon'
New-Item -ItemType Directory -Force -Path `$profile|Out-Null
Remove-Item `$result -Force -ErrorAction SilentlyContinue
`$args=@('--remote-debugging-port=9223','--remote-allow-origins=*','--no-first-run','--no-default-browser-check',"--user-data-dir=`$profile",'--lang=ru-RU','--new-window',`$url)
Start-Process -FilePath `$browser -ArgumentList `$args|Out-Null
`$deadline=(Get-Date).AddSeconds(45)
`$targets=`$null
while((Get-Date)-lt `$deadline){
  try{`$targets=Invoke-RestMethod -Uri 'http://127.0.0.1:9223/json' -TimeoutSec 2;if(`$targets){break}}catch{}
  Start-Sleep -Milliseconds 500
}
if(-not `$targets){[IO.File]::WriteAllText(`$result,'{"status":"NO_CDP"}',(New-Object Text.UTF8Encoding(`$false)));exit 0}
`$t=`$targets|Where-Object{`$_.type -eq 'page' -and `$_.url -like 'https://www.ozon.ru/*'}|Select-Object -First 1
if(-not `$t){`$t=`$targets|Where-Object{`$_.type -eq 'page'}|Select-Object -First 1}
if(-not `$t){[IO.File]::WriteAllText(`$result,'{"status":"NO_PAGE"}',(New-Object Text.UTF8Encoding(`$false)));exit 0}
Add-Type -AssemblyName System.Net.WebSockets.Client
`$ws=New-Object System.Net.WebSockets.ClientWebSocket
`$cts=New-Object Threading.CancellationTokenSource
`$ws.ConnectAsync([Uri]`$t.webSocketDebuggerUrl,`$cts.Token).Wait()
function Send-Cdp([int]`$id,[string]`$method,[string]`$params='{}'){
  `$json='{"id":'+`$id+',"method":"'+`$method+'","params":'+`$params+'}'
  `$bytes=[Text.Encoding]::UTF8.GetBytes(`$json)
  `$seg=New-Object ArraySegment[byte] -ArgumentList (,`$bytes)
  `$ws.SendAsync(`$seg,[Net.WebSockets.WebSocketMessageType]::Text,`$true,`$cts.Token).Wait()
}
function Recv-Cdp([int]`$wanted){
  for(`$n=0;`$n -lt 30;`$n++){
    `$buf=New-Object byte[] 1048576
    `$seg=New-Object ArraySegment[byte] -ArgumentList (,`$buf)
    `$r=`$ws.ReceiveAsync(`$seg,`$cts.Token).Result
    `$txt=[Text.Encoding]::UTF8.GetString(`$buf,0,`$r.Count)
    try{`$o=`$txt|ConvertFrom-Json;if(`$o.id -eq `$wanted){return `$o}}catch{}
  }
  return `$null
}
Start-Sleep -Seconds 8
`$expr="JSON.stringify({title:document.title,url:location.href,body:document.body?document.body.innerText.slice(0,12000):'',html:document.documentElement?document.documentElement.outerHTML.slice(0,12000):''})"
`$p=@{expression=`$expr;returnByValue=`$true}|ConvertTo-Json -Compress
Send-Cdp 1 'Runtime.evaluate' `$p
`$resp=Recv-Cdp 1
if(`$resp -and `$resp.result.result.value){`$payload=`$resp.result.result.value}else{`$payload='{"status":"NO_EVAL"}'}
[IO.File]::WriteAllText(`$result,`$payload,(New-Object Text.UTF8Encoding(`$false)))
Send-Cdp 2 'Browser.close' '{}'
try{`$ws.Dispose()}catch{}
"@
[IO.File]::WriteAllText($runner,$script,(New-Object Text.UTF8Encoding($false)))
$taskName='MarketplaceMonitor-Interactive-Ozon-Gate'
$action=New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$runner`""
$principal=New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings=New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 3)
Register-ScheduledTask -TaskName $taskName -Action $action -Principal $principal -Settings $settings -Force | Out-Null
Remove-Item $result -Force -ErrorAction SilentlyContinue
Start-ScheduledTask -TaskName $taskName
Write-Host 'TASK_STARTED=YES'
$deadline=(Get-Date).AddSeconds(90)
while((Get-Date)-lt $deadline -and -not (Test-Path $result)){Start-Sleep -Seconds 1}
if(Test-Path $result){
  Write-Host 'RESULT_FOUND=YES'
  $raw=Get-Content $result -Raw -Encoding UTF8
  Write-Host "RESULT_LEN=$($raw.Length)"
  try{
    $o=$raw|ConvertFrom-Json
    if($o.status){Write-Host "STATUS=$($o.status)"}
    if($o.title){Write-Host "TITLE_BASE64=$([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes([string]$o.title)))"}
    if($o.url){Write-Host "URL=$($o.url)"}
    if($o.body){
      Write-Host "HAS_SKU=$([bool]($o.body -match '1420875699'))"
      Write-Host "HAS_PRICE_TOKEN=$([bool]($o.body -match '[0-9][0-9 ]{1,8}'))"
      Write-Host "HAS_BLOCK_ASCII=$([bool]($o.body -match 'Antibot|incidentId|fab_chlg|__rr=1'))"
      $preview=($o.body -replace '[\r\n]+',' ');if($preview.Length -gt 1200){$preview=$preview.Substring(0,1200)};Write-Host "BODY_PREVIEW_BASE64=$([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($preview)))"
    }
  }catch{Write-Host "PARSE_ERROR=$($_.Exception.Message)"}
}else{
  Write-Host 'RESULT_FOUND=NO'
  $ti=Get-ScheduledTaskInfo -TaskName $taskName
  Write-Host "LAST_TASK_RESULT=$($ti.LastTaskResult)"
}
Write-Host '=== INTERACTIVE_OZON_GATE_SETUP_END ==='
