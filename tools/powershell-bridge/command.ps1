$ErrorActionPreference = 'Stop'
Write-Host '=== MCM_FROZEN_CDP_RUN_BEGIN ==='
$taskName = '\MarketplaceCardMonitor-UserNode-Canonical'
$runtimeRoot = 'C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
& schtasks.exe /Run /TN $taskName
if ($LASTEXITCODE -ne 0) { throw "schtasks /Run failed: $LASTEXITCODE" }
Write-Host 'TASK_RUN_REQUESTED=YES'
Start-Sleep -Seconds 45
foreach ($p in @(
  (Join-Path $runtimeRoot 'plain-cdp-canonical.json'),
  (Join-Path $runtimeRoot 'canonical-task-exit.json'),
  (Join-Path $runtimeRoot 'canonical-task.started')
)) {
  if (Test-Path $p) {
    Write-Host "--- FILE=$p ---"
    Get-Content $p -Raw
  } else {
    Write-Host "MISSING_FILE=$p"
  }
}
Write-Host '=== MCM_FROZEN_CDP_RUN_END ==='
