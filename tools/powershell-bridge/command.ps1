$ErrorActionPreference = 'Continue'
Write-Host '=== MARKETPLACES_CODEX_DIAG_BEGIN ==='
Write-Host ("IDENTITY={0}" -f [System.Security.Principal.WindowsIdentity]::GetCurrent().Name)
Write-Host ("COMPUTER={0}" -f $env:COMPUTERNAME)
Write-Host ("SESSION={0}" -f (Get-Process -Id $PID).SessionId)

$tokenUser = [Environment]::GetEnvironmentVariable('MARKETPLACES_MCP_TOKEN','User')
Write-Host ("TOKEN_USER_PRESENT={0}" -f (-not [string]::IsNullOrWhiteSpace($tokenUser)))
$tokenUser = $null

$configPath = Join-Path $HOME '.codex\config.toml'
Write-Host ("CODEX_CONFIG_PATH={0}" -f $configPath)
Write-Host ("CODEX_CONFIG_EXISTS={0}" -f (Test-Path $configPath))
if (Test-Path $configPath) {
  $cfg = Get-Content -Raw -Path $configPath
  $hasRemote = $cfg -match '(?m)^\[mcp_servers\.marketplaces-yandex\]'
  $hasEnv = $cfg -match '(?m)^bearer_token_env_var\s*=\s*"MARKETPLACES_MCP_TOKEN"'
  $hasHttps = $cfg -match '(?m)^url\s*=\s*"https://[^\"]+/mcp"'
  Write-Host ("MCP_REMOTE_CONFIGURED={0}" -f $hasRemote)
  Write-Host ("MCP_TOKEN_ENV_REFERENCE_OK={0}" -f $hasEnv)
  Write-Host ("MCP_HTTPS_URL_PRESENT={0}" -f $hasHttps)
  foreach ($name in @('wildberries','ozon','ozon-perf')) {
    $present = $cfg -match ("(?m)^\[mcp_servers\." + [regex]::Escape($name) + "\]")
    Write-Host ("LOCAL_MCP_{0}_PRESENT={1}" -f ($name -replace '-','_').ToUpperInvariant(),$present)
  }
}

$codex = Get-Command codex -ErrorAction SilentlyContinue
Write-Host ("CODEX_COMMAND_PRESENT={0}" -f [bool]$codex)
if ($codex) {
  Write-Host ("CODEX_PATH={0}" -f $codex.Source)
  & $codex.Source --version 2>&1 | ForEach-Object { Write-Host ("CODEX_VERSION={0}" -f $_) }
  Write-Host '--- CODEX_MCP_LIST ---'
  & $codex.Source mcp list 2>&1 | ForEach-Object {
    $line = [string]$_
    if ($line -match '(?i)token|bearer|secret') { $line = '[REDACTED_SENSITIVE_LINE]' }
    Write-Host $line
  }
}

$roots = @(
  (Join-Path $env:USERPROFILE 'Google Drive'),
  (Join-Path $env:USERPROFILE 'My Drive'),
  'G:\My Drive',
  'G:\Мой диск',
  'G:\Shared drives'
) | Where-Object { $_ -and (Test-Path $_) }
$target = $null
foreach ($root in $roots) {
  $candidate = Get-ChildItem -Path $root -Directory -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.Name -eq 'marketplaces-mcp-only' } | Select-Object -First 1
  if ($candidate) { $target = $candidate.FullName; break }
}
Write-Host ("MCP_ONLY_PROJECT_FOUND={0}" -f [bool]$target)
if ($target) {
  Write-Host ("MCP_ONLY_PROJECT_PATH={0}" -f $target)
  Write-Host ("AGENTS_PRESENT={0}" -f (Test-Path (Join-Path $target 'AGENTS.md')))
}
Write-Host '=== MARKETPLACES_CODEX_DIAG_END ==='
exit 0
