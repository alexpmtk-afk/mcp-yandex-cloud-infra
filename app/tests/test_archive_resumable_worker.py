from __future__ import annotations

import asyncio
import hashlib
from types import SimpleNamespace

from core import archive_resumable_worker
from core.archive_drive_resumable import UploadProgress, UploadSession


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
        self.backups = {}
        self.range_reads = []
        self.full_reads = 0
    async def ensure_folder_path(self, parts): return "/".join(parts)
    async def find_child(self, parent, name, **kwargs):
        del kwargs
        if name == "annual-candidate.csv": return FakeObject(f"{parent}/{name}", self.candidate)
        key = f"{parent}/{name}"
        data = self.backups.get(key)
        return None if data is None else FakeObject(key, data)
    async def download_range(self, file_id, start, end):
        del file_id
        self.range_reads.append((start, end))
        return self.candidate[start:end]
    async def download_bytes(self, file_id):
        del file_id
        self.full_reads += 1
        return self.candidate
    async def upload_bytes(self, parent, name, data, **kwargs):
        del kwargs
        key = f"{parent}/{name}"
        self.backups[key] = bytes(data)
        return FakeObject(key, bytes(data))


class FakeDrive:
    def __init__(self, candidate: bytes):
        self.candidate = candidate
        self.promotions = []
    async def ensure_folder_path(self, parts): return "/".join(parts)
    async def start_resumable_session(self, **kwargs):
        return {"session_uri": "https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&upload_id=laser-test", "file_id": "drive-file-1"}
    async def file_metadata(self, file_id):
        return {"id": file_id, "size": str(len(self.candidate)), "sha256Checksum": hashlib.sha256(self.candidate).hexdigest()}
    async def find_child(self, parent_id, name, **kwargs):
        del parent_id, name, kwargs
        return None
    async def promote_verified_file(self, *, parent_id, file_id, staging_name, canonical_name, expected_bytes, expected_sha256, previous_file_id=None):
        del parent_id, staging_name, previous_file_id
        assert expected_bytes == len(self.candidate)
        assert expected_sha256 == hashlib.sha256(self.candidate).hexdigest()
        self.promotions.append(file_id)
        return SimpleNamespace(id=file_id, name=canonical_name, size=expected_bytes, sha256_checksum=expected_sha256)


class FakeStore:
    def __init__(self, candidate: bytes):
        self.yandex = FakeYandex(candidate)
        self.drive = FakeDrive(candidate)


class FakeQueue:
    def __init__(self, state):
        self.state = state
        self.delegate_calls = []
    async def _next_due(self): return self.state["job_id"], 0
    async def _load(self, job_id): return self.state if job_id == self.state["job_id"] else None
    async def _save(self, state): self.state = state
    async def _schedule(self, job_id, delay_seconds=0):
        del job_id, delay_seconds
    async def _unschedule(self, job_id):
        del job_id
    async def worker_step(self, job_id):
        self.delegate_calls.append(job_id)
        return {"ok": True, "action": "delegated"}


class FakeUploader:
    chunk_size = 4
    def __init__(self, candidate: bytes):
        self.candidate = candidate
        self.started = 0
        self.offset = 0
        self.file_id = "drive-file-1"
        self.session_uri = "https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&upload_id=laser-test"
        self.sha256 = hashlib.sha256(candidate).hexdigest()
    async def start_session(self, **kwargs):
        self.started += 1
        return UploadSession(self.session_uri, self.file_id, 0)
    async def query_status(self, session_uri, total_bytes):
        del session_uri
        if self.offset >= total_bytes:
            return UploadProgress("complete", total_bytes, {"id": self.file_id, "size": str(total_bytes), "sha256Checksum": self.sha256})
        return UploadProgress("incomplete", self.offset, None)
    async def upload_chunk(self, *, session_uri, offset, total_bytes, data):
        del session_uri
        self.offset = offset + len(data)
        if self.offset >= total_bytes:
            return UploadProgress("complete", total_bytes, {"id": self.file_id, "size": str(total_bytes), "sha256Checksum": self.sha256})
        return UploadProgress("incomplete", self.offset, None)
    async def file_metadata(self, file_id):
        return {"id": file_id, "size": str(len(self.candidate)), "sha256Checksum": self.sha256}
    async def find_named_file(self, parent_id, name):
        del parent_id, name
        return None


def _laser_state(candidate: bytes):
    return {
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


def test_existing_laser_23_of_38_continues_upload_without_wb_or_prepare(monkeypatch):
    monkeypatch.setattr(archive_resumable_worker, "ArchiveLock", DummyLock)
    candidate = b"existing-laser-report-24-candidate"
    state = _laser_state(candidate)
    queue = FakeQueue(state)
    uploader = FakeUploader(candidate)
    worker = archive_resumable_worker.WBFinanceResumableWorker(queue, FakeStore(candidate), uploader)
    result = asyncio.run(worker.worker_step(state["job_id"]))
    assert result["action"] == "drive_resumable_session_started"
    assert result["canonical_untouched"] is True
    assert uploader.started == 1
    assert queue.delegate_calls == []
    assert queue.state["completed_count"] == 23
    assert queue.state["finalize"]["report_id"] == 743994450
    assert queue.state["finalize"]["phase"] == "UPLOAD_ANNUAL"
    assert queue.state["finalize"]["resumable_upload"]["offset"] == 0


def test_resumable_upload_advances_to_commit_only_after_drive_and_backup_verification(monkeypatch):
    monkeypatch.setattr(archive_resumable_worker, "ArchiveLock", DummyLock)
    candidate = b"abcdefghijkl"
    state = _laser_state(candidate)
    queue = FakeQueue(state)
    store = FakeStore(candidate)
    uploader = FakeUploader(candidate)
    worker = archive_resumable_worker.WBFinanceResumableWorker(queue, store, uploader)
    asyncio.run(worker.worker_step(state["job_id"]))
    asyncio.run(worker.worker_step(state["job_id"]))
    asyncio.run(worker.worker_step(state["job_id"]))
    final = asyncio.run(worker.worker_step(state["job_id"]))
    assert final["action"] == "report_annual_uploaded_resumable"
    assert final["drive_verified"] is True
    assert final["backup_verified"] is True
    assert final["canonical_promoted"] is True
    assert store.drive.promotions == ["drive-file-1"]
    assert queue.state["finalize"]["phase"] == "COMMIT"
    assert queue.state["completed_count"] == 23
    assert queue.delegate_calls == []
