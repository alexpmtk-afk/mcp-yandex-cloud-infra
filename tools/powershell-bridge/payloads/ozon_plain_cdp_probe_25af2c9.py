#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import websocket

BLOCK_RE = re.compile(
    r"(captcha|капч|access denied|доступ ограничен|похоже.{0,30}нет соединения|"
    r"incidentid|fab_chlg|__rr=1|robot|антибот)",
    re.I | re.S,
)
SKU_RE = re.compile(r"/product/[^/?#]*-(\d+)(?:/|$|\?)", re.I)
RUBLE_RE = re.compile(r"(?<!\d)(\d{1,3}(?:[\s\u00a0\u202f]\d{3})+|\d{2,7})\s*₽")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def http_json(url: str, timeout: float = 2.0) -> Any:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def cdp_call(ws: websocket.WebSocket, seq: int, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    ws.send(json.dumps({"id": seq, "method": method, "params": params or {}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == seq:
            return msg


def rubles(text: str) -> list[int]:
    out: list[int] = []
    for m in RUBLE_RE.finditer(text or ""):
        try:
            value = int(re.sub(r"\D", "", m.group(1)))
        except ValueError:
            continue
        if 1 <= value <= 10_000_000 and value not in out:
            out.append(value)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--browser-path", required=True)
    ap.add_argument("--profile-dir", required=True)
    ap.add_argument("--target-url", required=True)
    ap.add_argument("--expected-sku")
    ap.add_argument("--expected-region")
    ap.add_argument("--output", required=True)
    ap.add_argument("--screenshot")
    ap.add_argument("--port", type=int, default=9227)
    ap.add_argument("--settle-seconds", type=int, default=18)
    args = ap.parse_args()

    browser = Path(args.browser_path)
    profile = Path(args.profile_dir)
    output = Path(args.output)
    screenshot = Path(args.screenshot) if args.screenshot else None
    profile.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    if screenshot:
        screenshot.parent.mkdir(parents=True, exist_ok=True)

    result: dict[str, Any] = {
        "started_at": now(),
        "browser": str(browser),
        "profile": str(profile),
        "target_url": args.target_url,
        "expected_sku": args.expected_sku,
        "expected_region": args.expected_region,
        "debug_port": args.port,
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
        "status": "UNKNOWN",
        "error": None,
    }

    proc: subprocess.Popen[Any] | None = None
    ws: websocket.WebSocket | None = None
    try:
        if not browser.exists():
            raise FileNotFoundError(f"browser not found: {browser}")

        cmd = [
            str(browser),
            f"--user-data-dir={profile}",
            f"--remote-debugging-port={args.port}",
            f"--remote-allow-origins=http://127.0.0.1:{args.port}",
            "--new-window",
            "--no-first-run",
            "--no-default-browser-check",
            args.target_url,
        ]
        proc = subprocess.Popen(cmd)
        result["browser_started"] = True

        endpoint = f"http://127.0.0.1:{args.port}/json/list"
        deadline = time.time() + 30
        pages: list[dict[str, Any]] = []
        while time.time() < deadline:
            try:
                raw = http_json(endpoint)
                if isinstance(raw, list):
                    result["cdp_ready"] = True
                    pages = raw
                    if pages:
                        break
            except Exception:
                pass
            time.sleep(0.5)

        if not pages:
            result["status"] = "CDP_PAGE_NOT_FOUND"
            return 2

        time.sleep(max(0, args.settle_seconds))
        try:
            raw = http_json(endpoint)
            if isinstance(raw, list):
                pages = raw
        except Exception:
            pass

        page = next(
            (
                p for p in pages
                if p.get("type") == "page" and "ozon.ru/product/" in str(p.get("url", ""))
            ),
            None,
        )
        if page is None:
            page = next((p for p in pages if p.get("type") == "page"), None)
        if not page or not page.get("webSocketDebuggerUrl"):
            result["status"] = "CDP_PAGE_NOT_FOUND"
            return 3

        ws = websocket.create_connection(
            page["webSocketDebuggerUrl"],
            timeout=10,
            origin=f"http://127.0.0.1:{args.port}",
        )
        result["cdp_attached"] = True

        expr = r'''JSON.stringify({
          url: location.href,
          title: document.title,
          h1: (document.querySelector('h1') || {}).innerText || '',
          webdriver: navigator.webdriver,
          body: (document.body && document.body.innerText) ? document.body.innerText : ''
        })'''
        reply = cdp_call(ws, 1, "Runtime.evaluate", {
            "expression": expr,
            "returnByValue": True,
            "awaitPromise": True,
        })
        value = (
            reply.get("result", {})
            .get("result", {})
            .get("value")
        )
        if not isinstance(value, str):
            result["status"] = "CDP_NO_EVAL"
            result["error"] = json.dumps(reply, ensure_ascii=False)[:4000]
            return 4

        payload = json.loads(value)
        body = str(payload.get("body") or "")
        final_url = str(payload.get("url") or "")
        result["final_url"] = final_url
        m = SKU_RE.search(final_url)
        result["actual_sku"] = m.group(1) if m else None
        result["title"] = payload.get("title")
        result["h1"] = payload.get("h1")
        result["navigator_webdriver"] = payload.get("webdriver")
        result["blocked"] = bool(BLOCK_RE.search(body))
        result["price_candidates_rub"] = rubles(body)[:50]
        result["body_excerpt"] = body[:8000]
        if args.expected_region:
            result["region_ok"] = args.expected_region.casefold() in body.casefold()

        if screenshot:
            shot = cdp_call(ws, 2, "Page.captureScreenshot", {"format": "png"})
            data = shot.get("result", {}).get("data")
            if isinstance(data, str) and data:
                screenshot.write_bytes(base64.b64decode(data))
                result["screenshot"] = str(screenshot)

        sku_ok = not args.expected_sku or result["actual_sku"] == args.expected_sku
        if result["blocked"]:
            result["status"] = "ANTI_BOT"
        elif not sku_ok:
            result["status"] = "PRODUCT_IDENTITY_MISMATCH"
        elif args.expected_region and result["region_ok"] is not True:
            result["status"] = "REGION_UNRESOLVED"
        elif not result["price_candidates_rub"]:
            result["status"] = "DOM_PRICE_UNRESOLVED"
        else:
            result["status"] = "PLAIN_CDP_DOM_PASS"
            return 0
        return 5

    except Exception as exc:
        result["status"] = "COLLECTOR_EXCEPTION"
        result["error"] = repr(exc)
        return 10
    finally:
        result["finished_at"] = now()
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        if ws is not None:
            try:
                cdp_call(ws, 99, "Browser.close")
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


if __name__ == "__main__":
    raise SystemExit(main())
