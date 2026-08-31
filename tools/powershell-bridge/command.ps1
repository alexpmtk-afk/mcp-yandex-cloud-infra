$ErrorActionPreference = 'Stop'
Write-Host 'POWERSHELL_BRIDGE_TEST_V1'
Write-Host ('PowerShell=' + $PSVersionTable.PSVersion.ToString())
Write-Host ('Computer=' + $env:COMPUTERNAME)
Write-Host ('Date=' + (Get-Date).ToString('o'))
