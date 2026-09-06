$ErrorActionPreference = 'Continue'

Write-Host '=== OZON_USER_NODE_AUDIT_BEGIN ==='
Write-Host "RUNNER=$env:RUNNER_NAME"
Write-Host "COMPUTER=$env:COMPUTERNAME"
Write-Host "SERVICE_USER=$env:USERNAME"

Write-Host '--- INTERACTIVE_SESSIONS ---'
try {
    quser 2>&1 | ForEach-Object { Write-Host $_ }
} catch {
    Write-Host "QUSER_ERROR=$($_.Exception.Message)"
}

Write-Host '--- MARKETPLACE_SCHEDULED_TASKS ---'
try {
    $tasks = Get-ScheduledTask -ErrorAction Stop |
        Where-Object {
            $_.TaskName -match '(?i)ozon|marketplace|card.monitor' -or
            $_.TaskPath -match '(?i)ozon|marketplace|card.monitor'
        }

    if (-not $tasks) {
        Write-Host 'SCHEDULED_TASKS_FOUND=NO'
    } else {
        Write-Host 'SCHEDULED_TASKS_FOUND=YES'
        foreach ($task in $tasks) {
            Write-Host "TASK_NAME=$($task.TaskName)"
            Write-Host "TASK_PATH=$($task.TaskPath)"
            Write-Host "TASK_STATE=$($task.State)"
            Write-Host "TASK_USER=$($task.Principal.UserId)"
            Write-Host "TASK_LOGON_TYPE=$($task.Principal.LogonType)"
            foreach ($action in $task.Actions) {
                Write-Host "TASK_EXECUTE=$($action.Execute)"
                Write-Host "TASK_ARGUMENTS=$($action.Arguments)"
                Write-Host "TASK_WORKDIR=$($action.WorkingDirectory)"
            }
            try {
                $info = Get-ScheduledTaskInfo -TaskName $task.TaskName -TaskPath $task.TaskPath
                Write-Host "TASK_LAST_RUN=$($info.LastRunTime)"
                Write-Host "TASK_LAST_RESULT=$($info.LastTaskResult)"
            } catch {}
            Write-Host '---'
        }
    }
} catch {
    Write-Host "SCHEDULED_TASK_ERROR=$($_.Exception.Message)"
}

Write-Host '--- EXISTING_MONITOR_FILES ---'
$root = 'C:\ProgramData\ChatGPT-PK\marketplace-card-monitor'
Write-Host "MONITOR_ROOT_EXISTS=$(Test-Path $root)"
if (Test-Path $root) {
    Get-ChildItem -Path $root -Force -Recurse -ErrorAction SilentlyContinue |
        Where-Object {
            $_.FullName -notmatch '(?i)\\profile|\\user data|\\cache'
        } |
        Select-Object -First 200 |
        ForEach-Object {
            Write-Host ("ITEM={0}|TYPE={1}|SIZE={2}|MODIFIED={3}" -f
                $_.FullName,
                $(if ($_.PSIsContainer) {'DIR'} else {'FILE'}),
                $(if ($_.PSIsContainer) {''} else {$_.Length}),
                $_.LastWriteTime.ToString('s'))
        }
}

Write-Host '--- CHROME ---'
$chromeCandidates = @(
    'C:\Program Files\Google\Chrome\Application\chrome.exe',
    'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
    'C:\Users\Win10_Game_OS\AppData\Local\Google\Chrome\Application\chrome.exe'
)

$chromeFound = $false
foreach ($path in $chromeCandidates) {
    if (Test-Path $path) {
        $chromeFound = $true
        Write-Host "CHROME_PATH=$path"
        try {
            Write-Host "CHROME_VERSION=$((Get-Item $path).VersionInfo.ProductVersion)"
        } catch {}
    }
}
if (-not $chromeFound) {
    Write-Host 'CHROME_FOUND=NO'
}

Write-Host '--- PYTHON_AND_PLAYWRIGHT ---'
$pythonCandidates = @()

foreach ($name in @('python.exe','python','py.exe','py')) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cmd -and $cmd.Source) {
        $pythonCandidates += $cmd.Source
    }
}

Get-ChildItem 'C:\Users\Win10_Game_OS\AppData\Local\Programs\Python' -Directory -ErrorAction SilentlyContinue |
    ForEach-Object {
        $candidate = Join-Path $_.FullName 'python.exe'
        if (Test-Path $candidate) {
            $pythonCandidates += $candidate
        }
    }

$pythonCandidates = $pythonCandidates | Select-Object -Unique

if (-not $pythonCandidates) {
    Write-Host 'PYTHON_FOUND=NO'
} else {
    foreach ($pythonPath in $pythonCandidates) {
        Write-Host "PYTHON_PATH=$pythonPath"
        try {
            & $pythonPath -c "import sys,importlib.util; print('PYTHON_VERSION=' + sys.version.replace(chr(10),' ')); print('PLAYWRIGHT_PRESENT=' + str(importlib.util.find_spec('playwright') is not None))" 2>&1 |
                ForEach-Object { Write-Host $_ }
        } catch {
            Write-Host "PYTHON_CHECK_ERROR=$($_.Exception.Message)"
        }
    }
}

Write-Host '--- GITHUB_CLI ---'
$gh = Get-Command gh.exe -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $gh) {
    $gh = Get-Command gh -ErrorAction SilentlyContinue | Select-Object -First 1
}
if (-not $gh) {
    Write-Host 'GH_FOUND=NO'
} else {
    Write-Host "GH_PATH=$($gh.Source)"
    Write-Host 'GH_AUTH_STATUS_BEGIN'
    & $gh.Source auth status 2>&1 | ForEach-Object { Write-Host $_ }
    Write-Host 'GH_AUTH_STATUS_END'

    Write-Host 'GH_MARKETPLACE_REPO_CHECK_BEGIN'
    & $gh.Source repo view alexpmtk-afk/marketplace-card-monitor --json nameWithOwner,defaultBranchRef 2>&1 |
        ForEach-Object { Write-Host $_ }
    Write-Host 'GH_MARKETPLACE_REPO_CHECK_END'
}

Write-Host '=== OZON_USER_NODE_AUDIT_END ==='
