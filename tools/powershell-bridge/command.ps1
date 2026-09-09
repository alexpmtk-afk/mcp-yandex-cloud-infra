$ErrorActionPreference='Continue'
Write-Host '=== WORK_POST_INSTALL_AUDIT_BEGIN ==='
$checks=@(
 'C:\Program Files\nodejs\node.exe',
 'C:\Program Files\nodejs\npm.cmd',
 'C:\Program Files\nodejs\npx.cmd',
 'C:\Users\user\.desktop-commander-device\device.json',
 'C:\ProgramData\ChatGPT-PowerShell',
 'C:\ProgramData\ChatGPT-PowerShell\scripts',
 'C:\ProgramData\ChatGPT-PowerShell\config',
 'C:\ProgramData\ChatGPT-PowerShell\logs',
 'C:\ProgramData\ChatGPT-PowerShell\state'
)
foreach($p in $checks){ Write-Host ("PATH={0} EXISTS={1}" -f $p,(Test-Path -LiteralPath $p)) }
if(Test-Path 'C:\Program Files\nodejs\node.exe'){ try { Write-Host ('NODE_VERSION=' + (& 'C:\Program Files\nodejs\node.exe' --version)) } catch {} }
if(Test-Path 'C:\Program Files\nodejs\npm.cmd'){ try { Write-Host ('NPM_VERSION=' + (& 'C:\Program Files\nodejs\npm.cmd' --version)) } catch {} }
if(Test-Path 'C:\Program Files\nodejs\npx.cmd'){ try { Write-Host ('NPX_VERSION=' + (& 'C:\Program Files\nodejs\npx.cmd' --version)) } catch {} }
try {
 Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*desktop-commander*remote*' } | ForEach-Object { Write-Host ("DC_REMOTE_PROCESS PID={0} USER_SCOPE=UNKNOWN NAME={1}" -f $_.ProcessId,$_.Name) }
} catch {}
try {
 $t=Get-ScheduledTask -TaskName 'ChatGPT-PowerShell-DesktopCommander' -ErrorAction SilentlyContinue
 if($t){ Write-Host ('TASK_EXISTS=True STATE=' + $t.State) } else { Write-Host 'TASK_EXISTS=False' }
} catch { Write-Host 'TASK_EXISTS=CHECK_FAILED' }
Write-Host '=== WORK_POST_INSTALL_AUDIT_END ==='
