from __future__ import annotations

from datetime import datetime

from fastmcp import FastMCP

from app.storage import Storage
from app.whitelist import Whitelist


def build_mcp(whitelist: Whitelist, storage: Storage) -> FastMCP:
    mcp = FastMCP("Telegram News Reader")

    @mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
    def telegram_list_allowed_chats() -> list[dict]:
        """List Telegram chats allowed by the server whitelist."""
        return [{"chat_id": item.chat_id, "name": item.name} for item in whitelist.list_allowed()]

    @mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
    def telegram_get_recent(chat_id: int, limit: int = 20) -> list[dict]:
        """Get recently collected messages from one allowed Telegram chat."""
        whitelist.assert_allowed(chat_id)
        return storage.get_recent_local(chat_id, min(max(limit, 1), 500))

    @mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
    def telegram_get_messages(
        chat_id: int,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 200,
    ) -> list[dict]:
        """Get collected messages in a date range from one allowed Telegram chat."""
        whitelist.assert_allowed(chat_id)
        return storage.get_messages_local(
            chat_id,
            date_from=datetime.fromisoformat(date_from) if date_from else None,
            date_to=datetime.fromisoformat(date_to) if date_to else None,
            limit=min(max(limit, 1), 1000),
        )

    @mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
    def telegram_search(
        query: str,
        chat_ids: list[int] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Search already collected Telegram messages. Only whitelisted chats are searched."""
        ids = chat_ids or [item.chat_id for item in whitelist.list_allowed()]
        for chat_id in ids:
            whitelist.assert_allowed(chat_id)
        return storage.search_local(
            query,
            chat_ids=ids,
            date_from=datetime.fromisoformat(date_from) if date_from else None,
            date_to=datetime.fromisoformat(date_to) if date_to else None,
            limit=min(max(limit, 1), 1000),
        )

    @mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
    def telegram_get_message(chat_id: int, message_id: int) -> dict | None:
        """Get one previously collected Telegram message by chat and message ID."""
        whitelist.assert_allowed(chat_id)
        return storage.get_message_local(chat_id, message_id)

    return mcp
