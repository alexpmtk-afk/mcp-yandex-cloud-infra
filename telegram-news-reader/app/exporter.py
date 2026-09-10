from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.media_pipeline import media_manifest
from app.object_storage import ObjectStorage
from app.storage import Storage
from app.whitelist import Whitelist


class TelegramNewsExporter:
    """Write a compact rolling export for currently allowed chats."""

    def __init__(self, storage: Storage, whitelist: Whitelist, output_path: str | Path):
        self.storage = storage
        self.whitelist = whitelist
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.media_root = Path(os.getenv("TELEGRAM_MEDIA_PATH", "/state/media"))
        self.objects = ObjectStorage()

    def export_latest_window(self, hours: int = 36, limit: int = 5000) -> dict:
        allowed_ids = [item.chat_id for item in self.whitelist.list_allowed()]
        rows = self._latest_rows(allowed_ids, hours=hours, limit=limit)

        messages = []
        media_messages = 0
        preview_messages = 0
        for row in rows:
            row.setdefault("username", None)
            media = media_manifest(self.media_root, int(row["chat_id"]), int(row["message_id"]))
            if media:
                object_key = media.get("object_key")
                preview_object_key = media.get("preview_object_key")
                media_url = self.objects.presigned_url(object_key) if object_key else media.get("media_url")
                preview_url = (
                    self.objects.presigned_url(preview_object_key)
                    if preview_object_key
                    else media.get("preview_url")
                )
                row["media_asset"] = {
                    "media_type": media.get("media_type"),
                    "size": media.get("size"),
                    "object_key": object_key,
                    "media_url": media_url,
                    "preview_size": media.get("preview_size"),
                    "preview_object_key": preview_object_key,
                    "preview_url": preview_url,
                }
                media_messages += 1
                if preview_url:
                    preview_messages += 1
            else:
                row["media_asset"] = None
            messages.append(row)

        payload = {
            "schema": "TELEGRAM_NEWS_READER_V1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "window_hours": hours,
            "allowed_chats": len(allowed_ids),
            "message_count": len(messages),
            "media_message_count": media_messages,
            "preview_message_count": preview_messages,
            "messages": messages,
        }
        self._write(payload)
        return {"messages": len(messages), "path": str(self.output_path)}

    def export_incremental(self, limit: int = 5000) -> dict:
        """Compatibility export retained for tests/tools that rely on the old cursor."""
        allowed_ids = [item.chat_id for item in self.whitelist.list_allowed()]
        cursor = self.storage.get_export_cursor()
        rows = self.storage.get_messages_after_rowid(cursor, allowed_ids, limit=limit)
        max_rowid = cursor
        messages = []
        for row in rows:
            max_rowid = max(max_rowid, int(row.pop("_rowid")))
            row.setdefault("username", None)
            messages.append(row)
        payload = {
            "schema": "TELEGRAM_NEWS_READER_V1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "allowed_chats": len(allowed_ids),
            "messages": messages,
        }
        self._write(payload)
        if rows:
            self.storage.set_export_cursor(max_rowid)
        return {"messages": len(messages), "cursor": max_rowid, "path": str(self.output_path)}

    def _latest_rows(self, chat_ids: list[int], *, hours: int, limit: int) -> list[dict]:
        if not chat_ids:
            return []
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=max(1, hours))).isoformat()
        marks = ",".join("?" for _ in chat_ids)
        sql = f"""
            SELECT chat_id, message_id, chat_title, datetime, sender_id, text,
                   url, media_type, views, forwards, reply_to_message_id, collected_at
            FROM messages
            WHERE chat_id IN ({marks}) AND datetime >= ?
            ORDER BY datetime DESC
            LIMIT ?
        """
        params = [*[int(x) for x in chat_ids], cutoff, max(1, int(limit))]
        conn = sqlite3.connect(self.storage.path)
        conn.row_factory = sqlite3.Row
        try:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def _write(self, payload: dict) -> None:
        tmp = self.output_path.with_suffix(self.output_path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.output_path)
