from __future__ import annotations

import asyncio
import hashlib
from types import SimpleNamespace

from core import archive_resumable_worker
from core.archive_drive_resumable import UploadSession


class DummyLock:
    def __init__(self, *args, **kwargs):
        pass
    async def __aenter__(self):
        return self
    async def __aexit__(self, *args):
        return None


class FakeObject:
    def __init__(self, key: str, data: bytes):
        self.id = key
        self.name = key.rsplit("/", 1)[-1]
        self.size = len(data)
        self.etag = hashlib.md5(data, usedforsecurity=False).hexdigest()
        self.mime_type = "text/csv"


class FakeYandex:
    def __init__(self, candidate: bytes):
        self.candidate = candidate
    async def ensure_folder_path(self, parts):
        return "/".join(parts)
    async def find_child(self, parent, name, **kwargs):
        del kwargs
        if name == "annual-candidate.csv":
            return FakeObject(f"{parent}/{name}", self.candidate)
        return None
    async def download_bytes(self, file_id):
        del file_id
        return self.candidate


class FakeDrive:
    async def ensure_folder_path(self, parts):
        return "/".join(parts)
    async def start_resumable_session(self, **kwargs):
        return {
            "session_uri": "https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&upload_id=laser-test",
            "file_id": "drive-file-1",
        }
    async def file_metadata(self, file_id):
        return {"id": file_id, "size": "0", "md5Checksum": ""}
    async def find_child(self, parent_id, name, **kwargs):
        del parent_id, name, kwargs
        return SimpleNamespace(id="drive-file-1", name="annual.csv", size=0, md5_checksum="", mime_type="text/csv", modified_time=None)


class FakeStore:
    def __init__(self, candidate: bytes):
        self.yandex = FakeYandex(candidate)
        self.drive = FakeDrive()


class FakeQueue:
    def __init__(self, state):
        self.state = state
        self.delegate_calls = []
    async def _next_due(self):
        return self.state["job_id"], 0
    async def _load(self, job_id):
        return self.state if job_id == self.state["job_id"] else None
    async def _save(self, state):
        self.state = state
    async def _schedule(self, job_id, delay_seconds=0):
        del job_id, delay_seconds
    async def _unschedule(self, job_id):
        del job_id
    async def worker_step(self, job_id):
        self.delegate_calls.append(job_id)
        return {"ok": True, "action": "delegated"}


class FakeUploader:
    chunk_size = 4 * 1024 * 1024
    def __init__(self):
        self.started = 0
    async def start_session(self, *, parent_id, name, total_bytes, mime_type):
        del parent_id, name, mime_type
        self.started += 1
        return UploadSession(
            uri="https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&upload_id=laser-test",
            file_id="drive-file-1",
            offset=0,
        )


def test_existing_laser_23_of_38_continues_upload_without_wb_or_prepare(monkeypatch):
    monkeypatch.setattr(archive_resumable_worker, "ArchiveLock", DummyLock)
    candidate = b"existing-laser-report-24-candidate"
    state = {
        "job_id": "wb-finance-wb_laser_master-2026",
        "status": "QUEUED",
        "phase": "DOWNLOAD",
        "cabinet": "wb_laser_master",
        "year": 2026,
        "completed_count": 23,
        "provider_calls": 123,
        "finalize": {
            "report_id": 743994450,
            "phase": "UPLOAD_ANNUAL",
            "annual_bytes": len(candidate),
            "annual_sha256": hashlib.sha256(candidate).hexdigest(),
        },
    }
    queue = FakeQueue(state)
    uploader = FakeUploader()
    worker = archive_resumable_worker.WBFinanceResumableWorker(queue, FakeStore(candidate), uploader)

    result = asyncio.run(worker.worker_step(state["job_id"]))

    assert result["action"] == "drive_resumable_session_started"
    assert uploader.started == 1
    assert queue.delegate_calls == []
    assert queue.state["completed_count"] == 23
    assert queue.state["finalize"]["report_id"] == 743994450
    assert queue.state["finalize"]["phase"] == "UPLOAD_ANNUAL"
    assert queue.state["finalize"]["resumable_upload"]["offset"] == 0
    assert queue.state["finalize"]["resumable_upload"]["session_broker"] == "google_apps_script"
