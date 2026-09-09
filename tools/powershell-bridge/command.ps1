$ErrorActionPreference='Stop'
Write-Host '=== WORK_STANDARD_DIRS_BEGIN ==='
$dirs=@(
 'C:\ProgramData\ChatGPT-PowerShell',
 'C:\ProgramData\ChatGPT-PowerShell\scripts',
 'C:\ProgramData\ChatGPT-PowerShell\config',
 'C:\ProgramData\ChatGPT-PowerShell\logs',
 'C:\ProgramData\ChatGPT-PowerShell\state'
)
foreach($d in $dirs){
 if(-not (Test-Path -LiteralPath $d)){ New-Item -ItemType Directory -Path $d -Force | Out-Null }
 Write-Host ("PATH={0} EXISTS={1}" -f $d,(Test-Path -LiteralPath $d))
}
Write-Host 'OLD_BRIDGE_PRESERVED=True'
Write-Host '=== WORK_STANDARD_DIRS_END ==='
