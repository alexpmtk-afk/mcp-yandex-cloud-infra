$ErrorActionPreference = 'Stop'
$runner = Join-Path $HOME 'actions-runner\codex-bridge'
Set-Location $runner
Write-Host 'BRIDGE_SERVICE_INSTALL_BEGIN'
& .\svc.cmd install
if ($LASTEXITCODE -ne 0) { throw "svc install failed: $LASTEXITCODE" }
& .\svc.cmd start
if ($LASTEXITCODE -ne 0) { throw "svc start failed: $LASTEXITCODE" }
Write-Host 'BRIDGE_SERVICE_INSTALL_OK'
Get-Service | Where-Object { $_.Name -like 'actions.runner.*' } | Select-Object Name,Status,StartType | Format-Table -AutoSize
