# Card Monitor admin probe: compare the persistent WB profile with a clean profile.
$ErrorActionPreference = 'Stop'
$runtimeRoot = 'C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
$taskName = 'MarketplaceCardMonitor-WB-Profile-Probe-Once'
$probe = Join-Path $runtimeRoot 'wb-profile-probe.py'
$result = Join-Path $runtimeRoot 'wb-profile-probe-result.txt'
$interactiveUser = (Get-CimInstance Win32_ComputerSystem -ErrorAction Stop).UserName
if ([string]::IsNullOrWhiteSpace($interactiveUser)) { throw 'No interactive Windows user is logged on.' }
if (Test-Path $result) { Remove-Item $result -Force }

$probeCode = @'
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(r'C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1')
config = json.loads((root / 'tires-195-55-r16.json').read_text(encoding='utf-8'))
card = next(x for x in config['cards'] if x['id'] == 'wb-cordiant-snow-cross-2')
discovery = root / 'target_discovery.py'
browser = pathlib.Path(r'C:\Program Files\Yandex\YandexBrowser\Application\browser.exe')
profiles = [
    ('existing', root / 'profiles' / 'Wildberries'),
    ('fresh', root / 'profiles' / 'Wildberries-Fresh-Probe'),
]
lines = []
for index, (label, profile) in enumerate(profiles):
    out = root / f'wb-profile-probe-{label}.json'
    if label == 'fresh' and profile.exists():
        import shutil
        shutil.rmtree(profile, ignore_errors=True)
    cmd = [
        sys.executable, str(discovery), '--browser-path', str(browser),
        '--profile-dir', str(profile), '--marketplace', 'wildberries',
        '--query', card['query'], '--output', str(out), '--port', str(9340 + index),
        '--settle-seconds', '10'
    ]
    for token in card.get('required_tokens', []):
        cmd += ['--required', str(token)]
    for token in card.get('preferred_tokens', []):
        cmd += ['--preferred', str(token)]
    for token in card.get('forbidden_tokens', []):
        cmd += ['--forbidden', str(token)]
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=95)
        payload = json.loads(out.read_text(encoding='utf-8')) if out.exists() else {}
        selected = payload.get('selected') or {}
        lines.append(
            f"PROFILE={label} EXIT={cp.returncode} STATUS={payload.get('status')} "
            f"RAW={payload.get('raw_product_links')} SKU={selected.get('sku')} URL={selected.get('url')} "
            f"ERR={payload.get('error')}"
        )
    except Exception as exc:
        lines.append(f'PROFILE={label} EXCEPTION={type(exc).__name__}:{exc}')
(root / 'wb-profile-probe-result.txt').write_text('\n'.join(lines), encoding='utf-8')
'@
[IO.File]::WriteAllText($probe, $probeCode, (New-Object Text.UTF8Encoding($false)))
try { Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue } catch {}
$python = Join-Path $runtimeRoot '.venv\Scripts\python.exe'
$action = New-ScheduledTaskAction -Execute $python -Argument "`"$probe`""
$principal = New-ScheduledTaskPrincipal -UserId $interactiveUser -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $taskName -Action $action -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
$deadline = (Get-Date).AddMinutes(5)
while ((Get-Date) -lt $deadline -and -not (Test-Path $result)) { Start-Sleep -Seconds 3 }
if (-not (Test-Path $result)) { throw 'Timed out waiting for WB profile probe.' }
Write-Host '--- WB_PROFILE_PROBE ---'
Get-Content -Raw -LiteralPath $result
try { Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue } catch {}
Remove-Item $probe -Force -ErrorAction SilentlyContinue
