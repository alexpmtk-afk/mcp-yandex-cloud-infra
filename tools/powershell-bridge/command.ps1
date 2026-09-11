$ErrorActionPreference = 'Stop'
Write-Host 'BRIDGE_V2_WORK_RECOVERY_VERIFY'
Write-Host "Runner=$env:RUNNER_NAME"
Write-Host "Computer=$env:COMPUTERNAME"
whoami.exe
Get-Service -Name 'actions.runner.alexpmtk-afk-mcp-yandex-cloud-infra.Codex-Bridge-Work-MANAGER-MP2' | Select-Object Name, Status, StartType
sc.exe qfailure "actions.runner.alexpmtk-afk-mcp-yandex-cloud-infra.Codex-Bridge-Work-MANAGER-MP2"
sc.exe qfailureflag "actions.runner.alexpmtk-afk-mcp-yandex-cloud-infra.Codex-Bridge-Work-MANAGER-MP2"
Get-Date
