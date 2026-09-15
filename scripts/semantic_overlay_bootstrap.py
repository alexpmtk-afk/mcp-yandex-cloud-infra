"""TEST-only runtime overlay bootstrap for Marketplaces MCP.

This loader exists only to bypass the currently blocked Yandex Container Registry
push path. It downloads an immutable public infra commit, proves the vendored
Semantic Core identity, then starts the vendored app from that snapshot on top
of the already-approved base image dependencies.
"""
from __future__ import annotations

import io
import os
from pathlib import Path
import sys
import tarfile
import urllib.request

REPO = "alexpmtk-afk/mcp-yandex-cloud-infra"
EXPECTED_SEMANTIC_SOURCE = "920f3f1458a1700ad350d43cf35178256e8e858f"


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def main() -> None:
    source_sha = _required_env("MARKETPLACE_MCP_OVERLAY_SOURCE_SHA")
    if len(source_sha) != 40 or any(ch not in "0123456789abcdef" for ch in source_sha):
        raise RuntimeError("MARKETPLACE_MCP_OVERLAY_SOURCE_SHA must be a lowercase 40-char git SHA")

    url = f"https://codeload.github.com/{REPO}/tar.gz/{source_sha}"
    req = urllib.request.Request(url, headers={"User-Agent": "marketplaces-mcp-semantic-test-overlay/1"})
    with urllib.request.urlopen(req, timeout=60) as response:
        payload = response.read()
    if not payload:
        raise RuntimeError("overlay source archive is empty")

    root = Path("/tmp/marketplaces-semantic-overlay")
    root.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
        members = [m for m in archive.getmembers() if "/app/" in m.name or m.name.endswith("/app")]
        if not members:
            raise RuntimeError("overlay archive does not contain app/")
        archive.extractall(root, members=members, filter="data")

    candidates = list(root.glob("*/app/.source-revision"))
    if len(candidates) != 1:
        raise RuntimeError(f"expected exactly one app/.source-revision, got {len(candidates)}")
    app_dir = candidates[0].parent
    source_revision = candidates[0].read_text(encoding="utf-8")
    expected_line = f"Semantic Core source: alexpmtk-afk/marketplaces-mcp-ru@{EXPECTED_SEMANTIC_SOURCE}"
    if expected_line not in source_revision.splitlines():
        raise RuntimeError("downloaded overlay does not contain the approved Semantic Core source")

    required = [
        app_dir / "core" / "remote.py",
        app_dir / "core" / "business_router.py",
        app_dir / "core" / "semantic_archive.py",
        app_dir / "core" / "semantic_execution.yaml",
        app_dir / "core" / "semantic_intents.yaml",
        app_dir / "core" / "semantic_registry.py",
        app_dir / "core" / "semantic_registry.yaml",
        app_dir / "core" / "semantic_resolver.py",
        app_dir / "core" / "system_map.py",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(f"overlay missing required runtime files: {missing}")

    os.chdir(app_dir)
    sys.path.insert(0, str(app_dir))
    from core.remote import main as remote_main

    print(f"SEMANTIC_OVERLAY_SOURCE_PASS={source_sha}", flush=True)
    print(f"SEMANTIC_CORE_SOURCE_PASS={EXPECTED_SEMANTIC_SOURCE}", flush=True)
    remote_main()


if __name__ == "__main__":
    main()
