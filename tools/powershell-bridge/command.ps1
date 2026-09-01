Write-Host "COMPUTER=$env:COMPUTERNAME"
Write-Host "USER=$env:USERNAME"
Write-Host "TIME=$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host "POWERSHELL=$($PSVersionTable.PSVersion)"

Get-Service | Where-Object {
    $_.Name -like 'actions.runner.*Codex-Bridge*'
} | Select-Object Name,Status,StartType
