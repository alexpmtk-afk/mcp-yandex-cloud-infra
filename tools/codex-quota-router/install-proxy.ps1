param(
    [Parameter(Mandatory = $true)][string]$CodexHome,
    [Parameter(Mandatory = $true)][string]$CodexExePath
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$sourceRoot = $PSScriptRoot
$routerDest = Join-Path $CodexHome 'quota-router'
$exeDir = Split-Path -Parent $CodexExePath
$realExe = Join-Path $exeDir 'codex-real.exe'
$marker = Join-Path $routerDest 'proxy-install.json'
$shimSource = Join-Path $sourceRoot 'shim\CodexRouterShim.cs'
$shimTemp = Join-Path $env:TEMP ("codex-router-shim-{0}.exe" -f [Guid]::NewGuid().ToString('N'))

if (-not (Test-Path $CodexHome)) { throw "Codex home not found: $CodexHome" }
if (-not (Test-Path $CodexExePath)) { throw "Codex executable not found: $CodexExePath" }
if (-not (Test-Path $shimSource)) { throw "Shim source not found: $shimSource" }

$running = Get-CimInstance Win32_Process | Where-Object {
    $_.ExecutablePath -and ([IO.Path]::GetFullPath($_.ExecutablePath) -eq [IO.Path]::GetFullPath($CodexExePath))
}
if ($running) {
    throw 'Codex is still running. Close Codex Desktop before installing the proxy.'
}

$node = Get-Command node.exe -ErrorAction SilentlyContinue
if (-not $node) {
    $candidate = Join-Path $env:ProgramFiles 'nodejs\node.exe'
    if (-not (Test-Path $candidate)) { throw 'Node.js was not found.' }
}

New-Item -ItemType Directory -Force -Path (Join-Path $routerDest 'bin') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $routerDest 'lib') | Out-Null

$copyMap = @{
    (Join-Path $sourceRoot 'policy.json') = (Join-Path $routerDest 'policy.json')
    (Join-Path $sourceRoot 'bin\app-server-proxy.js') = (Join-Path $routerDest 'bin\app-server-proxy.js')
    (Join-Path $sourceRoot 'bin\quota-router.js') = (Join-Path $routerDest 'bin\quota-router.js')
    (Join-Path $sourceRoot 'bin\status.js') = (Join-Path $routerDest 'bin\status.js')
    (Join-Path $sourceRoot 'bin\usage-snapshot.js') = (Join-Path $routerDest 'bin\usage-snapshot.js')
    (Join-Path $sourceRoot 'lib\proxy-core.js') = (Join-Path $routerDest 'lib\proxy-core.js')
    (Join-Path $sourceRoot 'lib\router-core.js') = (Join-Path $routerDest 'lib\router-core.js')
    (Join-Path $sourceRoot 'lib\usage.js') = (Join-Path $routerDest 'lib\usage.js')
}
foreach ($src in $copyMap.Keys) {
    if (-not (Test-Path $src)) { throw "Required router file missing: $src" }
    Copy-Item -LiteralPath $src -Destination $copyMap[$src] -Force
}

if (Test-Path $shimTemp) { Remove-Item $shimTemp -Force }
Add-Type -Path $shimSource -OutputAssembly $shimTemp -OutputType ConsoleApplication
if (-not (Test-Path $shimTemp)) { throw 'Shim compilation did not produce an executable.' }

$originalHash = (Get-FileHash -LiteralPath $CodexExePath -Algorithm SHA256).Hash
$alreadyInstalled = Test-Path $realExe

try {
    if (-not $alreadyInstalled) {
        Move-Item -LiteralPath $CodexExePath -Destination $realExe
    }

    Copy-Item -LiteralPath $shimTemp -Destination $CodexExePath -Force

    $oldCodexHome = $env:CODEX_HOME
    $env:CODEX_HOME = $CodexHome
    try {
        $versionOutput = & $CodexExePath --version 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "Shim smoke test failed with exit code $LASTEXITCODE. Output: $versionOutput"
        }
    }
    finally {
        if ($null -eq $oldCodexHome) { Remove-Item Env:CODEX_HOME -ErrorAction SilentlyContinue }
        else { $env:CODEX_HOME = $oldCodexHome }
    }

    [pscustomobject]@{
        version = '0.2.0'
        installedAt = [DateTimeOffset]::UtcNow.ToString('o')
        codexExe = $CodexExePath
        realExe = $realExe
        originalSha256 = $originalHash
        shimSha256 = (Get-FileHash -LiteralPath $CodexExePath -Algorithm SHA256).Hash
    } | ConvertTo-Json | Set-Content -LiteralPath $marker -Encoding UTF8

    Write-Host 'CODEX_AUTO_ROUTER_PROXY=INSTALLED'
    Write-Host ("CODEX_EXE=" + $CodexExePath)
    Write-Host ("REAL_EXE=" + $realExe)
    Write-Host ("MARKER=" + $marker)
}
catch {
    if (Test-Path $realExe) {
        Remove-Item -LiteralPath $CodexExePath -Force -ErrorAction SilentlyContinue
        Move-Item -LiteralPath $realExe -Destination $CodexExePath -Force
    }
    throw
}
finally {
    Remove-Item -LiteralPath $shimTemp -Force -ErrorAction SilentlyContinue
}
