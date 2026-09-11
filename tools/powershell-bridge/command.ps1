$ErrorActionPreference = 'Stop'
Write-Host 'BRIDGE_V2_WORK_HEALTH_OK_2'
Write-Host "Runner=$env:RUNNER_NAME"
Write-Host "Computer=$env:COMPUTERNAME"
whoami.exe
hostname.exe
Get-Date
Get-Service | Where-Object { $_.Name -like 'actions.runner*' } | Select-Object Name, Status, StartType
Get-Command git | Select-Object Name, Source
Get-Command yc | Select-Object Name, Source
Test-Path -LiteralPath 'C:\ProgramData'
Get-Item -LiteralPath 'C:\ProgramData' | Select-Object FullName, Attributes
