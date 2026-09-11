$ErrorActionPreference = 'Stop'
Write-Host 'BRIDGE_V2_HEALTH_OK'
Write-Host "Runner=$env:RUNNER_NAME"
Write-Host "Computer=$env:COMPUTERNAME"
whoami.exe
Get-Date
Get-Service | Where-Object { $_.Name -like 'actions.runner*' } | Select-Object Name, Status
