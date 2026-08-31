$ErrorActionPreference = 'Stop'
Write-Host 'POWERSHELL_BRIDGE_READY'
Write-Host ("User=" + $env:USERNAME)
Write-Host ("Computer=" + $env:COMPUTERNAME)
Write-Host ("PowerShell=" + $PSVersionTable.PSVersion.ToString())
