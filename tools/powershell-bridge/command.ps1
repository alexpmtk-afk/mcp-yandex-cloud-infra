$ErrorActionPreference='Continue'
Write-Host '=== WORK_AUTOSTART_AUDIT_BEGIN ==='
try {
  $t=Get-ScheduledTask -TaskName 'ChatGPT-PowerShell-DesktopCommander' -ErrorAction SilentlyContinue
  if($t){
    Write-Host ('TASK_EXISTS=True')
    Write-Host ('TASK_STATE=' + $t.State)
    Write-Host ('TASK_USER=' + $t.Principal.UserId)
    $i=Get-ScheduledTaskInfo -TaskName 'ChatGPT-PowerShell-DesktopCommander' -ErrorAction SilentlyContinue
    if($i){ Write-Host ('LAST_RESULT=' + $i.LastTaskResult); Write-Host ('LAST_RUN=' + $i.LastRunTime) }
    $t.Actions | ForEach-Object { Write-Host ('ACTION_EXEC=' + $_.Execute); Write-Host ('ACTION_ARGS=' + $_.Arguments) }
  } else { Write-Host 'TASK_EXISTS=False' }
} catch { Write-Host ('TASK_CHECK_ERROR=' + $_.Exception.Message) }
try {
  $procs=Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*desktop-commander*remote*' -or $_.CommandLine -like '*desktop-commander@0.2.48*' }
  if($procs){ $procs | ForEach-Object { Write-Host ("PROC PID={0} PPID={1} NAME={2} CMD={3}" -f $_.ProcessId,$_.ParentProcessId,$_.Name,$_.CommandLine) } } else { Write-Host 'REMOTE_PROCESS=NONE' }
} catch { Write-Host ('PROC_CHECK_ERROR=' + $_.Exception.Message) }
Write-Host '=== WORK_AUTOSTART_AUDIT_END ==='
