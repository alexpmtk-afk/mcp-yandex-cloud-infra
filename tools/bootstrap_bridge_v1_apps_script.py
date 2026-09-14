#!/usr/bin/env python3
"""One-time owner-side bootstrap for Google Drive Bridge Protocol v1.

This helper performs the only owner-interactive part of Bridge v1:
- OAuth consent for Apps Script project/deployment management and Drive/Sheets scopes;
- creation of two separate Apps Script projects and versioned web-app deployments;
- generation of two independent Bridge secrets in memory;
- temporary transfer of those secrets to GitHub Environment `test` via stdin;
- dispatch of Marketplaces/Birzha bootstrap and live acceptance workflows;
- deletion of the temporary GitHub secrets in a finally block.

The real Bridge secrets are never printed and never written to the repository.
The project-specific Yandex Lockboxes remain the durable runtime stores.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

REPO = "alexpmtk-afk/mcp-yandex-cloud-infra"
AUTH_URI_DEFAULT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URI_DEFAULT = "https://oauth2.googleapis.com/token"
SCRIPT_API = "https://script.googleapis.com/v1"
DRIVE_API = "https://www.googleapis.com/drive/v3"
APPS_SCRIPT_SETTINGS = "https://script.google.com/home/usersettings"

SCOPES = [
    "https://www.googleapis.com/auth/script.projects",
    "https://www.googleapis.com/auth/script.deployments",
    "https://www.googleapis.com/auth/script.webapp.deploy",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/script.external_request",
]

PROJECTS = {
    "marketplaces": {
        "title": "Yandex Google Drive Bridge v1 - Marketplaces",
        "root_id": "1UVKUcFfDhCDk6nMHX1mWg9cRL05DT-OJ",
        "root_name": "MCP архив базы данных",
        "sheets_enabled": False,
        "bootstrap_secret": "MARKETPLACES_GDRIVE_BRIDGE_V1_BOOTSTRAP_SECRET",
        "bootstrap_workflow": "marketplaces-drive-bridge-v1-bootstrap.yml",
        "acceptance_workflow": "marketplaces-drive-bridge-v1-acceptance.yml",
        "foreign_file_id": "1A7IzjXYSCWReZXdtrPZgZgLTnFIifsT2",
    },
    "birzha": {
        "title": "Yandex Google Drive Bridge v1 - Birzha",
        "root_id": "1A7IzjXYSCWReZXdtrPZgZgLTnFIifsT2",
        "root_name": "Архив рыночных данных",
        "sheets_enabled": True,
        "bootstrap_secret": "BIRZHA_GDRIVE_BRIDGE_V1_BOOTSTRAP_SECRET",
        "bootstrap_workflow": "birzha-drive-bridge-v1-bootstrap.yml",
        "acceptance_workflow": "birzha-drive-bridge-v1-acceptance.yml",
        "foreign_file_id": "1UVKUcFfDhCDk6nMHX1mWg9cRL05DT-OJ",
    },
}


def die(message: str) -> None:
    raise RuntimeError(message)


def run_gh(args: list[str], *, input_text: str | None = None, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["gh", *args], input=input_text, text=True, check=True, capture_output=capture)


def load_client(path: Path) -> dict[str, str]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        die(f"Не удалось прочитать OAuth credentials JSON: {exc}")
    cfg = raw.get("installed")
    if not isinstance(cfg, dict):
        die("Нужен OAuth Client ID типа Desktop app: отсутствует секция 'installed'.")
    client_id = str(cfg.get("client_id", "")).strip()
    client_secret = str(cfg.get("client_secret", "")).strip()
    if not client_id or not client_secret:
        die("В Desktop OAuth JSON отсутствуют client_id/client_secret.")
    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "auth_uri": str(cfg.get("auth_uri") or AUTH_URI_DEFAULT),
        "token_uri": str(cfg.get("token_uri") or TOKEN_URI_DEFAULT),
    }


def discover_credentials(explicit: Path | None) -> Path:
    if explicit:
        if not explicit.is_file():
            die(f"OAuth credentials file not found: {explicit}")
        return explicit
    home = Path.home()
    candidates = [
        Path.cwd() / "credentials.json",
        Path.cwd() / "client_secret.json",
        home / "Downloads" / "credentials.json",
        home / "Desktop" / "credentials.json",
        home / "Documents" / "credentials.json",
    ]
    for p in candidates:
        if p.is_file():
            try:
                load_client(p)
                print(f"OAuth Desktop credentials: {p}")
                return p
            except Exception:
                pass
    die("Не найден Google Desktop OAuth credentials.json. Укажите путь параметром --credentials.")


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
            "<h2>Google authorization received</h2>"
            "<p>You can close this window and return to the terminal.</p>"
            "</body></html>"
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def authorize(client: dict[str, str]) -> str:
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
    state = secrets.token_urlsafe(24)
    server = HTTPServer(("127.0.0.1", 0), OAuthCallback)
    server.timeout = 600
    OAuthCallback.result = {}
    OAuthCallback.expected_state = state
    redirect_uri = f"http://127.0.0.1:{server.server_port}/oauth2callback"
    query = urllib.parse.urlencode({
        "client_id": client["client_id"],
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    auth_url = f"{client['auth_uri']}?{query}"
    print("Открываю Google OAuth. Разрешите запрошенные Drive / Sheets / Apps Script права.")
    if not webbrowser.open(auth_url, new=1, autoraise=True):
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
    req = urllib.request.Request(client["token_uri"], data=body, headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            token = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:600]
        die(f"Google token exchange HTTP {exc.code}: {detail}")
    access_token = str(token.get("access_token", "")).strip()
    if not access_token:
        die("Google OAuth did not return access_token.")
    return access_token


def api_json(method: str, url: str, access_token: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None if body is None else json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json", "Content-Type": "application/json"}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1200]
        raise RuntimeError(f"Google API {method} {url} -> HTTP {exc.code}: {detail}") from exc


def verify_root(access_token: str, project: dict[str, Any]) -> None:
    fields = urllib.parse.quote("id,name,mimeType,trashed")
    item = api_json("GET", f"{DRIVE_API}/files/{project['root_id']}?fields={fields}&supportsAllDrives=true", access_token)
    if item.get("id") != project["root_id"] or item.get("name") != project["root_name"]:
        die(f"Google account does not see expected root: {project['root_name']}")
    if item.get("mimeType") != "application/vnd.google-apps.folder" or item.get("trashed") is True:
        die(f"Invalid root folder: {project['root_name']}")
    print(f"Drive root {project['root_name']}: PASS")


def js_config(project_id: str, project: dict[str, Any], secret: str) -> str:
    return (
        "const BRIDGE_DEPLOYMENT_CONFIG = Object.freeze({\n"
        f"  secret: {json.dumps(secret)},\n"
        f"  projectId: {json.dumps(project_id)},\n"
        f"  rootId: {json.dumps(project['root_id'])},\n"
        f"  rootName: {json.dumps(project['root_name'], ensure_ascii=False)},\n"
        f"  sheetsEnabled: {'true' if project['sheets_enabled'] else 'false'},\n"
        "  smallMaxBytes: 5242880\n"
        "});\n"
    )


def create_script_project(access_token: str, repo_root: Path, project_id: str, project: dict[str, Any], secret: str) -> dict[str, str]:
    created_script_id = ""
    try:
        created = api_json("POST", f"{SCRIPT_API}/projects", access_token, {"title": project["title"]})
        created_script_id = str(created.get("scriptId", "")).strip()
        if not created_script_id:
            die(f"Apps Script project create returned no scriptId for {project_id}")
        bridge_source = (repo_root / "shared/google-drive-bridge/bridge.gs").read_text(encoding="utf-8")
        manifest_source = (repo_root / "shared/google-drive-bridge/appsscript.json").read_text(encoding="utf-8")
        bootstrap_source = (
            "function bridgeAuthorizeOwner() {\n"
            "  const cfg = config_();\n"
            "  const root = DriveApp.getFolderById(cfg.rootId);\n"
            "  const name = root.getName();\n"
            "  UrlFetchApp.fetch('https://www.googleapis.com/discovery/v1/apis', {muteHttpExceptions:true});\n"
            "  return {ok:true, project_id:cfg.projectId, root_id:root.getId(), root_name:name};\n"
            "}\n"
        )
        content = {
            "files": [
                {"name": "bridge", "type": "SERVER_JS", "source": bridge_source},
                {"name": "deployment_config", "type": "SERVER_JS", "source": js_config(project_id, project, secret)},
                {"name": "bootstrap_authorize", "type": "SERVER_JS", "source": bootstrap_source},
                {"name": "appsscript", "type": "JSON", "source": manifest_source},
            ]
        }
        api_json("PUT", f"{SCRIPT_API}/projects/{created_script_id}/content", access_token, content)
        version = api_json("POST", f"{SCRIPT_API}/projects/{created_script_id}/versions", access_token, {"description": "Yandex Google Drive Bridge v1 bootstrap"})
        version_number = int(version.get("versionNumber") or 0)
        if version_number <= 0:
            die(f"Apps Script version create failed for {project_id}")
        deployment = api_json("POST", f"{SCRIPT_API}/projects/{created_script_id}/deployments", access_token, {
            "versionNumber": version_number,
            "manifestFileName": "appsscript",
            "description": f"Bridge v1 {project_id}",
        })
        deployment_id = str(deployment.get("deploymentId", "")).strip()
        web_url = ""
        for entry in deployment.get("entryPoints") or []:
            if entry.get("entryPointType") == "WEB_APP":
                web_url = str((entry.get("webApp") or {}).get("url") or "").strip()
                if web_url:
                    break
        if not deployment_id or not web_url:
            die(f"Apps Script deployment returned no web-app URL for {project_id}")
        print(f"Apps Script {project_id}: project/version/deployment created — PASS")
        return {"script_id": created_script_id, "deployment_id": deployment_id, "url": web_url}
    except Exception:
        if created_script_id:
            try:
                req = urllib.request.Request(f"{DRIVE_API}/files/{created_script_id}", headers={"Authorization": f"Bearer {access_token}"}, method="DELETE")
                urllib.request.urlopen(req, timeout=30).read()
                print(f"Rolled back incomplete Apps Script project {project_id}.")
            except Exception:
                print(f"WARNING: failed to remove incomplete Apps Script project for {project_id}.", file=sys.stderr)
        raise


def bridge_health(url: str, project_id: str, secret: str) -> dict[str, Any]:
    request_id = secrets.token_hex(16)
    body = json.dumps({"secret": secret, "project_id": project_id, "request_id": request_id, "action": "health", "payload": {}}).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "Accept": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as response:
        raw = response.read().decode("utf-8")
    data = json.loads(raw)
    if data.get("ok") is not True:
        raise RuntimeError(f"Bridge {project_id} health failed: {data.get('error')}")
    if data.get("request_id") != request_id:
        raise RuntimeError(f"Bridge {project_id} request_id mismatch")
    return data


def ensure_bridge_authorized(record: dict[str, str], project_id: str, secret: str) -> None:
    last: Exception | None = None
    for _ in range(12):
        try:
            data = bridge_health(record["url"], project_id, secret)
            result = data.get("result") or {}
            if result.get("project_id") != project_id:
                raise RuntimeError("project_id mismatch")
            print(f"Bridge {project_id} live health: PASS")
            return
        except Exception as exc:
            last = exc
            time.sleep(5)
    print(f"Bridge {project_id} needs owner authorization once.")
    edit_url = f"https://script.google.com/d/{record['script_id']}/edit"
    webbrowser.open(edit_url, new=1, autoraise=True)
    print("В открывшемся Apps Script выберите функцию bridgeAuthorizeOwner, нажмите Run и подтвердите разрешения Google.")
    input("После успешного выполнения функции нажмите Enter здесь: ")
    for _ in range(12):
        try:
            bridge_health(record["url"], project_id, secret)
            print(f"Bridge {project_id} owner authorization: PASS")
            return
        except Exception as exc:
            last = exc
            time.sleep(5)
    raise RuntimeError(f"Bridge {project_id} still not healthy after owner authorization: {last}")


def newest_dispatch_run(workflow: str, after_epoch: float) -> dict[str, Any]:
    deadline = time.time() + 90
    while time.time() < deadline:
        proc = run_gh(["run", "list", "--repo", REPO, "--workflow", workflow, "--event", "workflow_dispatch", "--limit", "10", "--json", "databaseId,createdAt,status,conclusion,url"], capture=True)
        for run in json.loads(proc.stdout or "[]"):
            created = str(run.get("createdAt", ""))
            try:
                ts = datetime.fromisoformat(created.replace("Z", "+00:00")).astimezone(timezone.utc).timestamp()
            except ValueError:
                continue
            if ts >= after_epoch - 10:
                return run
        time.sleep(2)
    die(f"GitHub Actions run did not appear for {workflow}")


def dispatch_and_watch(workflow: str, fields: dict[str, str]) -> int:
    args = ["workflow", "run", workflow, "--repo", REPO, "--ref", "main"]
    for key, value in fields.items():
        args.extend(["-f", f"{key}={value}"])
    started = time.time()
    run_gh(args, capture=True)
    run = newest_dispatch_run(workflow, started)
    run_id = int(run["databaseId"])
    print(f"GitHub Actions {workflow} #{run_id}")
    run_gh(["run", "watch", str(run_id), "--repo", REPO, "--exit-status"])
    return run_id


def main() -> int:
    parser = argparse.ArgumentParser(description="Create and validate isolated Marketplaces/Birzha Apps Script Bridge v1 deployments.")
    parser.add_argument("--credentials", type=Path, default=None, help="Google Desktop OAuth credentials JSON")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    if not (repo_root / "shared/google-drive-bridge/bridge.gs").is_file():
        die(f"Invalid infrastructure checkout: {repo_root}")
    if "injected.secret" not in (repo_root / "shared/google-drive-bridge/bridge.gs").read_text(encoding="utf-8"):
        die("Bridge source is not finalization-ready: deployment config fallback is missing.")
    if shutil.which("gh") is None:
        die("GitHub CLI (gh) not found.")
    run_gh(["auth", "status", "--hostname", "github.com"], capture=True)

    credentials = discover_credentials(args.credentials)
    client = load_client(credentials)
    access_token = authorize(client)
    for project in PROJECTS.values():
        verify_root(access_token, project)

    secrets_by_project = {name: secrets.token_urlsafe(72) for name in PROJECTS}
    records: dict[str, dict[str, str]] = {}
    temp_secrets: list[str] = []
    try:
        try:
            for name, project in PROJECTS.items():
                records[name] = create_script_project(access_token, repo_root, name, project, secrets_by_project[name])
        except RuntimeError as exc:
            if "403" in str(exc):
                print("Google Apps Script API access may be disabled for this account/client.")
                webbrowser.open(APPS_SCRIPT_SETTINGS, new=1, autoraise=True)
                print("Включите 'Google Apps Script API' в Apps Script Settings, затем повторите запуск.")
            raise

        for name in PROJECTS:
            ensure_bridge_authorized(records[name], name, secrets_by_project[name])

        for name, project in PROJECTS.items():
            secret_name = project["bootstrap_secret"]
            run_gh(["secret", "set", secret_name, "--env", "test", "--repo", REPO], input_text=secrets_by_project[name], capture=True)
            temp_secrets.append(secret_name)
            print(f"Temporary GitHub Environment secret for {name}: SET")

        bootstrap_runs = {}
        for name, project in PROJECTS.items():
            bootstrap_runs[name] = dispatch_and_watch(project["bootstrap_workflow"], {"bridge_url": records[name]["url"]})
            print(f"Bootstrap {name}: PASS")

        acceptance_runs = {}
        for name, project in PROJECTS.items():
            acceptance_runs[name] = dispatch_and_watch(project["acceptance_workflow"], {
                "bridge_url": records[name]["url"],
                "foreign_file_id": project["foreign_file_id"],
            })
            print(f"Acceptance {name}: PASS")

        safe = {
            name: {
                "script_id": records[name]["script_id"],
                "deployment_id": records[name]["deployment_id"],
                "url": records[name]["url"],
                "bootstrap_run_id": bootstrap_runs[name],
                "acceptance_run_id": acceptance_runs[name],
            }
            for name in PROJECTS
        }
        state_path = repo_root / "control/bridge-v1-owner-bootstrap-result.json"
        state_path.write_text(json.dumps(safe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Non-secret bootstrap result: {state_path}")
        print("BRIDGE_V1_OWNER_BOOTSTRAP=PASS")
    finally:
        for secret_name in temp_secrets:
            try:
                run_gh(["secret", "delete", secret_name, "--env", "test", "--repo", REPO], capture=True)
                print(f"Temporary GitHub Environment secret {secret_name}: DELETED")
            except subprocess.CalledProcessError:
                print(f"WARNING: failed to delete temporary GitHub secret {secret_name}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        cmd = " ".join(exc.cmd) if isinstance(exc.cmd, list) else str(exc.cmd)
        print(f"COMMAND FAILED: {cmd}", file=sys.stderr)
        raise SystemExit(exc.returncode or 1)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
