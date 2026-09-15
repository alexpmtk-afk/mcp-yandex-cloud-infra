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

    $script = Join-Path $tempRoot 'tools\finish_bridge_v1.py'
    if (-not (Test-Path $script)) {
        throw "End-to-end Bridge v1 finisher not found: $script"
    }

    $args = @($script, '--repo-root', $tempRoot)
    if ($KeepClaspLogin) {
        $args += '--keep-clasp-login'
    }

    Write-Host 'Starting Bridge v1 end-to-end activation. Google consent pages will open in your default browser.'
    & python @args
    if ($LASTEXITCODE -ne 0) {
        throw "Bridge v1 end-to-end activation failed with exit code $LASTEXITCODE"
    }

    $result = Join-Path $tempRoot 'control\bridge-v1-owner-bootstrap-result.json'
    if (-not (Test-Path $result)) {
        throw 'Activation completed without the expected non-secret result file.'
    }
    Copy-Item -LiteralPath $result -Destination $resultCopy -Force
    Write-Host 'BRIDGE_V1_END_TO_END_PRODUCTION=PASS'
    Write-Host "Non-secret result copied to: $resultCopy"
}
finally {
    if (Test-Path $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
