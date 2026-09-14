from __future__ import annotations

import asyncio

import httpx
import pytest

from core import archive_drive_resumable
from core.archive_drive_resumable import (
    CHUNK_GRANULARITY,
    MAX_CHUNK_SIZE,
    GoogleDriveResumableUploader,
    ResumableUploadError,
)
from core.archive_google import ArchiveStorageNotConfigured


class Broker:
    async def start_resumable_session(self, **kwargs):
        del kwargs
        return {
            "session_uri": "https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&upload_id=test",
            "file_id": None,
        }

    async def file_metadata(self, file_id):
        return {"id": file_id, "size": "1", "sha256Checksum": "0" * 64}

    async def find_child(self, parent_id, name):
        del parent_id, name
        return None


def response(status: int, *, headers=None, body=None):
    req = httpx.Request("PUT", "https://www.googleapis.com/upload/drive/v3/files?upload_id=x")
    return httpx.Response(status, headers=headers or {}, json=body, request=req) if body is not None else httpx.Response(status, headers=headers or {}, request=req)


def test_chunk_guard_requires_alignment_and_upper_bound():
    with pytest.raises(ArchiveStorageNotConfigured):
        GoogleDriveResumableUploader(session_broker=Broker(), chunk_size=CHUNK_GRANULARITY + 1)
    with pytest.raises(ArchiveStorageNotConfigured):
        GoogleDriveResumableUploader(session_broker=Broker(), chunk_size=MAX_CHUNK_SIZE + CHUNK_GRANULARITY)


def test_session_uri_is_restricted_to_google_upload_endpoint():
    with pytest.raises(ResumableUploadError):
        GoogleDriveResumableUploader._validate_session_uri("https://example.com/upload/drive/v3/files?upload_id=x")
    with pytest.raises(ResumableUploadError):
        GoogleDriveResumableUploader._validate_session_uri("https://user@www.googleapis.com/upload/drive/v3/files?upload_id=x")


def test_direct_resumable_transport_never_follows_redirects(monkeypatch):
    seen = {}

    class Client:
        def __init__(self, *args, **kwargs):
            del args
            seen.update(kwargs)
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def request(self, method, url, **kwargs):
            del method, url, kwargs
            return response(308)

    monkeypatch.setattr(archive_drive_resumable.httpx, "AsyncClient", Client)
    up = GoogleDriveResumableUploader(session_broker=Broker(), chunk_size=CHUNK_GRANULARITY)
    asyncio.run(up.query_status("https://www.googleapis.com/upload/drive/v3/files?upload_id=x", CHUNK_GRANULARITY))
    assert seen["follow_redirects"] is False


def test_malformed_range_fails_safe(monkeypatch):
    up = GoogleDriveResumableUploader(session_broker=Broker(), chunk_size=CHUNK_GRANULARITY)
    async def fake(*args, **kwargs):
        del args, kwargs
        return response(308, headers={"Range": "garbage"})
    monkeypatch.setattr(up, "_request", fake)
    with pytest.raises(ResumableUploadError) as exc:
        asyncio.run(up.query_status("https://www.googleapis.com/upload/drive/v3/files?upload_id=x", CHUNK_GRANULARITY))
    assert exc.value.retryable is True


@pytest.mark.parametrize("status", [400, 401, 403, 404, 410])
def test_non_rate_limit_4xx_marks_session_for_restart(monkeypatch, status):
    up = GoogleDriveResumableUploader(session_broker=Broker(), chunk_size=CHUNK_GRANULARITY)
    async def fake(*args, **kwargs):
        del args, kwargs
        return response(status, body={"error": {"errors": [{"reason": "forbidden"}]}} if status == 403 else None)
    monkeypatch.setattr(up, "_request", fake)
    result = asyncio.run(up.query_status("https://www.googleapis.com/upload/drive/v3/files?upload_id=x", CHUNK_GRANULARITY))
    assert result.state == "expired"
    assert result.offset == 0


def test_rate_limit_403_is_retryable_not_session_restart(monkeypatch):
    up = GoogleDriveResumableUploader(session_broker=Broker(), chunk_size=CHUNK_GRANULARITY)
    async def fake(*args, **kwargs):
        del args, kwargs
        return response(403, headers={"Retry-After": "7"}, body={"error": {"errors": [{"reason": "rateLimitExceeded"}]}})
    monkeypatch.setattr(up, "_request", fake)
    with pytest.raises(ResumableUploadError) as exc:
        asyncio.run(up.query_status("https://www.googleapis.com/upload/drive/v3/files?upload_id=x", CHUNK_GRANULARITY))
    assert exc.value.retryable is True
    assert exc.value.retry_after_seconds == 7


def test_non_final_chunk_must_be_256k_aligned():
    up = GoogleDriveResumableUploader(session_broker=Broker(), chunk_size=CHUNK_GRANULARITY)
    with pytest.raises(ResumableUploadError):
        asyncio.run(up.upload_chunk(
            session_uri="https://www.googleapis.com/upload/drive/v3/files?upload_id=x",
            offset=0,
            total_bytes=2 * CHUNK_GRANULARITY,
            data=b"x" * (CHUNK_GRANULARITY - 1),
        ))
