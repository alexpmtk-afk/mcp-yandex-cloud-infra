$ErrorActionPreference = 'Stop'
$zip = Join-Path $env:TEMP 'actions-runner-win-x64-2.337.0.zip'
$svcRunner = Join-Path $HOME 'actions-runner\codex-bridge-service'
$repo = 'alexpmtk-afk/mcp-yandex-cloud-infra'
$url = 'https://github.com/alexpmtk-afk/mcp-yandex-cloud-infra'
$name = "Codex-Bridge-Service-$env:COMPUTERNAME"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
$elevated = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
Write-Host ("BRIDGE_SERVICE_ELEVATED=" + $elevated)
if (-not $elevated) {
  Write-Host 'BRIDGE_SERVICE_NEEDS_ELEVATION'
  exit 42
}

if (-not (Test-Path $zip)) { throw "Runner zip not found: $zip" }
if (Test-Path $svcRunner) { Remove-Item $svcRunner -Recurse -Force }
New-Item -ItemType Directory -Force -Path $svcRunner | Out-Null
Expand-Archive -Path $zip -DestinationPath $svcRunner -Force

$gh = (Get-Command gh -ErrorAction Stop).Source
$token = & $gh api -X POST "repos/$repo/actions/runners/registration-token" --jq .token
if (-not $token) { throw 'Failed to obtain runner registration token' }
try {
  Push-Location $svcRunner
  & .\config.cmd --unattended --url $url --token $token --name $name --labels 'codex-bridge,codex-bridge-service' --work '_work' --runasservice
  if ($LASTEXITCODE -ne 0) { throw "config --runasservice failed: $LASTEXITCODE" }
} finally {
  Pop-Location
  Remove-Variable token -ErrorAction SilentlyContinue
}

Write-Host 'BRIDGE_SERVICE_CONFIG_OK'
Get-Service | Where-Object { $_.Name -like 'actions.runner.*' } | Select-Object Name,Status,StartType | Format-Table -AutoSize
