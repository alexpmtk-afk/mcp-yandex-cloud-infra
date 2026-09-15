#!/usr/bin/env python3
"""One owner command: Apps Script -> Lockbox -> acceptance -> production cutovers.

The only interactive step is Google's owner OAuth/Apps Script consent opened by
clasp. Everything after that is dispatched, watched, and failed closed here.
No durable secret is printed or written to this repository.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import bootstrap_bridge_v1_apps_script as base

INFRA_REPO = "alexpmtk-afk/mcp-yandex-cloud-infra"
MARKETPLACES_REPO = "alexpmtk-afk/marketplaces-mcp-ru"
BIRZHA_REPO = "alexpmtk-afk/birzha-mcp-forecast"
BIRZHA_PUBLISH_WORKFLOW = "publish-m25-worker-image.yml"


def die(message: str) -> None:
    raise RuntimeError(message)


def gh(args: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return base.run_gh(args, capture=capture)


def main_sha(repo: str) -> str:
    result = gh(["api", f"repos/{repo}/branches/main", "--jq", ".commit.sha"], capture=True)
    sha = (result.stdout or "").strip()
    if len(sha) != 40 or any(ch not in "0123456789abcdef" for ch in sha.lower()):
        die(f"Could not resolve canonical main SHA for {repo}")
    return sha


def list_workflow_runs(repo: str, workflow: str) -> list[dict[str, Any]]:
    result = gh(
        [
            "run", "list", "--repo", repo, "--workflow", workflow,
            "--event", "workflow_dispatch", "--limit", "50",
            "--json", "databaseId,headSha,createdAt,status,conclusion",
        ],
        capture=True,
    )
    rows = json.loads(result.stdout or "[]")
    if not isinstance(rows, list):
        die(f"Unexpected workflow run list for {repo}/{workflow}")
    return rows


def dispatch_and_watch(
    repo: str,
    workflow: str,
    *,
    ref: str = "main",
    inputs: dict[str, str] | None = None,
    expected_head_sha: str | None = None,
) -> int:
    args = ["workflow", "run", workflow, "--repo", repo, "--ref", ref]
    for key, value in (inputs or {}).items():
        args += ["-f", f"{key}={value}"]
    dispatched_at = datetime.now(timezone.utc)
    gh(args, capture=True)

    deadline = time.monotonic() + 150
    run_id = 0
    while time.monotonic() < deadline:
        for row in list_workflow_runs(repo, workflow):
            try:
                created = datetime.fromisoformat(str(row.get("createdAt") or "").replace("Z", "+00:00"))
            except ValueError:
                continue
            if created < dispatched_at:
                continue
            if expected_head_sha and str(row.get("headSha") or "") != expected_head_sha:
                continue
            candidate = int(row.get("databaseId") or 0)
            if candidate:
                run_id = candidate
                break
        if run_id:
            break
        time.sleep(2)
    if not run_id:
        die(f"Could not resolve dispatched run {repo}/{workflow}")

    watched = base.run(
        ["gh", "run", "watch", str(run_id), "--repo", repo, "--exit-status"],
        capture=False,
        check=False,
    )
    if watched.returncode != 0:
        die(f"Workflow failed: {repo}/{workflow} run={run_id}")
    print(f"{repo}/{workflow}: PASS (run {run_id})")
    return run_id


def ensure_birzha_image_published(source_sha: str) -> int:
    for row in list_workflow_runs(BIRZHA_REPO, BIRZHA_PUBLISH_WORKFLOW):
        if (
            str(row.get("headSha") or "") == source_sha
            and row.get("status") == "completed"
            and row.get("conclusion") == "success"
        ):
            run_id = int(row.get("databaseId") or 0)
            if run_id:
                print(f"Birzha M25 image already published for {source_sha[:12]} (run {run_id})")
                return run_id
    return dispatch_and_watch(
        BIRZHA_REPO,
        BIRZHA_PUBLISH_WORKFLOW,
        ref="main",
        expected_head_sha=source_sha,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Finish Bridge v1 end-to-end production activation")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Path to canonical mcp-yandex-cloud-infra checkout",
    )
    parser.add_argument("--keep-clasp-login", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    for tool in ("python", "node", "npm", "npx", "gh"):
        base.require_tool(tool)
    base.bridge_source(repo_root)
    base.bootstrap_source(repo_root)
    gh(["auth", "status"], capture=True)

    records: dict[str, dict[str, str]] = {}
    runs: dict[str, int] = {}
    source_shas: dict[str, str] = {}
    temp_secret_names = [str(p["bootstrap_secret"]) for p in base.PROJECTS.values()]
    work_root = Path(tempfile.mkdtemp(prefix="bridge-v1-finish-"))

    try:
        base.ensure_clasp_login()

        for project_id, project in base.PROJECTS.items():
            print(f"=== APPS SCRIPT {project_id.upper()} ===")
            records[project_id] = base.deploy_project(repo_root, work_root, project_id, project)

        for project_id, project in base.PROJECTS.items():
            base.set_temp_secret(str(project["bootstrap_secret"]), records[project_id]["secret"])
            base.set_environment_variable(
                f"{project_id.upper()}_GDRIVE_BRIDGE_V1_URL",
                records[project_id]["url"],
            )

        for project_id in ("marketplaces", "birzha"):
            runs[f"{project_id}_lockbox"] = base.dispatch_and_watch(
                "google-drive-bridge-v1-lockbox-bootstrap.yml",
                {"project": project_id, "bridge_url": records[project_id]["url"]},
            )

        for project_id, project in base.PROJECTS.items():
            runs[f"{project_id}_acceptance"] = base.dispatch_and_watch(
                project["acceptance_workflow"],
                {"bridge_url": records[project_id]["url"]},
            )

        runs["cross_project"] = base.dispatch_and_watch(
            "google-drive-bridge-v1-cross-project-acceptance.yml",
            {
                "marketplaces_url": records["marketplaces"]["url"],
                "birzha_url": records["birzha"]["url"],
            },
        )

        for project_id, project in base.PROJECTS.items():
            runs[f"{project_id}_cutover_gate"] = base.dispatch_and_watch(project["cutover_gate"])

        source_shas["marketplaces"] = main_sha(MARKETPLACES_REPO)
        runs["marketplaces_cutover"] = dispatch_and_watch(
            INFRA_REPO,
            "marketplaces-drive-bridge-v1-cutover.yml",
            inputs={"source_sha": source_shas["marketplaces"]},
        )

        source_shas["birzha"] = main_sha(BIRZHA_REPO)
        runs["birzha_m25_publish"] = ensure_birzha_image_published(source_shas["birzha"])
        runs["birzha_cutover"] = dispatch_and_watch(
            INFRA_REPO,
            "birzha-drive-bridge-v1-cutover.yml",
            inputs={"source_sha": source_shas["birzha"]},
        )

        safe = {
            "protocol_version": base.EXPECTED_PROTOCOL,
            "bridge_release": base.EXPECTED_RELEASE,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "projects": {
                project_id: {
                    "script_id": record["script_id"],
                    "deployment_id": record["deployment_id"],
                    "url": record["url"],
                    "source_sha": source_shas.get(project_id),
                }
                for project_id, record in records.items()
            },
            "workflow_runs": runs,
            "result": "BRIDGE_V1_END_TO_END_PRODUCTION_PASS",
        }
        state_path = repo_root / "control/bridge-v1-owner-bootstrap-result.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(safe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Non-secret result: {state_path}")
        print("BRIDGE_V1_END_TO_END_PRODUCTION=PASS")
        return 0
    finally:
        for name in temp_secret_names:
            try:
                base.delete_temp_secret(name)
                print(f"Temporary GitHub secret {name}: DELETED")
            except Exception:
                print(f"WARNING: could not delete temporary GitHub secret {name}", file=sys.stderr)
        shutil.rmtree(work_root, ignore_errors=True)
        if not args.keep_clasp_login:
            try:
                base.clasp(["logout"], capture=True, check=False)
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
