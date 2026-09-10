from __future__ import annotations

import json
import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from app.models import MessageRecord
from app.object_storage import ObjectStorage
from app.telegram_client import TelegramReader

SUPPORTED_MEDIA = {"photo", "image", "gif", "animation"}


@dataclass(frozen=True)
class MediaRef:
    chat_id: int
    message_id: int
    media_type: str | None


class MediaPipeline:
    """Read-only capture of visual Telegram media for allowed chats."""

    def __init__(self, reader: TelegramReader, root: str | Path | None = None):
        self.reader = reader
        self.root = Path(root or os.getenv("TELEGRAM_MEDIA_PATH", "/state/media"))
        self.objects = ObjectStorage()

    async def capture(self, records: Iterable[MessageRecord]) -> int:
        refs = [MediaRef(x.chat_id, x.message_id, x.media_type) for x in records]
        return await self.capture_refs(refs)

    async def capture_local_rows(self, rows: Iterable[Mapping[str, object]]) -> int:
        refs = [
            MediaRef(
                int(row["chat_id"]),
                int(row["message_id"]),
                str(row.get("media_type") or "") or None,
            )
            for row in rows
        ]
        return await self.capture_refs(refs)

    async def capture_refs(self, refs: Iterable[MediaRef]) -> int:
        saved = 0
        for ref in refs:
            if ref.media_type not in SUPPORTED_MEDIA:
                continue
            if await self._capture_one(ref):
                saved += 1
        return saved

    async def _capture_one(self, ref: MediaRef) -> bool:
        folder = self.root / str(ref.chat_id)
        folder.mkdir(parents=True, exist_ok=True)
        manifest = folder / f"{ref.message_id}.json"

        previous = None
        if manifest.exists():
            try:
                previous = json.loads(manifest.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                previous = None
            if previous and previous.get("object_key"):
                return False

        self.reader.whitelist.assert_allowed(ref.chat_id)
        entity = await self.reader.client.get_entity(int(ref.chat_id))
        message = await self.reader.client.get_messages(entity, ids=int(ref.message_id))
        if not message or not getattr(message, "media", None):
            return False

        actual = None
        if previous:
            local_path = previous.get("local_path")
            if local_path and Path(str(local_path)).exists():
                actual = Path(str(local_path))

        if actual is None:
            ext = self._extension(message, ref.media_type or "media")
            target = folder / f"{ref.message_id}{ext}"
            downloaded = await self.reader.client.download_media(message, file=str(target))
            if not downloaded:
                return False
            actual = Path(downloaded)

        object_key = None
        media_url = None
        if self.objects.enabled:
            uploaded = self.objects.upload(
                actual,
                chat_id=ref.chat_id,
                message_id=ref.message_id,
            )
            if uploaded:
                object_key, media_url = uploaded

        metadata = {
            "chat_id": ref.chat_id,
            "message_id": ref.message_id,
            "media_type": ref.media_type,
            "local_path": str(actual),
            "size": actual.stat().st_size if actual.exists() else None,
            "object_key": object_key,
            "media_url": media_url,
        }
        manifest.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        return True

    @staticmethod
    def _extension(message, kind: str) -> str:
        file_info = getattr(message, "file", None)
        ext = getattr(file_info, "ext", None)
        if ext:
            return str(ext)
        mime = getattr(file_info, "mime_type", None)
        guessed = mimetypes.guess_extension(mime or "")
        if guessed:
            return guessed
        if kind == "photo":
            return ".jpg"
        if kind == "gif":
            return ".gif"
        if kind == "animation":
            return ".mp4"
        return ".bin"


def media_manifest(root: str | Path, chat_id: int, message_id: int) -> dict | None:
    path = Path(root) / str(chat_id) / f"{message_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
