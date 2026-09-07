$ErrorActionPreference = 'Stop'

Write-Host '=== OZON_HOME_DIRECT_USER_CDP_BEGIN ==='

$runtimeRoot = 'C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
$repoRoot = Join-Path $runtimeRoot 'repo'
$browser = 'C:\Program Files\Yandex\YandexBrowser\Application\browser.exe'
$profile = Join-Path $runtimeRoot 'profiles\MarketplaceMonitor\Ozon-Yandex-CDP-Direct'
$launcher = Join-Path $runtimeRoot 'launch-ozon-yandex-cdp-direct.ps1'
$resultPath = Join-Path $runtimeRoot 'plain-cdp-direct.json'
$screenshotPath = Join-Path $runtimeRoot 'plain-cdp-direct.png'
$startedPath = Join-Path $runtimeRoot 'plain-cdp-direct.started'

foreach ($path in @($resultPath,$screenshotPath,$startedPath)) {
    if (Test-Path $path) {
        Remove-Item $path -Force
    }
}

if (-not (Test-Path $browser)) {
    throw "Yandex Browser not found: $browser"
}

$script = @'
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$env:PYTHONUTF8 = '1'
$env:GIT_TERMINAL_PROMPT = '0'

$runtimeRoot = 'C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
$repoRoot = Join-Path $runtimeRoot 'repo'
$browser = 'C:\Program Files\Yandex\YandexBrowser\Application\browser.exe'
$profile = Join-Path $runtimeRoot 'profiles\MarketplaceMonitor\Ozon-Yandex-CDP-Direct'
$resultPath = Join-Path $runtimeRoot 'plain-cdp-direct.json'
$screenshotPath = Join-Path $runtimeRoot 'plain-cdp-direct.png'
$startedPath = Join-Path $runtimeRoot 'plain-cdp-direct.started'
$branch = 'implementation/ozon-user-node-gate'
$git = 'C:\Program Files\Git\cmd\git.exe'
$venvPython = Join-Path $runtimeRoot '.venv\Scripts\python.exe'

"STARTED $(Get-Date -Format o) USER=$([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) SESSION=$((Get-Process -Id $PID).SessionId)" |
    Set-Content -Path $startedPath -Encoding UTF8

& $git -C $repoRoot fetch origin $branch
if ($LASTEXITCODE -ne 0) {
    throw "git fetch failed: $LASTEXITCODE"
}

& $git -C $repoRoot checkout $branch
if ($LASTEXITCODE -ne 0) {
    throw "git checkout failed: $LASTEXITCODE"
}

& $git -C $repoRoot pull --ff-only origin $branch
if ($LASTEXITCODE -ne 0) {
    throw "git pull failed: $LASTEXITCODE"
}

if (-not (Test-Path $venvPython)) {
    throw "Venv Python not found: $venvPython"
}

& $venvPython -m pip install -r (Join-Path $repoRoot 'requirements.txt') --disable-pip-version-check
if ($LASTEXITCODE -ne 0) {
    throw "pip install failed: $LASTEXITCODE"
}

$probe = Join-Path $repoRoot 'src\ozon_plain_cdp_probe.py'

if (-not (Test-Path $probe)) {
    throw "CDP probe not found: $probe"
}

& $venvPython `
    $probe `
    --browser-path $browser `
    --profile-dir $profile `
    --target-url 'https://www.ozon.ru/product/nippel-dlya-beskamernyh-shin-ventil-sosok-avtomobilnyy-rezinovyy-1420875699/' `
    --expected-sku '1420875699' `
    --expected-region 'Воронеж' `
    --output $resultPath `
    --screenshot $screenshotPath `
    --port 9227 `
    --settle-seconds 18

exit $LASTEXITCODE
'@

[IO.File]::WriteAllText(
    $launcher,
    $script,
    (New-Object System.Text.UnicodeEncoding($false,$true))
)

$user = "$env:COMPUTERNAME\Win10_Game_OS"
& icacls.exe $runtimeRoot /grant "${user}:(OI)(CI)M" /T /C | Out-Null

$nativeSource = @"
using System;
using System.Text;
using System.Runtime.InteropServices;

