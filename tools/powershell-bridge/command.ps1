$root = 'C:\ProgramData\ChatGPT-PK\powershell-admin-runner'

$svc = Get-Service | Where-Object {
    $_.Name -like 'actions.runner.*Codex-Bridge-Admin-*'
} | Select-Object -First 1

Write-Host ("RUNNER_CONFIG=" + (Test-Path (Join-Path $root '.runner')))

if ($svc) {
    Write-Host "ADMIN_SERVICE=$($svc.Name)"
    Write-Host "STATUS=$($svc.Status)"
    Write-Host "STARTTYPE=$($svc.StartType)"
} else {
    Write-Host 'ADMIN_SERVICE=NOT_FOUND'
}
