$ErrorActionPreference = 'Stop'

Write-Host '=== USER_CONTEXT_PROBE_ADMIN_BEGIN ==='

$user = "$env:COMPUTERNAME\Win10_Game_OS"
$probeRoot = 'C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\interactive-probe-v1'
$probeScript = Join-Path $probeRoot 'probe.ps1'
$resultFile = Join-Path $probeRoot 'result.json'
$taskName = 'MarketplaceCardMonitor-UserContextProbe'

if (-not (Test-Path $probeScript)) {
    throw "Probe script not found: $probeScript"
}

if (Test-Path $resultFile) {
    Remove-Item $resultFile -Force
}

try {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
} catch {}

$action = New-ScheduledTaskAction `
    -Execute 'powershell.exe' `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$probeScript`""

$principal = New-ScheduledTaskPrincipal `
    -UserId $user `
    -LogonType Interactive `
    -RunLevel Limited

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 2) `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

try {
    Register-ScheduledTask `
        -TaskName $taskName `
        -Action $action `
        -Principal $principal `
        -Settings $settings `
        -Force | Out-Null

    Write-Host "TASK_REGISTERED=YES"
    Write-Host "TASK_USER=$user"

    Start-ScheduledTask -TaskName $taskName
    Write-Host 'TASK_STARTED=YES'

    $deadline = (Get-Date).AddSeconds(90)

    while ((Get-Date) -lt $deadline -and -not (Test-Path $resultFile)) {
        Start-Sleep -Seconds 2
    }

    if (-not (Test-Path $resultFile)) {
        Write-Host 'USER_CONTEXT_RESULT=TIMEOUT'
        $info = Get-ScheduledTaskInfo -TaskName $taskName
        Write-Host "TASK_LAST_RESULT=$($info.LastTaskResult)"
        exit 2
    }

    Write-Host '--- USER_CONTEXT_RESULT ---'
    Get-Content $resultFile -Raw

    $info = Get-ScheduledTaskInfo -TaskName $taskName
    Write-Host "TASK_LAST_RESULT=$($info.LastTaskResult)"
}
finally {
    Unregister-ScheduledTask `
        -TaskName $taskName `
        -Confirm:$false `
        -ErrorAction SilentlyContinue

    Write-Host 'TASK_REMOVED=YES'
}

Write-Host '=== USER_CONTEXT_PROBE_ADMIN_END ==='
