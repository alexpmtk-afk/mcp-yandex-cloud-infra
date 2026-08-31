$ErrorActionPreference = 'Stop'
Write-Host 'BRIDGE_SERVICE_STATUS_BEGIN'
Get-Service | Where-Object { $_.Name -like 'actions.runner.*' } | Select-Object Name,Status,StartType | Format-Table -AutoSize
$svcRoot = Join-Path $HOME 'actions-runner\codex-bridge-service'
Write-Host '--- service runner diag files ---'
if (Test-Path (Join-Path $svcRoot '_diag')) {
  Get-ChildItem (Join-Path $svcRoot '_diag') -File | Sort-Object LastWriteTime -Descending | Select-Object -First 5 Name,LastWriteTime,Length | Format-Table -AutoSize
  $latest = Get-ChildItem (Join-Path $svcRoot '_diag') -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if ($latest) {
    Write-Host ("--- latest diag tail: " + $latest.Name + " ---")
    Get-Content $latest.FullName -Tail 80
  }
} else {
  Write-Host 'NO_SERVICE_DIAG_DIR'
}
Write-Host 'BRIDGE_SERVICE_STATUS_END'
