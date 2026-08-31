param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$sourceRoot = Split-Path -Parent $PSScriptRoot
$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ("codex-router-standalone-test-" + [Guid]::NewGuid().ToString('N'))
$resolvedSystemTemp = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$resolvedTempRoot = [IO.Path]::GetFullPath($tempRoot)
if (-not $resolvedTempRoot.StartsWith($resolvedSystemTemp, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Unsafe test directory: $resolvedTempRoot"
}

$savedEnvironment = @{}
foreach ($name in @('CODEX_HOME','CODEX_CLI_PATH','LOCALAPPDATA','CODEX_ROUTER_REAL_EXE','CODEX_ROUTER_PROXY_JS','CODEX_ROUTER_LOCALAPPDATA','CODEX_ROUTER_DISCOVER_ONLY')) {
    $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}

New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null
try {
    $launcher = Join-Path $tempRoot 'codex-router.exe'
    Add-Type -Path (Join-Path $sourceRoot 'shim\CodexRouterShim.cs') -OutputAssembly $launcher -OutputType ConsoleApplication
    if (-not (Test-Path -LiteralPath $launcher)) { throw 'launcher compilation failed' }

    $fake = Join-Path $tempRoot 'fake-codex.exe'
    $fakeSource = @'
using System;
public static class FakeCodex {
    public static int Main(string[] args) {
        if (args.Length == 1 && args[0] == "--version") { Console.WriteLine("codex-cli 0.0.0-fake"); return 0; }
        string line;
        while ((line = Console.ReadLine()) != null) Console.WriteLine(line);
        return 0;
    }
}
'@
    Add-Type -TypeDefinition $fakeSource -OutputAssembly $fake -OutputType ConsoleApplication

    $local = Join-Path $tempRoot 'localappdata-discovery'
    $oldDir = Join-Path $local 'OpenAI\Codex\bin\oldhash'
    $newDir = Join-Path $local 'OpenAI\Codex\bin\newhash'
    New-Item -ItemType Directory -Force -Path $oldDir,$newDir | Out-Null
    Set-Content -LiteralPath (Join-Path $oldDir 'codex.exe') -Value 'old'
    Set-Content -LiteralPath (Join-Path $newDir 'codex.exe') -Value 'new'
    (Get-Item -LiteralPath (Join-Path $oldDir 'codex.exe')).LastWriteTimeUtc = [DateTime]::UtcNow.AddDays(-2)
    (Get-Item -LiteralPath (Join-Path $newDir 'codex.exe')).LastWriteTimeUtc = [DateTime]::UtcNow.AddMinutes(-1)
    $env:CODEX_ROUTER_LOCALAPPDATA = $local
    $env:CODEX_ROUTER_DISCOVER_ONLY = '1'
    $env:CODEX_ROUTER_REAL_EXE = $launcher
    $found = (& $launcher).Trim()
    if ([IO.Path]::GetFullPath($found) -ne [IO.Path]::GetFullPath((Join-Path $newDir 'codex.exe'))) {
        throw "launcher discovery or recursion guard failed: $found"
    }

    Remove-Item Env:CODEX_ROUTER_DISCOVER_ONLY -ErrorAction SilentlyContinue
    Remove-Item Env:CODEX_ROUTER_LOCALAPPDATA -ErrorAction SilentlyContinue
    $codexHome = Join-Path $tempRoot '.codex-e2e'
    New-Item -ItemType Directory -Force -Path (Join-Path $codexHome 'quota-router') | Out-Null
    $env:CODEX_HOME = $codexHome
    $env:CODEX_ROUTER_REAL_EXE = $fake
    $env:CODEX_ROUTER_PROXY_JS = Join-Path $sourceRoot 'bin\app-server-proxy.js'
    $simplePrompt = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('0J/QvtC60LDQttC4INGB0L/QuNGB0L7QuiDRhNCw0LnQu9C+0LIg0LIg0YLQtdC60YPRidC10Lkg0L/QsNC/0LrQtS4g0J3QuNGH0LXQs9C+INC90LUg0LjQt9C80LXQvdGP0Lku'))
    $request = @{
        jsonrpc = '2.0'; id = 7; method = 'turn/start'; params = @{
            threadId = 'existing-old-thread'; model = 'gpt-5.6-sol'; effort = 'medium'
            collaborationMode = @{ mode='default'; settings=@{ model='gpt-5.6-sol'; reasoning_effort='medium'; developer_instructions='preserve-me' } }
            input = @(@{ type='text'; text=$simplePrompt; text_elements=@() })
        }
    }
    $wire = ([char]0xFEFF) + ($request | ConvertTo-Json -Compress -Depth 12)
    $startInfo = New-Object Diagnostics.ProcessStartInfo
    $startInfo.FileName = $launcher
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardInput = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $launcherProcess = [Diagnostics.Process]::Start($startInfo)
    $wireBytes = [Text.Encoding]::UTF8.GetBytes($wire + "`n")
    $launcherProcess.StandardInput.BaseStream.Write($wireBytes, 0, $wireBytes.Length)
    $launcherProcess.StandardInput.Close()
    $responseText = $launcherProcess.StandardOutput.ReadToEnd().TrimStart([char]0xFEFF)
    $launcherError = $launcherProcess.StandardError.ReadToEnd()
    $launcherProcess.WaitForExit()
    if ($launcherProcess.ExitCode -ne 0) { throw "launcher routing e2e exited $($launcherProcess.ExitCode): $launcherError" }
    try { $response = $responseText | ConvertFrom-Json }
    catch { throw "launcher returned invalid JSON: $responseText" }
    if ($response.params.threadId -ne 'existing-old-thread') { throw 'threadId was not preserved' }
    if ($response.params.model -ne 'gpt-5.6-luna' -or $response.params.effort -ne 'low') { throw 'simple route is not Luna/low' }
    if ($response.params.collaborationMode.settings.model -ne 'gpt-5.6-luna') { throw 'collaboration model was not routed' }
    if ($response.params.collaborationMode.settings.reasoning_effort -ne 'low') { throw 'collaboration effort was not routed' }
    if ($response.params.collaborationMode.settings.developer_instructions -ne 'preserve-me') { throw 'developer instructions changed' }

    Remove-Item Env:CODEX_ROUTER_REAL_EXE -ErrorAction SilentlyContinue
    Remove-Item Env:CODEX_ROUTER_PROXY_JS -ErrorAction SilentlyContinue
    $profile = Join-Path $tempRoot 'fake-user'
    $installLocal = Join-Path $profile 'AppData\Local'
    $binDir = Join-Path $installLocal 'OpenAI\Codex\bin\testhash'
    $installHome = Join-Path $profile '.codex'
    New-Item -ItemType Directory -Force -Path $binDir,$installHome | Out-Null
    $original = Join-Path $binDir 'codex.exe'
    Copy-Item -LiteralPath $fake -Destination $original -Force
    $hashBefore = (Get-FileHash -LiteralPath $original -Algorithm SHA256).Hash
    & (Join-Path $sourceRoot 'install-standalone.ps1') -CodexHome $installHome -UserProfilePath $profile -UserLocalAppData $installLocal -SkipEnvironmentRegistration
    $installedLauncher = Join-Path $installHome 'quota-router\codex-router.exe'
    $markerPath = Join-Path $installHome 'quota-router\standalone-install.json'
    if (-not (Test-Path -LiteralPath $installedLauncher)) { throw 'launcher missing after install' }
    $marker = Get-Content -LiteralPath $markerPath -Raw | ConvertFrom-Json
    if ($marker.version -ne '0.4.0' -or $marker.environmentRegistered) { throw 'invalid installer marker' }
    if ($marker.realExeSha256Before -ne $hashBefore -or $marker.realExeSha256After -ne $hashBefore) { throw 'original hash marker mismatch' }
    if ((Get-FileHash -LiteralPath $original -Algorithm SHA256).Hash -ne $hashBefore) { throw 'installer modified original Codex' }

    $env:CODEX_HOME = $installHome
    $env:CODEX_CLI_PATH = $installedLauncher
    $env:LOCALAPPDATA = $installLocal
    $status = (& node (Join-Path $installHome 'quota-router\bin\status.js')) | ConvertFrom-Json
    if (-not $status.active -or $status.routerVersion -ne '0.4.0') { throw 'status does not report active v0.4.0 router' }
    if ([IO.Path]::GetFullPath($status.launcherPath) -ne [IO.Path]::GetFullPath($installedLauncher)) { throw 'status launcher path mismatch' }
    if ([IO.Path]::GetFullPath($status.realCodexPath) -ne [IO.Path]::GetFullPath($original)) { throw 'status real Codex path mismatch' }

    & (Join-Path $sourceRoot 'uninstall-standalone.ps1') -CodexHome $installHome
    if (Test-Path -LiteralPath $installedLauncher) { throw 'launcher remains after uninstall' }
    if (Test-Path -LiteralPath $markerPath) { throw 'marker remains after uninstall' }
    if ((Get-FileHash -LiteralPath $original -Algorithm SHA256).Hash -ne $hashBefore) { throw 'uninstaller modified original Codex' }

    Write-Host 'standalone launcher/install/uninstall e2e: PASS'
}
finally {
    foreach ($name in $savedEnvironment.Keys) {
        $value = $savedEnvironment[$name]
        if ($null -eq $value) { Remove-Item "Env:$name" -ErrorAction SilentlyContinue }
        else { [Environment]::SetEnvironmentVariable($name, $value, 'Process') }
    }
    if (Test-Path -LiteralPath $resolvedTempRoot) { Remove-Item -LiteralPath $resolvedTempRoot -Recurse -Force }
}
