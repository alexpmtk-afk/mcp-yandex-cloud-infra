$ErrorActionPreference = 'Continue'

Write-Host '=== ADMIN_RUNNER_RECOVERY_BEGIN ==='

Write-Host "COMPUTER=$env:COMPUTERNAME"
Write-Host "IDENTITY=$([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)"

$svc = Get-Service |
    Where-Object {
        $_.Name -like 'actions.runner.*Codex-Bridge-Admin-*'
    } |
    Select-Object -First 1

if (-not $svc) {
    Write-Host 'ADMIN_SERVICE_FOUND=NO'
    exit 3
}

Write-Host 'ADMIN_SERVICE_FOUND=YES'
Write-Host "ADMIN_SERVICE_NAME=$($svc.Name)"
Write-Host "ADMIN_SERVICE_STATUS_BEFORE=$($svc.Status)"
Write-Host "ADMIN_SERVICE_STARTTYPE=$($svc.StartType)"

Write-Host '--- ADMIN_RUNNER_PROCESSES_BEFORE ---'

Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
        $_.CommandLine -and
        $_.CommandLine -match 'powershell-admin-runner'
    } |
    ForEach-Object {
        Write-Host "PID=$($_.ProcessId)|SESSION=$($_.SessionId)|NAME=$($_.Name)|CMD=$($_.CommandLine)"
    }

try {
    if ($svc.Status -eq 'Running') {
        Restart-Service `
            -Name $svc.Name `
            -Force `
            -ErrorAction Stop

        Write-Host 'ADMIN_SERVICE_RESTART_REQUESTED=YES'
    }
    else {
        Start-Service `
            -Name $svc.Name `
            -ErrorAction Stop

        Write-Host 'ADMIN_SERVICE_START_REQUESTED=YES'
    }
}
catch {
    Write-Host "ADMIN_SERVICE_CONTROL_ERROR=$($_.Exception.Message)"
    exit 4
}

Start-Sleep -Seconds 8

$svc = Get-Service -Name $svc.Name

Write-Host "ADMIN_SERVICE_STATUS_AFTER=$($svc.Status)"

Write-Host '--- ADMIN_RUNNER_PROCESSES_AFTER ---'

Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
        $_.CommandLine -and
        $_.CommandLine -match 'powershell-admin-runner'
    } |
    ForEach-Object {
        Write-Host "PID=$($_.ProcessId)|SESSION=$($_.SessionId)|NAME=$($_.Name)|CMD=$($_.CommandLine)"
    }

if ($svc.Status -ne 'Running') {
    exit 5
}

Write-Host 'ADMIN_RUNNER_RECOVERY_OK'
Write-Host '=== ADMIN_RUNNER_RECOVERY_END ==='
