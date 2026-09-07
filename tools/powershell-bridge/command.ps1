$ErrorActionPreference = 'Stop'

Write-Host '=== MCM_CANONICAL_REPAIR_AND_CDP_BEGIN ==='

$user = "$env:COMPUTERNAME\Win10_Game_OS"
$runtimeRoot = 'C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
$taskRoot = 'C:\Windows\System32\Tasks'
$backupRoot = Join-Path $runtimeRoot ('task-backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))

$taskName = 'MarketplaceCardMonitor-UserNode-Canonical'
$launcher = Join-Path $runtimeRoot 'canonical-user-node-launcher.ps1'
$probe = Join-Path $runtimeRoot 'ozon-plain-cdp-runtime.py'
$startedFile = Join-Path $runtimeRoot 'canonical-task.started'
$taskExitFile = Join-Path $runtimeRoot 'canonical-task-exit.json'
$resultFile = Join-Path $runtimeRoot 'plain-cdp-canonical.json'
$screenshotFile = Join-Path $runtimeRoot 'plain-cdp-canonical.png'

$venvPython = Join-Path $runtimeRoot '.venv\Scripts\python.exe'
$browser = 'C:\Program Files\Yandex\YandexBrowser\Application\browser.exe'
$profile = Join-Path $runtimeRoot 'profiles\MarketplaceMonitor\Ozon-Yandex-CDP-Canonical'

New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null
New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null

& icacls.exe $runtimeRoot /grant "${user}:(OI)(CI)M" /T /C | Out-Null

Write-Host '--- ORPHAN_TASK_CLEANUP ---'

$taskFiles = @(
    Get-ChildItem `
        -Path $taskRoot `
        -File `
        -Force `
        -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Name -like 'MarketplaceCardMonitor*'
    }
)

