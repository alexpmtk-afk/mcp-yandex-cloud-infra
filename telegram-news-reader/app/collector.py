from __future__ import annotations

import logging

from app.media_pipeline import MediaPipeline
from app.storage import Storage
from app.telegram_client import TelegramReader

LOGGER = logging.getLogger(__name__)


class Collector:
    def __init__(self, reader: TelegramReader, storage: Storage):
        self.reader = reader
        self.storage = storage
        self.media = MediaPipeline(reader)
        self.last_result: dict[int, int] = {}
        self.last_errors: dict[int, str] = {}

    async def sync_chat(self, chat_id: int, bootstrap_limit: int = 200) -> int:
        last_message_id = self.storage.get_last_message_id(chat_id)
        if last_message_id is None:
            messages = await self.reader.get_recent_messages(chat_id, bootstrap_limit)
        else:
            messages = await self.reader.get_messages_after_id(chat_id, last_message_id)

        inserted = self.storage.insert_messages(messages)
        if messages:
            self.storage.update_sync_state(chat_id, messages)
            await self.media.capture(messages)

        recent_rows = self.storage.get_recent_local(chat_id, limit=30)
        if recent_rows:
            await self.media.capture_local_rows(recent_rows)
        return inserted

    async def sync_all_allowed(self, bootstrap_limit: int = 200) -> dict[int, int]:
        result: dict[int, int] = {}
        errors: dict[int, str] = {}
        for item in self.reader.whitelist.list_allowed():
            try:
                result[item.chat_id] = await self.sync_chat(item.chat_id, bootstrap_limit)
            except Exception as exc:
                LOGGER.warning(
                    "chat_sync_error chat_id=%s error=%s",
                    item.chat_id,
                    type(exc).__name__,
                )
                errors[item.chat_id] = type(exc).__name__
                result[item.chat_id] = 0
        self.last_result = result
        self.last_errors = errors
        return result
