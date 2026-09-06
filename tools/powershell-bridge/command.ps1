$ErrorActionPreference = 'Continue'
$folderId = 'b1g0224nfivl9224dm96'
$vm = 'marketplace-card-monitor-ozon'

Write-Host '=== MARKETPLACE_CARD_MONITOR_DISCOVERY_BEGIN ==='
Write-Host "RUNNER_USER=$env:USERNAME"

$ycCandidates = @(
  'C:\Users\Win10_Game_OS\yandex-cloud\bin\yc.exe',
  'C:\Users\Win10_Game_OS\AppData\Local\Yandex\Cloud\yc.exe',
  'C:\Users\Win10_Game_OS\AppData\Local\Yandex\Cloud\bin\yc.exe',
  'C:\Program Files\Yandex.Cloud\bin\yc.exe'
)
$yc = $ycCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $yc) {
  $yc = Get-ChildItem 'C:\Users\Win10_Game_OS' -Filter yc.exe -File -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
}
if (-not $yc) { throw 'YC_EXE_NOT_FOUND' }
Write-Host "YC_EXE=$yc"
& $yc --version

# Use the already authenticated user profile explicitly, without changing other projects.
$env:YC_CONFIG_PROFILE = 'marketplace-card-monitor'
Write-Host '=== YC_CONFIG ==='
& $yc config list

Write-Host '=== VM_IN_PROJECT_FOLDER ==='
& $yc compute instance list --folder-id $folderId
Write-Host '=== NETWORKS ==='
& $yc vpc network list --folder-id $folderId
Write-Host '=== SUBNETS ==='
& $yc vpc subnet list --folder-id $folderId

$vmJson = & $yc compute instance get $vm --folder-id $folderId --format json 2>$null
if ($LASTEXITCODE -eq 0 -and $vmJson) {
  $obj = $vmJson | ConvertFrom-Json
  Write-Host "VM_FOUND=YES"
  Write-Host "VM_ID=$($obj.id)"
  Write-Host "VM_STATUS=$($obj.status)"
  Write-Host "VM_ZONE=$($obj.zone_id)"
  $nic = $obj.network_interfaces | Select-Object -First 1
  Write-Host "VM_INTERNAL_IP=$($nic.primary_v4_address.address)"
  Write-Host "VM_EXTERNAL_IP=$($nic.primary_v4_address.one_to_one_nat.address)"
} else {
  Write-Host 'VM_FOUND=NO'
}
Write-Host '=== MARKETPLACE_CARD_MONITOR_DISCOVERY_END ==='
