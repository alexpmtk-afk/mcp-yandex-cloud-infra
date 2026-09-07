$ErrorActionPreference = 'Stop'

Write-Host '=== OZON_HOME_YANDEX_PLAIN_CONTROL_V2_BEGIN ==='

$user = 'Win10_Game_OS'
$runtimeRoot = 'C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
$browser = 'C:\Program Files\Yandex\YandexBrowser\Application\browser.exe'
$profile = Join-Path $runtimeRoot 'profiles\MarketplaceMonitor\Ozon-Yandex-Plain-V2'
$scriptPath = Join-Path $runtimeRoot 'ozon-yandex-plain-control-v2.ps1'
$startedPath = Join-Path $runtimeRoot 'ozon-yandex-plain-control-v2.started'
$resultPath = Join-Path $runtimeRoot 'ozon-yandex-plain-control-v2.json'
$taskName = 'MarketplaceCardMonitor-Ozon-Yandex-PlainControl-V2'

foreach ($path in @($startedPath,$resultPath)) {
    if (Test-Path $path) {
        Remove-Item $path -Force
    }
}

New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null
& icacls.exe $runtimeRoot /grant "${user}:(OI)(CI)M" /T /C | Out-Null

$script = @'
$ErrorActionPreference = 'Continue'

$browser = 'C:\Program Files\Yandex\YandexBrowser\Application\browser.exe'
$runtimeRoot = 'C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
$profile = Join-Path $runtimeRoot 'profiles\MarketplaceMonitor\Ozon-Yandex-Plain-V2'
$startedPath = Join-Path $runtimeRoot 'ozon-yandex-plain-control-v2.started'
$resultPath = Join-Path $runtimeRoot 'ozon-yandex-plain-control-v2.json'
$target = 'https://www.ozon.ru/product/nippel-dlya-beskamernyh-shin-ventil-sosok-avtomobilnyy-rezinovyy-1420875699/'

"STARTED $(Get-Date -Format o) USER=$([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) SESSION=$((Get-Process -Id $PID).SessionId)" |
    Set-Content -Path $startedPath -Encoding UTF8

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
    error = $null
}

try {
    Start-Process `
        -FilePath $browser `
        -ArgumentList @(
            "--user-data-dir=$profile",
            '--new-window',
            '--no-first-run',
            '--no-default-browser-check',
            $target
        ) | Out-Null

    $result.launch_ok = $true

    Start-Sleep -Seconds 20

    $processes = @(
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

    $result.process_ids = @(
        $processes | Select-Object -ExpandProperty ProcessId
    )

    $titles = @()

    foreach ($item in $processes) {
        try {
            $p = Get-Process -Id $item.ProcessId -ErrorAction Stop
            if ($p.MainWindowTitle) {
                $titles += $p.MainWindowTitle
            }
        }
        catch {}
    }

    $result.window_titles = @($titles | Select-Object -Unique)
}
catch {
    $result.error = $_.Exception.Message
}
finally {
    $result |
        ConvertTo-Json -Depth 6 |
        Set-Content -Path $resultPath -Encoding UTF8
}

exit 0
'@

[IO.File]::WriteAllText(
    $scriptPath,
    $script,
    (New-Object Text.UTF8Encoding($false))
)

& icacls.exe $scriptPath /grant "${user}:RX" /C | Out-Null

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

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Principal $principal `
    -Settings $settings `
    -Force | Out-Null

Write-Host 'TASK_REGISTERED=YES'

Start-ScheduledTask -TaskName $taskName
Write-Host 'TASK_START_REQUESTED=YES'

foreach ($delay in @(2,5,10)) {
    Start-Sleep -Seconds $delay

    $task = Get-ScheduledTask -TaskName $taskName
    $info = Get-ScheduledTaskInfo -TaskName $taskName

    Write-Host "CHECK_AFTER_${delay}S_STATE=$($task.State)"
    Write-Host "CHECK_AFTER_${delay}S_LAST_RESULT=$($info.LastTaskResult)"
    Write-Host "CHECK_AFTER_${delay}S_STARTED_FILE=$(Test-Path $startedPath)"
}

$deadline = (Get-Date).AddSeconds(50)

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

Write-Host '--- RESULT ---'
if (Test-Path $resultPath) {
    Get-Content $resultPath -Raw
}
else {
    Write-Host 'NOT_FOUND'
}

$finalTask = Get-ScheduledTask -TaskName $taskName
$finalInfo = Get-ScheduledTaskInfo -TaskName $taskName

Write-Host "FINAL_STATE=$($finalTask.State)"
Write-Host "FINAL_LAST_RESULT=$($finalInfo.LastTaskResult)"
Write-Host "FINAL_LAST_RUN=$($finalInfo.LastRunTime)"

Unregister-ScheduledTask `
    -TaskName $taskName `
    -Confirm:$false `
    -ErrorAction SilentlyContinue

Write-Host '=== OZON_HOME_YANDEX_PLAIN_CONTROL_V2_END ==='
