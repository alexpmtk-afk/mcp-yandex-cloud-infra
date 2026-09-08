# MANAGER_MP2_DIAGNOSTIC=YES
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

Write-Host '=== MARKETPLACES_MANAGER_MP2_DIAGNOSTIC_BEGIN ==='
Write-Host "COMPUTER=$env:COMPUTERNAME"
Write-Host "RUNNER_NAME=$env:RUNNER_NAME"
Write-Host "BRIDGE_IDENTITY=$([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)"

$interactiveUser = (Get-CimInstance Win32_ComputerSystem -ErrorAction Stop).UserName
Write-Host "INTERACTIVE_USER=$interactiveUser"
if ([string]::IsNullOrWhiteSpace($interactiveUser)) { throw 'No interactive user is logged on.' }

$nt = New-Object System.Security.Principal.NTAccount($interactiveUser)
$sid = $nt.Translate([System.Security.Principal.SecurityIdentifier]).Value
Write-Host "INTERACTIVE_SID=$sid"

$profile = Get-CimInstance Win32_UserProfile | Where-Object { $_.SID -eq $sid } | Select-Object -First 1
if ($profile) {
  Write-Host "USER_PROFILE=$($profile.LocalPath)"
  Write-Host "USER_PROFILE_LOADED=$($profile.Loaded)"
} else {
  Write-Host 'USER_PROFILE=NOT_FOUND'
}

Write-Host '--- FILESYSTEM_DRIVES ---'
Get-PSDrive -PSProvider FileSystem | ForEach-Object { Write-Host ("DRIVE={0} ROOT={1}" -f $_.Name,$_.Root) }

$roots = @('X:\','G:\','D:\','C:\') | Where-Object { Test-Path -LiteralPath $_ }
$project = $null
$candidates = @(
  'X:\Мой диск\Marketplaces\MCP отчеты МП\marketplaces-mcp-only',
  'X:\My Drive\Marketplaces\MCP отчеты МП\marketplaces-mcp-only',
  'G:\Мой диск\Marketplaces\MCP отчеты МП\marketplaces-mcp-only',
  'G:\My Drive\Marketplaces\MCP отчеты МП\marketplaces-mcp-only'
)
foreach ($p in $candidates) {
  if (Test-Path -LiteralPath $p) { $project = $p; break }
}
if (-not $project) {
  foreach ($r in $roots) {
    try {
      $hit = Get-ChildItem -LiteralPath $r -Directory -Recurse -Depth 5 -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -eq 'marketplaces-mcp-only' } | Select-Object -First 1
      if ($hit) { $project = $hit.FullName; break }
    } catch {}
  }
}
Write-Host "PROJECT_FOUND=$([bool]$project)"
if ($project) { Write-Host "PROJECT_PATH=$project" }

$profilePath = if ($profile) { $profile.LocalPath } else { $null }
$codexCandidates = @()
if ($profilePath) {
  $codexCandidates += (Join-Path $profilePath 'AppData\Roaming\npm\codex.cmd')
  $codexCandidates += (Join-Path $profilePath 'AppData\Local\Programs\codex\codex.exe')
  $codexCandidates += (Join-Path $profilePath '.codex\config.toml')
}
foreach ($p in $codexCandidates) { Write-Host "CHECK_PATH=$p EXISTS=$(Test-Path -LiteralPath $p)" }

$userEnvTokenPresent = $false
try {
  $envKey = "Registry::HKEY_USERS\$sid\Environment"
  $v = (Get-ItemProperty -LiteralPath $envKey -Name 'MARKETPLACES_MCP_TOKEN' -ErrorAction Stop).MARKETPLACES_MCP_TOKEN
  $userEnvTokenPresent = -not [string]::IsNullOrWhiteSpace($v)
} catch {}
Write-Host "USER_TOKEN_REGISTRY_PRESENT=$userEnvTokenPresent"

if ($profilePath) {
  $cfg = Join-Path $profilePath '.codex\config.toml'
  if (Test-Path -LiteralPath $cfg) {
    $text = Get-Content -Raw -LiteralPath $cfg
    Write-Host "GLOBAL_CONFIG_EXISTS=True"
    Write-Host "GLOBAL_HAS_MARKETPLACES_YANDEX=$([bool]($text -match '(?m)^\[mcp_servers\.marketplaces-yandex\]'))"
    Write-Host "GLOBAL_USES_TOKEN_ENV=$([bool]($text -match 'bearer_token_env_var\s*=\s*"MARKETPLACES_MCP_TOKEN"'))"
  } else { Write-Host 'GLOBAL_CONFIG_EXISTS=False' }
}

Write-Host '--- USER_SCHEDULED_TASKS ---'
Get-ScheduledTask -ErrorAction SilentlyContinue |
  Where-Object { $_.Principal.UserId -eq $interactiveUser -or $_.Principal.UserId -eq $sid } |
  Select-Object -First 30 |
  ForEach-Object {
    Write-Host ("TASK={0} USER={1} LOGON={2} RUNLEVEL={3} STATE={4}" -f $_.TaskName,$_.Principal.UserId,$_.Principal.LogonType,$_.Principal.RunLevel,$_.State)
  }

Write-Host '=== MARKETPLACES_MANAGER_MP2_DIAGNOSTIC_END ==='
