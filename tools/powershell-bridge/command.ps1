$ErrorActionPreference = 'Stop'

$runtimeRoot = 'C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
$taskName = 'MarketplaceCardMonitor-UserNode-Canonical'
$startedFile = Join-Path $runtimeRoot 'canonical-task.started'
$taskExitFile = Join-Path $runtimeRoot 'canonical-task-exit.json'
$resultFile = Join-Path $runtimeRoot 'plain-cdp-canonical.json'
$screenshotFile = Join-Path $runtimeRoot 'plain-cdp-canonical.png'

function Run-Gate([int]$n) {
    foreach ($path in @($startedFile, $taskExitFile, $resultFile, $screenshotFile)) {
        if (Test-Path $path) { Remove-Item $path -Force }
    }

    & schtasks.exe /Run /TN "\$taskName"
    if ($LASTEXITCODE -ne 0) { throw "Gate $n schtasks /Run failed: $LASTEXITCODE" }

    $deadline = (Get-Date).AddSeconds(120)
    while ((Get-Date) -lt $deadline -and -not (Test-Path $taskExitFile)) {
        Start-Sleep -Seconds 2
    }

    if (-not (Test-Path $taskExitFile)) { throw "Gate $n task exit not found" }
    if (-not (Test-Path $resultFile)) { throw "Gate $n result not found" }

    $exit = Get-Content $taskExitFile -Raw | ConvertFrom-Json
    $result = Get-Content $resultFile -Raw -Encoding UTF8 | ConvertFrom-Json

    $archiveResult = Join-Path $runtimeRoot ("plain-cdp-canonical-run{0}.json" -f $n)
    $archiveExit = Join-Path $runtimeRoot ("canonical-task-exit-run{0}.json" -f $n)
    $archiveScreenshot = Join-Path $runtimeRoot ("plain-cdp-canonical-run{0}.png" -f $n)
    Copy-Item $resultFile $archiveResult -Force
    Copy-Item $taskExitFile $archiveExit -Force
    if (Test-Path $screenshotFile) { Copy-Item $screenshotFile $archiveScreenshot -Force }

    Write-Host "=== GATE_RUN_$n ==="
    Write-Host "EXIT_CODE=$($exit.exit_code)"
    Write-Host "USER=$($exit.user)"
    Write-Host "SESSION=$($exit.session_id)"
    Write-Host "STATUS=$($result.status)"
    Write-Host "SKU=$($result.actual_sku)"
    Write-Host "CDP_READY=$($result.cdp_ready)"
    Write-Host "CDP_ATTACHED=$($result.cdp_attached)"
    Write-Host "BLOCKED=$($result.blocked)"
    Write-Host "REGION_OK=$($result.region_ok)"
    Write-Host "PRICES=$([string]::Join(',', @($result.price_candidates_rub | Select-Object -First 5)))"
    Write-Host "SCREENSHOT=$(Test-Path $archiveScreenshot)"

    if ([int]$exit.exit_code -ne 0 -or $result.status -ne 'PLAIN_CDP_DOM_PASS' -or $result.actual_sku -ne '1420875699') {
        throw "Gate $n failed: exit=$($exit.exit_code), status=$($result.status), sku=$($result.actual_sku)"
    }

    Start-Sleep -Seconds 3
}

Run-Gate 2
Run-Gate 3
Write-Host 'OZON_GATE_3X_PASS=YES'
