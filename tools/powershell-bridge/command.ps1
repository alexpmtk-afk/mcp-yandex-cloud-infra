Write-Host '=== RUNNER_PROCESS_PATHS ==='
Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'Runner.Listener.exe' } | ForEach-Object { Write-Host ("PID="+$_.ProcessId+" PATH="+$_.ExecutablePath+" CMD="+$_.CommandLine) }
Write-Host '=== YC_CANDIDATES ==='
@(
  'C:\Program Files\Yandex.Cloud\bin\yc.exe',
  'C:\Users\Win10_Game_OS\yandex-cloud\bin\yc.exe',
  'C:\Users\Win10_Game_OS\AppData\Local\Yandex.Cloud\bin\yc.exe',
  'C:\Users\Win10_Game_OS\AppData\Local\Programs\Yandex.Cloud\bin\yc.exe'
) | ForEach-Object { Write-Host ($_+'='+[bool](Test-Path $_)) }
