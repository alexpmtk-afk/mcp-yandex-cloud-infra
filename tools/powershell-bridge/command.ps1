whoami
"USERPROFILE=$env:USERPROFILE"
Get-Command gh,git,node,yc -ErrorAction SilentlyContinue | Select-Object Name,Source
Get-Service | Where-Object { $_.Name -like 'actions.runner.*Codex-Bridge-Service*' } | Select-Object Name,Status,StartType
Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('Runner.Listener.exe','Runner.Worker.exe') } | Select-Object ProcessId,Name,ExecutablePath
