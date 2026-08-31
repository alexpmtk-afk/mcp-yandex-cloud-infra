# One-time Windows setup for Codex -> Yandex Marketplace MCP.
# No secret values are stored in this script or repository.
# The MCP bearer is read directly from Yandex Lockbox after the user authenticates to Yandex Cloud.

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$CloudId = 'b1gi4pr9msenirafh2c7'
$FolderName = 'marketplaces-mcp-test'
$SecretName = 'marketplaces-mcp-api-credentials'
$SecretKey = 'mcp_bearer_token'
$McpName = 'marketplaces-yandex'
$McpUrl = 'https://d5deoa6cl4irtmkp5ad6.bu9mdbe1.apigw.yandexcloud.net/mcp'
$TokenEnvName = 'MARKETPLACES_MCP_TOKEN'

function Write-Step([string]$Text) {
    Write-Host "[Codex MCP] $Text"
}

function Ensure-YcCli {
    $yc = Get-Command yc -ErrorAction SilentlyContinue
    if ($yc) { return $yc.Source }

    Write-Step 'Yandex Cloud CLI is not installed. Installing from the official Yandex Cloud installer...'
    $installer = (New-Object System.Net.WebClient).DownloadString('https://storage.yandexcloud.net/yandexcloud-yc/install.ps1')
    Invoke-Expression $installer

    $candidate = Join-Path $HOME 'yandex-cloud\bin\yc.exe'
    if (Test-Path $candidate) {
        $env:PATH = "$(Split-Path $candidate);$env:PATH"
        return $candidate
    }
    $yc = Get-Command yc -ErrorAction SilentlyContinue
    if (-not $yc) { throw 'Yandex Cloud CLI installation finished, but yc.exe was not found.' }
    return $yc.Source
}

function Ensure-YandexAuth([string]$YcPath) {
    & $YcPath resource-manager cloud get --id $CloudId --format json --no-user-output *> $null
    if ($LASTEXITCODE -eq 0) { return }

    Write-Step 'Yandex authentication is required. A browser window will open; sign in to the Yandex account that owns this cloud.'
    & $YcPath init --cloud-id $CloudId
    if ($LASTEXITCODE -ne 0) { throw 'Yandex Cloud authentication was not completed.' }
}

function Read-McpBearer([string]$YcPath) {
    # --key returns only the requested value. It is captured in memory and never printed.
    $value = & $YcPath lockbox payload get --name $SecretName --key $SecretKey --cloud-id $CloudId --folder-name $FolderName --no-user-output 2>$null
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($value)) {
        throw 'Could not read the MCP bearer from Yandex Lockbox. The signed-in Yandex account needs permission to read this secret.'
    }
    return ($value | Out-String).Trim()
}

function Set-CodexConfig([string]$Token) {
    # Codex officially supports bearer_token_env_var for Streamable HTTP MCP.
    # Store the MCP-only bearer in the Windows user environment, never in config.toml.
    [Environment]::SetEnvironmentVariable($TokenEnvName, $Token, 'User')
    Set-Item -Path "Env:$TokenEnvName" -Value $Token

    $codexDir = Join-Path $HOME '.codex'
    $configPath = Join-Path $codexDir 'config.toml'
    New-Item -ItemType Directory -Force -Path $codexDir | Out-Null
    if (-not (Test-Path $configPath)) { New-Item -ItemType File -Path $configPath | Out-Null }

    $content = Get-Content -Raw -Path $configPath
    if ($null -eq $content) { $content = '' }

    $escapedName = [regex]::Escape($McpName)
    $pattern = "(?ms)^\[mcp_servers\.$escapedName\]\r?\n.*?(?=^\[|\z)"
    $content = [regex]::Replace($content, $pattern, '')
    $content = $content.TrimEnd()

    $block = @"
[mcp_servers.$McpName]
url = "$McpUrl"
bearer_token_env_var = "$TokenEnvName"
required = true
startup_timeout_sec = 30
tool_timeout_sec = 120
default_tools_approval_mode = "writes"
"@

    if ($content.Length -gt 0) { $content += "`r`n`r`n" }
    $content += $block.Trim() + "`r`n"
    Set-Content -Path $configPath -Value $content -Encoding UTF8

    # Safety check: secret value must not be written into config.toml.
    $written = Get-Content -Raw -Path $configPath
    if ($written.Contains($Token)) {
        throw 'Safety check failed: secret value appeared in config.toml.'
    }
    if (-not $written.Contains("bearer_token_env_var = `"$TokenEnvName`"")) {
        throw 'Codex MCP configuration was not written correctly.'
    }
    return $configPath
}

function Test-Mcp([string]$Token) {
    $headers = @{
        Authorization = "Bearer $Token"
        Accept = 'application/json, text/event-stream'
        'Content-Type' = 'application/json'
    }
    $body = @{
        jsonrpc = '2.0'
        id = 1
        method = 'initialize'
        params = @{
            protocolVersion = '2025-06-18'
            capabilities = @{}
            clientInfo = @{ name = 'codex-windows-setup'; version = '1' }
        }
    } | ConvertTo-Json -Depth 8 -Compress

    $response = Invoke-WebRequest -Uri $McpUrl -Method Post -Headers $headers -Body $body -UseBasicParsing -TimeoutSec 30
    if ($response.StatusCode -ne 200) { throw "MCP initialize failed with HTTP $($response.StatusCode)." }
    $session = $response.Headers['mcp-session-id']
    if (-not $session) { throw 'MCP initialize returned no session id.' }
    Write-Step 'Direct MCP initialize: PASS.'
}

$ycPath = Ensure-YcCli
Ensure-YandexAuth -YcPath $ycPath
Write-Step 'Reading the MCP-only bearer from Yandex Lockbox without printing it...'
$bearer = Read-McpBearer -YcPath $ycPath
try {
    $configPath = Set-CodexConfig -Token $bearer
    Test-Mcp -Token $bearer
    Write-Step "Codex configuration: $configPath"
    Write-Step 'Setup complete. Fully exit and reopen the ChatGPT desktop app / Codex so it inherits the new Windows environment variable.'
    Write-Step 'Then type /mcp. The server marketplaces-yandex should be enabled.'
} finally {
    # Remove the PowerShell-process copy; the persistent user environment copy remains for Codex.
    Remove-Item -Path "Env:$TokenEnvName" -ErrorAction SilentlyContinue
    $bearer = $null
}
