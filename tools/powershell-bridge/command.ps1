$ErrorActionPreference = 'Stop'
Write-Host 'PRIVATE_HOME_RUNNER_DIAG'
Get-CimInstance Win32_Service | Where-Object { $_.Name -like 'actions.runner.alexpmtk-afk-gpt-powershell-bridge*' } | Select-Object Name, State, StartMode, StartName, ProcessId, PathName
Write-Host '--- RUNNER DIAG FILES ---'
$diag = 'C:\ProgramData\ChatGPT-PK\powershell-private-home-runner\_diag'
if (Test-Path -LiteralPath $diag) {
  Get-ChildItem -LiteralPath $diag -File | Sort-Object LastWriteTime -Descending | Select-Object -First 5 Name, Length, LastWriteTime
  $latest = Get-ChildItem -LiteralPath $diag -File -Filter 'Runner_*.log' | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if ($latest) { Write-Host '--- LATEST RUNNER LOG TAIL ---'; Get-Content -LiteralPath $latest.FullName -Tail 80 }
}
