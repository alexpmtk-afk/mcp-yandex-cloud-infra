# MANAGER_MP2_USER_LAUNCH_PROBE=YES
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

Write-Host '=== MANAGER_MP2_USER_LAUNCH_PROBE_BEGIN ==='
$interactiveUser = (Get-CimInstance Win32_ComputerSystem -ErrorAction Stop).UserName
Write-Host "INTERACTIVE_USER=$interactiveUser"
Write-Host "BRIDGE_IDENTITY=$([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)"

Write-Host '--- CODEX_DISCOVERY ---'
try {
  $c = Get-Command codex -ErrorAction Stop
  Write-Host "SERVICE_CODEX_FOUND=True PATH=$($c.Source)"
} catch { Write-Host 'SERVICE_CODEX_FOUND=False' }
foreach ($p in @(
  'C:\Program Files\nodejs\codex.cmd',
  'C:\Program Files\Codex\codex.exe',
  'C:\Users\user\AppData\Local\Microsoft\WindowsApps\codex.exe',
  'C:\Users\user\AppData\Roaming\npm\codex.ps1',
  'C:\Users\user\AppData\Roaming\npm\codex.cmd'
)) {
  try { $e = Test-Path -LiteralPath $p -ErrorAction Stop } catch { $e = $false }
  Write-Host "CODEX_CANDIDATE=$p EXISTS=$e"
}

$runtimeRoot = Join-Path $env:ProgramData 'ChatGPT-PK\manager-mp2-user-probe'
New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null
$marker = Join-Path $runtimeRoot 'marker.txt'
$script = Join-Path $runtimeRoot 'probe.ps1'
$taskName = 'ChatGPT-Manager-MP2-User-Probe'
if (Test-Path $marker) { Remove-Item $marker -Force }
$code = @'
$ErrorActionPreference = 'Stop'
$marker = 'C:\ProgramData\ChatGPT-PK\manager-mp2-user-probe\marker.txt'
"USER=$([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) SESSION=$((Get-Process -Id $PID).SessionId) HOME=$HOME" | Set-Content -LiteralPath $marker -Encoding ASCII
'@
[IO.File]::WriteAllText($script,$code,(New-Object System.Text.ASCIIEncoding))

try {
  try { Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue } catch {}
  $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`""
  $principal = New-ScheduledTaskPrincipal -UserId $interactiveUser -LogonType Interactive -RunLevel Limited
  $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 2) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
  try {
    Register-ScheduledTask -TaskName $taskName -Action $action -Principal $principal -Settings $settings -Force -ErrorAction Stop | Out-Null
    Write-Host 'USER_TASK_REGISTER=PASS'
    Start-ScheduledTask -TaskName $taskName -ErrorAction Stop
    Write-Host 'USER_TASK_START=PASS'
    $deadline=(Get-Date).AddSeconds(30)
    while((Get-Date)-lt $deadline -and -not (Test-Path $marker)){ Start-Sleep -Seconds 2 }
    if(Test-Path $marker){
      Write-Host 'USER_TASK_MARKER=PASS'
      Get-Content -Raw -LiteralPath $marker
    } else {
      $ti=Get-ScheduledTaskInfo -TaskName $taskName -ErrorAction SilentlyContinue
      Write-Host "USER_TASK_MARKER=FAIL LAST_RESULT=$($ti.LastTaskResult)"
    }
  } catch {
    Write-Host "USER_TASK_REGISTER_OR_START=FAIL TYPE=$($_.Exception.GetType().Name) MESSAGE=$($_.Exception.Message)"
  }
} finally {
  try { Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue } catch {}
  Remove-Item $script -Force -ErrorAction SilentlyContinue
  Remove-Item $marker -Force -ErrorAction SilentlyContinue
  try { Remove-Item $runtimeRoot -Force -ErrorAction SilentlyContinue } catch {}
}
Write-Host '=== MANAGER_MP2_USER_LAUNCH_PROBE_END ==='
