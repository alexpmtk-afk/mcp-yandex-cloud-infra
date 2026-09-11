$ErrorActionPreference = 'Stop'
Write-Host 'OUTSIDE_ROOT_BODY_SHOULD_NOT_EXECUTE'
Set-Content -LiteralPath 'C:\Windows\Temp\bridge-v2-should-not-exist.txt' -Value 'blocked' -Encoding UTF8
