$ErrorActionPreference = 'Stop'
Write-Host 'HOME_LEGACY_INVENTORY_BEGIN'
Write-Host "Runner=$env:RUNNER_NAME"
Write-Host "Computer=$env:COMPUTERNAME"
Write-Host '--- RUNNER SERVICES ---'
Get-CimInstance Win32_Service | Where-Object { $_.Name -like 'actions.runner.*' } | Select-Object Name, State, StartMode, StartName, PathName
Write-Host '--- CHATGPT-PK ROOT ---'
if (Test-Path -LiteralPath 'C:\ProgramData\ChatGPT-PK') {
  Get-ChildItem -LiteralPath 'C:\ProgramData\ChatGPT-PK' -Force | Select-Object Name, FullName, Mode, Length, LastWriteTime
}
Write-Host '--- BRIDGE/CODEX SCHEDULED TASKS ---'
Get-ScheduledTask | Where-Object { $_.TaskName -like '*bridge*' -or $_.TaskName -like '*codex*' -or $_.TaskName -like '*DesktopCommander*' -or $_.TaskPath -like '*bridge*' } | Select-Object TaskName, TaskPath, State
Write-Host 'HOME_LEGACY_INVENTORY_END'
