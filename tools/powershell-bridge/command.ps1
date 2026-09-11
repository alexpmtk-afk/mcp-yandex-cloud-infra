$ErrorActionPreference = 'Stop'
$script = @'
$ErrorActionPreference = 'Stop'

Write-Host '=== PRIVATE_HOME_BRIDGE_RUNNER_BOOTSTRAP_BEGIN ==='

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this script from PowerShell as Administrator.'
}

if ($env:COMPUTERNAME -ne 'DESKTOP-7F6KPIL') {
    throw "Wrong machine: $env:COMPUTERNAME"
}

$root = 'C:\ProgramData\ChatGPT-PK\powershell-private-home-runner'
$zip = Join-Path $root 'actions-runner-win-x64-2.337.0.zip'
$url = 'https://github.com/actions/runner/releases/download/v2.337.0/actions-runner-win-x64-2.337.0.zip'
$expectedHash = '1150692AFA94E71F872017E254EA55B6EECE1EECE3FE7E3A6D4C93D0A1B85CFC'
$repoUrl = 'https://github.com/alexpmtk-afk/gpt-powershell-bridge'
$runnerName = 'GPT-PowerShell-Home-DESKTOP-7F6KPIL'
$runnerLabel = 'gpt-powershell-home'

New-Item -ItemType Directory -Path $root -Force | Out-Null

if (Test-Path -LiteralPath (Join-Path $root '.runner')) {
    throw 'A runner is already configured in the private HOME runner directory. Stop to avoid overwriting it.'
}

$configCmd = Join-Path $root 'config.cmd'
if (-not (Test-Path -LiteralPath $configCmd)) {
    Write-Host 'Downloading official GitHub Actions runner 2.337.0...'
    Invoke-WebRequest -Uri $url -OutFile $zip
    $actualHash = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToUpperInvariant()
    if ($actualHash -ne $expectedHash) {
        throw "Runner package SHA256 mismatch. Actual=$actualHash"
    }
    Write-Host 'RUNNER_PACKAGE_HASH=PASS'
    Expand-Archive -LiteralPath $zip -DestinationPath $root -Force
} else {
    Write-Host 'Runner files already present; reusing installation directory.'
}

Write-Host ''
Write-Host 'Copy the ENTIRE Configure command from GitHub now, then press Enter here.'
Read-Host 'Press Enter after copying the Configure command' | Out-Null

$clip = Get-Clipboard -Raw
if ([string]::IsNullOrWhiteSpace($clip)) {
    throw 'Clipboard is empty.'
}

$match = [regex]::Match($clip, '(?i)--token\s+["'']?([^\s"'']+)["'']?')
if (-not $match.Success) {
    throw 'Could not extract --token from the copied Configure command.'
}
$plainToken = $match.Groups[1].Value
Set-Clipboard -Value ' '
$clip = $null

Push-Location $root
try {
    & .\config.cmd --url $repoUrl --token $plainToken --name $runnerName --labels $runnerLabel --work '_work' --unattended --runasservice
    if ($LASTEXITCODE -ne 0) { throw "config.cmd failed with exit code $LASTEXITCODE" }
}
finally {
    Pop-Location
    $plainToken = $null
}

$services = @(Get-CimInstance Win32_Service | Where-Object {
    $_.Name -like 'actions.runner.alexpmtk-afk-gpt-powershell-bridge*' -and
    ($_.PathName -like "*$root*" -or $_.DisplayName -like "*$runnerName*")
})
if ($services.Count -ne 1) {
    Write-Host 'Runner registration completed, but private HOME service selection is ambiguous.'
    $services | Select-Object Name, State, StartMode, StartName, PathName | Format-Table -AutoSize
    exit 0
}

$serviceName = $services[0].Name
Set-Service -Name $serviceName -StartupType Automatic
& sc.exe failure $serviceName reset= 86400 actions= restart/5000/restart/15000/restart/60000 | Out-Null
if ($LASTEXITCODE -ne 0) { throw "sc.exe failure failed with exit code $LASTEXITCODE" }
& sc.exe failureflag $serviceName 1 | Out-Null
if ($LASTEXITCODE -ne 0) { throw "sc.exe failureflag failed with exit code $LASTEXITCODE" }

$svc = Get-Service -Name $serviceName
if ($svc.Status -ne 'Running') {
    Start-Service -Name $serviceName
    $svc.WaitForStatus('Running', [TimeSpan]::FromSeconds(20))
}

Get-Service -Name $serviceName | Select-Object Name, Status, StartType | Format-Table -AutoSize
Write-Host 'PRIVATE_HOME_BRIDGE_RUNNER_BOOTSTRAP=PASS'
Write-Host '=== PRIVATE_HOME_BRIDGE_RUNNER_BOOTSTRAP_END ==='
'@

New-Item -ItemType Directory -Path 'C:\ProgramData\ChatGPT-PK' -Force | Out-Null
Set-Content -LiteralPath 'C:\ProgramData\ChatGPT-PK\bootstrap-private-home-runner.ps1' -Value $script -Encoding UTF8
Write-Host 'HOME_BOOTSTRAP_SCRIPT_STAGED=True'
Write-Host 'HOME_BOOTSTRAP_PATH=C:\ProgramData\ChatGPT-PK\bootstrap-private-home-runner.ps1'
