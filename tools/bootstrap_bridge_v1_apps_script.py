#!/usr/bin/env python3
"""Finish Google Drive Bridge v1 owner bootstrap with official Google clasp OAuth.

The script performs all automatable work. The owner only completes Google's
interactive consent screens opened by clasp / Apps Script. No custom Desktop
OAuth credentials.json is required.

Security invariants:
- two independent Apps Script projects/deployments;
- final secrets are generated only in memory;
- final secrets are POSTed to a temporary bootstrap web app and stored only in
  Apps Script Script Properties plus the project-specific Yandex Lockbox;
- final secrets are never embedded in Apps Script source or URLs;
- temporary bootstrap source contains only a disposable bootstrap token and
  non-secret project/root metadata;
- bootstrap source is removed before the final v1.0.0 redeployment;
- temporary GitHub Environment secrets are deleted in a finally block.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = "alexpmtk-afk/mcp-yandex-cloud-infra"
CLASP_PACKAGE = "@google/clasp@3"
CLASP_USER = "bridge-v1-owner"
APPS_SCRIPT_SETTINGS = "https://script.google.com/home/usersettings"
EXPECTED_RELEASE = "1.0.0"
EXPECTED_PROTOCOL = 1
SMALL_MAX_BYTES = 5 * 1024 * 1024

PROJECTS: dict[str, dict[str, Any]] = {
    "marketplaces": {
        "title": "Yandex Google Drive Bridge v1 - Marketplaces",
        "root_id": "1UVKUcFfDhCDk6nMHX1mWg9cRL05DT-OJ",
        "root_name": "MCP архив базы данных",
        "sheets_enabled": False,
        "bootstrap_secret": "MARKETPLACES_GDRIVE_BRIDGE_V1_BOOTSTRAP_SECRET",
        "bootstrap_workflow": "marketplaces-drive-bridge-v1-bootstrap.yml",
        "acceptance_workflow": "marketplaces-drive-bridge-v1-acceptance.yml",
        "cutover_gate": "marketplaces-drive-bridge-v1-cutover-gate.yml",
    },
    "birzha": {
        "title": "Yandex Google Drive Bridge v1 - Birzha",
        "root_id": "1A7IzjXYSCWReZXdtrPZgZgLTnFIifsT2",
        "root_name": "Архив рыночных данных",
        "sheets_enabled": True,
        "bootstrap_secret": "BIRZHA_GDRIVE_BRIDGE_V1_BOOTSTRAP_SECRET",
        "bootstrap_workflow": "birzha-drive-bridge-v1-bootstrap.yml",
        "acceptance_workflow": "birzha-drive-bridge-v1-acceptance.yml",
        "cutover_gate": "birzha-drive-bridge-v1-cutover-gate.yml",
    },
}


def die(message: str) -> None:
    raise RuntimeError(message)


def require_tool(name: str) -> None:
    if not shutil.which(name):
        die(f"Required tool is not available in PATH: {name}")


def run(
    args: list[str],
    *,
    cwd: Path | None = None,
    input_text: str | None = None,
    capture: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        input=input_text,
        text=True,
        check=check,
        capture_output=capture,
    )


def run_gh(args: list[str], *, input_text: str | None = None, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return run(["gh", *args], input_text=input_text, capture=capture)


def clasp(args: list[str], *, cwd: Path | None = None, capture: bool = False, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(
        ["npx", "-y", CLASP_PACKAGE, "--user", CLASP_USER, *args],
        cwd=cwd,
        capture=capture,
        check=check,
    )


def ensure_clasp_login() -> None:
    probe = clasp(["show-authorized-user", "--json"], capture=True, check=False)
    if probe.returncode == 0:
        try:
            data = json.loads(probe.stdout or "{}")
        except json.JSONDecodeError:
            data = {}
        if data:
            print("Google clasp owner session: READY")
            return
    print("Открываю официальный Google clasp OAuth. Подтвердите доступ в браузере.")
    clasp(["login"])
    probe = clasp(["show-authorized-user", "--json"], capture=True)
    if not (probe.stdout or "").strip():
        die("clasp login completed without an authorized user")
    print("Google clasp owner session: PASS")


def bridge_manifest(repo_root: Path) -> str:
    return (repo_root / "shared/google-drive-bridge/appsscript.json").read_text(encoding="utf-8")


def bridge_source(repo_root: Path) -> str:
    source = (repo_root / "shared/google-drive-bridge/bridge.gs").read_text(encoding="utf-8")
    if "BRIDGE_RELEASE = '1.0.0'" not in source:
        die("Canonical bridge.gs is not stable release 1.0.0")
    if "NOT_IMPLEMENTED" in source:
        die("Canonical bridge.gs still contains NOT_IMPLEMENTED")
    return source


def bootstrap_source(repo_root: Path) -> str:
    return (repo_root / "shared/google-drive-bridge/bootstrap.gs").read_text(encoding="utf-8")


def bootstrap_config_source(project_id: str, project: dict[str, Any], token: str) -> str:
    return (
        "const BRIDGE_BOOTSTRAP_CONFIG = Object.freeze({\n"
        f"  token: {json.dumps(token)},\n"
        f"  projectId: {json.dumps(project_id)},\n"
        f"  rootId: {json.dumps(project['root_id'])},\n"
        f"  rootName: {json.dumps(project['root_name'], ensure_ascii=False)},\n"
        f"  sheetsEnabled: {'true' if project['sheets_enabled'] else 'false'},\n"
        f"  smallMaxBytes: {SMALL_MAX_BYTES}\n"
        "});\n"
    )


def read_script_id(project_dir: Path) -> str:
    path = project_dir / ".clasp.json"
    if not path.is_file():
        die(f"clasp did not create {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    value = str(data.get("scriptId") or "").strip()
    if not value:
        die(".clasp.json contains no scriptId")
    return value


def parse_deployment_id(text: str) -> str:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = None

    def walk(value: Any) -> str:
        if isinstance(value, dict):
            candidate = str(value.get("deploymentId") or value.get("deployment_id") or "").strip()
            if candidate:
                return candidate
            for child in value.values():
                found = walk(child)
                if found:
                    return found
        elif isinstance(value, list):
            for child in value:
                found = walk(child)
                if found:
                    return found
        return ""

    found = walk(data) if data is not None else ""
    if found:
        return found
    match = re.search(r"\b(AKfy[A-Za-z0-9_-]{20,})\b", text)
    if match:
        return match.group(1)
    die("Unable to resolve Apps Script deployment ID from clasp output")


def prepare_bootstrap_project(
    repo_root: Path,
    project_dir: Path,
    project_id: str,
    project: dict[str, Any],
    token: str,
) -> None:
    for child in project_dir.iterdir():
        if child.name == ".clasp.json":
            continue
        if child.is_file():
            child.unlink()
        elif child.is_dir():
            shutil.rmtree(child)
    (project_dir / "bootstrap.gs").write_text(bootstrap_source(repo_root), encoding="utf-8")
    (project_dir / "bootstrap_config.gs").write_text(
        bootstrap_config_source(project_id, project, token), encoding="utf-8"
    )
    (project_dir / "appsscript.json").write_text(bridge_manifest(repo_root), encoding="utf-8")


def prepare_final_project(repo_root: Path, project_dir: Path) -> None:
    for child in project_dir.iterdir():
        if child.name == ".clasp.json":
            continue
        if child.is_file():
            child.unlink()
        elif child.is_dir():
            shutil.rmtree(child)
    (project_dir / "bridge.gs").write_text(bridge_source(repo_root), encoding="utf-8")
    (project_dir / "appsscript.json").write_text(bridge_manifest(repo_root), encoding="utf-8")


def create_script(project_dir: Path, project: dict[str, Any]) -> str:
    project_dir.mkdir(parents=True, exist_ok=True)
    first = clasp(
        ["create-script", "--title", project["title"], "--type", "webapp", "--rootDir", ".", "--json"],
        cwd=project_dir,
        capture=True,
        check=False,
    )
    if first.returncode != 0:
        combined = (first.stdout or "") + "\n" + (first.stderr or "")
        if "Apps Script API" in combined or "script.googleapis.com" in combined:
            print("Apps Script API user setting is disabled. Opening Google setting page.")
            webbrowser.open(APPS_SCRIPT_SETTINGS, new=1, autoraise=True)
            input("Включите Google Apps Script API на открытой странице и нажмите Enter здесь: ")
            first = clasp(
                ["create-script", "--title", project["title"], "--type", "webapp", "--rootDir", ".", "--json"],
                cwd=project_dir,
                capture=True,
                check=False,
            )
        if first.returncode != 0:
            detail = ((first.stdout or "") + "\n" + (first.stderr or ""))[-1600:]
            die(f"clasp create-script failed: {detail}")
    return read_script_id(project_dir)


def create_deployment(project_dir: Path, description: str, deployment_id: str = "") -> str:
    args = ["create-deployment", "--description", description, "--json"]
    if deployment_id:
        args += ["--deploymentId", deployment_id]
    result = clasp(args, cwd=project_dir, capture=True)
    resolved = parse_deployment_id((result.stdout or "") + "\n" + (result.stderr or ""))
    if deployment_id and resolved != deployment_id:
        die("clasp redeploy returned a different deployment ID")
    return resolved


def http_json(url: str, *, payload: dict[str, Any] | None = None, timeout: int = 60) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Accept": "application/json"}
    method = "GET"
    if data is not None:
        headers["Content-Type"] = "application/json"
        method = "POST"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read().decode("utf-8", errors="replace")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Apps Script returned a non-JSON response") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("Apps Script returned a non-object JSON response")
    return parsed


def wait_for_owner_authorization(url: str, token: str, project_id: str, timeout_seconds: int = 600) -> None:
    owner_url = url + "?" + urllib.parse.urlencode({"bootstrap_token": token})
    print(f"Открываю Google authorization для {project_id}. Подтвердите разрешения, если Google их запросит.")
    if not webbrowser.open(owner_url, new=1, autoraise=True):
        die("Could not open the Google authorization page in the default browser")
    deadline = time.monotonic() + timeout_seconds
    last_error = ""
    while time.monotonic() < deadline:
        try:
            data = http_json(owner_url, timeout=30)
            if data.get("ok") is True and data.get("phase") == "bootstrap_authorized":
                if data.get("project_id") != project_id:
                    die(f"Bootstrap project identity mismatch for {project_id}")
                print(f"Google runtime authorization {project_id}: PASS")
                return
            last_error = str(data.get("error") or data)[:300]
        except Exception as exc:  # consent page / propagation while owner is interacting
            last_error = type(exc).__name__
        time.sleep(3)
    die(f"Google owner authorization did not complete for {project_id}: {last_error}")


def install_script_properties(url: str, token: str, project_id: str, secret: str) -> None:
    data = http_json(
        url,
        payload={
            "action": "bootstrap_install",
            "bootstrap_token": token,
            "secret": secret,
        },
    )
    if data.get("ok") is not True or data.get("phase") != "bootstrap_installed":
        die(f"Apps Script property bootstrap failed for {project_id}: {str(data)[:500]}")
    if data.get("project_id") != project_id:
        die(f"Apps Script property bootstrap identity mismatch for {project_id}")
    print(f"Script Properties {project_id}: PASS")


def bridge_health(url: str, project_id: str, secret: str) -> dict[str, Any]:
    request_id = uuid.uuid4().hex
    data = http_json(
        url,
        payload={
            "secret": secret,
            "project_id": project_id,
            "request_id": request_id,
            "action": "health",
            "payload": {},
        },
    )
    if data.get("ok") is not True:
        die(f"Bridge health failed for {project_id}: {str(data)[:500]}")
    if data.get("request_id") != request_id or data.get("project_id") != project_id:
        die(f"Bridge envelope identity mismatch for {project_id}")
    result = data.get("result") or {}
    if int(result.get("protocol_version") or 0) != EXPECTED_PROTOCOL:
        die(f"Bridge protocol mismatch for {project_id}")
    if result.get("bridge_release") != EXPECTED_RELEASE:
        die(f"Bridge release mismatch for {project_id}")
    if result.get("root_id") != PROJECTS[project_id]["root_id"]:
        die(f"Bridge root mismatch for {project_id}")
    print(f"Bridge final health {project_id}: PASS")
    return data


def prove_bootstrap_removed(url: str, project_id: str) -> None:
    data = http_json(
        url,
        payload={
            "project_id": project_id,
            "request_id": uuid.uuid4().hex,
            "action": "bootstrap_install",
            "bootstrap_token": "retired",
            "payload": {},
        },
    )
    if data.get("ok") is not False:
        die(f"Bootstrap surface unexpectedly remained active for {project_id}")
    error = data.get("error") or {}
    if error.get("code") != "UNAUTHORIZED":
        die(f"Unexpected final bootstrap probe result for {project_id}: {str(data)[:500]}")
    print(f"Bootstrap surface removed {project_id}: PASS")


def prove_remote_source_clean(project_dir: Path, secret: str, token: str, project_id: str) -> None:
    clasp(["pull"], cwd=project_dir, capture=True)
    offenders: list[str] = []
    for path in project_dir.iterdir():
        if not path.is_file() or path.name == ".clasp.json":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if secret in text or token in text or "BRIDGE_BOOTSTRAP_CONFIG" in text or "bootstrap_install" in text:
            offenders.append(path.name)
    if offenders:
        die(f"Final remote Apps Script source still contains bootstrap material for {project_id}: {offenders}")
    print(f"Remote source secret/bootstrap scan {project_id}: PASS")


def deploy_project(repo_root: Path, work_root: Path, project_id: str, project: dict[str, Any]) -> dict[str, str]:
    project_dir = work_root / project_id
    script_id = create_script(project_dir, project)
    token = secrets.token_urlsafe(48)
    secret = secrets.token_urlsafe(64)
    prepare_bootstrap_project(repo_root, project_dir, project_id, project, token)
    clasp(["push", "--force"], cwd=project_dir, capture=True)
    deployment_id = create_deployment(project_dir, f"Bridge v1 {project_id} secure bootstrap")
    url = f"https://script.google.com/macros/s/{deployment_id}/exec"
    wait_for_owner_authorization(url, token, project_id)
    install_script_properties(url, token, project_id, secret)

    prepare_final_project(repo_root, project_dir)
    clasp(["push", "--force"], cwd=project_dir, capture=True)
    create_deployment(project_dir, f"Bridge v1 {project_id} release {EXPECTED_RELEASE}", deployment_id)
    bridge_health(url, project_id, secret)
    prove_bootstrap_removed(url, project_id)
    prove_remote_source_clean(project_dir, secret, token, project_id)
    return {
        "script_id": script_id,
        "deployment_id": deployment_id,
        "url": url,
        "secret": secret,
    }


def set_temp_secret(name: str, value: str) -> None:
    run_gh(["secret", "set", name, "--env", "test", "--repo", REPO], input_text=value)


def delete_temp_secret(name: str) -> None:
    run_gh(["secret", "delete", name, "--env", "test", "--repo", REPO], capture=True)


def set_environment_variable(name: str, value: str) -> None:
    run_gh(["variable", "set", name, "--env", "test", "--repo", REPO, "--body", value], capture=True)


def dispatch_and_watch(workflow: str, inputs: dict[str, str] | None = None) -> int:
    args = ["workflow", "run", workflow, "--repo", REPO, "--ref", "main"]
    for key, value in (inputs or {}).items():
        args += ["-f", f"{key}={value}"]
    dispatched_at = datetime.now(timezone.utc)
    run_gh(args, capture=True)
    deadline = time.monotonic() + 120
    run_id = 0
    while time.monotonic() < deadline:
        listed = run_gh(
            [
                "run", "list", "--repo", REPO, "--workflow", workflow,
                "--event", "workflow_dispatch", "--limit", "10",
                "--json", "databaseId,createdAt,status,conclusion",
            ],
            capture=True,
        )
        rows = json.loads(listed.stdout or "[]")
        for row in rows:
            created_raw = str(row.get("createdAt") or "").replace("Z", "+00:00")
            try:
                created = datetime.fromisoformat(created_raw)
            except ValueError:
                continue
            if created >= dispatched_at and int(row.get("databaseId") or 0) > 0:
                run_id = int(row["databaseId"])
                break
        if run_id:
            break
        time.sleep(2)
    if not run_id:
        die(f"Could not resolve dispatched GitHub workflow run: {workflow}")
    watched = run_gh(["run", "watch", str(run_id), "--repo", REPO, "--exit-status"], capture=False, input_text=None)
    if watched.returncode != 0:
        die(f"GitHub workflow failed: {workflow} run={run_id}")
    print(f"{workflow}: PASS (run {run_id})")
    return run_id


def run_remote_acceptance(records: dict[str, dict[str, str]]) -> dict[str, int]:
    runs: dict[str, int] = {}
    for project_id, project in PROJECTS.items():
        runs[f"{project_id}_bootstrap"] = dispatch_and_watch(
            project["bootstrap_workflow"], {"bridge_url": records[project_id]["url"]}
        )
    for project_id, project in PROJECTS.items():
        runs[f"{project_id}_acceptance"] = dispatch_and_watch(
            project["acceptance_workflow"], {"bridge_url": records[project_id]["url"]}
        )
    runs["cross_project"] = dispatch_and_watch(
        "google-drive-bridge-v1-cross-project-acceptance.yml",
        {
            "marketplaces_url": records["marketplaces"]["url"],
            "birzha_url": records["birzha"]["url"],
        },
    )
    for project_id, project in PROJECTS.items():
        runs[f"{project_id}_cutover_gate"] = dispatch_and_watch(project["cutover_gate"])
    return runs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Finish owner-side Apps Script Bridge v1 deployment")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Path to canonical mcp-yandex-cloud-infra checkout",
    )
    parser.add_argument(
        "--keep-clasp-login",
        action="store_true",
        help="Do not delete the named clasp credential profile after completion",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    for tool in ("python", "node", "npm", "npx", "gh"):
        require_tool(tool)
    if not (repo_root / "shared/google-drive-bridge/bridge.gs").is_file():
        die(f"Canonical Bridge source not found under {repo_root}")
    bridge_source(repo_root)
    bootstrap_source(repo_root)
    run_gh(["auth", "status"], capture=True)

    temp_secret_names = [str(p["bootstrap_secret"]) for p in PROJECTS.values()]
    records: dict[str, dict[str, str]] = {}
    workflow_runs: dict[str, int] = {}
    work_root = Path(tempfile.mkdtemp(prefix="bridge-v1-owner-"))
    try:
        ensure_clasp_login()
        for project_id, project in PROJECTS.items():
            print(f"=== {project_id.upper()} ===")
            records[project_id] = deploy_project(repo_root, work_root, project_id, project)

        for project_id, project in PROJECTS.items():
            set_temp_secret(str(project["bootstrap_secret"]), records[project_id]["secret"])
            set_environment_variable(f"{project_id.upper()}_GDRIVE_BRIDGE_V1_URL", records[project_id]["url"])

        workflow_runs = run_remote_acceptance(records)

        safe = {
            "protocol_version": EXPECTED_PROTOCOL,
            "bridge_release": EXPECTED_RELEASE,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "projects": {
                project_id: {
                    "script_id": record["script_id"],
                    "deployment_id": record["deployment_id"],
                    "url": record["url"],
                }
                for project_id, record in records.items()
            },
            "workflow_runs": workflow_runs,
            "result": "BRIDGE_V1_OWNER_BOOTSTRAP_PASS",
        }
        state_path = repo_root / "control/bridge-v1-owner-bootstrap-result.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(safe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Non-secret result: {state_path}")
        print("BRIDGE_V1_OWNER_BOOTSTRAP=PASS")
        return 0
    finally:
        for name in temp_secret_names:
            try:
                delete_temp_secret(name)
                print(f"Temporary GitHub secret {name}: DELETED")
            except Exception:
                print(f"WARNING: could not delete temporary GitHub secret {name}", file=sys.stderr)
        shutil.rmtree(work_root, ignore_errors=True)
        if not args.keep_clasp_login:
            try:
                clasp(["logout"], capture=True, check=False)
                print("Temporary clasp owner profile: LOGGED OUT")
            except Exception:
                pass


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        cmd = " ".join(str(x) for x in exc.cmd) if isinstance(exc.cmd, list) else str(exc.cmd)
        print(f"COMMAND FAILED: {cmd}", file=sys.stderr)
        raise SystemExit(exc.returncode or 1)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
