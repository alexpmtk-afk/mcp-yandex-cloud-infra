$ErrorActionPreference='Continue'
Write-Host '=== INTERACTIVE_OZON_STATE_BEGIN ==='
$root='C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\interactive-gate'
$task='MarketplaceMonitor-Interactive-Ozon-Gate'
try{$t=Get-ScheduledTask -TaskName $task;$i=Get-ScheduledTaskInfo -TaskName $task;Write-Host "TASK_STATE=$($t.State)";Write-Host "TASK_LAST_RESULT=$($i.LastTaskResult)";Write-Host "TASK_LAST_RUN=$($i.LastRunTime)"}catch{Write-Host "TASK_ERROR=$($_.Exception.Message)"}
Write-Host '=== PROCESSES ==='
Get-CimInstance Win32_Process | Where-Object {$_.Name -match 'browser.exe|powershell.exe'} | ForEach-Object {
  $owner='';try{$o=Invoke-CimMethod -InputObject $_ -MethodName GetOwner;$owner="$($o.Domain)\$($o.User)"}catch{}
  Write-Host ("PROC PID={0} NAME={1} SESSION={2} OWNER={3} CMD={4}" -f $_.ProcessId,$_.Name,$_.SessionId,$owner,$_.CommandLine)
}
foreach($f in @('result.json','trace.txt','interactive-ozon-test.ps1')){$p=Join-Path $root $f;if(Test-Path $p){$fi=Get-Item $p;Write-Host "FILE=$f SIZE=$($fi.Length) MODIFIED=$($fi.LastWriteTime.ToString('o'))";if($f -ne 'interactive-ozon-test.ps1'){$raw=Get-Content $p -Raw -Encoding UTF8;if($raw.Length -gt 6000){$raw=$raw.Substring(0,6000)};Write-Host ("FILE_B64_$($f.Replace('.','_'))="+[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($raw)))}}else{Write-Host "FILE=$f MISSING"}}
try{$targets=Invoke-RestMethod 'http://127.0.0.1:9223/json' -TimeoutSec 3;foreach($x in $targets){Write-Host "CDP_TARGET_TYPE=$($x.type) URL=$($x.url) TITLE_B64=$([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes([string]$x.title))) WS=$($x.webSocketDebuggerUrl)"}}catch{Write-Host "CDP_HTTP_ERROR=$($_.Exception.Message)"}
Write-Host '=== INTERACTIVE_OZON_STATE_END ==='
