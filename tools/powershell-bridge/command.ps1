$ErrorActionPreference = 'Stop'
$diag="$HOME\actions-runner\codex-bridge-service\_diag"
$latest=Get-ChildItem $diag -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1
Write-Host $latest.Name
Get-Content $latest.FullName -Tail 100
