# MANAGER_MP2_DIAGNOSTIC_ASCII_V2=YES
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

Write-Host '=== MARKETPLACES_MANAGER_MP2_DIAGNOSTIC_V2_BEGIN ==='
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
$profilePath = if ($profile) { $profile.LocalPath } else { $null }
Write-Host "USER_PROFILE=$profilePath"
Write-Host "USER_PROFILE_LOADED=$([bool]($profile -and $profile.Loaded))"

Write-Host '--- FILESYSTEM_DRIVES ---'
Get-PSDrive -PSProvider FileSystem | ForEach-Object { Write-Host ("DRIVE={0} ROOT={1}" -f $_.Name,$_.Root) }

foreach ($r in @('X:\','G:\','D:\','C:\')) {
  try {
    $ok = Test-Path -LiteralPath $r -ErrorAction Stop
    Write-Host "ROOT_ACCESS=$r EXISTS=$ok"
  } catch {
    Write-Host "ROOT_ACCESS=$r ERROR=$($_.Exception.GetType().Name)"
  }
}

if ($profilePath) {
  foreach ($p in @(
    (Join-Path $profilePath 'AppData\Roaming\npm\codex.cmd'),
    (Join-Path $profilePath 'AppData\Local\Programs\codex\codex.exe'),
    (Join-Path $profilePath '.codex\config.toml'),
    (Join-Path $profilePath '.codex\auth.json')
  )) {
    try { $exists = Test-Path -LiteralPath $p -ErrorAction Stop } catch { $exists = $false }
    Write-Host "CHECK_PATH=$p EXISTS=$exists"
  }
}

$userEnvTokenPresent = $false
try {
  $envKey = "Registry::HKEY_USERS\$sid\Environment"
  $v = (Get-ItemProperty -LiteralPath $envKey -Name 'MARKETPLACES_MCP_TOKEN' -ErrorAction Stop).MARKETPLACES_MCP_TOKEN
  $userEnvTokenPresent = -not [string]::IsNullOrWhiteSpace($v)
} catch {}
Write-Host "USER_TOKEN_REGISTRY_PRESENT=$userEnvTokenPresent"

if ($profilePath) {
  $cfg = Join-Path $profilePath '.codex\config.toml'
  try { $cfgExists = Test-Path -LiteralPath $cfg -ErrorAction Stop } catch { $cfgExists = $false }
  if ($cfgExists) {
    try {
      $text = Get-Content -Raw -LiteralPath $cfg -ErrorAction Stop
      Write-Host 'GLOBAL_CONFIG_READABLE=True'
      Write-Host "GLOBAL_HAS_MARKETPLACES_YANDEX=$([bool]($text -match '(?m)^\[mcp_servers\.marketplaces-yandex\]'))"
      Write-Host "GLOBAL_USES_TOKEN_ENV=$([bool]($text -match 'bearer_token_env_var\s*=\s*"MARKETPLACES_MCP_TOKEN"'))"
    } catch {
      Write-Host 'GLOBAL_CONFIG_READABLE=False'
    }
  } else { Write-Host 'GLOBAL_CONFIG_READABLE=False' }
}

Write-Host '--- USER_SCHEDULED_TASKS ---'
try {
  Get-ScheduledTask -ErrorAction Stop |
    Where-Object { $_.Principal.UserId -eq $interactiveUser -or $_.Principal.UserId -eq $sid -or $_.Principal.UserId -match '\\user$' } |
    Select-Object -First 80 |
    ForEach-Object {
      $cmd = $null
      try { $cmd = ($_.Actions | Select-Object -First 1).Execute } catch {}
      Write-Host ("TASK={0} USER={1} LOGON={2} RUNLEVEL={3} STATE={4} EXEC={5}" -f $_.TaskName,$_.Principal.UserId,$_.Principal.LogonType,$_.Principal.RunLevel,$_.State,$cmd)
    }
} catch {
  Write-Host "TASK_ENUM_ERROR=$($_.Exception.Message)"
}

Write-Host '=== MARKETPLACES_MANAGER_MP2_DIAGNOSTIC_V2_END ==='
