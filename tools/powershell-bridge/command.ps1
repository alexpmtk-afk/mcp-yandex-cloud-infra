$ErrorActionPreference = 'Stop'
Write-Host 'BRIDGE_V2_WORK_READY_CANDIDATE'
Write-Host "Runner=$env:RUNNER_NAME"
Write-Host "Computer=$env:COMPUTERNAME"
whoami.exe
Get-Service -Name 'actions.runner.alexpmtk-afk-mcp-yandex-cloud-infra.Codex-Bridge-Work-MANAGER-MP2' | Select-Object Name, Status, StartType
Test-Path -LiteralPath 'C:\ProgramData\ChatGPT-PK\bridge-v2-sandbox\smoke.txt'
Get-Content -LiteralPath 'C:\ProgramData\ChatGPT-PK\bridge-v2-sandbox\smoke.txt'
Get-Date
