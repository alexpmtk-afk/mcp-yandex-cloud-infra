$ErrorActionPreference = 'Stop'
$runner = Join-Path $HOME 'actions-runner\codex-bridge'
Set-Location $runner
Write-Host 'BRIDGE_SERVICE_DIAG_BEGIN'
Write-Host '--- runner root files ---'
Get-ChildItem -Name
Write-Host '--- config help (service-related lines) ---'
& .\config.cmd --help 2>&1 | Select-String -Pattern 'service|runasservice|unattended|remove' -CaseSensitive:$false
Write-Host 'BRIDGE_SERVICE_DIAG_END'
