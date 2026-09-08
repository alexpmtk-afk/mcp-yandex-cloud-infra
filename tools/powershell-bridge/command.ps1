# MANAGER_MP2_BOOTSTRAP_PREREQS=YES
$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
Write-Host '=== MANAGER_MP2_BOOTSTRAP_PREREQS_BEGIN ==='
foreach($name in @('node','npm','winget','git','yc')){
  $cmd = Get-Command $name -ErrorAction SilentlyContinue
  if($cmd){
    Write-Host ("CMD={0} FOUND=True PATH={1}" -f $name,$cmd.Source)
    try {
      $ver = & $cmd.Source --version 2>&1 | Out-String
      Write-Host ("CMD={0} VERSION={1}" -f $name,$ver.Trim())
    } catch {}
  } else { Write-Host ("CMD={0} FOUND=False" -f $name) }
}
foreach($p in @(
  'C:\Program Files\nodejs\node.exe',
  'C:\Program Files\nodejs\npm.cmd',
  'C:\Program Files\Git\cmd\git.exe',
  'C:\Users\user\AppData\Local\Microsoft\WindowsApps\winget.exe',
  'C:\Users\user\yandex-cloud\bin\yc.exe'
)){
  try{$e=Test-Path -LiteralPath $p -ErrorAction Stop}catch{$e=$false}
  Write-Host "PATH=$p EXISTS=$e"
}
Write-Host '=== MANAGER_MP2_BOOTSTRAP_PREREQS_END ==='