public static class UserSessionNative
{
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    public struct STARTUPINFO
    {
        public Int32 cb;
        public string lpReserved;
        public string lpDesktop;
        public string lpTitle;
        public Int32 dwX;
        public Int32 dwY;
        public Int32 dwXSize;
        public Int32 dwYSize;
        public Int32 dwXCountChars;
        public Int32 dwYCountChars;
        public Int32 dwFillAttribute;
        public Int32 dwFlags;
        public Int16 wShowWindow;
        public Int16 cbReserved2;
        public IntPtr lpReserved2;
        public IntPtr hStdInput;
        public IntPtr hStdOutput;
        public IntPtr hStdError;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct PROCESS_INFORMATION
    {
        public IntPtr hProcess;
        public IntPtr hThread;
        public UInt32 dwProcessId;
        public UInt32 dwThreadId;
    }

    [DllImport("kernel32.dll")]
    public static extern UInt32 WTSGetActiveConsoleSessionId();

    [DllImport("Wtsapi32.dll", SetLastError = true)]
    public static extern bool WTSQueryUserToken(
        UInt32 SessionId,
        out IntPtr phToken
    );

    [DllImport("userenv.dll", SetLastError = true)]
    public static extern bool CreateEnvironmentBlock(
        out IntPtr lpEnvironment,
        IntPtr hToken,
        bool bInherit
    );

    [DllImport("userenv.dll", SetLastError = true)]
    public static extern bool DestroyEnvironmentBlock(
        IntPtr lpEnvironment
    );

    [DllImport(
        "advapi32.dll",
        SetLastError = true,
        CharSet = CharSet.Unicode
    )]
    public static extern bool CreateProcessAsUser(
        IntPtr hToken,
        string lpApplicationName,
        StringBuilder lpCommandLine,
        IntPtr lpProcessAttributes,
        IntPtr lpThreadAttributes,
        bool bInheritHandles,
        UInt32 dwCreationFlags,
        IntPtr lpEnvironment,
        string lpCurrentDirectory,
        ref STARTUPINFO lpStartupInfo,
        out PROCESS_INFORMATION lpProcessInformation
    );

    [DllImport(
        "advapi32.dll",
        SetLastError = true,
        CharSet = CharSet.Unicode
    )]
    public static extern bool CreateProcessWithTokenW(
        IntPtr hToken,
        UInt32 dwLogonFlags,
        string lpApplicationName,
        StringBuilder lpCommandLine,
        UInt32 dwCreationFlags,
        IntPtr lpEnvironment,
        string lpCurrentDirectory,
        ref STARTUPINFO lpStartupInfo,
        out PROCESS_INFORMATION lpProcessInformation
    );

    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool CloseHandle(IntPtr hObject);
}
"@

Add-Type -TypeDefinition $nativeSource

$sessionId = [UserSessionNative]::WTSGetActiveConsoleSessionId()

if ($sessionId -eq [uint32]::MaxValue) {
    throw 'No active console session found.'
}

Write-Host "ACTIVE_SESSION_ID=$sessionId"

$token = [IntPtr]::Zero
$environment = [IntPtr]::Zero

if (-not [UserSessionNative]::WTSQueryUserToken(
    $sessionId,
    [ref]$token
)) {
    $code = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
    throw "WTSQueryUserToken failed: $code"
}

try {
    if (-not [UserSessionNative]::CreateEnvironmentBlock(
        [ref]$environment,
        $token,
        $false
    )) {
        $code = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
        throw "CreateEnvironmentBlock failed: $code"
    }

    $si = New-Object 'UserSessionNative+STARTUPINFO'
    $si.cb = [Runtime.InteropServices.Marshal]::SizeOf($si)
    $si.lpDesktop = 'winsta0\default'

    $pi = New-Object 'UserSessionNative+PROCESS_INFORMATION'

    $powershell = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
    $commandLine = New-Object System.Text.StringBuilder
    [void]$commandLine.Append(
        "-NoProfile -ExecutionPolicy Bypass -File `"$launcher`""
    )

    $CREATE_UNICODE_ENVIRONMENT = 0x00000400

    $launched = [UserSessionNative]::CreateProcessAsUser(
        $token,
        $powershell,
        $commandLine,
        [IntPtr]::Zero,
        [IntPtr]::Zero,
        $false,
        $CREATE_UNICODE_ENVIRONMENT,
        $environment,
        $runtimeRoot,
        [ref]$si,
        [ref]$pi
    )

    $launchMethod = 'CreateProcessAsUser'

    if (-not $launched) {
        $firstError = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
        Write-Host "CREATE_PROCESS_AS_USER_ERROR=$firstError"

        $pi = New-Object 'UserSessionNative+PROCESS_INFORMATION'
        $commandLine = New-Object System.Text.StringBuilder
        [void]$commandLine.Append(
            "-NoProfile -ExecutionPolicy Bypass -File `"$launcher`""
        )

        $LOGON_WITH_PROFILE = 0x00000001

        $launched = [UserSessionNative]::CreateProcessWithTokenW(
            $token,
            $LOGON_WITH_PROFILE,
            $powershell,
            $commandLine,
            $CREATE_UNICODE_ENVIRONMENT,
            $environment,
            $runtimeRoot,
            [ref]$si,
            [ref]$pi
        )

        $launchMethod = 'CreateProcessWithTokenW'
    }

    if (-not $launched) {
        $code = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
        throw "Direct user-session launch failed: $code"
    }

    Write-Host "DIRECT_LAUNCH=YES"
    Write-Host "DIRECT_LAUNCH_METHOD=$launchMethod"
    Write-Host "DIRECT_CHILD_PID=$($pi.dwProcessId)"

    [UserSessionNative]::CloseHandle($pi.hThread) | Out-Null
    [UserSessionNative]::CloseHandle($pi.hProcess) | Out-Null

    $deadline = (Get-Date).AddSeconds(110)

    while (
        (Get-Date) -lt $deadline -and
        -not (Test-Path $resultPath)
    ) {
        Start-Sleep -Seconds 2
    }

    Write-Host '--- START_MARKER ---'

    if (Test-Path $startedPath) {
        Get-Content $startedPath -Raw
    }
    else {
        Write-Host 'NOT_FOUND'
    }

    Write-Host '--- CDP_RESULT ---'

    if (Test-Path $resultPath) {
        Get-Content $resultPath -Raw
    }
    else {
        Write-Host 'NOT_FOUND'
    }

    Write-Host "SCREENSHOT_EXISTS=$(Test-Path $screenshotPath)"

    $child = Get-Process `
        -Id $pi.dwProcessId `
        -ErrorAction SilentlyContinue

    Write-Host "CHILD_STILL_RUNNING=$([bool]$child)"
}
finally {
    if ($environment -ne [IntPtr]::Zero) {
        [UserSessionNative]::DestroyEnvironmentBlock(
            $environment
        ) | Out-Null
    }

    if ($token -ne [IntPtr]::Zero) {
        [UserSessionNative]::CloseHandle($token) | Out-Null
    }
}

Write-Host '=== OZON_HOME_DIRECT_USER_CDP_END ==='
