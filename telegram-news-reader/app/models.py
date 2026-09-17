from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class DialogRecord:
    chat_id: int
    title: str
    username: str | None
    type: str
    unread_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MessageRecord:
    message_id: int
    chat_id: int
    chat_title: str
    datetime: datetime
    text: str
    sender_id: int | None
    views: int | None
    forwards: int | None
    reply_to_message_id: int | None
    media_type: str | None
    url: str | None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["datetime"] = self.datetime.isoformat()
        return data
