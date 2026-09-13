$ErrorActionPreference='Stop'
Write-Host '=== MARKETPLACE_ADMIN_PROBE_BEGIN ==='
Write-Host ('HOST=' + $env:COMPUTERNAME)
Write-Host ('IDENTITY=' + [Security.Principal.WindowsIdentity]::GetCurrent().Name)
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
Write-Host ('ELEVATED=' + $isAdmin)
$cs=Get-CimInstance Win32_ComputerSystem
Write-Host ('INTERACTIVE_USER=' + [string]$cs.UserName)
try {
  $t=Get-ScheduledTask -TaskName 'MarketplaceCardMonitor-UserNode-Canonical' -ErrorAction Stop
  Write-Host ('CANONICAL_TASK_STATE=' + $t.State)
} catch {
  Write-Host 'CANONICAL_TASK=MISSING'
}
Write-Host '=== MARKETPLACE_ADMIN_PROBE_END ==='
exit 0
