$ErrorActionPreference = 'Stop'

Write-Host '=== BRIDGE_V2_RUNNER_BOOTSTRAP_BEGIN ==='

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this bootstrap once from an elevated PowerShell (Run as Administrator).'
}

$machine = $env:COMPUTERNAME
$expectedRunner = switch ($machine.ToUpperInvariant()) {
    'DESKTOP-7F6KPIL' { 'Codex-Bridge-Service-DESKTOP-7F6KPIL' }
    'MANAGER-MP2'     { 'Codex-Bridge-Work-MANAGER-MP2' }
    default           { $null }
}

$services = @(Get-CimInstance Win32_Service | Where-Object {
    $_.Name -like 'actions.runner.alexpmtk-afk-mcp-yandex-cloud-infra.*'
})

if ($services.Count -eq 0) {
    throw 'GitHub self-hosted runner service was not found. Runner installation/registration is required.'
}

$selected = $null
if ($expectedRunner) {
    $selected = $services | Where-Object {
        $_.Name -like "*$expectedRunner*" -or $_.DisplayName -like "*$expectedRunner*"
    } | Select-Object -First 1
}
if (-not $selected -and $services.Count -eq 1) {
    $selected = $services[0]
}
if (-not $selected) {
    Write-Host 'Candidate runner services:'
    $services | Select-Object Name, DisplayName, State, StartMode | Format-Table -AutoSize
    throw 'Could not choose one runner service unambiguously.'
}

$serviceName = $selected.Name
Write-Host "Machine=$machine"
Write-Host "RunnerService=$serviceName"

Set-Service -Name $serviceName -StartupType Automatic

# Ask Service Control Manager to restart the runner after crashes.
& sc.exe failure $serviceName reset= 86400 actions= restart/5000/restart/15000/restart/60000 | Out-Host
if ($LASTEXITCODE -ne 0) { throw "sc.exe failure failed with exit code $LASTEXITCODE" }
& sc.exe failureflag $serviceName 1 | Out-Host
if ($LASTEXITCODE -ne 0) { throw "sc.exe failureflag failed with exit code $LASTEXITCODE" }

$svc = Get-Service -Name $serviceName
if ($svc.Status -ne 'Running') {
    Start-Service -Name $serviceName
    $svc.WaitForStatus('Running', [TimeSpan]::FromSeconds(20))
}

$final = Get-CimInstance Win32_Service -Filter "Name='$serviceName'"
Write-Host "ServiceState=$($final.State)"
Write-Host "StartMode=$($final.StartMode)"
Write-Host 'Recovery=restart/restart/restart'
Write-Host 'BRIDGE_V2_RUNNER_BOOTSTRAP=PASS'
Write-Host '=== BRIDGE_V2_RUNNER_BOOTSTRAP_END ==='
