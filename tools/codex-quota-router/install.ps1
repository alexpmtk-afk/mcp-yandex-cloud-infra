param(
  [switch]$SkipUsageMonitor,
  [switch]$SkipDefaultModel
)
$ErrorActionPreference = 'Stop'
$Source = Split-Path -Parent $MyInvocation.MyCommand.Path
$CodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME '.codex' }
$InstallDir = Join-Path $CodexHome 'quota-router'
$HooksFile = Join-Path $CodexHome 'hooks.json'
$ConfigFile = Join-Path $CodexHome 'config.toml'
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Copy-Item (Join-Path $Source 'bin') $InstallDir -Recurse -Force
Copy-Item (Join-Path $Source 'lib') $InstallDir -Recurse -Force
Copy-Item (Join-Path $Source 'test') $InstallDir -Recurse -Force
Copy-Item (Join-Path $Source 'policy.json') $InstallDir -Force

# Back up existing global hook configuration.
if (Test-Path $HooksFile) {
  $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
  Copy-Item $HooksFile "$HooksFile.bak.$stamp" -Force
  $root = Get-Content $HooksFile -Raw | ConvertFrom-Json
} else {
  $root = [pscustomobject]@{ hooks = [pscustomobject]@{} }
}
if (-not $root.hooks) { $root | Add-Member -NotePropertyName hooks -NotePropertyValue ([pscustomobject]@{}) }

function Ensure-Event($name) {
  $p = $root.hooks.PSObject.Properties[$name]
  if (-not $p) { $root.hooks | Add-Member -NotePropertyName $name -NotePropertyValue @() }
}
function Remove-QuotaRouter($groups) {
  $out = @()
  foreach ($g in @($groups)) {
    $keep = $true
    foreach ($h in @($g.hooks)) {
      if ($h.command -and ($h.command -match 'quota-router[\\/].*(quota-router|usage-snapshot)\.js')) { $keep = $false }
    }
    if ($keep) { $out += $g }
  }
  return ,$out
}
Ensure-Event 'UserPromptSubmit'; Ensure-Event 'Stop'
$root.hooks.UserPromptSubmit = Remove-QuotaRouter $root.hooks.UserPromptSubmit
$root.hooks.Stop = Remove-QuotaRouter $root.hooks.Stop
$routerCmd = 'node "' + (Join-Path $InstallDir 'bin\quota-router.js') + '"'
$snapCmd = 'node "' + (Join-Path $InstallDir 'bin\usage-snapshot.js') + '"'
$root.hooks.UserPromptSubmit += [pscustomobject]@{ hooks = @([pscustomobject]@{type='command';command=$routerCmd;timeout=10;statusMessage='Quota Router preflight'}) }
$root.hooks.Stop += [pscustomobject]@{ hooks = @([pscustomobject]@{type='command';command=$snapCmd;timeout=10;statusMessage='Saving quota snapshot'}) }
$root | ConvertTo-Json -Depth 12 | Set-Content -Path $HooksFile -Encoding UTF8

# Hooks are enabled by default in current Codex. If config explicitly disables them, turn them back on.
if (Test-Path $ConfigFile) {
  $cfg = Get-Content $ConfigFile -Raw
  if ($cfg -match '(?ms)^\[features\].*?^hooks\s*=\s*false\s*$') {
    $cfg = [regex]::Replace($cfg, '(?m)^hooks\s*=\s*false\s*$', 'hooks = true', 1)
    Set-Content $ConfigFile $cfg -Encoding UTF8
  }
}

if (-not $SkipDefaultModel) {
  if (-not (Test-Path $ConfigFile)) { New-Item -ItemType File -Path $ConfigFile -Force | Out-Null }
  $cfg = Get-Content $ConfigFile -Raw
  function Set-TopLevelTomlKey([string]$text, [string]$key, [string]$value) {
    $lines = @($text -split "`r?`n", 0, 'RegexMatch')
    $firstTable = $lines.Count
    for ($i=0; $i -lt $lines.Count; $i++) { if ($lines[$i] -match '^\s*\[') { $firstTable=$i; break } }
    $found=$false
    for ($i=0; $i -lt $firstTable; $i++) {
      if ($lines[$i] -match ('^\s*' + [regex]::Escape($key) + '\s*=')) { $lines[$i] = "$key = $value"; $found=$true; break }
    }
    if (-not $found) {
      $before = if ($firstTable -gt 0) { @($lines[0..($firstTable-1)]) } else { @() }
      $after = if ($firstTable -lt $lines.Count) { @($lines[$firstTable..($lines.Count-1)]) } else { @() }
      $lines = @("$key = $value") + $before + $after
    }
    return ($lines -join "`r`n")
  }
  $cfg = Set-TopLevelTomlKey $cfg 'model' '"gpt-5.6-luna"'
  $cfg = Set-TopLevelTomlKey $cfg 'model_reasoning_effort' '"low"'
  Set-Content $ConfigFile $cfg -Encoding UTF8
}

if (-not $SkipUsageMonitor) {
  $plugin = Join-Path $CodexHome 'plugins\codex-usage-monitor'
  if (Get-Command git -ErrorAction SilentlyContinue) {
    if (Test-Path (Join-Path $plugin '.git')) { & git -C $plugin pull --ff-only | Out-Host }
    elseif (-not (Test-Path $plugin)) { & git clone --depth 1 https://github.com/harveyxiacn/codex-usage-monitor.git $plugin | Out-Host }
  } else { Write-Warning 'git not found; codex-usage-monitor not installed. Router still works from local Codex JSONL.' }
}

& node (Join-Path $InstallDir 'test\router.test.js') 2>$null
Write-Host ''
Write-Host 'CODEX QUOTA ROUTER installed.'
Write-Host "Codex home: $CodexHome"
Write-Host "Hooks: $HooksFile"
Write-Host 'Restart Codex/ChatGPT Desktop, then open /hooks and trust the new user hooks.'
Write-Host 'Default route: gpt-5.6-luna / low.'
Write-Host 'Emergency bypass marker: QUOTA_FORCE'
