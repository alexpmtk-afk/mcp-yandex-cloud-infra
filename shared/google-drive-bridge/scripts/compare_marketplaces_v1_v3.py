from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "python_client"))
from bridge_client import BridgeConfig, BridgeError, GoogleDriveBridgeClient  # noqa: E402

MIB = 1024 * 1024
CHUNK = 4 * MIB
LARGE_BYTES = 16 * MIB
DIAG_PATH = ".bridge-comparison"


def env(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def deterministic_bytes(size: int) -> bytes:
    block = hashlib.sha256(b"marketplaces-bridge-v1-v3-comparison").digest()
    return (block * ((size + len(block) - 1) // len(block)))[:size]


def confirmed_offset(range_header: str) -> int:
    match = re.search(r"bytes=0-(\d+)", range_header or "")
    return int(match.group(1)) + 1 if match else 0


async def direct_resumable_with_forced_restart(session_uri: str, data: bytes, mime_type: str) -> tuple[dict[str, Any], int]:
    """Upload one chunk, throw away the client, query Drive offset, then resume."""
    total = len(data)
    first_end = min(total, CHUNK)
    headers = {
        "Content-Type": mime_type,
        "Content-Length": str(first_end),
        "Content-Range": f"bytes 0-{first_end - 1}/{total}",
    }
    async with httpx.AsyncClient(timeout=300, follow_redirects=False) as client:
        first = await client.put(session_uri, content=data[:first_end], headers=headers)
        if first.status_code not in {200, 201, 308}:
            raise RuntimeError(f"first resumable chunk HTTP {first.status_code}")
        if first.status_code in {200, 201}:
            return dict(first.json()), total

    # Simulate caller restart / lost local state. Google is authoritative.
    async with httpx.AsyncClient(timeout=300, follow_redirects=False) as client:
        probe = await client.put(
            session_uri,
            content=b"",
            headers={"Content-Length": "0", "Content-Range": f"bytes */{total}"},
        )
        if probe.status_code in {200, 201}:
            return dict(probe.json()), total
        if probe.status_code != 308:
            raise RuntimeError(f"resumable status probe HTTP {probe.status_code}")
        offset = confirmed_offset(probe.headers.get("Range", ""))
        if offset != first_end:
            raise RuntimeError(f"Drive confirmed offset {offset}, expected {first_end}")

        while offset < total:
            end = min(total, offset + CHUNK)
            part = data[offset:end]
            response = await client.put(
                session_uri,
                content=part,
                headers={
                    "Content-Type": mime_type,
                    "Content-Length": str(len(part)),
                    "Content-Range": f"bytes {offset}-{end - 1}/{total}",
                },
            )
            if response.status_code in {200, 201}:
                return dict(response.json()), offset
            if response.status_code != 308:
                raise RuntimeError(f"resumable upload HTTP {response.status_code}")
            next_offset = confirmed_offset(response.headers.get("Range", ""))
            if next_offset <= offset:
                raise RuntimeError(f"Drive offset did not advance: {offset} -> {next_offset}")
            offset = next_offset
    raise RuntimeError("resumable upload ended without final Drive response")


class V3:
    def __init__(self, url: str, secret: str):
        self.url = url
        self.secret = secret
        self.client = httpx.AsyncClient(timeout=300, follow_redirects=True)

    async def close(self) -> None:
        await self.client.aclose()

    async def call(self, action: str, *, expect_ok: bool = True, **payload: Any) -> dict[str, Any]:
        response = await self.client.post(
            self.url,
            json={"secret": self.secret, "action": action, **payload},
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        data = response.json()
        if expect_ok and data.get("ok") is not True:
            raise RuntimeError(f"v3 {action} rejected: {data.get('error')}")
        return data


async def compare_v3(run_id: str, foreign_id: str, large: bytes) -> dict[str, Any]:
    result: dict[str, Any] = {"bridge": "v3-marketplaces-specific"}
    v3 = V3(env("V3_URL"), env("V3_SECRET"))
    cleanup_ids: list[str] = []
    try:
        t0 = time.perf_counter()
        health = await v3.call("health")
        result["health_seconds"] = round(time.perf_counter() - t0, 3)
        result["health_pass"] = health.get("version") == 3 and health.get("root_id") == env("ROOT_ID")
        result["capabilities"] = health.get("capabilities") or {}

        outside = await v3.call("metadata_by_id", expect_ok=False, file_id=foreign_id)
        result["outside_root_pass"] = outside.get("ok") is False and str(outside.get("error") or "") == "file_outside_archive_root"

        small_name = f".bridge-v3-small.diagnostic-report-{run_id}.csv"
        payload = b"bridge-v3-small:" + deterministic_bytes(512)
        sha = hashlib.sha256(payload).hexdigest()
        first = await v3.call(
            "write", path=DIAG_PATH, filename=small_name, mime_type="text/csv",
            content_base64=base64.b64encode(payload).decode(), sha256=sha,
        )
        first_id = str((first.get("file") or {}).get("id") or "")
        second = await v3.call(
            "write", path=DIAG_PATH, filename=small_name, mime_type="text/csv",
            content_base64=base64.b64encode(payload).decode(), sha256=sha,
        )
        second_id = str((second.get("file") or {}).get("id") or "")
        if second_id:
            cleanup_ids.append(second_id)
        read = await v3.call("read", path=DIAG_PATH, filename=small_name)
        raw = base64.b64decode(str(read.get("content_base64") or ""), validate=True)
        result["small_io_pass"] = raw == payload
        # v3's generic write is intentionally replacement-based, not a protocol-level idempotent mutation.
        result["generic_write_replay_same_file_id"] = bool(first_id) and first_id == second_id

        async def concurrent_one(slot: int) -> tuple[str, float]:
            name = f".bridge-v3-conc-{slot}.diagnostic-report-{run_id}.csv"
            body = f"v3-concurrency-{slot}".encode() + deterministic_bytes(1024)
            started = time.perf_counter()
            response = await v3.call(
                "write", path=DIAG_PATH, filename=name, mime_type="text/csv",
                content_base64=base64.b64encode(body).decode(), sha256=hashlib.sha256(body).hexdigest(),
            )
            elapsed = time.perf_counter() - started
            fid = str((response.get("file") or {}).get("id") or "")
            if fid:
                cleanup_ids.append(fid)
            return fid, elapsed

        conc_start = time.perf_counter()
        conc = await asyncio.gather(*(concurrent_one(i) for i in range(4)))
        result["concurrency_wall_seconds"] = round(time.perf_counter() - conc_start, 3)
        result["concurrency_individual_seconds"] = [round(x[1], 3) for x in conc]
        result["concurrency_pass"] = all(bool(x[0]) for x in conc)

        large_name = f".bridge-v3-large.diagnostic-report-{run_id}.csv"
        large_sha = hashlib.sha256(large).hexdigest()
        t0 = time.perf_counter()
        start = await v3.call(
            "resumable_start", path=DIAG_PATH, filename=large_name,
            mime_type="text/csv", total_bytes=len(large),
        )
        session_uri = str(start.get("session_uri") or "")
        if not session_uri:
            raise RuntimeError("v3 resumable_start returned no session URI")
        final, recovered_from = await direct_resumable_with_forced_restart(session_uri, large, "text/csv")
        large_id = str(final.get("id") or start.get("file_id") or "")
        if not large_id:
            raise RuntimeError("v3 large upload returned no file id")
        cleanup_ids.append(large_id)
        meta = await v3.call("metadata_by_id", file_id=large_id)
        mf = meta.get("file") or {}
        result["large_upload_seconds"] = round(time.perf_counter() - t0, 3)
        result["large_resume_confirmed_offset"] = recovered_from
        result["large_upload_pass"] = int(mf.get("size") or -1) == len(large) and str(mf.get("sha256Checksum") or "").lower() == large_sha

        promote_args = dict(
            path=DIAG_PATH, file_id=large_id, staging_filename=large_name,
            canonical_filename=large_name, expected_bytes=len(large),
            expected_sha256=large_sha, previous_file_id="",
        )
        first_promote = await v3.call("promote_verified", **promote_args)
        second_promote = await v3.call("promote_verified", **promote_args)
        result["promotion_replay_pass"] = (
            str((first_promote.get("file") or {}).get("id") or "") == large_id
            and str((second_promote.get("file") or {}).get("id") or "") == large_id
        )

        t0 = time.perf_counter()
        try:
            downloaded = await v3.call("read_by_id", file_id=large_id)
            back = base64.b64decode(str(downloaded.get("content_base64") or ""), validate=True)
            result["large_download_seconds"] = round(time.perf_counter() - t0, 3)
            result["large_download_pass"] = len(back) == len(large) and hashlib.sha256(back).hexdigest() == large_sha
            result["large_download_transport"] = "single Apps Script Base64 response"
        except Exception as exc:
            result["large_download_pass"] = False
            result["large_download_error"] = type(exc).__name__
            result["large_download_transport"] = "single Apps Script Base64 response"

    except Exception as exc:
        result["fatal_error"] = f"{type(exc).__name__}: {exc}"
    finally:
        for file_id in list(dict.fromkeys(cleanup_ids)):
            try:
                await v3.call("trash_by_id", file_id=file_id)
            except Exception:
                pass
        await v3.close()
    return result


async def compare_v1(run_id: str, foreign_id: str, large: bytes) -> dict[str, Any]:
    result: dict[str, Any] = {"bridge": "shared-v1"}
    client = GoogleDriveBridgeClient(
        BridgeConfig(url=env("V1_URL"), secret=env("V1_SECRET"), project_id="marketplaces", timeout_seconds=300)
    )
    cleanup_ids: list[str] = []
    try:
        t0 = time.perf_counter()
        health = await client.health()
        result["health_seconds"] = round(time.perf_counter() - t0, 3)
        result["health_pass"] = int(health.get("protocol_version") or 0) == 1 and health.get("root_id") == env("ROOT_ID")
        result["bridge_release"] = health.get("bridge_release")
        result["capabilities"] = health.get("capabilities") or {}

        try:
            await client.metadata_by_id(foreign_id)
            result["outside_root_pass"] = False
        except BridgeError as exc:
            result["outside_root_pass"] = exc.code == "OUTSIDE_ROOT"

        small_name = f"bridge-v1-small-{run_id}.csv"
        payload = b"bridge-v1-small:" + deterministic_bytes(512)
        idem = f"compare-small:{run_id}:{hashlib.sha256(payload).hexdigest()}"
        first = await client.write_small(DIAG_PATH, small_name, payload, mime_type="text/csv", idempotency_key=idem)
        first_id = str((first.get("file") or {}).get("id") or "")
        second = await client.write_small(DIAG_PATH, small_name, payload, mime_type="text/csv", idempotency_key=idem)
        second_id = str((second.get("file") or {}).get("id") or "")
        if second_id:
            cleanup_ids.append(second_id)
        _, raw = await client.read_small(DIAG_PATH, small_name)
        result["small_io_pass"] = raw == payload
        result["generic_write_replay_same_file_id"] = bool(first_id) and first_id == second_id

        async def concurrent_one(slot: int) -> tuple[str, float]:
            name = f"bridge-v1-conc-{run_id}-{slot}.csv"
            body = f"v1-concurrency-{slot}".encode() + deterministic_bytes(1024)
            started = time.perf_counter()
            response = await client.write_small(
                DIAG_PATH, name, body, mime_type="text/csv",
                idempotency_key=f"compare-conc:{run_id}:{slot}:{hashlib.sha256(body).hexdigest()}",
            )
            elapsed = time.perf_counter() - started
            fid = str((response.get("file") or {}).get("id") or "")
            if fid:
                cleanup_ids.append(fid)
            return fid, elapsed

        conc_start = time.perf_counter()
        conc = await asyncio.gather(*(concurrent_one(i) for i in range(4)))
        result["concurrency_wall_seconds"] = round(time.perf_counter() - conc_start, 3)
        result["concurrency_individual_seconds"] = [round(x[1], 3) for x in conc]
        result["concurrency_pass"] = all(bool(x[0]) for x in conc)

        large_name = f"bridge-v1-large-{run_id}.csv"
        large_sha = hashlib.sha256(large).hexdigest()
        start_idem = f"compare-large-start:{run_id}:{large_sha}"
        t0 = time.perf_counter()
        start = await client.resumable_start(
            DIAG_PATH, large_name, len(large), mime_type="text/csv", idempotency_key=start_idem,
        )
        replay_start = await client.resumable_start(
            DIAG_PATH, large_name, len(large), mime_type="text/csv", idempotency_key=start_idem,
        )
        result["resumable_start_replay_same_session"] = (
            str(start.get("session_uri") or "") == str(replay_start.get("session_uri") or "")
        )
        session_uri = str(start.get("session_uri") or "")
        if not session_uri:
            raise RuntimeError("v1 resumable_start returned no session URI")
        final, recovered_from = await direct_resumable_with_forced_restart(session_uri, large, "text/csv")
        large_id = str(final.get("id") or start.get("file_id") or "")
        if not large_id:
            raise RuntimeError("v1 large upload returned no file id")
        cleanup_ids.append(large_id)
        staging_name = str(start.get("staging_filename") or large_name)
        meta = await client.metadata_by_id(large_id)
        result["large_upload_seconds"] = round(time.perf_counter() - t0, 3)
        result["large_resume_confirmed_offset"] = recovered_from
        result["large_upload_pass"] = int(meta.get("size") or -1) == len(large) and str(meta.get("sha256_checksum") or meta.get("sha256Checksum") or "").lower() == large_sha

        promote_idem = f"compare-promote:{run_id}:{large_sha}"
        first_promote = await client.promote_verified(
            path=DIAG_PATH, file_id=large_id, staging_filename=staging_name,
            canonical_filename=large_name, expected_bytes=len(large), expected_sha256=large_sha,
            previous_file_id=None, idempotency_key=promote_idem,
        )
        second_promote = await client.promote_verified(
            path=DIAG_PATH, file_id=large_id, staging_filename=staging_name,
            canonical_filename=large_name, expected_bytes=len(large), expected_sha256=large_sha,
            previous_file_id=None, idempotency_key=promote_idem,
        )
        result["promotion_replay_pass"] = (
            str((first_promote.get("file") or {}).get("id") or "") == large_id
            and str((second_promote.get("file") or {}).get("id") or "") == large_id
        )

        t0 = time.perf_counter()
        try:
            dmeta, back = await client.download_large_by_id(large_id, max_bytes=len(large) + 1, poll_seconds=0.5)
            result["large_download_seconds"] = round(time.perf_counter() - t0, 3)
            result["large_download_pass"] = len(back) == len(large) and hashlib.sha256(back).hexdigest() == large_sha
            result["large_download_transport"] = "bounded authenticated range chunks via Bridge v1"
            result["large_download_meta_size"] = dmeta.get("size")
        except Exception as exc:
            result["large_download_pass"] = False
            result["large_download_error"] = type(exc).__name__
            result["large_download_transport"] = "bounded authenticated range chunks via Bridge v1"

    except Exception as exc:
        result["fatal_error"] = f"{type(exc).__name__}: {exc}"
    finally:
        for file_id in list(dict.fromkeys(cleanup_ids)):
            try:
                await client.trash_by_id(file_id, idempotency_key=f"compare-cleanup:{run_id}:{file_id}")
            except Exception:
                pass
    return result


async def main() -> None:
    run_id = env("RUN_ID")
    foreign_id = env("FOREIGN_FILE_ID")
    large = deterministic_bytes(LARGE_BYTES)
    expected_sha = hashlib.sha256(large).hexdigest()
    print(f"COMPARISON_PAYLOAD_BYTES={len(large)}")
    print(f"COMPARISON_PAYLOAD_SHA256={expected_sha}")

    v1, v3 = await asyncio.gather(
        compare_v1(run_id, foreign_id, large),
        compare_v3(run_id, foreign_id, large),
    )
    summary = {"v1": v1, "v3": v3}
    print("BRIDGE_COMPARISON_JSON=" + json.dumps(summary, ensure_ascii=False, sort_keys=True))

    if not v1.get("health_pass") or not v3.get("health_pass"):
        raise SystemExit("Both bridge deployments must pass authenticated health for comparison to be valid")


if __name__ == "__main__":
    asyncio.run(main())
