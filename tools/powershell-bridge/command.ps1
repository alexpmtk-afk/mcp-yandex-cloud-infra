$ErrorActionPreference = 'Stop'

Write-Host '=== OZON_USER_NODE_DEPLOY_AND_SMOKE_BEGIN ==='

$user = "$env:COMPUTERNAME\Win10_Game_OS"
$runtimeRoot = 'C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
$repoRoot = Join-Path $runtimeRoot 'repo'
$launcher = Join-Path $runtimeRoot 'launch-ozon-smoke.ps1'
$taskName = 'MarketplaceCardMonitor-Ozon-UserNode'
$exitFile = Join-Path $runtimeRoot 'task-exit.json'
$gateFile = Join-Path $runtimeRoot 'latest-gate.json'
$bootstrapStatus = Join-Path $runtimeRoot 'bootstrap-status.json'
$taskLog = Join-Path $runtimeRoot 'task-latest.log'

New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null
& icacls.exe $runtimeRoot /grant "${user}:(OI)(CI)M" /T /C | Out-Null

foreach ($path in @($exitFile, $gateFile, $bootstrapStatus, $taskLog)) {
    if (Test-Path $path) {
        Remove-Item $path -Force
    }
}

$script = @'
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$env:PYTHONUTF8 = '1'
$env:GH_TOKEN = $null
$env:GITHUB_TOKEN = $null
$env:GIT_TERMINAL_PROMPT = '0'

$runtimeRoot = 'C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
$repoRoot = Join-Path $runtimeRoot 'repo'
$branch = 'implementation/ozon-user-node-gate'
$repo = 'alexpmtk-afk/marketplace-card-monitor'

$gh = 'C:\Program Files\GitHub CLI\gh.exe'
$git = 'C:\Program Files\Git\cmd\git.exe'

if (-not (Test-Path $gh)) {
    throw "GitHub CLI not found: $gh"
}
if (-not (Test-Path $git)) {
    throw "Git not found: $git"
}

if (Test-Path (Join-Path $repoRoot '.git')) {
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
}
else {
    if (Test-Path $repoRoot) {
        Remove-Item $repoRoot -Recurse -Force
    }

    & $gh repo clone $repo $repoRoot -- --branch $branch --single-branch
    if ($LASTEXITCODE -ne 0) {
        throw "gh repo clone failed: $LASTEXITCODE"
    }
}

$entry = Join-Path $repoRoot 'scripts\user_node_task_entry.ps1'
$config = Join-Path $repoRoot 'config\ozon-user-node-smoke.json'

if (-not (Test-Path $entry)) {
    throw "Task entry not found: $entry"
}
if (-not (Test-Path $config)) {
    throw "Smoke config not found: $config"
}

& powershell.exe `
    -NoProfile `
    -ExecutionPolicy Bypass `
    -File $entry `
    -RepoRoot $repoRoot `
    -RuntimeRoot $runtimeRoot `
    -ConfigPath $config `
    -Runs 1

$exit = $LASTEXITCODE
if ($null -eq $exit) {
    $exit = 0
}

exit $exit
'@

[IO.File]::WriteAllText(
    $launcher,
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
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$launcher`""

$principal = New-ScheduledTaskPrincipal `
    -UserId $user `
    -LogonType Interactive `
    -RunLevel Limited

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 8) `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Principal $principal `
    -Settings $settings `
    -Force | Out-Null

Write-Host "TASK_REGISTERED=YES"
Write-Host "TASK_NAME=$taskName"
Write-Host "TASK_USER=$user"

Start-ScheduledTask -TaskName $taskName
Write-Host 'TASK_STARTED=YES'

$deadline = (Get-Date).AddMinutes(8)

while ((Get-Date) -lt $deadline) {
    if (Test-Path $exitFile) {
        $info = Get-ScheduledTaskInfo -TaskName $taskName
        $task = Get-ScheduledTask -TaskName $taskName
        if ($task.State -ne 'Running') {
            break
        }
    }

    Start-Sleep -Seconds 3
}

Write-Host '--- TASK_INFO ---'
$task = Get-ScheduledTask -TaskName $taskName
$info = Get-ScheduledTaskInfo -TaskName $taskName
Write-Host "TASK_STATE=$($task.State)"
Write-Host "TASK_LAST_RESULT=$($info.LastTaskResult)"
Write-Host "TASK_LAST_RUN=$($info.LastRunTime)"

if (Test-Path $exitFile) {
    Write-Host '--- TASK_EXIT_JSON ---'
    Get-Content $exitFile -Raw
}
else {
    Write-Host 'TASK_EXIT_JSON=NOT_FOUND'
}

if (Test-Path $bootstrapStatus) {
    Write-Host '--- BOOTSTRAP_STATUS_JSON ---'
    Get-Content $bootstrapStatus -Raw
}
else {
    Write-Host 'BOOTSTRAP_STATUS_JSON=NOT_FOUND'
}

if (Test-Path $gateFile) {
    Write-Host '--- LATEST_GATE_JSON ---'
    Get-Content $gateFile -Raw
}
else {
    Write-Host 'LATEST_GATE_JSON=NOT_FOUND'
}

if (Test-Path $taskLog) {
    Write-Host '--- TASK_LOG_TAIL ---'
    Get-Content $taskLog -Tail 120
}
else {
    Write-Host 'TASK_LOG=NOT_FOUND'
}

Write-Host '=== OZON_USER_NODE_DEPLOY_AND_SMOKE_END ==='
