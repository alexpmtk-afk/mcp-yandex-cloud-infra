from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from telethon import TelegramClient

from app.config import Settings
from app.errors import AuthorizationRequired
from app.formatting import dialog_type, media_type, public_message_url
from app.models import DialogRecord, MessageRecord
from app.whitelist import Whitelist


class TelegramReader:
    """Read-only application wrapper around Telethon.

    The wrapper intentionally exposes no send/edit/delete/join/leave operations.
    """

    def __init__(self, settings: Settings, whitelist: Whitelist | None = None):
        self.settings = settings
        self.whitelist = whitelist or Whitelist(settings.whitelist_path)
        Path(settings.session_path).parent.mkdir(parents=True, exist_ok=True)
        self.client = TelegramClient(
            str(settings.session_path),
            settings.api_id,
            settings.api_hash,
            proxy=settings.telethon_proxy(),
        )

    async def connect(self, *, interactive_login: bool = False) -> None:
        await self.client.connect()
        if await self.client.is_user_authorized():
            return
        if not interactive_login:
            await self.client.disconnect()
            raise AuthorizationRequired(
                "Telegram session is not authorized. Run scripts/login.py locally."
            )
        await self.client.start(phone=self.settings.phone)

    async def disconnect(self) -> None:
        await self.client.disconnect()

    async def is_authorized(self) -> bool:
        was_connected = self.client.is_connected()
        if not was_connected:
            await self.client.connect()
        try:
            return bool(await self.client.is_user_authorized())
        finally:
            if not was_connected:
                await self.client.disconnect()

    async def list_dialogs(self) -> list[DialogRecord]:
        result: list[DialogRecord] = []
        async for dialog in self.client.iter_dialogs():
            entity = dialog.entity
            result.append(
                DialogRecord(
                    chat_id=int(dialog.id),
                    title=str(dialog.name or ""),
                    username=getattr(entity, "username", None),
                    type=dialog_type(entity),
                    unread_count=int(getattr(dialog, "unread_count", 0) or 0),
                )
            )
        return result

    async def get_recent_messages(
        self, chat_id: int, limit: int = 20
    ) -> list[MessageRecord]:
        entity = await self._allowed_entity(chat_id)
        records: list[MessageRecord] = []
        async for message in self.client.iter_messages(entity, limit=max(1, limit)):
            records.append(self._message_record(chat_id, entity, message))
        return records

    async def get_messages_since(
        self,
        chat_id: int,
        datetime_from: datetime,
        *,
        limit: int = 1000,
    ) -> list[MessageRecord]:
        entity = await self._allowed_entity(chat_id)
        cutoff = _as_utc(datetime_from)
        result: list[MessageRecord] = []
        async for message in self.client.iter_messages(entity, limit=max(1, limit)):
            if message.date and _as_utc(message.date) < cutoff:
                break
            result.append(self._message_record(chat_id, entity, message))
        return result

    async def get_messages_after_id(
        self, chat_id: int, last_message_id: int
    ) -> list[MessageRecord]:
        entity = await self._allowed_entity(chat_id)
        result: list[MessageRecord] = []
        async for message in self.client.iter_messages(
            entity, min_id=int(last_message_id), reverse=True
        ):
            result.append(self._message_record(chat_id, entity, message))
        return result

    async def search_messages(
        self,
        chat_id: int,
        query: str,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 100,
        scan_limit: int = 2000,
    ) -> list[MessageRecord]:
        entity = await self._allowed_entity(chat_id)
        result: list[MessageRecord] = []
        low = _as_utc(date_from) if date_from else None
        high = _as_utc(date_to) if date_to else None
        async for message in self.client.iter_messages(
            entity, search=query, limit=max(limit, scan_limit)
        ):
            if not message.date:
                continue
            moment = _as_utc(message.date)
            if high and moment > high:
                continue
            if low and moment < low:
                break
            result.append(self._message_record(chat_id, entity, message))
            if len(result) >= limit:
                break
        return result

    async def get_message(
        self, chat_id: int, message_id: int
    ) -> MessageRecord | None:
        entity = await self._allowed_entity(chat_id)
        message = await self.client.get_messages(entity, ids=int(message_id))
        if not message:
            return None
        return self._message_record(chat_id, entity, message)

    async def _allowed_entity(self, chat_id: int):
        self.whitelist.assert_allowed(chat_id)
        return await self.client.get_entity(int(chat_id))

    def _message_record(self, chat_id: int, entity, message) -> MessageRecord:
        username = getattr(entity, "username", None)
        title = (
            getattr(entity, "title", None)
            or " ".join(
                part
                for part in [
                    getattr(entity, "first_name", None),
                    getattr(entity, "last_name", None),
                ]
                if part
            )
            or str(chat_id)
        )
        reply_to = getattr(message, "reply_to_msg_id", None)
        return MessageRecord(
            message_id=int(message.id),
            chat_id=int(chat_id),
            chat_title=str(title),
            datetime=_as_utc(message.date),
            text=str(getattr(message, "message", None) or ""),
            sender_id=getattr(message, "sender_id", None),
            views=getattr(message, "views", None),
            forwards=getattr(message, "forwards", None),
            reply_to_message_id=int(reply_to) if reply_to else None,
            media_type=media_type(message),
            url=public_message_url(username, int(message.id)),
        )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
