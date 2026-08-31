param(
    [Parameter(Mandatory = $true)][string]$CodexHome
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$routerDest = Join-Path $CodexHome 'quota-router'
$launcher = Join-Path $routerDest 'codex-router.exe'
$marker = Join-Path $routerDest 'standalone-install.json'

if (-not (Test-Path $marker)) { throw "Standalone install marker not found: $marker" }
$state = Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json

if ($state.environmentRegistered -and $state.registryPath) {
    $registryPath = [string]$state.registryPath
    if (Test-Path $registryPath) {
        if ($state.hadPreviousCliPath) {
            New-ItemProperty -LiteralPath $registryPath -Name CODEX_CLI_PATH -Value ([string]$state.previousCliPath) -PropertyType String -Force | Out-Null
        }
        else {
            Remove-ItemProperty -LiteralPath $registryPath -Name CODEX_CLI_PATH -ErrorAction SilentlyContinue
        }
    }
}

Remove-Item -LiteralPath $launcher -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $marker -Force -ErrorAction SilentlyContinue

Write-Host 'CODEX_AUTO_ROUTER_STANDALONE=REMOVED'
Write-Host 'RESTART_CODEX_DESKTOP_REQUIRED=True'
