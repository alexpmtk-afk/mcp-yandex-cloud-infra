$ErrorActionPreference='Continue'
Write-Host '=== WORK_DC_DIAG_BEGIN ==='
$npm='C:\Program Files\nodejs\npm.cmd'
if(Test-Path $npm){
  try {
    $v=& $npm view '@wonderwhy-er/desktop-commander@latest' version 2>&1 | Out-String
    Write-Host ('LATEST_VERSION=' + $v.Trim())
  } catch { Write-Host ('NPM_VIEW_ERROR=' + $_.Exception.Message) }
  try {
    $b=& $npm view '@wonderwhy-er/desktop-commander@latest' bin --json 2>&1 | Out-String
    Write-Host ('BIN_META=' + $b.Trim())
  } catch {}
}
try {
  $procs=Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*desktop-commander*' -or $_.CommandLine -like '*npx*' }
  if($procs){ $procs | ForEach-Object { Write-Host ("PROC PID={0} NAME={1} CMD={2}" -f $_.ProcessId,$_.Name,$_.CommandLine) } } else { Write-Host 'DC_OR_NPX_PROCESS=NONE' }
} catch {}
$dev='C:\Users\user\.desktop-commander-device\device.json'
Write-Host ('DEVICE_FILE_EXISTS=' + (Test-Path -LiteralPath $dev))
$logDir='C:\Users\user\AppData\Local\npm-cache\_logs'
if(Test-Path -LiteralPath $logDir){
  $logs=Get-ChildItem -LiteralPath $logDir -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 3
  foreach($l in $logs){
    Write-Host ("NPM_LOG={0} LASTWRITE={1}" -f $l.Name,$l.LastWriteTime)
    try {
      Get-Content -LiteralPath $l.FullName -Tail 80 -ErrorAction SilentlyContinue | Where-Object { $_ -match '(?i)(error|err!|exit|code|desktop-commander|remote|verbose cli|silly packumentCache|warn)' } | Select-Object -Last 25 | ForEach-Object { Write-Host ('LOG> ' + $_) }
    } catch {}
  }
} else { Write-Host 'USER_NPM_LOG_DIR=UNAVAILABLE' }
Write-Host '=== WORK_DC_DIAG_END ==='
