$ErrorActionPreference = 'Stop'
Write-Host 'BRIDGE_V2_WRITE_SANDBOX_BEGIN'
New-Item -LiteralPath 'C:\ProgramData\ChatGPT-PK\bridge-v2-sandbox' -ItemType Directory -Force
Set-Content -LiteralPath 'C:\ProgramData\ChatGPT-PK\bridge-v2-sandbox\smoke.txt' -Value 'bridge-v2-write-ok' -Encoding UTF8
Add-Content -LiteralPath 'C:\ProgramData\ChatGPT-PK\bridge-v2-sandbox\smoke.txt' -Value 'second-line' -Encoding UTF8
Get-Content -LiteralPath 'C:\ProgramData\ChatGPT-PK\bridge-v2-sandbox\smoke.txt'
Get-Item -LiteralPath 'C:\ProgramData\ChatGPT-PK\bridge-v2-sandbox\smoke.txt' | Select-Object FullName, Length
Write-Host 'BRIDGE_V2_WRITE_SANDBOX_END'
