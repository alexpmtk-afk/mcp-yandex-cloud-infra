$ErrorActionPreference = 'Continue'

Write-Host '=== OZON_YANDEX_PLAIN_POSTAUDIT_BEGIN ==='

$runtimeRoot = 'C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
$scriptPath = Join-Path $runtimeRoot 'ozon-yandex-plain-control.ps1'
$resultPath = Join-Path $runtimeRoot 'ozon-yandex-plain-control.json'
$profile = Join-Path $runtimeRoot 'profiles\MarketplaceMonitor\Ozon-Yandex-Plain'
$taskName = 'MarketplaceCardMonitor-Ozon-Yandex-PlainControl'

Write-Host "SCRIPT_EXISTS=$(Test-Path $scriptPath)"
Write-Host "RESULT_EXISTS=$(Test-Path $resultPath)"
Write-Host "PROFILE_EXISTS=$(Test-Path $profile)"

if (Test-Path $scriptPath) {
    Write-Host '--- SCRIPT_INFO ---'
    Get-Item $scriptPath |
        Select-Object FullName,Length,CreationTime,LastWriteTime |
        Format-List
}

if (Test-Path $resultPath) {
    Write-Host '--- RESULT_JSON ---'
    Get-Content $resultPath -Raw
}

if (Test-Path $profile) {
    Write-Host '--- PROFILE_TOP_FILES ---'
    Get-ChildItem $profile -Force -ErrorAction SilentlyContinue |
        Select-Object -First 60 Name,Length,CreationTime,LastWriteTime |
        Format-Table -AutoSize
}

Write-Host '--- YANDEX_PROFILE_PROCESSES ---'

Get-CimInstance Win32_Process `
    -Filter "Name='browser.exe'" `
    -ErrorAction SilentlyContinue |
    Where-Object {
        $_.CommandLine -and
        $_.CommandLine.IndexOf(
            $profile,
            [System.StringComparison]::OrdinalIgnoreCase
        ) -ge 0
    } |
    Select-Object ProcessId,SessionId,CreationDate,CommandLine |
    Format-List

Write-Host '--- TASK_SCHEDULER_EVENTS ---'

try {
    Get-WinEvent `
        -LogName 'Microsoft-Windows-TaskScheduler/Operational' `
        -MaxEvents 300 `
        -ErrorAction Stop |
    Where-Object {
        $_.Message -match [regex]::Escape($taskName) -or
        $_.Message -match 'ozon-yandex-plain-control'
    } |
    Select-Object -First 40 TimeCreated,Id,LevelDisplayName,Message |
    Format-List
}
catch {
    Write-Host "TASK_EVENT_ERROR=$($_.Exception.Message)"
}

Write-Host '--- POWERSHELL_RELATED_PROCESSES ---'

Get-CimInstance Win32_Process `
    -Filter "Name='powershell.exe'" `
    -ErrorAction SilentlyContinue |
    Where-Object {
        $_.CommandLine -and
        $_.CommandLine -match 'ozon-yandex-plain-control'
    } |
    Select-Object ProcessId,SessionId,CreationDate,CommandLine |
    Format-List

Write-Host '=== OZON_YANDEX_PLAIN_POSTAUDIT_END ==='
