$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

Write-Host '=== MARKETPLACES_NATIVE_CODEX_E2E ==='

$project = 'X:\Мой диск\Marketplaces\MCP отчеты МП\marketplaces-mcp-only'
$config = Join-Path $project '.codex\config.toml'
$tokenName = 'MARKETPLACES_MCP_TOKEN'
$token = [Environment]::GetEnvironmentVariable($tokenName, 'User')

if (-not (Test-Path -LiteralPath $project -PathType Container)) {
    throw "Acceptance project not found: $project"
}
if (-not (Test-Path -LiteralPath $config -PathType Leaf)) {
    throw "Project MCP config not found: $config"
}
if ([string]::IsNullOrWhiteSpace($token)) {
    throw 'MARKETPLACES_MCP_TOKEN is not configured at User scope.'
}

Write-Host 'PROJECT_EXISTS=YES'
Write-Host 'USER_TOKEN_CONFIGURED=YES'

$configText = Get-Content -LiteralPath $config -Raw -Encoding UTF8
$remoteEnabled = $configText -match '(?ms)\[mcp_servers\.marketplaces-yandex\].*?enabled\s*=\s*true'
$wbDisabled = $configText -match '(?ms)\[mcp_servers\.wildberries\].*?enabled\s*=\s*false'
$ozonDisabled = $configText -match '(?ms)\[mcp_servers\.ozon\].*?enabled\s*=\s*false'
$perfDisabled = $configText -match '(?ms)\[mcp_servers\.ozon-perf\].*?enabled\s*=\s*false'
if (-not ($remoteEnabled -and $wbDisabled -and $ozonDisabled -and $perfDisabled)) {
    throw 'Project MCP isolation config is not in the required remote-only state.'
}
Write-Host 'PROJECT_REMOTE_ONLY_CONFIG=PASS'

Set-Location -LiteralPath $project
Write-Host "CODEX_VERSION=$(& codex --version)"

$env:MARKETPLACES_MCP_TOKEN = $token
try {
    Write-Host '--- MCP REGISTRATION ---'
    & codex mcp get marketplaces-yandex
    if ($LASTEXITCODE -ne 0) { throw 'codex mcp get marketplaces-yandex failed.' }

    $prompt = 'Покажи один существующий товар Ozon из моего кабинета.'
    $out = Join-Path $env:RUNNER_TEMP 'marketplaces-native-e2e.jsonl'
    Remove-Item -LiteralPath $out -Force -ErrorAction SilentlyContinue

    Write-Host 'NATURAL_LANGUAGE_PROMPT=Покажи один существующий товар Ozon из моего кабинета.'
    & codex exec --ephemeral --skip-git-repo-check --sandbox read-only --json $prompt 2>&1 | Tee-Object -FilePath $out
    $exit = $LASTEXITCODE
    if ($exit -ne 0) { throw "codex exec failed with exit code $exit" }

    $raw = Get-Content -LiteralPath $out -Raw -Encoding UTF8
    $usedRemote = $raw -match 'marketplaces-yandex'
    $usedOzonProducts = $raw -match 'ozon_get_products'
    $sourceEvidence = $raw -match 'Источник:\s*MCP marketplaces-yandex'
    $toolEvidence = $raw -match 'Инструмент:\s*ozon_get_products'

    Write-Host "REMOTE_MCP_EVIDENCE=$usedRemote"
    Write-Host "OZON_GET_PRODUCTS_EVIDENCE=$usedOzonProducts"
    Write-Host "SOURCE_LINE_EVIDENCE=$sourceEvidence"
    Write-Host "TOOL_LINE_EVIDENCE=$toolEvidence"

    if (-not $usedRemote) { throw 'Native Codex output did not prove marketplaces-yandex usage.' }
    if (-not $usedOzonProducts) { throw 'Native Codex did not prove automatic selection of ozon_get_products.' }
    if (-not $sourceEvidence) { throw 'Final answer did not include the required MCP source evidence.' }
    if (-not $toolEvidence) { throw 'Final answer did not include the actual MCP tool evidence.' }

    Write-Host 'NATIVE_NATURAL_LANGUAGE_E2E=PASS'
}
finally {
    Remove-Item Env:MARKETPLACES_MCP_TOKEN -ErrorAction SilentlyContinue
    $token = $null
}
