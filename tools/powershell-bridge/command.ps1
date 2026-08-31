$ErrorActionPreference = 'Stop'
$svcRoot = Join-Path $HOME 'actions-runner\codex-bridge-service'
$diag = Join-Path $svcRoot '_diag'
Write-Host 'BRIDGE_SERVICE_FAILURE_DIAG_BEGIN'
Get-Service | Where-Object { $_.Name -like 'actions.runner.*' } | Select-Object Name,Status,StartType | Format-Table -AutoSize
$files = Get-ChildItem $diag -File | Sort-Object LastWriteTime -Descending
foreach ($f in $files | Select-Object -First 3) {
  Write-Host ("--- " + $f.Name + " ---")
  Get-Content $f.FullName -Tail 140
}
Write-Host 'BRIDGE_SERVICE_FAILURE_DIAG_END'
