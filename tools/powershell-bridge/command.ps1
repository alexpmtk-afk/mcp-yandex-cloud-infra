$ErrorActionPreference = 'Stop'
Write-Host 'BRIDGE_V2_WORK_SAFE_E2E'
Write-Host "Runner=$env:RUNNER_NAME"
Write-Host "Computer=$env:COMPUTERNAME"
whoami.exe
hostname.exe
Get-Date
Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, BuildNumber
Get-Service | Where-Object { $_.Name -like 'actions.runner*' } | Select-Object Name, Status, StartType
Get-Command git | Select-Object Name, Source
$yc = Get-Command yc -ErrorAction SilentlyContinue
Write-Host "YC_PRESENT=$([bool]$yc)"
Test-Path -LiteralPath 'C:\ProgramData\ChatGPT-PK'
Get-Item -LiteralPath 'C:\ProgramData\ChatGPT-PK' | Select-Object FullName, Attributes
