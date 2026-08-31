$old = Get-Process -Id 30208 -ErrorAction SilentlyContinue
if ($old) { Stop-Process -Id 30208 -Force; Write-Host 'OLD_RUNNER_STOPPED=30208' } else { Write-Host 'OLD_RUNNER_ALREADY_GONE' }
Start-Sleep -Seconds 2
Get-Service | Where-Object { $_.Name -like 'actions.runner.*Codex-Bridge-Service*' } | Select-Object Name,Status,StartType
Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'Runner.Listener.exe' } | ForEach-Object { Write-Host ("LISTENER PID="+$_.ProcessId+" PATH="+$_.ExecutablePath+" CMD="+$_.CommandLine) }
