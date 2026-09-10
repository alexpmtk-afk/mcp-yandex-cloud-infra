from __future__ import annotations

import json
import mimetypes
import os
from pathlib import Path
from typing import Iterable

from app.models import MessageRecord
from app.object_storage import ObjectStorage
from app.telegram_client import TelegramReader

SUPPORTED_MEDIA = {"photo", "image", "gif", "animation"}


class MediaPipeline:
    """Read-only capture of visual Telegram media for allowed chats."""

    def __init__(self, reader: TelegramReader, root: str | Path | None = None):
        self.reader = reader
        self.root = Path(root or os.getenv("TELEGRAM_MEDIA_PATH", "/state/media"))
        self.root.mkdir(parents=True, exist_ok=True)
        self.objects = ObjectStorage()

    async def capture(self, records: Iterable[MessageRecord]) -> int:
        saved = 0
        for record in records:
            if record.media_type not in SUPPORTED_MEDIA:
                continue
            if await self._capture_one(record):
                saved += 1
        return saved

    async def _capture_one(self, record: MessageRecord) -> bool:
        folder = self.root / str(record.chat_id)
        folder.mkdir(parents=True, exist_ok=True)
        manifest = folder / f"{record.message_id}.json"
        if manifest.exists():
            return False

        self.reader.whitelist.assert_allowed(record.chat_id)
        entity = await self.reader.client.get_entity(int(record.chat_id))
        message = await self.reader.client.get_messages(entity, ids=int(record.message_id))
        if not message or not getattr(message, "media", None):
            return False

        ext = self._extension(message, record.media_type)
        target = folder / f"{record.message_id}{ext}"
        downloaded = await self.reader.client.download_media(message, file=str(target))
        if not downloaded:
            return False

        actual = Path(downloaded)
        object_key = None
        media_url = None
        if self.objects.enabled:
            uploaded = self.objects.upload(
                actual,
                chat_id=record.chat_id,
                message_id=record.message_id,
            )
            if uploaded:
                object_key, media_url = uploaded

        metadata = {
            "chat_id": record.chat_id,
            "message_id": record.message_id,
            "media_type": record.media_type,
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
