#!/usr/bin/env python3
"""Runtime wrapper for the Bridge v1 finisher.

Apps Script web-app deployments can briefly return HTTP 404/5xx while a new
version propagates. This wrapper makes every deployment-bound transition
resilient without weakening semantic checks and reuses the exact deployment
URL already recorded for each project after a downstream failure.
"""
from __future__ import annotations

import subprocess
import sys
import time
import urllib.error

import finish_bridge_v1 as finisher
import resume_bridge_v1_apps_script as resume

_original_install_script_properties = finisher.base.install_script_properties
_original_bridge_health = finisher.base.bridge_health
_original_prove_bootstrap_removed = finisher.base.prove_bootstrap_removed

_TRANSIENT_HTTP_CODES = {404, 408, 425, 429, 500, 502, 503, 504}


def _is_transient_transport(exc: Exception) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return int(exc.code) in _TRANSIENT_HTTP_CODES
    return isinstance(exc, (urllib.error.URLError, TimeoutError, ConnectionError))


def _retry_transient_transport(call, *, label: str, project_id: str, timeout_seconds: int = 180):
    deadline = time.monotonic() + timeout_seconds
    attempt = 0
    last_exc: Exception | None = None
    while time.monotonic() < deadline:
        attempt += 1
        try:
            return call()
        except Exception as exc:
            if not _is_transient_transport(exc):
                raise
            last_exc = exc
            remaining = max(0, int(deadline - time.monotonic()))
            detail = f"HTTP {exc.code}" if isinstance(exc, urllib.error.HTTPError) else type(exc).__name__
            print(
                f"Apps Script {label} for {project_id} is still propagating "
                f"(attempt {attempt}, {detail}); waiting, {remaining}s left..."
            )
            time.sleep(3)
    if last_exc is not None:
        raise last_exc
    raise RuntimeError(f"Apps Script {label} did not become ready for {project_id}")


def install_script_properties_with_retry(
    url: str,
    token: str,
    project_id: str,
    secret: str,
    timeout_seconds: int = 180,
):
    return _retry_transient_transport(
        lambda: _original_install_script_properties(url, token, project_id, secret),
        label="bootstrap install",
        project_id=project_id,
        timeout_seconds=timeout_seconds,
    )


def bridge_health_with_propagation_retry(
    url: str,
    project_id: str,
    secret: str,
    timeout_seconds: int = 180,
):
    deadline = time.monotonic() + timeout_seconds
    last_exc: Exception | None = None
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        try:
            return _original_bridge_health(url, project_id, secret)
        except Exception as exc:
            last_exc = exc
            remaining = max(0, int(deadline - time.monotonic()))
            print(
                f"Apps Script final deployment for {project_id} is still propagating "
                f"(attempt {attempt}, {type(exc).__name__}); waiting, {remaining}s left..."
            )
            time.sleep(3)
    if last_exc is not None:
        raise last_exc
    raise RuntimeError(f"Apps Script final deployment did not become ready for {project_id}")


def prove_bootstrap_removed_with_retry(
    url: str,
    project_id: str,
    timeout_seconds: int = 180,
):
    deadline = time.monotonic() + timeout_seconds
    last_exc: Exception | None = None
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        try:
            return _original_prove_bootstrap_removed(url, project_id)
        except Exception as exc:
            last_exc = exc
            remaining = max(0, int(deadline - time.monotonic()))
            print(
                f"Apps Script bootstrap retirement for {project_id} is still propagating "
                f"(attempt {attempt}, {type(exc).__name__}); waiting, {remaining}s left..."
            )
            time.sleep(3)
    if last_exc is not None:
        raise last_exc
    raise RuntimeError(f"Apps Script bootstrap retirement did not become visible for {project_id}")


finisher.base.install_script_properties = install_script_properties_with_retry
finisher.base.bridge_health = bridge_health_with_propagation_retry
finisher.base.prove_bootstrap_removed = prove_bootstrap_removed_with_retry
# Resume uses the recorded GitHub environment URL to find the exact existing
# script/deployment and rotates only the secret on the same project identity.
finisher.base.deploy_project = resume.deploy_or_reuse_project


if __name__ == "__main__":
    try:
        raise SystemExit(finisher.main())
    except subprocess.CalledProcessError as exc:
        cmd = " ".join(str(x) for x in exc.cmd) if isinstance(exc.cmd, list) else str(exc.cmd)
        print(f"COMMAND FAILED: {cmd}", file=sys.stderr)
        raise SystemExit(exc.returncode or 1)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
