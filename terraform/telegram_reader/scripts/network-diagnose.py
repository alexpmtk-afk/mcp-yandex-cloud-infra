from __future__ import annotations

import socket
import sqlite3
import urllib.request
from pathlib import Path

SESSION = Path('/state/telegram_news.session')
rows: list[tuple[int, str, int]] = []
if SESSION.exists():
    try:
        with sqlite3.connect(str(SESSION), timeout=2) as db:
            rows = [(int(dc), str(host), int(port)) for dc, host, port in db.execute(
                'select dc_id, server_address, port from sessions'
            ).fetchall()]
    except Exception as exc:
        print(f'SESSION_DC_ERROR={type(exc).__name__}')

print(f'SESSION_DC={rows}')
targets: list[tuple[str, int, str]] = []
for dc, host, port in rows:
    targets.append((host, port, f'SESSION_DC{dc}_{port}'))
    for alt in (80, 443, 5222):
        if alt != port:
            targets.append((host, alt, f'SESSION_DC{dc}_{alt}'))
for host, port, label in [
    ('149.154.167.51', 443, 'TG_DC2_443'),
    ('149.154.167.51', 80, 'TG_DC2_80'),
    ('149.154.167.91', 443, 'TG_DC4_443'),
    ('149.154.167.91', 80, 'TG_DC4_80'),
]:
    targets.append((host, port, label))

seen: set[tuple[str, int]] = set()
for host, port, label in targets:
    key = (host, port)
    if key in seen:
        continue
    seen.add(key)
    try:
        with socket.create_connection(key, timeout=5):
            print(f'{label}=PASS ({host}:{port})')
    except Exception as exc:
        print(f'{label}=FAIL ({host}:{port}) {type(exc).__name__}')

try:
    request = urllib.request.Request('https://api.telegram.org/', method='HEAD')
    with urllib.request.urlopen(request, timeout=10) as response:
        print(f'TG_HTTPS=PASS status={response.status}')
except Exception as exc:
    print(f'TG_HTTPS=FAIL {type(exc).__name__}')
