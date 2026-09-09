$ErrorActionPreference='Stop'
$taskName='ChatGPT-PowerShell-DesktopCommander'
$user='MANAGER-MP2\user'
$action=New-ScheduledTaskAction -Execute 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe' -Argument '-NoProfile -WindowStyle Hidden -Command "& ''C:\Program Files\nodejs\npm.cmd'' exec --yes --package=@wonderwhy-er/desktop-commander@0.2.48 -- desktop-commander remote"'
$trigger=New-ScheduledTaskTrigger -AtLogOn -User $user
$settings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal=New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$task=New-ScheduledTask -Action $action -Trigger $trigger -Settings $settings -Principal $principal
Register-ScheduledTask -TaskName $taskName -InputObject $task -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
Start-Sleep -Seconds 5
$t=Get-ScheduledTask -TaskName $taskName
$i=Get-ScheduledTaskInfo -TaskName $taskName
Write-Host ('TASK_EXISTS=' + [bool]$t)
Write-Host ('TASK_STATE=' + $t.State)
Write-Host ('TASK_USER=' + $t.Principal.UserId)
Write-Host ('LAST_RESULT=' + $i.LastTaskResult)
Write-Host ('LAST_RUN=' + $i.LastRunTime)
