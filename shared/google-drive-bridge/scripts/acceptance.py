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


def env(name: str, *, required: bool = True) -> str:
    value = (os.getenv(name) or "").strip()
    if required and not value:
        raise RuntimeError(f"{name} is required")
    return value


async def expect_error(coro, code: str) -> None:
    try:
        await coro
    except BridgeError as exc:
        if exc.code != code:
            raise RuntimeError(f"expected {code}, got {exc.code}: {exc}") from exc
        return
    raise RuntimeError(f"expected bridge error {code}")


async def _concurrent_resource_acceptance(client: GoogleDriveBridgeClient, project: str, path: str) -> None:
    async def one(slot: str) -> tuple[str, bytes, str]:
        payload = f"bridge-v1-concurrency:{project}:{slot}:".encode() + secrets.token_bytes(128)
        sha = hashlib.sha256(payload).hexdigest()
        name = f"concurrent-{slot}-{project}.bin"
        result = await client.write_small(
            path,
            name,
            payload,
            mime_type="application/octet-stream",
            idempotency_key=f"acceptance-concurrent:{project}:{slot}:{sha}",
        )
        file_id = str((result.get("file") or {}).get("id") or "")
        if not file_id:
            raise RuntimeError(f"concurrent write {slot} returned no file id")
        return name, payload, file_id

    results = await asyncio.gather(one("a"), one("b"), one("c"), one("d"))
    try:
        reads = await asyncio.gather(*(client.read_small(path, name) for name, _, _ in results))
        for (name, expected, file_id), (meta, raw) in zip(results, reads):
            if raw != expected:
                raise RuntimeError(f"concurrent read bytes mismatch for {name}")
            if str((meta or {}).get("id") or "") != file_id:
                raise RuntimeError(f"concurrent read file id mismatch for {name}")
    finally:
        await asyncio.gather(*(
            client.trash_by_id(file_id, idempotency_key=f"acceptance-concurrent-trash:{project}:{file_id}")
            for _, _, file_id in results
        ))


async def main() -> None:
    url = env("GDRIVE_BRIDGE_URL")
    secret = env("GDRIVE_BRIDGE_SECRET")
    project = env("GDRIVE_BRIDGE_PROJECT_ID")
    expected_root = env("GDRIVE_BRIDGE_EXPECTED_ROOT_ID")
    foreign_file_id = env("GDRIVE_BRIDGE_FOREIGN_FILE_ID", required=False)

    client = GoogleDriveBridgeClient(BridgeConfig(url=url, secret=secret, project_id=project))
    health = await client.health()
    assert health.get("project_id") == project, health
    assert health.get("root_id") == expected_root, health
    assert int(health.get("protocol_version") or 0) == 1, health
    print("HEALTH=PASS")

    wrong_project = GoogleDriveBridgeClient(
        BridgeConfig(url=url, secret=secret, project_id=f"{project}-wrong")
    )
    await expect_error(wrong_project.health(), "PROJECT_MISMATCH")
    print("WRONG_PROJECT=PASS")

    diag_path = ".bridge-acceptance"
    diag_name = f"acceptance-{project}.bin"
    payload = (f"bridge-v1:{project}:".encode("utf-8") + secrets.token_bytes(64))
    idem = f"acceptance-small:{project}:{hashlib.sha256(payload).hexdigest()}"

    first = await client.write_small(
        diag_path,
        diag_name,
        payload,
        mime_type="application/octet-stream",
        idempotency_key=idem,
    )
    first_file = dict(first.get("file") or {})
    file_id = str(first_file.get("id") or "")
    if not file_id:
        raise RuntimeError("small write returned no file id")

    second = await client.write_small(
        diag_path,
        diag_name,
        payload,
        mime_type="application/octet-stream",
        idempotency_key=idem,
    )
    second_id = str((second.get("file") or {}).get("id") or "")
    if second_id != file_id:
        raise RuntimeError("idempotent replay changed file id")

    read_meta, read_bytes = await client.read_small(diag_path, diag_name)
    if read_bytes != payload:
        raise RuntimeError("small read bytes mismatch")
    if str((read_meta or {}).get("id") or "") != file_id:
        raise RuntimeError("small read file id mismatch")
    print("SMALL_IO_AND_REPLAY=PASS")

    if foreign_file_id:
        await expect_error(client.metadata_by_id(foreign_file_id), "OUTSIDE_ROOT")
        print("FOREIGN_ROOT=PASS")
    else:
        print("FOREIGN_ROOT=SKIP (set GDRIVE_BRIDGE_FOREIGN_FILE_ID)")

    await _concurrent_resource_acceptance(client, project, diag_path)
    print("INDEPENDENT_RESOURCE_CONCURRENCY=PASS")

    await client.trash_by_id(
        file_id,
        idempotency_key=f"acceptance-trash:{project}:{file_id}",
    )
    print("DIAGNOSTIC_CLEANUP=PASS")

    if (os.getenv("GDRIVE_BRIDGE_RUN_LARGE") or "").strip() == "1":
        size = int((os.getenv("GDRIVE_BRIDGE_LARGE_BYTES") or str(16 * 1024 * 1024)).strip())
        large = secrets.token_bytes(size)
        sha = hashlib.sha256(large).hexdigest()
        large_name = f"acceptance-large-{project}.bin"
        large_idem = f"acceptance-large:{project}:{sha}"
        start = await client.resumable_start(
            diag_path,
            large_name,
            len(large),
            mime_type="application/octet-stream",
            idempotency_key=large_idem,
        )
        session_uri = str(start.get("session_uri") or "")
        if not session_uri:
            raise RuntimeError("resumable_start returned no session URI")
        final = await client.upload_resumable_chunks(
            session_uri,
            large,
            mime_type="application/octet-stream",
        )
        large_file_id = str(final.get("id") or start.get("file_id") or "")
        if not large_file_id:
            raise RuntimeError("Drive resumable upload returned no final file id")
        staging_name = str(start.get("staging_filename") or large_name)
        promoted = await client.promote_verified(
            path=diag_path,
            file_id=large_file_id,
            staging_filename=staging_name,
            canonical_filename=large_name,
            expected_bytes=len(large),
            expected_sha256=sha,
            previous_file_id=None,
            idempotency_key=f"acceptance-promote:{project}:{sha}",
        )
        meta = dict(promoted.get("file") or {})
        if int(meta.get("size") or -1) != len(large):
            raise RuntimeError("large size mismatch")
        if str(meta.get("sha256_checksum") or "").lower() != sha:
            raise RuntimeError("large SHA256 mismatch")
        print(f"LARGE_RESUMABLE={len(large)} bytes PASS")

        download_meta, downloaded = await client.download_large_by_id(
            large_file_id,
            max_bytes=max(len(large), 1),
        )
        if downloaded != large:
            raise RuntimeError("large direct-download bytes mismatch")
        if int(download_meta.get("size") or -1) != len(large):
            raise RuntimeError("large direct-download size mismatch")
        if str(download_meta.get("sha256_checksum") or "").lower() != sha:
            raise RuntimeError("large direct-download SHA256 mismatch")
        print(f"LARGE_DIRECT_DOWNLOAD={len(downloaded)} bytes SHA256 PASS")

        await client.trash_by_id(
            large_file_id,
            idempotency_key=f"acceptance-trash-large:{project}:{large_file_id}",
        )
    else:
        print("LARGE_RESUMABLE_AND_DOWNLOAD=SKIP (set GDRIVE_BRIDGE_RUN_LARGE=1)")

    print("COMMON_ACCEPTANCE=PASS")


if __name__ == "__main__":
    asyncio.run(main())