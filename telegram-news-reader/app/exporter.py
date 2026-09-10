from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.storage import Storage
from app.whitelist import Whitelist


class TelegramNewsExporter:
    """Write a compact incremental export for the currently allowed chats."""

    def __init__(self, storage: Storage, whitelist: Whitelist, output_path: str | Path):
        self.storage = storage
        self.whitelist = whitelist
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

    def export_incremental(self, limit: int = 5000) -> dict:
        allowed_ids = [item.chat_id for item in self.whitelist.list_allowed()]
        cursor = self.storage.get_export_cursor()
        rows = self.storage.get_messages_after_rowid(cursor, allowed_ids, limit=limit)

        messages = []
        max_rowid = cursor
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

        tmp = self.output_path.with_suffix(self.output_path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.output_path)

        if rows:
            self.storage.set_export_cursor(max_rowid)

        return {"messages": len(messages), "cursor": max_rowid, "path": str(self.output_path)}
