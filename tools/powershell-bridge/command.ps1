$ErrorActionPreference = 'Stop'

$dir = 'C:\Users\Win10_Game_OS\actions-runner\codex-bridge-service'
$ps1 = Join-Path $dir 'INSTALL_CHATGPT_ADMIN_BRIDGE.ps1'
$cmd = Join-Path $dir 'START_CHATGPT_ADMIN_BRIDGE.cmd'

$uri = 'https://api.github.com/repos/alexpmtk-afk/mcp-yandex-cloud-infra/contents/tools/powershell-admin-bridge/bootstrap-admin.ps1?ref=800a82c0d62cb818002ca2c1db972d11e88df387'
$headers = @{
    Authorization = "Bearer $env:GH_TOKEN"
    Accept = 'application/vnd.github+json'
    'X-GitHub-Api-Version' = '2022-11-28'
    'User-Agent' = 'powershell-admin-bootstrap'
}

$resp = Invoke-RestMethod -Uri $uri -Headers $headers -Method Get
$raw = ($resp.content -replace '\s','')
[IO.File]::WriteAllBytes($ps1,[Convert]::FromBase64String($raw))

$launcher = @'
@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\Users\Win10_Game_OS\actions-runner\codex-bridge-service\INSTALL_CHATGPT_ADMIN_BRIDGE.ps1"
pause
'@

Set-Content -Path $cmd -Value $launcher -Encoding ASCII

Write-Host "BOOTSTRAP_READY=$ps1"
Write-Host "LAUNCHER_READY=$cmd"
