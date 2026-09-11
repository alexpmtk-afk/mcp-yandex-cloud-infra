$ErrorActionPreference = 'Stop'
Write-Host 'BRIDGE_V2_WRITE_VERIFY_BEGIN'
Test-Path -LiteralPath 'C:\ProgramData\ChatGPT-PK\bridge-v2-sandbox\smoke.txt'
Get-Content -LiteralPath 'C:\ProgramData\ChatGPT-PK\bridge-v2-sandbox\smoke.txt'
Get-Item -LiteralPath 'C:\ProgramData\ChatGPT-PK\bridge-v2-sandbox\smoke.txt' | Select-Object FullName, Length, LastWriteTime
Write-Host 'BRIDGE_V2_WRITE_VERIFY_END'
