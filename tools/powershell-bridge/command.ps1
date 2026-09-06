$ErrorActionPreference = 'Stop'
$profile = 'marketplace-card-monitor'
$folderId = 'b1g0224nfivl9224dm96'
$zone = 'ru-central1-d'
$network = 'marketplace-card-monitor-net'
$subnet = 'marketplace-card-monitor-subnet-d'
$vm = 'marketplace-card-monitor-ozon'

Write-Host '=== MARKETPLACE_CARD_MONITOR_YC_DEPLOY_BEGIN ==='
yc config profile activate $profile
Write-Host "PROFILE=$profile"
Write-Host "FOLDER=$folderId"

# Network
$netId = (yc vpc network get $network --folder-id $folderId --format json 2>$null | ConvertFrom-Json).id
if (-not $netId) {
  yc vpc network create --name $network --folder-id $folderId | Out-Host
  $netId = (yc vpc network get $network --folder-id $folderId --format json | ConvertFrom-Json).id
}
Write-Host "NETWORK_ID=$netId"

# Subnet
$subnetId = (yc vpc subnet get $subnet --folder-id $folderId --format json 2>$null | ConvertFrom-Json).id
if (-not $subnetId) {
  yc vpc subnet create --name $subnet --folder-id $folderId --zone $zone --network-id $netId --range 10.77.0.0/24 | Out-Host
  $subnetId = (yc vpc subnet get $subnet --folder-id $folderId --format json | ConvertFrom-Json).id
}
Write-Host "SUBNET_ID=$subnetId"

# Resolve current Ubuntu 24.04 LTS image from public images folder.
$imageId = yc compute image get-latest-from-family ubuntu-2404-lts --folder-id standard-images --format json | ConvertFrom-Json | Select-Object -ExpandProperty id
if (-not $imageId) { throw 'Ubuntu 24.04 LTS image not found' }
Write-Host "IMAGE_ID=$imageId"

# VM: intentionally modest feasibility-gate size. NAT IP only for the first Ozon test.
$vmId = (yc compute instance get $vm --folder-id $folderId --format json 2>$null | ConvertFrom-Json).id
if (-not $vmId) {
  yc compute instance create `
    --name $vm `
    --folder-id $folderId `
    --zone $zone `
    --platform standard-v3 `
    --cores 2 `
    --memory 4GB `
    --core-fraction 20 `
    --create-boot-disk "image-id=$imageId,size=20,type=network-hdd" `
    --network-interface "subnet-id=$subnetId,nat-ip-version=ipv4" `
    --metadata serial-port-enable=1 `
    --ssh-key "$env:USERPROFILE\.ssh\id_ed25519.pub" | Out-Host
}

Write-Host '=== VM ==='
yc compute instance get $vm --folder-id $folderId --format yaml
Write-Host '=== NETWORKS ==='
yc vpc network list --folder-id $folderId
Write-Host '=== SUBNETS ==='
yc vpc subnet list --folder-id $folderId
Write-Host '=== MARKETPLACE_CARD_MONITOR_YC_DEPLOY_END ==='
