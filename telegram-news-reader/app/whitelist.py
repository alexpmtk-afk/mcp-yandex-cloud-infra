from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from app.errors import AccessDenied


@dataclass(frozen=True)
class AllowedChat:
    chat_id: int
    name: str
    enabled: bool = True


class Whitelist:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._items = self._load()

    def _load(self) -> dict[int, AllowedChat]:
        if not self.path.exists():
            return {}
        payload = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        result: dict[int, AllowedChat] = {}
        for item in payload.get("allowed_chats", []) or []:
            chat = AllowedChat(
                chat_id=int(item["chat_id"]),
                name=str(item.get("name") or item["chat_id"]),
                enabled=bool(item.get("enabled", True)),
            )
            result[chat.chat_id] = chat
        return result

    def reload(self) -> None:
        self._items = self._load()

    def replace(self, items: list[AllowedChat]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        payload = {
            "allowed_chats": [
                {"chat_id": x.chat_id, "name": x.name, "enabled": x.enabled}
                for x in items
            ]
        }
        temp.write_text(
            yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        temp.chmod(0o600)
        temp.replace(self.path)
        self.reload()

    def assert_allowed(self, chat_id: int) -> AllowedChat:
        self.reload()
        item = self._items.get(int(chat_id))
        if not item or not item.enabled:
            raise AccessDenied(f"ACCESS_DENIED: chat_id={chat_id}")
        return item

    def list_allowed(self) -> list[AllowedChat]:
        self.reload()
        return [item for item in self._items.values() if item.enabled]
