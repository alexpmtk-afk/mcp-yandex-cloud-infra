$ErrorActionPreference = 'Continue'

Write-Host '=== OZON_USER_NODE_POSTFAIL_AUDIT_BEGIN ==='

$runtimeRoot = 'C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
$repoRoot = Join-Path $runtimeRoot 'repo'

Write-Host "RUNTIME_ROOT_EXISTS=$(Test-Path $runtimeRoot)"
Write-Host "REPO_ROOT_EXISTS=$(Test-Path $repoRoot)"
Write-Host "REPO_GIT_EXISTS=$(Test-Path (Join-Path $repoRoot '.git'))"

Write-Host '--- RUNTIME_FILES ---'
if (Test-Path $runtimeRoot) {
    Get-ChildItem -Path $runtimeRoot -Force -Recurse -ErrorAction SilentlyContinue |
        Where-Object {
            $_.FullName -notmatch '(?i)\\profiles\\|\\profile\\|\\cache\\|\\evidence\\'
        } |
        Select-Object -First 250 |
        ForEach-Object {
            Write-Host ("ITEM={0}|TYPE={1}|SIZE={2}|MODIFIED={3}" -f
                $_.FullName,
                $(if ($_.PSIsContainer) {'DIR'} else {'FILE'}),
                $(if ($_.PSIsContainer) {''} else {$_.Length}),
                $_.LastWriteTime.ToString('s'))
        }
}

foreach ($name in @(
    'task-exit.json',
    'bootstrap-status.json',
    'latest-gate.json',
    'task-latest.log'
)) {
    $path = Join-Path $runtimeRoot $name

    Write-Host "--- $name ---"

    if (Test-Path $path) {
        if ($name -eq 'task-latest.log') {
            Get-Content $path -Tail 200 -ErrorAction SilentlyContinue
        }
        else {
            Get-Content $path -Raw -ErrorAction SilentlyContinue
        }
    }
    else {
        Write-Host 'NOT_FOUND'
    }
}

Write-Host '--- REPO_STATE ---'
if (Test-Path (Join-Path $repoRoot '.git')) {
    $git = 'C:\Program Files\Git\cmd\git.exe'

    if (Test-Path $git) {
        & $git -C $repoRoot status --short --branch 2>&1 |
            ForEach-Object { Write-Host $_ }

        & $git -C $repoRoot rev-parse HEAD 2>&1 |
            ForEach-Object { Write-Host "REPO_HEAD=$_" }
    }
}

Write-Host '--- PYTHON_ENV ---'
$venvPython = Join-Path $runtimeRoot '.venv\Scripts\python.exe'
Write-Host "VENV_PYTHON_EXISTS=$(Test-Path $venvPython)"

if (Test-Path $venvPython) {
    & $venvPython -c "import sys,importlib.util; print('PYTHON=' + sys.version.replace(chr(10),' ')); print('PLAYWRIGHT=' + str(importlib.util.find_spec('playwright') is not None))" 2>&1 |
        ForEach-Object { Write-Host $_ }
}

Write-Host '--- CHROME_PROCESSES ---'
Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" -ErrorAction SilentlyContinue |
    Select-Object ProcessId,SessionId,CommandLine |
    ForEach-Object {
        $cmd = $_.CommandLine
        if ($cmd -match '(?i)marketplace|user-node-v1|MarketplaceMonitor') {
            Write-Host "CHROME_PID=$($_.ProcessId)|SESSION=$($_.SessionId)|CMD=$cmd"
        }
    }

Write-Host '--- TASK_STATE ---'
try {
    $task = Get-ScheduledTask -TaskName 'MarketplaceCardMonitor-Ozon-UserNode' -ErrorAction Stop
    Write-Host "TASK_FOUND=YES"
    Write-Host "TASK_STATE=$($task.State)"
    Write-Host "TASK_USER=$($task.Principal.UserId)"
}
catch {
    Write-Host 'TASK_FOUND=NO'
    Write-Host "TASK_ERROR=$($_.Exception.Message)"
}

Write-Host '=== OZON_USER_NODE_POSTFAIL_AUDIT_END ==='
