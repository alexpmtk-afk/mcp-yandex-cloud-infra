$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
Write-Host '=== WORK_GPT_POWERSHELL_AUDIT_BEGIN ==='
Write-Host ("HOSTNAME={0}" -f $env:COMPUTERNAME)
try { Write-Host ("INTERACTIVE_USER={0}" -f (Get-CimInstance Win32_ComputerSystem).UserName) } catch {}
Write-Host ("RUNNER_IDENTITY={0}" -f ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name))

foreach($name in @('node','npm.cmd','npx.cmd')){
  $cmd = Get-Command $name -ErrorAction SilentlyContinue
  if($cmd){
    Write-Host ("CMD={0} FOUND=True PATH={1}" -f $name,$cmd.Source)
    try { $ver = & $cmd.Source --version 2>&1 | Out-String; Write-Host ("CMD={0} VERSION={1}" -f $name,$ver.Trim()) } catch {}
  } else { Write-Host ("CMD={0} FOUND=False" -f $name) }
}

$paths = @(
  'C:\ProgramData\ChatGPT-PowerShell',
  'C:\ProgramData\ChatGPT-PowerShell\scripts',
  'C:\ProgramData\ChatGPT-PowerShell\config',
  'C:\ProgramData\ChatGPT-PowerShell\logs',
  'C:\ProgramData\ChatGPT-PowerShell\state',
  'C:\ProgramData\ChatGPT-PK',
  'C:\ProgramData\ChatGPT-PK\powershell-work-runner'
)
foreach($p in $paths){ Write-Host ("PATH={0} EXISTS={1}" -f $p,(Test-Path -LiteralPath $p)) }

try {
  $t = Get-ScheduledTask -TaskName 'ChatGPT-PowerShell-DesktopCommander' -ErrorAction SilentlyContinue
  if($t){
    Write-Host 'TASK=ChatGPT-PowerShell-DesktopCommander EXISTS=True'
    Write-Host ("TASK_STATE={0}" -f $t.State)
    Write-Host ("TASK_USER={0}" -f $t.Principal.UserId)
    Write-Host ("TASK_RUNLEVEL={0}" -f $t.Principal.RunLevel)
    Write-Host ("TASK_ACTION={0} {1}" -f $t.Actions.Execute,$t.Actions.Arguments)
    Write-Host ("TASK_EXECUTION_LIMIT={0}" -f $t.Settings.ExecutionTimeLimit)
    Write-Host ("TASK_MULTIPLE_INSTANCES={0}" -f $t.Settings.MultipleInstances)
    $ti = Get-ScheduledTaskInfo -TaskName 'ChatGPT-PowerShell-DesktopCommander' -ErrorAction SilentlyContinue
    if($ti){ Write-Host ("TASK_LAST_RESULT={0}" -f $ti.LastTaskResult) }
  } else { Write-Host 'TASK=ChatGPT-PowerShell-DesktopCommander EXISTS=False' }
} catch { Write-Host ("TASK_CHECK_ERROR={0}" -f $_.Exception.Message) }

try {
  Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*desktop-commander*' } | ForEach-Object {
    Write-Host ("DC_PROCESS PID={0} NAME={1} CMD={2}" -f $_.ProcessId,$_.Name,$_.CommandLine)
  }
} catch {}

try {
  Get-CimInstance Win32_Service | Where-Object { $_.Name -like 'actions.runner.*' } | ForEach-Object {
    Write-Host ("RUNNER_SERVICE NAME={0} STATE={1} STARTMODE={2} ACCOUNT={3} PATH={4}" -f $_.Name,$_.State,$_.StartMode,$_.StartName,$_.PathName)
  }
} catch {}

try {
  $interactive = (Get-CimInstance Win32_ComputerSystem).UserName
  if($interactive -and $interactive.Contains('\\')){
    $u = $interactive.Split('\\')[-1]
    $device = "C:\Users\$u\.desktop-commander-device\device.json"
    Write-Host ("DC_DEVICE_FILE_FOR_INTERACTIVE_USER EXISTS={0}" -f (Test-Path -LiteralPath $device))
  }
} catch {}
Write-Host '=== WORK_GPT_POWERSHELL_AUDIT_END ==='
