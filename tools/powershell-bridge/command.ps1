$ErrorActionPreference = 'Stop'
$script = @'
$ErrorActionPreference = 'Stop'

Write-Host '=== PRIVATE_BRIDGE_RUNNER_BOOTSTRAP_BEGIN ==='

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this script from PowerShell as Administrator.'
}

$root = 'C:\ProgramData\ChatGPT-PK\powershell-private-work-runner'
$zip = Join-Path $root 'actions-runner-win-x64-2.337.0.zip'
$url = 'https://github.com/actions/runner/releases/download/v2.337.0/actions-runner-win-x64-2.337.0.zip'
$expectedHash = '1150692AFA94E71F872017E254EA55B6EECE1EECE3FE7E3A6D4C93D0A1B85CFC'
$repoUrl = 'https://github.com/alexpmtk-afk/gpt-powershell-bridge'
$runnerName = 'GPT-PowerShell-Work-MANAGER-MP2'
$runnerLabel = 'gpt-powershell-work'

New-Item -ItemType Directory -Path $root -Force | Out-Null

if (Test-Path -LiteralPath (Join-Path $root '.runner')) {
    throw 'A runner is already configured in the private runner directory. Stop to avoid overwriting it.'
}

Write-Host 'Downloading official GitHub Actions runner 2.337.0...'
Invoke-WebRequest -Uri $url -OutFile $zip

$actualHash = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToUpperInvariant()
if ($actualHash -ne $expectedHash) {
    throw "Runner package SHA256 mismatch. Actual=$actualHash"
}
Write-Host 'RUNNER_PACKAGE_HASH=PASS'

Expand-Archive -LiteralPath $zip -DestinationPath $root -Force

Write-Host ''
Write-Host 'Paste the one-time GitHub registration token below. Input is hidden.'
$secureToken = Read-Host 'Registration token' -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
try {
    $plainToken = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    Push-Location $root
    try {
        & .\config.cmd --url $repoUrl --token $plainToken --name $runnerName --labels $runnerLabel --work '_work' --unattended --runasservice
        if ($LASTEXITCODE -ne 0) { throw "config.cmd failed with exit code $LASTEXITCODE" }
    }
    finally {
        Pop-Location
    }
}
finally {
    if ($bstr -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
    $plainToken = $null
    $secureToken = $null
}

$services = @(Get-Service | Where-Object {
    $_.Name -like 'actions.runner.alexpmtk-afk-gpt-powershell-bridge*' -or
    $_.Name -like 'actions.runner.alexpmtk-afk.gpt-powershell-bridge*' -or
    $_.DisplayName -like '*GPT-PowerShell-Work-MANAGER-MP2*'
})
if ($services.Count -ne 1) {
    Write-Host 'Runner registration completed, but service selection is ambiguous.'
    $services | Select-Object Name, Status, StartType | Format-Table -AutoSize
    exit 0
}

$svc = $services[0]
Set-Service -Name $svc.Name -StartupType Automatic
& sc.exe failure $svc.Name reset= 86400 actions= restart/5000/restart/15000/restart/60000 | Out-Null
& sc.exe failureflag $svc.Name 1 | Out-Null
if ($svc.Status -ne 'Running') { Start-Service -Name $svc.Name }

Get-Service -Name $svc.Name | Select-Object Name, Status, StartType | Format-Table -AutoSize
Write-Host 'PRIVATE_BRIDGE_RUNNER_BOOTSTRAP=PASS'
Write-Host '=== PRIVATE_BRIDGE_RUNNER_BOOTSTRAP_END ==='
'@

Set-Content -LiteralPath 'C:\ProgramData\ChatGPT-PK\bootstrap-private-bridge-runner.ps1' -Value $script -Encoding UTF8
Write-Host 'BOOTSTRAP_SCRIPT_STAGED=True'
Write-Host 'BOOTSTRAP_PATH=C:\ProgramData\ChatGPT-PK\bootstrap-private-bridge-runner.ps1'
