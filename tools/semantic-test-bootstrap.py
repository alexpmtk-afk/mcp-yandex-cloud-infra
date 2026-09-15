"""TEST-only bootstrap for running the vendored Marketplaces runtime from an immutable GitHub commit.

The container image remains unchanged. This script downloads the exact public
infra commit archive, proves that its vendored application points at the
approved Semantic Core source, then executes core.remote from that snapshot.
"""
from __future__ import annotations

import io
import os
from pathlib import Path
import runpy
import sys
import tarfile
import tempfile
import urllib.request

REPO = "alexpmtk-afk/mcp-yandex-cloud-infra"
EXPECTED_SEMANTIC_SOURCE = "920f3f1458a1700ad350d43cf35178256e8e858f"


def _safe_extract(tf: tarfile.TarFile, destination: Path) -> None:
    root = destination.resolve()
    for member in tf.getmembers():
        target = (destination / member.name).resolve()
        if target != root and root not in target.parents:
            raise RuntimeError(f"unsafe archive member: {member.name}")
    tf.extractall(destination)


def main() -> None:
    commit = os.environ.get("MARKETPLACE_SEMANTIC_BOOTSTRAP_COMMIT", "").strip()
    if len(commit) != 40 or any(ch not in "0123456789abcdef" for ch in commit):
        raise RuntimeError("MARKETPLACE_SEMANTIC_BOOTSTRAP_COMMIT must be a full lowercase commit SHA")

    url = f"https://github.com/{REPO}/archive/{commit}.tar.gz"
    req = urllib.request.Request(url, headers={"User-Agent": "marketplaces-semantic-test-bootstrap/1"})
    with urllib.request.urlopen(req, timeout=60) as response:
        payload = response.read()
    if len(payload) < 1024:
        raise RuntimeError("downloaded GitHub snapshot is unexpectedly small")

    temp_root = Path(tempfile.mkdtemp(prefix="marketplaces-semantic-"))
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as tf:
        _safe_extract(tf, temp_root)

    roots = [p for p in temp_root.iterdir() if p.is_dir()]
    if len(roots) != 1:
        raise RuntimeError(f"unexpected GitHub archive layout: {len(roots)} roots")
    app = roots[0] / "app"
    source_revision = app / ".source-revision"
    if not source_revision.is_file():
        raise RuntimeError("vendored app/.source-revision is missing")
    source_text = source_revision.read_text(encoding="utf-8")
    expected = f"Semantic Core source: alexpmtk-afk/marketplaces-mcp-ru@{EXPECTED_SEMANTIC_SOURCE}"
    if expected not in source_text:
        raise RuntimeError("vendored snapshot does not contain the approved Semantic Core source")

    required = [
        app / "core" / "business_router.py",
        app / "core" / "semantic_archive.py",
        app / "core" / "semantic_execution.yaml",
        app / "core" / "semantic_intents.yaml",
        app / "core" / "semantic_registry.yaml",
        app / "core" / "semantic_resolver.py",
        app / "core" / "remote.py",
    ]
    missing = [str(p.relative_to(app)) for p in required if not p.is_file()]
    if missing:
        raise RuntimeError(f"approved runtime snapshot is incomplete: {missing}")

    os.chdir(app)
    sys.path.insert(0, str(app))
    print(f"SEMANTIC_BOOTSTRAP_PASS commit={commit} source={EXPECTED_SEMANTIC_SOURCE}", flush=True)
    runpy.run_module("core.remote", run_name="__main__")


if __name__ == "__main__":
    main()
