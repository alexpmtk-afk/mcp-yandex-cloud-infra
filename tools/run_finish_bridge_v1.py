#!/usr/bin/env python3
"""Runtime wrapper for the Bridge v1 finisher.

Apps Script web-app redeployments can briefly return HTTP 404 or the previous
bootstrap version while the new deployment propagates. The canonical finisher
expects the final Bridge health immediately after redeploy, so this wrapper
adds a bounded retry around that final health check without weakening any
identity/release/root validation.
"""
from __future__ import annotations

import subprocess
import sys
import time

import finish_bridge_v1 as finisher

_original_bridge_health = finisher.base.bridge_health


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


finisher.base.bridge_health = bridge_health_with_propagation_retry


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
