from __future__ import annotations

import asyncio
import hashlib
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python_client"))

from bridge_client import BridgeConfig, BridgeError, GoogleDriveBridgeClient  # noqa: E402


def env(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def client(prefix: str) -> tuple[GoogleDriveBridgeClient, str]:
    project = env(f"{prefix}_PROJECT_ID")
    cfg = BridgeConfig(
        url=env(f"{prefix}_URL"),
        secret=env(f"{prefix}_SECRET"),
        project_id=project,
    )
    return GoogleDriveBridgeClient(cfg), env(f"{prefix}_ROOT_ID")


async def expect_outside_root(client_: GoogleDriveBridgeClient, file_id: str) -> None:
    try:
        await client_.metadata_by_id(file_id)
    except BridgeError as exc:
        if exc.code != "OUTSIDE_ROOT":
            raise RuntimeError(f"expected OUTSIDE_ROOT, got {exc.code}: {exc}") from exc
        return
    raise RuntimeError("foreign project file_id was accepted")


async def write_probe(client_: GoogleDriveBridgeClient, project: str) -> tuple[str, str, bytes]:
    payload = f"cross-project:{project}:".encode() + secrets.token_bytes(256)
    sha = hashlib.sha256(payload).hexdigest()
    name = f"cross-project-{project}.bin"
    result = await client_.write_small(
        ".bridge-cross-project-acceptance",
        name,
        payload,
        mime_type="application/octet-stream",
        idempotency_key=f"cross-project:{project}:{sha}",
    )
    file_id = str((result.get("file") or {}).get("id") or "")
    if not file_id:
        raise RuntimeError(f"{project}: write returned no file id")
    return name, file_id, payload


async def main() -> None:
    a, root_a = client("BRIDGE_A")
    b, root_b = client("BRIDGE_B")
    if a.config.project_id == b.config.project_id:
        raise RuntimeError("project IDs must differ")
    if root_a == root_b:
        raise RuntimeError("fixed roots must differ")

    health_a, health_b = await asyncio.gather(a.health(), b.health())
    if health_a.get("root_id") != root_a or health_b.get("root_id") != root_b:
        raise RuntimeError("health root mismatch")
    print("CROSS_PROJECT_HEALTH=PASS")

    probe_a, probe_b = await asyncio.gather(
        write_probe(a, a.config.project_id),
        write_probe(b, b.config.project_id),
    )
    name_a, file_a, payload_a = probe_a
    name_b, file_b, payload_b = probe_b

    try:
        (meta_a, raw_a), (meta_b, raw_b) = await asyncio.gather(
            a.read_small(".bridge-cross-project-acceptance", name_a),
            b.read_small(".bridge-cross-project-acceptance", name_b),
        )
        if raw_a != payload_a or raw_b != payload_b:
            raise RuntimeError("concurrent project read-back mismatch")
        if str((meta_a or {}).get("id") or "") != file_a:
            raise RuntimeError("project A file id mismatch")
        if str((meta_b or {}).get("id") or "") != file_b:
            raise RuntimeError("project B file id mismatch")
        print("CROSS_PROJECT_CONCURRENT_IO=PASS")

        await asyncio.gather(
            expect_outside_root(a, file_b),
            expect_outside_root(b, file_a),
        )
        print("CROSS_PROJECT_ROOT_ISOLATION=PASS")
    finally:
        await asyncio.gather(
            a.trash_by_id(file_a, idempotency_key=f"cross-project-trash:{a.config.project_id}:{file_a}"),
            b.trash_by_id(file_b, idempotency_key=f"cross-project-trash:{b.config.project_id}:{file_b}"),
        )

    print("CROSS_PROJECT_ACCEPTANCE=PASS")


if __name__ == "__main__":
    asyncio.run(main())
