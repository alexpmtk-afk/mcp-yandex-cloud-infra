from __future__ import annotations

import json
import logging
import mimetypes
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from PIL import Image

from app.models import MessageRecord
from app.object_storage import ObjectStorage
from app.telegram_client import TelegramReader

SUPPORTED_MEDIA = {"photo", "image", "gif", "animation"}
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class MediaRef:
    chat_id: int
    message_id: int
    media_type: str | None


class MediaPipeline:
    """Read-only capture of visual Telegram media for allowed chats."""

    def __init__(self, reader: TelegramReader, root: str | Path | None = None):
        self.reader = reader
        configured_root = str(root or os.getenv("TELEGRAM_MEDIA_PATH", "")).strip()
        self.root = (
            Path(configured_root)
            if configured_root
            else Path(reader.settings.database_path).parent / "media"
        )
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
            try:
                _, changed = await self._ensure_one(ref)
                if changed:
                    saved += 1
            except Exception as exc:
                LOGGER.warning(
                    "media_capture_error chat_id=%s message_id=%s type=%s error=%s",
                    ref.chat_id,
                    ref.message_id,
                    ref.media_type,
                    type(exc).__name__,
                )
        return saved

    async def ensure_asset(self, chat_id: int, message_id: int, media_type: str | None) -> dict | None:
        if media_type not in SUPPORTED_MEDIA:
            return None
        metadata, _ = await self._ensure_one(MediaRef(int(chat_id), int(message_id), media_type))
        return metadata

    async def _ensure_one(self, ref: MediaRef) -> tuple[dict | None, bool]:
        folder = self.root / str(ref.chat_id)
        folder.mkdir(parents=True, exist_ok=True)
        manifest = folder / f"{ref.message_id}.json"

        previous = None
        if manifest.exists():
            try:
                previous = json.loads(manifest.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                previous = None
            if previous and previous.get("object_key") and previous.get("preview_object_key"):
                previous["media_url"] = self.objects.signed_proxy_url(previous.get("object_key"))
                previous["preview_url"] = self.objects.signed_proxy_url(previous.get("preview_object_key"))
                return previous, False

        self.reader.whitelist.assert_allowed(ref.chat_id)
        entity = await self.reader._allowed_entity(int(ref.chat_id))
        message = await self.reader.client.get_messages(entity, ids=int(ref.message_id))
        if not message or not getattr(message, "media", None):
            return None, False

        ext = self._extension(message, ref.media_type or "media")
        object_key = previous.get("object_key") if previous else None
        preview_object_key = previous.get("preview_object_key") if previous else None
        object_info = None
        preview_info = None

        if self.objects.enabled and not object_key:
            candidate = self.objects.key_for(
                chat_id=ref.chat_id,
                message_id=ref.message_id,
                suffix=ext,
            )
            object_info = self.objects.object_info(candidate)
            if object_info:
                object_key = candidate

        if self.objects.enabled and not preview_object_key:
            preview_candidate = self.objects.key_for(
                chat_id=ref.chat_id,
                message_id=ref.message_id,
                suffix=".jpg",
                variant="preview",
            )
            preview_info = self.objects.object_info(preview_candidate)
            if preview_info:
                preview_object_key = preview_candidate

        # Serverless invocations are stateless. Reuse deterministic objects from
        # Object Storage and avoid downloading the same Telegram media repeatedly.
        if object_key and preview_object_key:
            metadata = {
                "chat_id": ref.chat_id,
                "message_id": ref.message_id,
                "media_type": ref.media_type,
                "local_path": None,
                "size": (object_info or {}).get("size") or (previous or {}).get("size"),
                "object_key": object_key,
                "media_url": self.objects.signed_proxy_url(object_key),
                "preview_local_path": None,
                "preview_size": (preview_info or {}).get("size") or (previous or {}).get("preview_size"),
                "preview_object_key": preview_object_key,
                "preview_url": self.objects.signed_proxy_url(preview_object_key),
            }
            self._write_manifest(manifest, metadata)
            return metadata, False

        actual = None
        if previous:
            local_path = previous.get("local_path")
            if local_path and Path(str(local_path)).exists():
                actual = Path(str(local_path))

        if actual is None:
            target = folder / f"{ref.message_id}{ext}"
            downloaded = await self.reader.client.download_media(message, file=str(target))
            if not downloaded:
                return None, False
            actual = Path(downloaded)

        changed = False
        if self.objects.enabled and not object_key:
            uploaded = self.objects.upload(actual, chat_id=ref.chat_id, message_id=ref.message_id)
            if uploaded:
                object_key, _ = uploaded
                changed = True

        preview_path = self._build_preview(actual, ref.media_type or "media")
        preview_size = (previous or {}).get("preview_size")
        if preview_path and preview_path.exists():
            preview_size = preview_path.stat().st_size
            if self.objects.enabled and not preview_object_key:
                uploaded_preview = self.objects.upload(
                    preview_path,
                    chat_id=ref.chat_id,
                    message_id=ref.message_id,
                    variant="preview",
                )
                if uploaded_preview:
                    preview_object_key, _ = uploaded_preview
                    changed = True

        metadata = {
            "chat_id": ref.chat_id,
            "message_id": ref.message_id,
            "media_type": ref.media_type,
            "local_path": str(actual),
            "size": actual.stat().st_size if actual.exists() else (object_info or {}).get("size"),
            "object_key": object_key,
            "media_url": self.objects.signed_proxy_url(object_key),
            "preview_local_path": str(preview_path) if preview_path else None,
            "preview_size": preview_size,
            "preview_object_key": preview_object_key,
            "preview_url": self.objects.signed_proxy_url(preview_object_key),
        }
        self._write_manifest(manifest, metadata)
        return metadata, changed

    @staticmethod
    def _write_manifest(manifest: Path, metadata: dict) -> None:
        tmp = manifest.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(manifest)

    @staticmethod
    def _build_preview(source: Path, kind: str) -> Path | None:
        preview = source.with_name(f"{source.stem}.preview.jpg")
        if preview.exists():
            return preview
        try:
            if kind in {"photo", "image", "gif"}:
                with Image.open(source) as image:
                    image.seek(0)
                    frame = image.convert("RGB")
                    frame.thumbnail((640, 640))
                    frame.save(preview, "JPEG", quality=72, optimize=True)
                return preview
            if kind == "animation":
                subprocess.run(
                    [
                        "ffmpeg",
                        "-loglevel",
                        "error",
                        "-y",
                        "-ss",
                        "0",
                        "-i",
                        str(source),
                        "-frames:v",
                        "1",
                        "-vf",
                        "scale='min(640,iw)':-2",
                        str(preview),
                    ],
                    check=True,
                    timeout=30,
                )
                return preview if preview.exists() else None
        except Exception as exc:
            LOGGER.warning(
                "media_preview_error path=%s type=%s error=%s",
                source,
                kind,
                type(exc).__name__,
            )
        return None

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
