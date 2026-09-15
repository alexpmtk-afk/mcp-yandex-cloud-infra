#!/usr/bin/env python3
"""Resume-aware Apps Script deployment helper for Bridge v1.

Reuses the exact Apps Script web-app deployment recorded in the GitHub test
Environment variable when possible. This prevents repeated owner runs from
creating duplicate Apps Script projects after a downstream Yandex/GitHub
failure. If no recorded deployment can be resolved, the canonical creator is
used as a safe fallback.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import bootstrap_bridge_v1_apps_script as base

REPO = "alexpmtk-afk/mcp-yandex-cloud-infra"


def _json_list(text: str) -> list[dict[str, Any]]:
    try:
        data = json.loads(text or "[]")
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("scripts", "items", "deployments", "results"):
            value = data.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
    return []


def _deployment_id_from_url(url: str) -> str:
    m = re.fullmatch(r"https://script\.google\.com/macros/s/(AKfy[A-Za-z0-9_-]+)/exec", url.strip())
    return m.group(1) if m else ""


def _recorded_url(project_id: str) -> str:
    name = f"{project_id.upper()}_GDRIVE_BRIDGE_V1_URL"
    result = base.run_gh(
        ["variable", "get", name, "--env", "test", "--repo", REPO],
        capture=True,
    )
    if result.returncode != 0:
        return ""
    return (result.stdout or "").strip()


def _list_scripts() -> list[dict[str, Any]]:
    result = base.clasp(["list-scripts", "--json"], capture=True, check=False)
    if result.returncode != 0:
        return []
    return _json_list(result.stdout or "")


def _script_id(item: dict[str, Any]) -> str:
    for key in ("scriptId", "script_id", "id"):
        value = str(item.get(key) or "").strip()
        if value:
            return value
    return ""


def _script_title(item: dict[str, Any]) -> str:
    for key in ("title", "name"):
        value = str(item.get(key) or "").strip()
        if value:
            return value
    return ""


def _list_deployments(script_id: str) -> list[dict[str, Any]]:
    result = base.clasp(["list-deployments", script_id, "--json"], capture=True, check=False)
    if result.returncode != 0:
        return []
    return _json_list(result.stdout or "")


def _deployment_id(item: dict[str, Any]) -> str:
    for key in ("deploymentId", "deployment_id", "id"):
        value = str(item.get(key) or "").strip()
        if value.startswith("AKfy"):
            return value
    return ""


def find_recorded_project(project_id: str, project: dict[str, Any]) -> tuple[str, str, str] | None:
    url = _recorded_url(project_id)
    deployment_id = _deployment_id_from_url(url)
    if not deployment_id:
        return None
    title = str(project["title"])
    for item in _list_scripts():
        if _script_title(item) != title:
            continue
        script_id = _script_id(item)
        if not script_id:
            continue
        if any(_deployment_id(dep) == deployment_id for dep in _list_deployments(script_id)):
            return script_id, deployment_id, url
    return None


def _write_clasp_project(project_dir: Path, script_id: str) -> None:
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / ".clasp.json").write_text(
        json.dumps({"scriptId": script_id}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def deploy_or_reuse_project(
    repo_root: Path,
    work_root: Path,
    project_id: str,
    project: dict[str, Any],
) -> dict[str, str]:
    existing = find_recorded_project(project_id, project)
    if not existing:
        print(f"No reusable recorded Apps Script found for {project_id}; creating canonical deployment.")
        return base.deploy_project(repo_root, work_root, project_id, project)

    script_id, deployment_id, url = existing
    print(f"Reusing recorded Apps Script deployment for {project_id}: {deployment_id[:12]}...")
    project_dir = work_root / project_id
    _write_clasp_project(project_dir, script_id)

    import secrets
    token = secrets.token_urlsafe(48)
    secret = secrets.token_urlsafe(64)

    base.prepare_bootstrap_project(repo_root, project_dir, project_id, project, token)
    base.clasp(["push", "--force"], cwd=project_dir, capture=True)
    base.create_deployment(project_dir, f"Bridge v1 {project_id} secure bootstrap resume", deployment_id)
    base.wait_for_owner_authorization(url, token, project_id)
    base.install_script_properties(url, token, project_id, secret)

    base.prepare_final_project(repo_root, project_dir)
    base.clasp(["push", "--force"], cwd=project_dir, capture=True)
    base.create_deployment(project_dir, f"Bridge v1 {project_id} release {base.EXPECTED_RELEASE}", deployment_id)
    base.bridge_health(url, project_id, secret)
    base.prove_bootstrap_removed(url, project_id)
    base.prove_remote_source_clean(project_dir, secret, token, project_id)
    return {
        "script_id": script_id,
        "deployment_id": deployment_id,
        "url": url,
        "secret": secret,
    }
