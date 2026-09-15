from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import random
import uuid
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import urlsplit

import httpx


class BridgeError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.retryable = bool(retryable)


@dataclass(frozen=True)
class BridgeConfig:
    url: str
    secret: str
    project_id: str
    timeout_seconds: float = 120.0
    max_attempts: int = 3


class GoogleDriveBridgeClient:
    """Protocol-v1 client shared by Yandex Cloud workloads.

    The client deliberately knows nothing about marketplace/birzha business logic.
    Resource locks, durable jobs and domain commits remain the caller's concern.
    """

    def __init__(self, config: BridgeConfig) -> None:
        self.config = config
        if not config.url.startswith("https://script.google.com/macros/s/"):
            raise ValueError("bridge URL must be a deployed Apps Script /exec URL")
        if not config.secret.strip() or not config.project_id.strip():
            raise ValueError("bridge secret and project_id are required")

    @staticmethod
    def new_request_id() -> str:
        return str(uuid.uuid4())

    @staticmethod
    def new_idempotency_key(prefix: str = "mutation") -> str:
        return f"{prefix}:{uuid.uuid4()}"

    async def call(
        self,
        action: str,
        payload: dict[str, Any] | None = None,
        *,
        request_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        request_id = request_id or self.new_request_id()
        body: dict[str, Any] = {
            "secret": self.config.secret,
            "project_id": self.config.project_id,
            "request_id": request_id,
            "action": action,
            "payload": payload or {},
        }
        if idempotency_key:
            body["idempotency_key"] = idempotency_key

        last_exc: BaseException | None = None
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=self.config.timeout_seconds,
                    follow_redirects=True,
                ) as client:
                    response = await client.post(
                        self.config.url,
                        json=body,
                        headers={"Accept": "application/json"},
                    )
                if response.status_code in {408, 425, 429, 500, 502, 503, 504}:
                    if attempt < self.config.max_attempts:
                        await self._backoff(attempt)
                        continue
                response.raise_for_status()
                try:
                    data = response.json()
                except ValueError as exc:
                    raise BridgeError("NON_JSON_RESPONSE", "bridge returned non-JSON response", retryable=False) from exc
                if not isinstance(data, dict):
                    raise BridgeError("INVALID_RESPONSE", "bridge response is not an object", retryable=False)
                if data.get("request_id") not in {None, request_id}:
                    raise BridgeError("REQUEST_ID_MISMATCH", "bridge echoed a different request_id", retryable=False)
                if data.get("ok") is not True:
                    err = data.get("error") if isinstance(data.get("error"), dict) else {}
                    exc = BridgeError(
                        str(err.get("code") or "BRIDGE_REJECTED"),
                        str(err.get("message") or "bridge rejected request"),
                        retryable=bool(err.get("retryable")),
                    )
                    if exc.retryable and attempt < self.config.max_attempts:
                        await self._backoff(attempt)
                        continue
                    raise exc
                if int(data.get("protocol_version") or 0) != 1:
                    raise BridgeError("PROTOCOL_MISMATCH", "expected protocol_version=1", retryable=False)
                if str(data.get("project_id") or "") != self.config.project_id:
                    raise BridgeError("PROJECT_MISMATCH", "bridge responded for a different project", retryable=False)
                result = data.get("result")
                return dict(result) if isinstance(result, dict) else {}
            except BridgeError:
                raise
            except (httpx.HTTPError, asyncio.TimeoutError) as exc:
                last_exc = exc
                if attempt < self.config.max_attempts:
                    await self._backoff(attempt)
                    continue
                raise BridgeError("TRANSPORT_ERROR", type(exc).__name__, retryable=True) from exc
        raise BridgeError("TRANSPORT_ERROR", type(last_exc).__name__ if last_exc else "unknown", retryable=True)

    @staticmethod
    async def _backoff(attempt: int) -> None:
        base = min(8.0, 0.75 * (2 ** (attempt - 1)))
        await asyncio.sleep(base + random.uniform(0.0, base * 0.25))

    async def health(self) -> dict[str, Any]:
        return await self.call("health")

    async def stat(self, path: str, filename: str) -> dict[str, Any]:
        return await self.call("stat", {"path": path, "filename": filename})

    async def metadata_by_id(self, file_id: str) -> dict[str, Any]:
        return await self.call("metadata_by_id", {"file_id": file_id})

    async def read_small(self, path: str, filename: str) -> tuple[dict[str, Any] | None, bytes | None]:
        result = await self.call("read_small", {"path": path, "filename": filename})
        if not result.get("found"):
            return None, None
        raw = base64.b64decode(str(result.get("content_base64") or ""), validate=True)
        expected = str(result.get("sha256") or "").lower()
        actual = hashlib.sha256(raw).hexdigest()
        if expected and expected != actual:
            raise BridgeError("SHA256_MISMATCH", "small-read SHA256 mismatch", retryable=False)
        file_meta = result.get("file") if isinstance(result.get("file"), dict) else {}
        size = file_meta.get("size")
        if size is not None and int(size) != len(raw):
            raise BridgeError("SIZE_MISMATCH", "small-read size mismatch", retryable=False)
        return dict(file_meta), raw

    async def write_small(
        self,
        path: str,
        filename: str,
        data: bytes,
        *,
        mime_type: str = "application/octet-stream",
        idempotency_key: str,
    ) -> dict[str, Any]:
        sha = hashlib.sha256(data).hexdigest()
        return await self.call(
            "write_small",
            {
                "path": path,
                "filename": filename,
                "mime_type": mime_type,
                "content_base64": base64.b64encode(data).decode("ascii"),
                "sha256": sha,
            },
            idempotency_key=idempotency_key,
        )

    async def trash_by_id(self, file_id: str, *, idempotency_key: str) -> dict[str, Any]:
        return await self.call("trash_by_id", {"file_id": file_id}, idempotency_key=idempotency_key)

    async def resumable_start(
        self,
        path: str,
        filename: str,
        total_bytes: int,
        *,
        mime_type: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return await self.call(
            "resumable_start",
            {
                "path": path,
                "filename": filename,
                "mime_type": mime_type,
                "total_bytes": int(total_bytes),
            },
            idempotency_key=idempotency_key,
        )

    async def promote_verified(
        self,
        *,
        path: str,
        file_id: str,
        staging_filename: str,
        canonical_filename: str,
        expected_bytes: int,
        expected_sha256: str,
        previous_file_id: str | None,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return await self.call(
            "promote_verified",
            {
                "path": path,
                "file_id": file_id,
                "staging_filename": staging_filename,
                "canonical_filename": canonical_filename,
                "expected_bytes": int(expected_bytes),
                "expected_sha256": expected_sha256.lower(),
                "previous_file_id": previous_file_id or "",
            },
            idempotency_key=idempotency_key,
        )

    async def large_download_start(self, file_id: str) -> dict[str, Any]:
        return await self.call("large_download_start", {"file_id": file_id})

    async def large_download_poll(self, download_ticket: str) -> dict[str, Any]:
        return await self.call("large_download_poll", {"download_ticket": download_ticket})

    async def download_large_by_id(
        self,
        file_id: str,
        *,
        max_bytes: int = 512 * 1024 * 1024,
        max_polls: int = 30,
        poll_seconds: float = 2.0,
        chunk_size: int = 4 * 1024 * 1024,
    ) -> tuple[dict[str, Any], bytes]:
        """Download a Drive blob without exposing the Apps Script OAuth token.

        Apps Script authenticates and validates the fixed-root boundary, brokers the
        Drive files.download LRO, and fetches bounded authenticated byte ranges.
        The Google OAuth credential never leaves Apps Script.
        """
        state = await self.large_download_start(file_id)
        for poll_index in range(max_polls + 1):
            if state.get("ready") is True:
                break
            ticket = str(state.get("download_ticket") or "").strip()
            if not ticket:
                raise BridgeError("DOWNLOAD_TICKET_MISSING", "bridge returned no download ticket", retryable=True)
            if poll_index >= max_polls:
                raise BridgeError("LARGE_DOWNLOAD_NOT_READY", "Drive download operation did not become ready", retryable=True)
            await asyncio.sleep(max(0.1, float(poll_seconds)))
            state = await self.large_download_poll(ticket)
        else:
            raise BridgeError("LARGE_DOWNLOAD_NOT_READY", "Drive download operation did not become ready", retryable=True)

        expected_size = int(state.get("total_bytes") if state.get("total_bytes") is not None else -1)
        expected_sha = str(state.get("sha256") or "").strip().lower()
        if expected_size < 0:
            raise BridgeError("SIZE_UNAVAILABLE", "bridge returned no valid large-download size", retryable=False)
        if expected_size > int(max_bytes):
            raise BridgeError("DOWNLOAD_TOO_LARGE", f"large download exceeds client safety limit {max_bytes}", retryable=False)
        if not _is_sha256(expected_sha):
            raise BridgeError("SHA256_UNAVAILABLE", "bridge returned no valid large-download SHA256", retryable=False)

        buffer = bytearray()
        hasher = hashlib.sha256()
        offset = 0
        per_chunk = max(1, min(int(chunk_size), 4 * 1024 * 1024))
        while offset < expected_size:
            length = min(per_chunk, expected_size - offset)
            part = await self.call(
                "large_download_poll",
                {"mode": "range_chunk", "file_id": file_id, "offset": offset, "length": length},
            )
            if str(part.get("mode") or "") != "range_chunk":
                raise BridgeError("INVALID_RESPONSE", "bridge returned invalid large-download chunk mode", retryable=False)
            if int(part.get("offset") if part.get("offset") is not None else -1) != offset:
                raise BridgeError("LARGE_DOWNLOAD_OFFSET_MISMATCH", "bridge returned unexpected chunk offset", retryable=False)
            if int(part.get("total_bytes") if part.get("total_bytes") is not None else -1) != expected_size:
                raise BridgeError("DOWNLOAD_SOURCE_CHANGED", "Drive file size changed during chunked download", retryable=True)
            if str(part.get("sha256") or "").strip().lower() != expected_sha:
                raise BridgeError("DOWNLOAD_SOURCE_CHANGED", "Drive file checksum changed during chunked download", retryable=True)
            try:
                chunk = base64.b64decode(str(part.get("content_base64") or ""), validate=True)
            except Exception as exc:
                raise BridgeError("INVALID_BASE64", "bridge returned invalid large-download chunk", retryable=False) from exc
            next_offset = int(part.get("next_offset") if part.get("next_offset") is not None else -1)
            if not chunk or next_offset != offset + len(chunk) or len(chunk) > length:
                raise BridgeError("LARGE_DOWNLOAD_CHUNK_SIZE_MISMATCH", "bridge returned invalid chunk byte count", retryable=False)
            buffer.extend(chunk)
            hasher.update(chunk)
            offset = next_offset
            if len(buffer) > expected_size:
                raise BridgeError("SIZE_MISMATCH", "large download exceeded expected Drive size", retryable=False)

        raw = bytes(buffer)
        if len(raw) != expected_size:
            raise BridgeError("SIZE_MISMATCH", f"large download size mismatch: {len(raw)} != {expected_size}", retryable=False)
        if hasher.hexdigest() != expected_sha:
            raise BridgeError("SHA256_MISMATCH", "large download SHA256 mismatch", retryable=False)
        metadata = {
            "id": file_id,
            "size": expected_size,
            "sha256_checksum": expected_sha,
            "mime_type": state.get("mime_type"),
            "modified_time": state.get("modified_time"),
            "partial_download_allowed": bool(state.get("partial_download_allowed")),
        }
        return metadata, raw

    async def upload_resumable_chunks(
        self,
        session_uri: str,
        data: bytes,
        *,
        mime_type: str,
        chunk_size: int = 4 * 1024 * 1024,
    ) -> dict[str, Any]:
        """Upload bytes directly to an already-created Drive resumable session.

        Non-final chunks are rounded down to a multiple of 256 KiB. HTTP 308
        Range is treated as authoritative. The session URI is never logged here.
        """
        unit = 256 * 1024
        chunk_size = max(unit, (int(chunk_size) // unit) * unit)
        total = len(data)
        offset = 0
        async with httpx.AsyncClient(timeout=self.config.timeout_seconds, follow_redirects=False) as client:
            while offset < total:
                end = min(total, offset + chunk_size)
                chunk = data[offset:end]
                headers = {
                    "Content-Type": mime_type,
                    "Content-Length": str(len(chunk)),
                    "Content-Range": f"bytes {offset}-{end - 1}/{total}",
                }
                response = await client.put(session_uri, content=chunk, headers=headers)
                if response.status_code in {200, 201}:
                    try:
                        return dict(response.json())
                    except ValueError:
                        return {}
                if response.status_code == 308:
                    range_header = response.headers.get("Range", "")
                    confirmed = _confirmed_offset(range_header)
                    if confirmed is None:
                        confirmed = await _query_resumable_offset(client, session_uri, total)
                    if confirmed < offset:
                        raise BridgeError("RESUMABLE_OFFSET_REGRESSION", "Drive confirmed an earlier offset", retryable=True)
                    offset = confirmed
                    continue
                if response.status_code in {408, 425, 429, 500, 502, 503, 504}:
                    confirmed = await _query_resumable_offset(client, session_uri, total)
                    offset = confirmed
                    await self._backoff(1)
                    continue
                raise BridgeError("RESUMABLE_UPLOAD_FAILED", f"Drive upload HTTP {response.status_code}", retryable=False)
        return {}

    async def sheet_ensure(
        self,
        *,
        path: str = "",
        filename: str = "",
        spreadsheet_id: str = "",
        idempotency_key: str,
    ) -> dict[str, Any]:
        return await self.call(
            "sheet_ensure",
            {"path": path, "filename": filename, "spreadsheet_id": spreadsheet_id},
            idempotency_key=idempotency_key,
        )

    async def sheet_stage_begin(
        self,
        *,
        spreadsheet_id: str,
        sheet_title: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return await self.call(
            "sheet_stage_begin",
            {"spreadsheet_id": spreadsheet_id, "sheet_title": sheet_title},
            idempotency_key=idempotency_key,
        )

    async def sheet_write_chunk(
        self,
        *,
        spreadsheet_id: str,
        stage_sheet_title: str,
        start_row: int,
        start_col: int,
        values: list[list[Any]],
        idempotency_key: str,
    ) -> dict[str, Any]:
        chunk_sha = hashlib.sha256(json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
        return await self.call(
            "sheet_write_chunk",
            {
                "spreadsheet_id": spreadsheet_id,
                "stage_sheet_title": stage_sheet_title,
                "start_row": int(start_row),
                "start_col": int(start_col),
                "values": values,
                "chunk_sha256": chunk_sha,
            },
            idempotency_key=idempotency_key,
        )

    async def sheet_verify(
        self,
        *,
        spreadsheet_id: str,
        stage_sheet_title: str,
        date_column: int = 0,
    ) -> dict[str, Any]:
        return await self.call(
            "sheet_verify",
            {"spreadsheet_id": spreadsheet_id, "stage_sheet_title": stage_sheet_title, "date_column": int(date_column)},
        )

    async def sheet_inspect(
        self,
        *,
        spreadsheet_id: str,
        sheet_title: str,
        date_column: int = 0,
    ) -> dict[str, Any]:
        return await self.call(
            "sheet_inspect",
            {"spreadsheet_id": spreadsheet_id, "sheet_title": sheet_title, "date_column": int(date_column)},
        )

    async def sheet_commit(
        self,
        *,
        spreadsheet_id: str,
        stage_sheet_title: str,
        target_sheet_title: str,
        expected_digest: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return await self.call(
            "sheet_commit",
            {
                "spreadsheet_id": spreadsheet_id,
                "stage_sheet_title": stage_sheet_title,
                "target_sheet_title": target_sheet_title,
                "expected_digest": expected_digest,
            },
            idempotency_key=idempotency_key,
        )

    async def sheet_abort(
        self,
        *,
        spreadsheet_id: str,
        stage_sheet_title: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return await self.call(
            "sheet_abort",
            {"spreadsheet_id": spreadsheet_id, "stage_sheet_title": stage_sheet_title},
            idempotency_key=idempotency_key,
        )


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(ch in "0123456789abcdef" for ch in value.lower())


def _validate_google_download_uri(uri: str) -> None:
    try:
        parsed = urlsplit(uri)
    except ValueError as exc:
        raise BridgeError("INVALID_DOWNLOAD_URI", "download URI is malformed", retryable=False) from exc
    host = (parsed.hostname or "").lower()
    allowed = (
        host == "googleapis.com"
        or host.endswith(".googleapis.com")
        or host == "googleusercontent.com"
        or host.endswith(".googleusercontent.com")
        or host == "drive.usercontent.google.com"
    )
    if parsed.scheme != "https" or not allowed:
        raise BridgeError("INVALID_DOWNLOAD_URI", "download URI host is not an allowed Google endpoint", retryable=False)


def _confirmed_offset(range_header: str) -> int | None:
    value = str(range_header or "").strip()
    if not value.startswith("bytes=0-"):
        return None
    try:
        last = int(value.split("-", 1)[1])
    except (TypeError, ValueError):
        return None
    return last + 1


async def _query_resumable_offset(client: httpx.AsyncClient, session_uri: str, total: int) -> int:
    response = await client.put(
        session_uri,
        content=b"",
        headers={"Content-Length": "0", "Content-Range": f"bytes */{total}"},
    )
    if response.status_code in {200, 201}:
        return total
    if response.status_code != 308:
        raise BridgeError("RESUMABLE_STATUS_FAILED", f"Drive session status HTTP {response.status_code}", retryable=True)
    confirmed = _confirmed_offset(response.headers.get("Range", ""))
    return 0 if confirmed is None else confirmed