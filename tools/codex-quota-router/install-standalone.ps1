param(
    [Parameter(Mandatory = $true)][string]$CodexHome,
    [string]$UserProfilePath,
    [string]$UserLocalAppData,
    [switch]$SkipEnvironmentRegistration
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$sourceRoot = $PSScriptRoot
$routerDest = Join-Path $CodexHome 'quota-router'
$launcher = Join-Path $routerDest 'codex-router.exe'
$marker = Join-Path $routerDest 'standalone-install.json'
$shimSource = Join-Path $sourceRoot 'shim\CodexRouterShim.cs'
$shimTemp = Join-Path $env:TEMP ("codex-router-standalone-{0}.exe" -f [Guid]::NewGuid().ToString('N'))

if (-not (Test-Path $CodexHome)) { throw "Codex home not found: $CodexHome" }
if (-not (Test-Path $shimSource)) { throw "Shim source not found: $shimSource" }

if ([string]::IsNullOrWhiteSpace($UserProfilePath)) {
    $UserProfilePath = Split-Path -Parent $CodexHome
}
if ([string]::IsNullOrWhiteSpace($UserLocalAppData)) {
    $UserLocalAppData = Join-Path $UserProfilePath 'AppData\Local'
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
if (-not (Test-Path $shimTemp)) { throw 'Standalone launcher compilation failed.' }
Copy-Item -LiteralPath $shimTemp -Destination $launcher -Force

$binRoot = Join-Path $UserLocalAppData 'OpenAI\Codex\bin'
$realExe = Get-ChildItem $binRoot -Recurse -Filter codex.exe -File -ErrorAction SilentlyContinue |
    Where-Object { [IO.Path]::GetFullPath($_.FullName) -ne [IO.Path]::GetFullPath($launcher) } |
    Sort-Object LastWriteTimeUtc -Descending |
    Select-Object -First 1 -ExpandProperty FullName
if (-not $realExe) { throw "Original Codex executable not found under: $binRoot" }
$realExeHashBefore = (Get-FileHash -LiteralPath $realExe -Algorithm SHA256).Hash

$oldCodexHome = $env:CODEX_HOME
$oldRealExe = $env:CODEX_ROUTER_REAL_EXE
try {
    $env:CODEX_HOME = $CodexHome
    $env:CODEX_ROUTER_REAL_EXE = $realExe
    $versionOutput = & $launcher --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Standalone launcher smoke test failed with exit code $LASTEXITCODE. Output: $versionOutput"
    }
}
finally {
    if ($null -eq $oldCodexHome) { Remove-Item Env:CODEX_HOME -ErrorAction SilentlyContinue }
    else { $env:CODEX_HOME = $oldCodexHome }
    if ($null -eq $oldRealExe) { Remove-Item Env:CODEX_ROUTER_REAL_EXE -ErrorAction SilentlyContinue }
    else { $env:CODEX_ROUTER_REAL_EXE = $oldRealExe }
}

$realExeHashAfter = (Get-FileHash -LiteralPath $realExe -Algorithm SHA256).Hash
if ($realExeHashAfter -ne $realExeHashBefore) {
    throw "Original Codex executable changed during installation: $realExe"
}

$userSid = $null
$registryPath = $null
$hadPreviousCliPath = $false
$previousCliPath = $null

if (-not $SkipEnvironmentRegistration) {
    $profileRoot = 'Registry::HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList'
    $targetProfile = [IO.Path]::GetFullPath($UserProfilePath).TrimEnd('\')
    foreach ($key in Get-ChildItem $profileRoot) {
        $profileImagePath = (Get-ItemProperty -LiteralPath $key.PSPath -Name ProfileImagePath -ErrorAction SilentlyContinue).ProfileImagePath
        if (-not $profileImagePath) { continue }
        $expanded = [Environment]::ExpandEnvironmentVariables([string]$profileImagePath)
        try { $expanded = [IO.Path]::GetFullPath($expanded).TrimEnd('\') } catch {}
        if ($expanded -ieq $targetProfile) {
            $userSid = $key.PSChildName
            break
        }
    }
    if (-not $userSid) { throw "User SID not found for profile: $UserProfilePath" }

    $registryPath = "Registry::HKEY_USERS\$userSid\Environment"
    if (-not (Test-Path $registryPath)) { throw "User environment registry hive is not loaded: $registryPath" }

    try {
        $previousCliPath = Get-ItemPropertyValue -LiteralPath $registryPath -Name CODEX_CLI_PATH -ErrorAction Stop
        $hadPreviousCliPath = $true
    }
    catch {
        $previousCliPath = $null
        $hadPreviousCliPath = $false
    }

    New-ItemProperty -LiteralPath $registryPath -Name CODEX_CLI_PATH -Value $launcher -PropertyType String -Force | Out-Null

    if (-not ('CodexRouter.EnvironmentBroadcast' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
namespace CodexRouter {
    public static class EnvironmentBroadcast {
        [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
        private static extern IntPtr SendMessageTimeout(
            IntPtr hWnd, uint message, UIntPtr wParam, string lParam,
            uint flags, uint timeout, out UIntPtr result);

        public static void Notify() {
            UIntPtr result;
            SendMessageTimeout(new IntPtr(0xffff), 0x001A, UIntPtr.Zero,
                "Environment", 0x0002, 5000, out result);
        }
    }
}
'@
    }
    [CodexRouter.EnvironmentBroadcast]::Notify()
}

[pscustomobject]@{
    version = '0.4.0'
    installedAt = [DateTimeOffset]::UtcNow.ToString('o')
    launcher = $launcher
    launcherSha256 = (Get-FileHash -LiteralPath $launcher -Algorithm SHA256).Hash
    realExeSmokeTest = $realExe
    realExeSha256Before = $realExeHashBefore
    realExeSha256After = $realExeHashAfter
    userProfile = $UserProfilePath
    userSid = $userSid
    registryPath = $registryPath
    environmentRegistered = (-not $SkipEnvironmentRegistration)
    hadPreviousCliPath = $hadPreviousCliPath
    previousCliPath = $previousCliPath
} | ConvertTo-Json | Set-Content -LiteralPath $marker -Encoding UTF8

Write-Host 'CODEX_AUTO_ROUTER_STANDALONE=INSTALLED'
Write-Host ("LAUNCHER=" + $launcher)
Write-Host ("REAL_EXE_SMOKE=" + $realExe)
Write-Host ("ENVIRONMENT_REGISTERED=" + (-not $SkipEnvironmentRegistration))
Write-Host 'RESTART_CODEX_DESKTOP_REQUIRED=True'

Remove-Item -LiteralPath $shimTemp -Force -ErrorAction SilentlyContinue
