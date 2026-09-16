"""Verified publication wrapper for WB Advertising Archive jobs."""
from __future__ import annotations

import asyncio
from typing import Any

from .archive_drive_resumable import DriveResumableUploadClient
from .archive_google import GoogleDriveArchiveStore
from .wb_advertising_archive_queue import WBAdvertisingArchiveJobQueue
from .wb_advertising_archive_worker import WBAdvertisingArchiveWorker


class VerifiedWBAdvertisingArchiveWorker:
    """Run provider ingestion, then publish staged datasets through the verified path."""

    def __init__(self, queue: WBAdvertisingArchiveJobQueue, store: Any) -> None:
        self.queue = queue
        self.store = store
        self.worker = WBAdvertisingArchiveWorker(queue, store)

    async def _verified_store(self) -> GoogleDriveArchiveStore | None:
        if not all(hasattr(self.store, attr) for attr in ("drive", "ensure_folder_path")):
            return None
        drive = getattr(self.store, "drive", None)
        if isinstance(drive, GoogleDriveArchiveStore):
            return drive
        return None

    async def _backup_store(self) -> Any | None:
        return getattr(self.store, "object_storage", None)

    async def _publication_step(self, job_id: str) -> dict[str, Any] | None:
        drive = await self._verified_store()
        backup = await self._backup_store()
        if drive is None or backup is None:
            return None

        state = await self.queue.load(job_id)
        if state is None or state.get("status") != "PUBLISHING":
            return None
        commit = dict(state.get("commit") or {})
        datasets = [str(item) for item in commit.get("datasets") or []]
        index = int(commit.get("index", 0) or 0)
        if index >= len(datasets):
            return None

        dataset = datasets[index]
        expected = dict((commit.get("expected") or {}).get(dataset) or {})
        candidate = dict((commit.get("candidates") or {}).get(dataset) or {})
        if not expected or not candidate:
            return None

        payload = await backup.download_bytes(str(candidate["object_key"]))
        if payload is None:
            raise RuntimeError(f"Advertising candidate is missing: {candidate['object_key']}")
        expected_bytes = int(expected.get("bytes", 0) or 0)
        expected_sha = str(expected.get("sha256") or "")
        if len(payload) != expected_bytes:
            raise RuntimeError(
                f"Advertising candidate size mismatch for {dataset}: {len(payload)} != {expected_bytes}"
            )

        parts = [str(item) for item in candidate.get("canonical_parts") or []]
        filename = str(candidate.get("canonical_name") or "")
        if not parts or not filename:
            raise RuntimeError(f"Advertising candidate canonical destination is incomplete: {dataset}")
        parent_id = await drive.ensure_folder_path(parts)
        canonical = await drive.stat_named(parent_id, filename)

        client = DriveResumableUploadClient(drive)
        staged_name = f".__staging__{filename}__{job_id}__{dataset}"
        session = await client.start_session(
            parent_id=parent_id,
            name=staged_name,
            mime_type="text/csv",
            total_bytes=expected_bytes,
            previous_file_id=canonical.id if canonical is not None else "",
        )
        session_uri = str(session["session_uri"])
        previous_file_id = str(session.get("previous_file_id") or "")
        try:
            uploaded = await asyncio.to_thread(
                client._http,
                "PUT",
                session_uri,
                payload,
                {
                    "Content-Length": str(expected_bytes),
                    "Content-Range": f"bytes 0-{max(0, expected_bytes - 1)}/{expected_bytes}",
                    "Content-Type": "text/csv",
                },
            )
            if int(uploaded["status"]) not in {200, 201}:
                raise RuntimeError(
                    f"Advertising Drive upload failed for {dataset}: HTTP {uploaded['status']}"
                )
            final_item = uploaded.get("json") or {}
            staged_file_id = str(final_item.get("id") or "")
            if not staged_file_id:
                raise RuntimeError(f"Advertising Drive upload returned no file id for {dataset}")
            await drive.verify_exact_file(
                parent_id=parent_id,
                file_id=staged_file_id,
                expected_name=staged_name,
                expected_size=expected_bytes,
                expected_sha256=expected_sha,
            )
            await backup.upload_bytes(str(candidate["backup_key"]), payload, content_type="text/csv")
            backup_stat = await backup.stat(str(candidate["backup_key"]))
            if backup_stat is None or int(backup_stat.size or 0) != expected_bytes:
                raise RuntimeError(f"Advertising Yandex backup verification failed for {dataset}")
            promoted = await drive.promote_verified_file(
                parent_id=parent_id,
                staged_file_id=staged_file_id,
                previous_file_id=previous_file_id,
                final_name=filename,
                expected_size=expected_bytes,
                expected_sha256=expected_sha,
            )
            canonical_id = str(promoted.get("canonical_file_id") or staged_file_id)
            await drive.verify_exact_file(
                parent_id=parent_id,
                file_id=canonical_id,
                expected_name=filename,
                expected_size=expected_bytes,
                expected_sha256=expected_sha,
            )
            return await self.worker.mark_dataset_published(job_id, dataset)
        finally:
            await drive.resumable_cleanup(session_uri=session_uri)

    async def worker_step(self, job_id: str = "") -> dict[str, Any]:
        selected = str(job_id).strip()
        if not selected:
            selected, wait = await self.queue.next_due()
            if not selected:
                return {
                    "ok": True,
                    "action": "idle",
                    "retry_after_seconds": int(wait) if wait > 0 else 0,
                }
        published = await self._publication_step(selected)
        if published is not None:
            return published
        return await self.worker.worker_step(selected)
