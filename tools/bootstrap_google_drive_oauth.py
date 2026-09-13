#!/usr/bin/env python3
"""One-time local bootstrap for the remote marketplace archive Google Drive OAuth.

The helper keeps the refresh token out of chat, files and command-line arguments:
1. reads a Google Desktop OAuth client credentials.json;
2. runs the loopback-browser authorization flow with PKCE;
3. verifies access to the exact archive root folder;
4. sends the minimal OAuth JSON to a temporary GitHub Actions secret via stdin;
5. runs the bootstrap workflow and waits for it to finish;
6. deletes the temporary GitHub Actions secret in a finally block.

The durable credential is stored by the workflow in Yandex Lockbox.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import secrets
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

REPO = "alexpmtk-afk/mcp-yandex-cloud-infra"
WORKFLOW = "bootstrap-google-drive-archive.yml"
TEMP_SECRET = "GOOGLE_DRIVE_OAUTH_JSON"
ROOT_ID = "1UVKUcFfDhCDk6nMHX1mWg9cRL05DT-OJ"
ROOT_NAME = "MCP архив базы данных"
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"
AUTH_URI_DEFAULT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URI_DEFAULT = "https://oauth2.googleapis.com/token"


def die(message: str) -> None:
    raise RuntimeError(message)


def run_gh(args: list[str], *, input_text: str | None = None, capture: bool = False) -> subprocess.CompletedProcess[str]:
    cmd = ["gh", *args]
    return subprocess.run(
        cmd,
        input=input_text,
        text=True,
        check=True,
        capture_output=capture,
    )


def load_client(path: Path) -> dict[str, str]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        die(f"Не удалось прочитать OAuth credentials JSON: {exc}")
    cfg = raw.get("installed")
    if not isinstance(cfg, dict):
        die("Нужен OAuth Client ID типа Desktop app: в JSON отсутствует секция 'installed'.")
    client_id = str(cfg.get("client_id", "")).strip()
    client_secret = str(cfg.get("client_secret", "")).strip()
    if not client_id or not client_secret:
        die("В Desktop OAuth JSON нет client_id/client_secret.")
    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "auth_uri": str(cfg.get("auth_uri") or AUTH_URI_DEFAULT),
        "token_uri": str(cfg.get("token_uri") or TOKEN_URI_DEFAULT),
    }


class OAuthCallback(BaseHTTPRequestHandler):
    result: dict[str, str] = {}
    expected_state = ""

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        state = (params.get("state") or [""])[0]
        code = (params.get("code") or [""])[0]
        error = (params.get("error") or [""])[0]
        if state != self.expected_state:
            self.result = {"error": "state_mismatch"}
        elif error:
            self.result = {"error": error}
        elif not code:
            self.result = {"error": "missing_code"}
        else:
            self.result = {"code": code}
        body = (
            "<html><body style='font-family:Segoe UI,Arial;padding:40px'>"
            "<h2>Авторизация получена</h2>"
            "<p>Можно закрыть это окно и вернуться в терминал.</p>"
            "</body></html>"
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def authorize(client: dict[str, str]) -> dict[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
    state = secrets.token_urlsafe(24)

    server = HTTPServer(("127.0.0.1", 0), OAuthCallback)
    server.timeout = 300
    OAuthCallback.result = {}
    OAuthCallback.expected_state = state
    redirect_uri = f"http://127.0.0.1:{server.server_port}/oauth2callback"

    query = urllib.parse.urlencode({
        "client_id": client["client_id"],
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": DRIVE_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    auth_url = f"{client['auth_uri']}?{query}"

    print("Открываю окно Google для одноразового разрешения доступа к архивной папке…")
    if not webbrowser.open(auth_url, new=1, autoraise=True):
        print("Браузер не открылся автоматически. Откройте эту ссылку на этом ПК:")
        print(auth_url)

    server.handle_request()
    server.server_close()
    result = OAuthCallback.result
    if not result.get("code"):
        die(f"Google OAuth не завершён: {result.get('error', 'timeout_or_unknown_error')}")

    body = urllib.parse.urlencode({
        "client_id": client["client_id"],
        "client_secret": client["client_secret"],
        "code": result["code"],
        "code_verifier": verifier,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }).encode("utf-8")
    req = urllib.request.Request(
        client["token_uri"],
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            token = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        die(f"Google token exchange завершился HTTP {exc.code}: {detail}")
    refresh_token = str(token.get("refresh_token", "")).strip()
    access_token = str(token.get("access_token", "")).strip()
    if not refresh_token:
        die("Google не вернул refresh_token. Повторите запуск и подтвердите consent.")
    if not access_token:
        die("Google не вернул access_token для контрольной проверки Drive.")
    return {"refresh_token": refresh_token, "access_token": access_token}


def verify_drive(access_token: str) -> None:
    fields = urllib.parse.quote("id,name,mimeType")
    url = f"https://www.googleapis.com/drive/v3/files/{ROOT_ID}?fields={fields}&supportsAllDrives=true"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            item = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        die(f"Не удалось проверить архивную папку Google Drive: HTTP {exc.code}: {detail}")
    if str(item.get("id")) != ROOT_ID or str(item.get("name")) != ROOT_NAME:
        die(f"Google OAuth видит другой объект вместо '{ROOT_NAME}'.")
    if str(item.get("mimeType")) != "application/vnd.google-apps.folder":
        die("Архивный Drive ID не является папкой.")
    print(f"Google Drive: папка '{ROOT_NAME}' доступна — PASS")


def newest_dispatch_run(after_epoch: float) -> dict[str, object]:
    deadline = time.time() + 90
    while time.time() < deadline:
        proc = run_gh([
            "run", "list", "--repo", REPO, "--workflow", WORKFLOW,
            "--event", "workflow_dispatch", "--limit", "10",
            "--json", "databaseId,createdAt,status,conclusion,url",
        ], capture=True)
        runs = json.loads(proc.stdout or "[]")
        for run in runs:
            created = str(run.get("createdAt", ""))
            try:
                created_epoch = time.mktime(time.strptime(created, "%Y-%m-%dT%H:%M:%SZ"))
            except ValueError:
                continue
            # UTC/local conversion can vary; a generous window avoids false misses.
            if created_epoch >= after_epoch - 300:
                return run
        time.sleep(2)
    die("GitHub Actions run не появился в течение 90 секунд.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Authorize Google Drive and bootstrap remote MCP archive storage.")
    parser.add_argument("credentials_json", type=Path, help="Google OAuth Desktop app credentials JSON")
    args = parser.parse_args()

    if shutil.which("gh") is None:
        die("Не найден GitHub CLI (gh). Он нужен для безопасной передачи одноразового секрета.")
    run_gh(["auth", "status", "--hostname", "github.com"], capture=True)

    client = load_client(args.credentials_json)
    token = authorize(client)
    verify_drive(token["access_token"])

    durable = json.dumps({
        "client_id": client["client_id"],
        "client_secret": client["client_secret"],
        "refresh_token": token["refresh_token"],
        "token_uri": client["token_uri"],
    }, ensure_ascii=False, separators=(",", ":"))

    secret_set = False
    try:
        run_gh(["secret", "set", TEMP_SECRET, "--repo", REPO], input_text=durable, capture=True)
        secret_set = True
        print("Временный GitHub Secret установлен без вывода значения — PASS")

        started = time.time()
        run_gh(["workflow", "run", WORKFLOW, "--repo", REPO, "--ref", "main"], capture=True)
        run = newest_dispatch_run(started)
        run_id = str(run["databaseId"])
        print(f"Запущен защищённый bootstrap workflow #{run_id}. Ожидаю результат…")
        run_gh(["run", "watch", run_id, "--repo", REPO, "--exit-status"])
        print("Yandex Lockbox + Drive-enabled MCP deployment — PASS")
    finally:
        if secret_set:
            try:
                run_gh(["secret", "delete", TEMP_SECRET, "--repo", REPO], capture=True)
                print("Временный GitHub Secret удалён — PASS")
            except subprocess.CalledProcessError:
                print("ВНИМАНИЕ: не удалось автоматически удалить временный GitHub Secret.", file=sys.stderr)
                print(f"Выполните: gh secret delete {TEMP_SECRET} --repo {REPO}", file=sys.stderr)

    print("Готово. Постоянный Google refresh token находится только в Yandex Lockbox.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"Команда завершилась ошибкой: {' '.join(exc.cmd) if isinstance(exc.cmd, list) else exc.cmd}", file=sys.stderr)
        raise SystemExit(exc.returncode or 1)
    except Exception as exc:
        print(f"ОШИБКА: {exc}", file=sys.stderr)
        raise SystemExit(1)
