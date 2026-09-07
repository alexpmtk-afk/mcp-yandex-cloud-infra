$ErrorActionPreference = 'Continue'

Write-Host '=== OZON_TASK_DISAPPEAR_AUDIT_BEGIN ==='

$since = (Get-Date).AddMinutes(-20)

Write-Host '--- CURRENT_MARKETPLACE_TASKS ---'

Get-ScheduledTask -ErrorAction SilentlyContinue |
    Where-Object {
        $_.TaskName -like 'MarketplaceCardMonitor*'
    } |
    ForEach-Object {
        Write-Host "TASK=$($_.TaskName)|STATE=$($_.State)|USER=$($_.Principal.UserId)|LOGON=$($_.Principal.LogonType)"
    }

Write-Host '--- TASK_FILES ---'

Get-ChildItem `
    'C:\Windows\System32\Tasks' `
    -Recurse `
    -Force `
    -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Name -like 'MarketplaceCardMonitor*'
    } |
    ForEach-Object {
        Write-Host "TASK_FILE=$($_.FullName)|MODIFIED=$($_.LastWriteTime.ToString('o'))"
    }

Write-Host '--- TASK_SCHEDULER_OPERATIONAL ---'

try {
    Get-WinEvent `
        -FilterHashtable @{
            LogName = 'Microsoft-Windows-TaskScheduler/Operational'
            StartTime = $since
        } `
        -ErrorAction Stop |
    Where-Object {
        $_.Message -match 'MarketplaceCardMonitor'
    } |
    Sort-Object TimeCreated |
    ForEach-Object {
        Write-Host "TIME=$($_.TimeCreated.ToString('o'))|ID=$($_.Id)"
        Write-Host $_.Message
        Write-Host '---'
    }
}
catch {
    Write-Host "TASK_LOG_ERROR=$($_.Exception.Message)"
}

Write-Host '--- SECURITY_TASK_EVENTS ---'

try {
    Get-WinEvent `
        -FilterHashtable @{
            LogName = 'Security'
            Id = 4698,4699,4702
            StartTime = $since
        } `
        -ErrorAction Stop |
    Where-Object {
        $_.Message -match 'MarketplaceCardMonitor'
    } |
    Sort-Object TimeCreated |
    ForEach-Object {
        Write-Host "TIME=$($_.TimeCreated.ToString('o'))|ID=$($_.Id)"
        Write-Host $_.Message
        Write-Host '---'
    }
}
catch {
    Write-Host "SECURITY_LOG_ERROR=$($_.Exception.Message)"
}

Write-Host '--- RELATED_PROCESSES ---'

Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
        $_.CommandLine -and (
            $_.CommandLine -match 'marketplace-card-monitor' -or
            $_.CommandLine -match 'MarketplaceCardMonitor'
        )
    } |
    ForEach-Object {
        Write-Host "PID=$($_.ProcessId)|SESSION=$($_.SessionId)|NAME=$($_.Name)|CMD=$($_.CommandLine)"
    }

Write-Host '=== OZON_TASK_DISAPPEAR_AUDIT_END ==='
