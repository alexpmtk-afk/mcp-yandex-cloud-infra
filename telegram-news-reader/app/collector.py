from __future__ import annotations

from app.storage import Storage
from app.telegram_client import TelegramReader


class Collector:
    def __init__(self, reader: TelegramReader, storage: Storage):
        self.reader = reader
        self.storage = storage

    async def sync_chat(self, chat_id: int, bootstrap_limit: int = 200) -> int:
        last_message_id = self.storage.get_last_message_id(chat_id)
        if last_message_id is None:
            messages = await self.reader.get_recent_messages(chat_id, bootstrap_limit)
        else:
            messages = await self.reader.get_messages_after_id(chat_id, last_message_id)

        inserted = self.storage.insert_messages(messages)
        if messages:
            self.storage.update_sync_state(chat_id, messages)
        return inserted

    async def sync_all_allowed(self, bootstrap_limit: int = 200) -> dict[int, int]:
        result: dict[int, int] = {}
        for item in self.reader.whitelist.list_allowed():
            result[item.chat_id] = await self.sync_chat(item.chat_id, bootstrap_limit)
        return result
