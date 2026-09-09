$ErrorActionPreference='Continue'
Write-Host '=== WORK_GPT_POWERSHELL_AUDIT2_BEGIN ==='
foreach($p in @(
 'C:\Program Files\nodejs\node.exe',
 'C:\Program Files\nodejs\npm.cmd',
 'C:\Program Files\nodejs\npx.cmd',
 'C:\Users\user\.desktop-commander-device\device.json',
 'C:\Users\user\AppData\Roaming\npm\npx.cmd',
 'C:\Users\user\AppData\Local\Programs\nodejs\node.exe'
)){ Write-Host ("PATH={0} EXISTS={1}" -f $p,(Test-Path -LiteralPath $p)) }
try {
 $wg='C:\Users\user\AppData\Local\Microsoft\WindowsApps\winget.exe'
 Write-Host ("WINGET_PATH_EXISTS={0}" -f (Test-Path -LiteralPath $wg))
} catch {}
try {
 Get-ScheduledTask | Where-Object { $_.TaskName -like '*DesktopCommander*' -or $_.TaskName -like '*ChatGPT-PowerShell*' } | ForEach-Object { Write-Host ("TASK NAME={0} STATE={1} USER={2}" -f $_.TaskName,$_.State,$_.Principal.UserId) }
} catch {}
Write-Host '=== WORK_GPT_POWERSHELL_AUDIT2_END ==='
