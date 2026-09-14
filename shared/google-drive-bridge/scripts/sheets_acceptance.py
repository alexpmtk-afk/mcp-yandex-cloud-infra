from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python_client"))

from bridge_client import BridgeConfig, GoogleDriveBridgeClient  # noqa: E402


def env(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


async def main() -> None:
    project = env("GDRIVE_BRIDGE_PROJECT_ID")
    client = GoogleDriveBridgeClient(
        BridgeConfig(
            url=env("GDRIVE_BRIDGE_URL"),
            secret=env("GDRIVE_BRIDGE_SECRET"),
            project_id=project,
        )
    )
    health = await client.health()
    caps = dict(health.get("capabilities") or {})
    if caps.get("google_sheets_chunked") is not True:
        raise RuntimeError("google_sheets_chunked capability is not enabled")

    ensure_key = f"sheets-acceptance-ensure:{project}"
    ensured = await client.sheet_ensure(
        path=".bridge-acceptance",
        filename=f"Bridge v1 Sheets Acceptance - {project}",
        idempotency_key=ensure_key,
    )
    spreadsheet = dict(ensured.get("spreadsheet") or {})
    spreadsheet_id = str(spreadsheet.get("id") or "")
    if not spreadsheet_id:
        raise RuntimeError("sheet_ensure returned no spreadsheet id")

    target_title = "CANONICAL_TEST"
    stage_key = f"sheets-acceptance-stage:{project}:{spreadsheet_id}"
    staged = await client.sheet_stage_begin(
        spreadsheet_id=spreadsheet_id,
        sheet_title=target_title,
        idempotency_key=stage_key,
    )
    stage_title = str(staged.get("stage_sheet_title") or "")
    if not stage_title:
        raise RuntimeError("sheet_stage_begin returned no stage sheet title")

    rows1 = [
        ["row_id", "date", "value"],
        [1, "2026-09-13", 100.0],
        [2, "2026-09-14", 101.5],
    ]
    rows2 = [
        [3, "2026-09-15", 102.0],
        [4, "2026-09-16", 99.5],
    ]
    await client.sheet_write_chunk(
        spreadsheet_id=spreadsheet_id,
        stage_sheet_title=stage_title,
        start_row=1,
        start_col=1,
        values=rows1,
        idempotency_key=f"sheets-acceptance-chunk1:{project}:{spreadsheet_id}",
    )

    # Replaying stage-begin with the same idempotency key must preserve rows already written.
    replayed_stage = await client.sheet_stage_begin(
        spreadsheet_id=spreadsheet_id,
        sheet_title=target_title,
        idempotency_key=stage_key,
    )
    if replayed_stage.get("replayed") is not True or str(replayed_stage.get("stage_sheet_title") or "") != stage_title:
        raise RuntimeError(f"stage-begin replay contract failed: {replayed_stage}")
    preserved = await client.sheet_verify(
        spreadsheet_id=spreadsheet_id,
        stage_sheet_title=stage_title,
        date_column=2,
    )
    if int(preserved.get("row_count") or -1) != 3:
        raise RuntimeError(f"stage replay destroyed staged rows: {preserved}")

    await client.sheet_write_chunk(
        spreadsheet_id=spreadsheet_id,
        stage_sheet_title=stage_title,
        start_row=4,
        start_col=1,
        values=rows2,
        idempotency_key=f"sheets-acceptance-chunk2:{project}:{spreadsheet_id}",
    )

    verified = await client.sheet_verify(
        spreadsheet_id=spreadsheet_id,
        stage_sheet_title=stage_title,
        date_column=2,
    )
    if int(verified.get("row_count") or -1) != 5:
        raise RuntimeError(f"unexpected row count: {verified}")
    if str(verified.get("first_date") or "") != "date":
        raise RuntimeError(f"unexpected first date marker: {verified}")
    if str(verified.get("last_date") or "") != "2026-09-16":
        raise RuntimeError(f"unexpected last date: {verified}")
    digest = str(verified.get("digest") or "")
    if len(digest) != 64:
        raise RuntimeError("sheet_verify returned invalid digest")

    commit_key = f"sheets-acceptance-commit:{project}:{spreadsheet_id}"
    first_commit = await client.sheet_commit(
        spreadsheet_id=spreadsheet_id,
        stage_sheet_title=stage_title,
        target_sheet_title=target_title,
        expected_digest=digest,
        idempotency_key=commit_key,
    )
    if first_commit.get("committed") is not True:
        raise RuntimeError("first sheet commit failed")

    inspected = await client.sheet_inspect(
        spreadsheet_id=spreadsheet_id,
        sheet_title=target_title,
        date_column=2,
    )
    if inspected.get("found") is not True:
        raise RuntimeError(f"post-commit target is missing: {inspected}")
    if int(inspected.get("row_count") or -1) != 5 or str(inspected.get("digest") or "") != digest:
        raise RuntimeError(f"post-commit read-back parity failed: {inspected}")
    if str(inspected.get("first_date") or "") != "date" or str(inspected.get("last_date") or "") != "2026-09-16":
        raise RuntimeError(f"post-commit date parity failed: {inspected}")

    replay = await client.sheet_commit(
        spreadsheet_id=spreadsheet_id,
        stage_sheet_title=stage_title,
        target_sheet_title=target_title,
        expected_digest=digest,
        idempotency_key=commit_key,
    )
    if replay.get("committed") is not True:
        raise RuntimeError("sheet commit replay failed")

    abort_key = f"sheets-acceptance-abort-stage:{project}:{spreadsheet_id}"
    abort_stage = await client.sheet_stage_begin(
        spreadsheet_id=spreadsheet_id,
        sheet_title="ABORT_TEST",
        idempotency_key=abort_key,
    )
    abort_title = str(abort_stage.get("stage_sheet_title") or "")
    aborted = await client.sheet_abort(
        spreadsheet_id=spreadsheet_id,
        stage_sheet_title=abort_title,
        idempotency_key=f"sheets-acceptance-abort:{project}:{spreadsheet_id}",
    )
    if aborted.get("aborted") is not True:
        raise RuntimeError(f"sheet abort failed: {aborted}")

    await client.trash_by_id(
        spreadsheet_id,
        idempotency_key=f"sheets-acceptance-trash:{project}:{spreadsheet_id}",
    )
    print("SHEETS_STAGE_REPLAY_WRITE_VERIFY_COMMIT_INSPECT_REPLAY_ABORT=PASS")


if __name__ == "__main__":
    asyncio.run(main())
