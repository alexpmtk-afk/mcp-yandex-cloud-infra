param([switch]$KeepFiles, [switch]$KeepUsageMonitor)
$ErrorActionPreference = 'Stop'
$CodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME '.codex' }
$HooksFile = Join-Path $CodexHome 'hooks.json'
$InstallDir = Join-Path $CodexHome 'quota-router'
if (Test-Path $HooksFile) {
  $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
  Copy-Item $HooksFile "$HooksFile.bak.$stamp" -Force
  $root = Get-Content $HooksFile -Raw | ConvertFrom-Json
  function Filter-Groups($groups) {
    $out=@()
    foreach ($g in @($groups)) {
      $keep=$true
      foreach ($h in @($g.hooks)) {
        if ($h.command -and ($h.command -match 'quota-router[\\/].*(quota-router|usage-snapshot)\.js')) { $keep=$false }
      }
      if ($keep) { $out += $g }
    }
    return ,$out
  }
  if ($root.hooks -and $root.hooks.UserPromptSubmit) { $root.hooks.UserPromptSubmit = Filter-Groups $root.hooks.UserPromptSubmit }
  if ($root.hooks -and $root.hooks.Stop) { $root.hooks.Stop = Filter-Groups $root.hooks.Stop }
  $root | ConvertTo-Json -Depth 12 | Set-Content $HooksFile -Encoding UTF8
}
if (-not $KeepFiles -and (Test-Path $InstallDir)) { Remove-Item $InstallDir -Recurse -Force }
if (-not $KeepUsageMonitor) {
  $plugin = Join-Path $CodexHome 'plugins\codex-usage-monitor'
  if (Test-Path $plugin) { Remove-Item $plugin -Recurse -Force }
}
Write-Host 'Codex Quota Router hooks removed. Restart Codex.'
