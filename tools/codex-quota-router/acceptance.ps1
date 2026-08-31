param()
$ErrorActionPreference = 'Stop'
$CodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME '.codex' }
$InstallDir = Join-Path $CodexHome 'quota-router'
$HooksFile = Join-Path $CodexHome 'hooks.json'
$ConfigFile = Join-Path $CodexHome 'config.toml'

function Pass([string]$name) { Write-Host "PASS  $name" }
function Fail([string]$name, [string]$detail) { throw "FAIL  $name :: $detail" }

if (-not (Get-Command node -ErrorAction SilentlyContinue)) { Fail 'node_available' 'Node.js is required by v0.1 router.' }
Pass 'node_available'

foreach ($p in @(
  (Join-Path $InstallDir 'bin\quota-router.js'),
  (Join-Path $InstallDir 'bin\usage-snapshot.js'),
  (Join-Path $InstallDir 'bin\status.js'),
  (Join-Path $InstallDir 'lib\router-core.js'),
  (Join-Path $InstallDir 'lib\usage.js'),
  (Join-Path $InstallDir 'policy.json'),
  (Join-Path $InstallDir 'test\router.test.js')
)) { if (-not (Test-Path $p)) { Fail 'installed_files' "Missing $p" } }
Pass 'installed_files'

if (-not (Test-Path $HooksFile)) { Fail 'hooks_file' "Missing $HooksFile" }
$hooksRaw = Get-Content $HooksFile -Raw
if ($hooksRaw -notmatch 'quota-router\.js' -or $hooksRaw -notmatch 'usage-snapshot\.js') { Fail 'global_hooks_registered' 'Router hooks not found.' }
Pass 'global_hooks_registered'

if (-not (Test-Path $ConfigFile)) { Fail 'config_file' "Missing $ConfigFile" }
$cfg = Get-Content $ConfigFile -Raw
$top = ($cfg -split '(?m)^\s*\[')[0]
if ($top -notmatch '(?m)^\s*model\s*=\s*"gpt-5\.6-luna"\s*$') { Fail 'default_model_luna' 'Top-level model is not gpt-5.6-luna.' }
if ($top -notmatch '(?m)^\s*model_reasoning_effort\s*=\s*"low"\s*$') { Fail 'default_reasoning_low' 'Top-level reasoning effort is not low.' }
Pass 'default_model_luna'
Pass 'default_reasoning_low'

& node (Join-Path $InstallDir 'test\router.test.js')
if ($LASTEXITCODE -ne 0) { Fail 'unit_tests' "exit=$LASTEXITCODE" }
Pass 'unit_tests'

$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("codex-quota-router-acceptance-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
try {
  $transcript = Join-Path $tmp 'session.jsonl'
  $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
  $reset5 = $now + 14400
  $reset7 = $now + 432000
  $l1 = @{ timestamp=(Get-Date).ToUniversalTime().ToString('o'); type='turn_context'; payload=@{ turn_id='t0'; model='gpt-5.6-luna'; effort='low'; model_context_window=1050000 } } | ConvertTo-Json -Compress -Depth 8
  $l2 = @{ timestamp=(Get-Date).ToUniversalTime().ToString('o'); type='event_msg'; payload=@{ type='token_count'; info=@{ total_token_usage=@{ input_tokens=1000; cached_input_tokens=500; output_tokens=100; reasoning_output_tokens=20; total_tokens=1120 }; last_token_usage=@{ input_tokens=1000; cached_input_tokens=500; output_tokens=100; reasoning_output_tokens=20; total_tokens=1120 } }; rate_limits=@{ plan_type='plus'; primary=@{ used_percent=20; window_minutes=300; resets_at=$reset5 }; secondary=@{ used_percent=10; window_minutes=10080; resets_at=$reset7 } } } } | ConvertTo-Json -Compress -Depth 12
  Set-Content -Path $transcript -Value @($l1,$l2) -Encoding UTF8
  $router = Join-Path $InstallDir 'bin\quota-router.js'

  $simple = @{ session_id='acceptance'; turn_id='simple'; transcript_path=$transcript; cwd=$tmp; hook_event_name='UserPromptSubmit'; model='gpt-5.6-luna'; permission_mode='default'; prompt='Show the latest commit and workflow status' } | ConvertTo-Json -Compress
  $simpleJson = ($simple | & node $router) | ConvertFrom-Json
  if ($simpleJson.decision -eq 'block' -or -not $simpleJson.hookSpecificOutput.additionalContext) { Fail 'simple_preflight' 'Simple Luna task was not allowed.' }
  Pass 'simple_preflight_luna_allowed'

  $heavy = @{ session_id='acceptance'; turn_id='heavy'; transcript_path=$transcript; cwd=$tmp; hook_event_name='UserPromptSubmit'; model='gpt-5.6-luna'; permission_mode='default'; prompt='Find and fix a complex MCP integration bug across GitHub, Yandex Cloud, and API, then run integration tests' } | ConvertTo-Json -Compress
  $heavyJson = ($heavy | & node $router) | ConvertFrom-Json
  if ($heavyJson.decision -ne 'block' -or $heavyJson.reason -notmatch 'gpt-5\.6-(terra|sol)') { Fail 'heavy_preflight' 'Heavy Luna task did not route upward.' }
  Pass 'heavy_preflight_routes_up'

  $history = Join-Path $CodexHome 'quota-router\history.jsonl'
  if (-not (Test-Path $history)) { Fail 'history_written' "Missing $history" }
  if (((Get-Content $history -Tail 20) -join "`n") -notmatch '"event":"preflight"') { Fail 'history_written' 'No preflight event.' }
  Pass 'history_written'

  Write-Host ''
  Write-Host 'CODEX_QUOTA_ROUTER_ACCEPTANCE=PASS'
  Write-Host "CodexHome=$CodexHome"
  Write-Host "History=$history"
}
finally { if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force } }
