$ErrorActionPreference = 'Stop'

Write-Host '=== USER_CONTEXT_PROBE_BEGIN ==='

$user = 'Win10_Game_OS'
$probeRoot = 'C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\interactive-probe-v1'
$probeScript = Join-Path $probeRoot 'probe.ps1'
$resultFile = Join-Path $probeRoot 'result.json'
$taskName = 'MarketplaceCardMonitor-UserContextProbe'

New-Item -ItemType Directory -Force -Path $probeRoot | Out-Null
if (Test-Path $resultFile) {
    Remove-Item $resultFile -Force
}

& icacls.exe $probeRoot /grant "${user}:(OI)(CI)M" /T /C | Out-Null

$script = @'
$ErrorActionPreference = 'Continue'

$env:GH_TOKEN = $null
$env:GITHUB_TOKEN = $null
$env:GIT_TERMINAL_PROMPT = '0'
$env:GCM_INTERACTIVE = 'Never'

$result = [ordered]@{
    timestamp = (Get-Date).ToString('o')
    user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    username = $env:USERNAME
    userprofile = $env:USERPROFILE
    session_id = (Get-Process -Id $PID).SessionId
    chrome_path = $null
    gh_path = $null
    gh_auth_ok = $false
    gh_repo_access = $false
    git_path = $null
    git_repo_access = $false
    winget_path = $null
    python_paths = @()
}

$chrome = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
if (Test-Path $chrome) {
    $result.chrome_path = $chrome
}

$gh = Get-Command gh.exe -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $gh) {
    $gh = Get-Command gh -ErrorAction SilentlyContinue | Select-Object -First 1
}

if ($gh) {
    $result.gh_path = $gh.Source

    & $gh.Source auth status --hostname github.com *> $null
    $result.gh_auth_ok = ($LASTEXITCODE -eq 0)

    if ($result.gh_auth_ok) {
        $repoName = & $gh.Source repo view alexpmtk-afk/marketplace-card-monitor --json nameWithOwner --jq '.nameWithOwner' 2>$null
        if ($LASTEXITCODE -eq 0 -and $repoName -eq 'alexpmtk-afk/marketplace-card-monitor') {
            $result.gh_repo_access = $true
        }
    }
}

$git = Get-Command git.exe -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $git) {
    $git = Get-Command git -ErrorAction SilentlyContinue | Select-Object -First 1
}

if ($git) {
    $result.git_path = $git.Source

    $probe = & $git.Source ls-remote https://github.com/alexpmtk-afk/marketplace-card-monitor.git HEAD 2>$null
    if ($LASTEXITCODE -eq 0 -and $probe) {
        $result.git_repo_access = $true
    }
}

$winget = Get-Command winget.exe -ErrorAction SilentlyContinue | Select-Object -First 1
if ($winget) {
    $result.winget_path = $winget.Source
}

$pythonCandidates = @()

foreach ($name in @('python.exe','python','py.exe','py')) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cmd -and $cmd.Source) {
        $pythonCandidates += $cmd.Source
    }
}

Get-ChildItem "$env:LOCALAPPDATA\Programs\Python" -Directory -ErrorAction SilentlyContinue |
    ForEach-Object {
        $candidate = Join-Path $_.FullName 'python.exe'
        if (Test-Path $candidate) {
            $pythonCandidates += $candidate
        }
    }

$result.python_paths = @($pythonCandidates | Select-Object -Unique)

$result |
    ConvertTo-Json -Depth 6 |
    Set-Content -Path 'C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\interactive-probe-v1\result.json' -Encoding UTF8
'@

[IO.File]::WriteAllText(
    $probeScript,
    $script,
    (New-Object Text.UTF8Encoding($false))
)

try {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
} catch {}

$action = New-ScheduledTaskAction `
    -Execute 'powershell.exe' `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$probeScript`""

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

Start-ScheduledTask -TaskName $taskName

$deadline = (Get-Date).AddSeconds(60)

while ((Get-Date) -lt $deadline -and -not (Test-Path $resultFile)) {
    Start-Sleep -Seconds 2
}

if (Test-Path $resultFile) {
    Write-Host '--- USER_CONTEXT_RESULT ---'
    Get-Content $resultFile -Raw
} else {
    Write-Host 'USER_CONTEXT_RESULT=TIMEOUT'
}

try {
    $info = Get-ScheduledTaskInfo -TaskName $taskName
    Write-Host "TASK_LAST_RESULT=$($info.LastTaskResult)"
} catch {}

Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

Write-Host '=== USER_CONTEXT_PROBE_END ==='
