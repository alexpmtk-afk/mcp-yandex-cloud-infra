$ErrorActionPreference = 'Stop'
Write-Host 'BRIDGE_V2_RUNNER_RECOVERY_BEGIN'
Get-Service -Name 'actions.runner.alexpmtk-afk-mcp-yandex-cloud-infra.Codex-Bridge-Work-MANAGER-MP2' | Select-Object Name, Status, StartType
sc.exe qfailure 'actions.runner.alexpmtk-afk-mcp-yandex-cloud-infra.Codex-Bridge-Work-MANAGER-MP2'
sc.exe qfailureflag 'actions.runner.alexpmtk-afk-mcp-yandex-cloud-infra.Codex-Bridge-Work-MANAGER-MP2'
Write-Host 'BRIDGE_V2_RUNNER_RECOVERY_END'
