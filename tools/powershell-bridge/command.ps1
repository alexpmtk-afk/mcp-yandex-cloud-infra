$ErrorActionPreference = 'Stop'

Write-Host '=== OZON_HOME_YANDEX_PLAIN_CONTROL_BEGIN ==='

$user = "$env:COMPUTERNAME\Win10_Game_OS"
$runtimeRoot = 'C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
$browser = 'C:\Program Files\Yandex\YandexBrowser\Application\browser.exe'
$profile = Join-Path $runtimeRoot 'profiles\MarketplaceMonitor\Ozon-Yandex-Plain'
$scriptPath = Join-Path $runtimeRoot 'ozon-yandex-plain-control.ps1'
$resultPath = Join-Path $runtimeRoot 'ozon-yandex-plain-control.json'
$taskName = 'MarketplaceCardMonitor-Ozon-Yandex-PlainControl'

if (-not (Test-Path $browser)) {
    throw "Yandex Browser not found: $browser"
}

if (Test-Path $resultPath) {
    Remove-Item $resultPath -Force
}

$script = @'
$ErrorActionPreference = 'Continue'

$browser = 'C:\Program Files\Yandex\YandexBrowser\Application\browser.exe'
$runtimeRoot = 'C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
$profile = Join-Path $runtimeRoot 'profiles\MarketplaceMonitor\Ozon-Yandex-Plain'
$resultPath = Join-Path $runtimeRoot 'ozon-yandex-plain-control.json'

$target = 'https://www.ozon.ru/product/nippel-dlya-beskamernyh-shin-ventil-sosok-avtomobilnyy-rezinovyy-1420875699/'

function Get-ControlProcesses {
    @(
        Get-CimInstance Win32_Process `
            -Filter "Name='browser.exe'" `
            -ErrorAction SilentlyContinue |
        Where-Object {
            $_.CommandLine -and
            $_.CommandLine.IndexOf(
                $profile,
                [System.StringComparison]::OrdinalIgnoreCase
            ) -ge 0
        }
    )
}

function Stop-ControlProcesses {
    Get-ControlProcesses |
        ForEach-Object {
            Stop-Process `
                -Id $_.ProcessId `
                -Force `
                -ErrorAction SilentlyContinue
        }
}

Stop-ControlProcesses
Start-Sleep -Seconds 2

New-Item -ItemType Directory -Force -Path $profile | Out-Null

$result = [ordered]@{
    timestamp = (Get-Date).ToString('o')
    user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    session_id = (Get-Process -Id $PID).SessionId
    browser = $browser
    profile = $profile
    target = $target
    launch_ok = $false
    process_ids = @()
    window_titles = @()
    blocked_title_seen = $false
    target_process_seen = $false
    error = $null
}

try {
    $arguments = @(
        "--user-data-dir=$profile",
        '--new-window',
        '--no-first-run',
        '--no-default-browser-check',
        $target
    )

    Start-Process `
        -FilePath $browser `
        -ArgumentList $arguments | Out-Null

    $result.launch_ok = $true

    Start-Sleep -Seconds 20

    $processes = Get-ControlProcesses

    $result.process_ids = @(
        $processes |
        Select-Object -ExpandProperty ProcessId
    )

    $result.target_process_seen = ($processes.Count -gt 0)

    $titles = @()

    foreach ($process in $processes) {
        try {
            $p = Get-Process `
                -Id $process.ProcessId `
                -ErrorAction Stop

            if ($p.MainWindowTitle) {
                $titles += $p.MainWindowTitle
            }
        }
        catch {}
    }

    $result.window_titles = @(
        $titles |
        Select-Object -Unique
    )

    foreach ($title in $result.window_titles) {
        if (
            $title -match
            '(?i)похоже.*нет соединения|access denied|captcha|антибот'
        ) {
            $result.blocked_title_seen = $true
        }
    }
}
catch {
    $result.error = $_.Exception.Message
}
finally {
    $result |
        ConvertTo-Json -Depth 6 |
        Set-Content `
            -Path $resultPath `
            -Encoding UTF8

    Stop-ControlProcesses
}

exit 0
'@

[IO.File]::WriteAllText(
    $scriptPath,
    $script,
    (New-Object Text.UTF8Encoding($false))
)

try {
    Unregister-ScheduledTask `
        -TaskName $taskName `
        -Confirm:$false `
        -ErrorAction SilentlyContinue
}
catch {}

$action = New-ScheduledTaskAction `
    -Execute 'powershell.exe' `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`""

$principal = New-ScheduledTaskPrincipal `
    -UserId $user `
    -LogonType Interactive `
    -RunLevel Limited

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 2) `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

try {
    Register-ScheduledTask `
        -TaskName $taskName `
        -Action $action `
        -Principal $principal `
        -Settings $settings `
        -Force | Out-Null

    Write-Host 'TASK_REGISTERED=YES'

    Start-ScheduledTask -TaskName $taskName
    Write-Host 'TASK_STARTED=YES'

    $deadline = (Get-Date).AddSeconds(70)

    while (
        (Get-Date) -lt $deadline -and
        -not (Test-Path $resultPath)
    ) {
        Start-Sleep -Seconds 2
    }

    if (Test-Path $resultPath) {
        Write-Host '--- PLAIN_YANDEX_RESULT ---'
        Get-Content $resultPath -Raw
    }
    else {
        Write-Host 'PLAIN_YANDEX_RESULT=TIMEOUT'
    }
}
finally {
    Unregister-ScheduledTask `
        -TaskName $taskName `
        -Confirm:$false `
        -ErrorAction SilentlyContinue
}

Write-Host '=== OZON_HOME_YANDEX_PLAIN_CONTROL_END ==='