foreach ($file in $taskFiles) {
    $name = $file.Name

    $psRegistered = $false
    $schtasksRegistered = $false

    try {
        $existing = Get-ScheduledTask `
            -TaskName $name `
            -ErrorAction Stop

        if ($existing) {
            $psRegistered = $true
        }
    }
    catch {}

    & schtasks.exe `
        /Query `
        /TN "\$name" `
        1>$null `
        2>$null

    if ($LASTEXITCODE -eq 0) {
        $schtasksRegistered = $true
    }

    Write-Host "TASK_CHECK=$name|PS=$psRegistered|SCHTASKS=$schtasksRegistered"

    if (-not $psRegistered -and -not $schtasksRegistered) {
        Copy-Item `
            -Path $file.FullName `
            -Destination (Join-Path $backupRoot $name) `
            -Force

        Remove-Item `
            -Path $file.FullName `
            -Force

        Write-Host "ORPHAN_REMOVED=$name"
    }
    else {
        Write-Host "REGISTERED_TASK_LEFT_INTACT=$name"
    }
}

Write-Host "TASK_BACKUP_ROOT=$backupRoot"

Write-Host '--- DEPENDENCY_CHECK ---'

if (-not (Test-Path $venvPython)) {
    throw "Venv Python not found: $venvPython"
}

if (-not (Test-Path $browser)) {
    throw "Yandex Browser not found: $browser"
}

& $venvPython `
    -c "import websocket; print('WEBSOCKET_VERSION=' + getattr(websocket,'__version__','unknown'))"

if ($LASTEXITCODE -ne 0) {
    & $venvPython `
        -m pip install `
        --disable-pip-version-check `
        'websocket-client>=1.8,<2'

    if ($LASTEXITCODE -ne 0) {
        throw "websocket-client install failed: $LASTEXITCODE"
    }
}

Write-Host 'DEPENDENCIES_READY=YES'

$probeCode = @'
from __future__ import annotations

import base64
import json
import re
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import websocket

BROWSER = Path(r"C:\Program Files\Yandex\YandexBrowser\Application\browser.exe")
RUNTIME = Path(r"C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1")
PROFILE = RUNTIME / "profiles" / "MarketplaceMonitor" / "Ozon-Yandex-CDP-Canonical"
OUTPUT = RUNTIME / "plain-cdp-canonical.json"
SCREENSHOT = RUNTIME / "plain-cdp-canonical.png"

TARGET = (
    "https://www.ozon.ru/product/"
    "nippel-dlya-beskamernyh-shin-ventil-sosok-avtomobilnyy-rezinovyy-"
    "1420875699/"
)

EXPECTED_SKU = "1420875699"
EXPECTED_REGION = "\u0412\u043e\u0440\u043e\u043d\u0435\u0436"
PORT = 9231


def now():
    return datetime.now(timezone.utc).isoformat()


def http_json(url, timeout=2.0):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def cdp_call(ws, seq, method, params=None):
    ws.send(json.dumps({
        "id": seq,
        "method": method,
        "params": params or {},
    }))

    while True:
        message = json.loads(ws.recv())

        if message.get("id") == seq:
            return message


def extract_prices(text):
    rub = re.escape(chr(0x20BD))

    pattern = re.compile(
        r"(?<!\d)"
        r"(\d{1,3}(?:[\s\u00a0\u202f]\d{3})+|\d{2,7})"
        r"\s*" + rub
    )

    values = []

    for match in pattern.finditer(text or ""):
        digits = re.sub(r"\D", "", match.group(1))

        if not digits:
            continue

        value = int(digits)

        if 1 <= value <= 10000000 and value not in values:
            values.append(value)

    return values


result = {
    "started_at": now(),
    "browser": str(BROWSER),
    "profile": str(PROFILE),
    "target_url": TARGET,
    "expected_sku": EXPECTED_SKU,
    "expected_region": EXPECTED_REGION,
    "browser_started": False,
    "cdp_ready": False,
    "cdp_attached": False,
    "final_url": None,
    "actual_sku": None,
    "title": None,
    "h1": None,
    "navigator_webdriver": None,
    "blocked": None,
    "region_ok": None,
    "price_candidates_rub": [],
    "body_excerpt": None,
    "screenshot": None,
    "status": "UNKNOWN",
    "error": None,
}

proc = None
ws = None

try:
    PROFILE.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(BROWSER),
        "--user-data-dir=" + str(PROFILE),
        "--remote-debugging-port=" + str(PORT),
        "--remote-allow-origins=http://127.0.0.1:" + str(PORT),
        "--new-window",
        "--no-first-run",
        "--no-default-browser-check",
        TARGET,
    ]

    proc = subprocess.Popen(cmd)
    result["browser_started"] = True

    endpoint = "http://127.0.0.1:%d/json/list" % PORT
    deadline = time.time() + 30
    pages = []

    while time.time() < deadline:
        try:
            candidate = http_json(endpoint)

            if isinstance(candidate, list):
                pages = candidate
                result["cdp_ready"] = True
                break
        except Exception:
            pass

        time.sleep(0.5)

    if not pages:
        result["status"] = "CDP_ENDPOINT_UNAVAILABLE"
        raise RuntimeError("CDP endpoint unavailable")

    time.sleep(18)

    try:
        candidate = http_json(endpoint)

        if isinstance(candidate, list):
            pages = candidate
    except Exception:
        pass

    page = next(
        (
            item
            for item in pages
            if item.get("type") == "page"
            and "ozon.ru/product/" in str(item.get("url", ""))
        ),
        None,
    )

    if page is None:
        page = next(
            (
                item
                for item in pages
                if item.get("type") == "page"
            ),
            None,
        )

    if not page or not page.get("webSocketDebuggerUrl"):
        result["status"] = "CDP_PAGE_NOT_FOUND"
        raise RuntimeError("CDP page not found")

    ws = websocket.create_connection(
        page["webSocketDebuggerUrl"],
        timeout=10,
        origin="http://127.0.0.1:%d" % PORT,
    )

    result["cdp_attached"] = True

    expression = r'''JSON.stringify({
      url: location.href,
      title: document.title,
      h1: (document.querySelector('h1') || {}).innerText || '',
      webdriver: navigator.webdriver,
      body: (document.body && document.body.innerText)
        ? document.body.innerText
        : ''
    })'''

    reply = cdp_call(
        ws,
        1,
        "Runtime.evaluate",
        {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True,
        },
    )

    value = (
        reply.get("result", {})
        .get("result", {})
        .get("value")
    )

    if not isinstance(value, str):
        result["status"] = "CDP_NO_EVAL"
        result["error"] = json.dumps(
            reply,
            ensure_ascii=True,
        )[:4000]

        raise RuntimeError("CDP evaluate returned no value")

    payload = json.loads(value)

    body = str(payload.get("body") or "")
    final_url = str(payload.get("url") or "")

    result["final_url"] = final_url
    result["title"] = payload.get("title")
    result["h1"] = payload.get("h1")
    result["navigator_webdriver"] = payload.get("webdriver")
    result["body_excerpt"] = body[:12000]

    sku_match = re.search(
        r"/product/[^/?#]*-(\d+)(?:/|$|\?)",
        final_url,
        re.I,
    )

    result["actual_sku"] = (
        sku_match.group(1)
        if sku_match
        else None
    )

    body_lower = body.lower()

    blocked_terms = [
        "__rr=1",
        "captcha",
        "access denied",
        "incidentid",
        "fab_chlg",
        "robot",
    ]

    result["blocked"] = (
        "__rr=1" in final_url.lower()
        or any(term in body_lower for term in blocked_terms)
    )

    result["region_ok"] = (
        EXPECTED_REGION.casefold()
        in body.casefold()
    )

    result["price_candidates_rub"] = extract_prices(body)[:60]

    screenshot_reply = cdp_call(
        ws,
        2,
        "Page.captureScreenshot",
        {"format": "png"},
    )

    screenshot_data = (
        screenshot_reply.get("result", {})
        .get("data")
    )

    if isinstance(screenshot_data, str) and screenshot_data:
        SCREENSHOT.write_bytes(
            base64.b64decode(screenshot_data)
        )

        result["screenshot"] = str(SCREENSHOT)

    if result["blocked"]:
        result["status"] = "ANTI_BOT"

    elif result["actual_sku"] != EXPECTED_SKU:
        result["status"] = "PRODUCT_IDENTITY_MISMATCH"

    elif result["region_ok"] is not True:
        result["status"] = "REGION_UNRESOLVED"

    elif not result["price_candidates_rub"]:
        result["status"] = "DOM_PRICE_UNRESOLVED"

    else:
        result["status"] = "PLAIN_CDP_DOM_PASS"

except Exception as exc:
    if result["status"] == "UNKNOWN":
        result["status"] = "COLLECTOR_EXCEPTION"

    if result["error"] is None:
        result["error"] = repr(exc)

finally:
    result["finished_at"] = now()

    OUTPUT.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    if ws is not None:
        try:
            cdp_call(
                ws,
                99,
                "Browser.close",
            )
        except Exception:
            pass

        try:
            ws.close()
        except Exception:
            pass

    elif proc is not None:
        try:
            proc.terminate()
        except Exception:
            pass


if result["status"] == "PLAIN_CDP_DOM_PASS":
    raise SystemExit(0)

raise SystemExit(5)
'@

[IO.File]::WriteAllText(
    $probe,
    $probeCode,
    (New-Object System.Text.UTF8Encoding($false))
)

$launcherCode = @'
$ErrorActionPreference = 'Continue'

$runtimeRoot = 'C:\ProgramData\ChatGPT-PK\marketplace-card-monitor\user-node-v1'
$python = Join-Path $runtimeRoot '.venv\Scripts\python.exe'
$probe = Join-Path $runtimeRoot 'ozon-plain-cdp-runtime.py'
$startedFile = Join-Path $runtimeRoot 'canonical-task.started'
$taskExitFile = Join-Path $runtimeRoot 'canonical-task-exit.json'

"STARTED $(Get-Date -Format o) USER=$([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) SESSION=$((Get-Process -Id $PID).SessionId)" |
    Set-Content `
        -Path $startedFile `
        -Encoding UTF8

& $python $probe

$exitCode = $LASTEXITCODE

if ($null -eq $exitCode) {
    $exitCode = 0
}

$exitResult = [ordered]@{
    timestamp = (Get-Date).ToString('o')
    exit_code = $exitCode
    user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    session_id = (Get-Process -Id $PID).SessionId
}

$exitResult |
    ConvertTo-Json -Depth 4 |
    Set-Content `
        -Path $taskExitFile `
        -Encoding UTF8

exit $exitCode
'@

[IO.File]::WriteAllText(
    $launcher,
    $launcherCode,
    (New-Object System.Text.UnicodeEncoding($false,$true))
)

foreach ($path in @(
    $startedFile,
    $taskExitFile,
    $resultFile,
    $screenshotFile
)) {
    if (Test-Path $path) {
        Remove-Item $path -Force
    }
}

Write-Host '--- CREATE_CANONICAL_TASK ---'

try {
    Unregister-ScheduledTask `
        -TaskName $taskName `
        -Confirm:$false `
        -ErrorAction SilentlyContinue
}
catch {}

$action = New-ScheduledTaskAction `
    -Execute 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe' `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$launcher`"" `
    -WorkingDirectory $runtimeRoot

$principal = New-ScheduledTaskPrincipal `
    -UserId $user `
    -LogonType Interactive `
    -RunLevel Limited

$trigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).AddYears(5)

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 3) `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Principal $principal `
    -Trigger $trigger `
    -Settings $settings `
    -Force | Out-Null

Write-Host 'CANONICAL_TASK_REGISTERED=YES'
Write-Host "CANONICAL_TASK_USER=$user"

$psVisible = $false

try {
    $taskCheck = Get-ScheduledTask `
        -TaskName $taskName `
        -ErrorAction Stop

    $psVisible = $true

    Write-Host "CANONICAL_PS_STATE=$($taskCheck.State)"
}
catch {
    Write-Host "CANONICAL_PS_QUERY_ERROR=$($_.Exception.Message)"
}

& schtasks.exe `
    /Query `
    /TN "\$taskName" `
    1>$null `
    2>$null

$schtasksVisible = ($LASTEXITCODE -eq 0)

Write-Host "CANONICAL_PS_VISIBLE=$psVisible"
Write-Host "CANONICAL_SCHTASKS_VISIBLE=$schtasksVisible"

$canonicalFile = Join-Path $taskRoot $taskName

Write-Host "CANONICAL_TASK_FILE_EXISTS=$(Test-Path $canonicalFile)"

if (-not $psVisible -and -not $schtasksVisible) {
    throw 'Canonical task registration did not persist.'
}

Write-Host '--- RUN_CANONICAL_TASK ---'

& schtasks.exe `
    /Run `
    /TN "\$taskName"

if ($LASTEXITCODE -ne 0) {
    Write-Host "SCHTASKS_RUN_FAILED=$LASTEXITCODE"

    Start-ScheduledTask `
        -TaskName $taskName `
        -ErrorAction Stop
}

Write-Host 'CANONICAL_TASK_RUN_REQUESTED=YES'

$startDeadline = (Get-Date).AddSeconds(20)

while (
    (Get-Date) -lt $startDeadline -and
    -not (Test-Path $startedFile)
) {
    Start-Sleep -Seconds 1
}

Write-Host '--- START_MARKER ---'

if (Test-Path $startedFile) {
    Get-Content $startedFile -Raw
}
else {
    Write-Host 'START_MARKER=NOT_FOUND'
}

$resultDeadline = (Get-Date).AddSeconds(100)

while (
    (Get-Date) -lt $resultDeadline -and
    -not (Test-Path $resultFile)
) {
    Start-Sleep -Seconds 2
}

Write-Host '--- TASK_EXIT ---'

if (Test-Path $taskExitFile) {
    Get-Content $taskExitFile -Raw
}
else {
    Write-Host 'TASK_EXIT=NOT_FOUND'
}

Write-Host '--- CDP_RESULT ---'

if (Test-Path $resultFile) {
    Get-Content $resultFile -Raw
}
else {
    Write-Host 'CDP_RESULT=NOT_FOUND'
}

Write-Host "SCREENSHOT_EXISTS=$(Test-Path $screenshotFile)"

Write-Host '--- CANONICAL_TASK_FINAL ---'

try {
    $finalTask = Get-ScheduledTask `
        -TaskName $taskName `
        -ErrorAction Stop

    $finalInfo = Get-ScheduledTaskInfo `
        -TaskName $taskName `
        -ErrorAction Stop

    Write-Host "FINAL_TASK_FOUND=YES"
    Write-Host "FINAL_TASK_STATE=$($finalTask.State)"
    Write-Host "FINAL_TASK_LAST_RESULT=$($finalInfo.LastTaskResult)"
}
catch {
    Write-Host 'FINAL_TASK_FOUND=NO'
    Write-Host "FINAL_TASK_ERROR=$($_.Exception.Message)"
}

& schtasks.exe `
    /Query `
    /TN "\$taskName" `
    /V `
    /FO LIST `
    2>&1 |
    Select-Object -First 40 |
    ForEach-Object {
        Write-Host $_
    }

Write-Host 'CANONICAL_TASK_LEFT_REGISTERED=YES'
Write-Host '=== MCM_CANONICAL_REPAIR_AND_CDP_END ==='
