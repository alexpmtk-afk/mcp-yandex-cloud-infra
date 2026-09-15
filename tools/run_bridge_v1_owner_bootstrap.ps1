[CmdletBinding()]
param(
    [switch]$KeepClaspLogin
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repo = 'alexpmtk-afk/mcp-yandex-cloud-infra'
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("bridge-v1-owner-" + [guid]::NewGuid().ToString('N'))
$resultCopy = Join-Path ([Environment]::GetFolderPath('Desktop')) 'bridge-v1-owner-bootstrap-result.json'

function Require-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command is not installed or not in PATH: $Name"
    }
}

try {
    foreach ($name in @('gh', 'git', 'python', 'node', 'npm', 'npx')) {
        Require-Command $name
    }

    gh auth status | Out-Host
    New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

    Write-Host 'Downloading canonical Bridge v1 main...'
    gh repo clone $repo $tempRoot -- --depth 1 --branch main

    $script = Join-Path $tempRoot 'tools\bootstrap_bridge_v1_apps_script.py'
    if (-not (Test-Path $script)) {
        throw "Owner bootstrap script not found: $script"
    }

    $args = @($script, '--repo-root', $tempRoot)
    if ($KeepClaspLogin) {
        $args += '--keep-clasp-login'
    }

    Write-Host 'Starting Google owner bootstrap. Google consent pages will open in your default browser.'
    & python @args
    if ($LASTEXITCODE -ne 0) {
        throw "Bridge v1 owner bootstrap failed with exit code $LASTEXITCODE"
    }

    $result = Join-Path $tempRoot 'control\bridge-v1-owner-bootstrap-result.json'
    if (-not (Test-Path $result)) {
        throw 'Bootstrap completed without the expected non-secret result file.'
    }
    Copy-Item -LiteralPath $result -Destination $resultCopy -Force
    Write-Host "BRIDGE_V1_OWNER_BOOTSTRAP=PASS"
    Write-Host "Non-secret result copied to: $resultCopy"
}
finally {
    if (Test-Path $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
