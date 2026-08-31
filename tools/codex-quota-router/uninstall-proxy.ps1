param(
    [Parameter(Mandatory = $true)][string]$CodexHome,
    [Parameter(Mandatory = $true)][string]$CodexExePath
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$exeDir = Split-Path -Parent $CodexExePath
$realExe = Join-Path $exeDir 'codex-real.exe'
$marker = Join-Path (Join-Path $CodexHome 'quota-router') 'proxy-install.json'

$running = Get-CimInstance Win32_Process | Where-Object {
    $_.ExecutablePath -and ([IO.Path]::GetFullPath($_.ExecutablePath) -eq [IO.Path]::GetFullPath($CodexExePath))
}
if ($running) {
    throw 'Codex is still running. Close Codex Desktop before removing the proxy.'
}

if (-not (Test-Path $realExe)) {
    throw "Backup real Codex executable not found: $realExe"
}

Remove-Item -LiteralPath $CodexExePath -Force -ErrorAction SilentlyContinue
Move-Item -LiteralPath $realExe -Destination $CodexExePath -Force
Remove-Item -LiteralPath $marker -Force -ErrorAction SilentlyContinue

Write-Host 'CODEX_AUTO_ROUTER_PROXY=REMOVED'
Write-Host ("RESTORED_EXE=" + $CodexExePath)
