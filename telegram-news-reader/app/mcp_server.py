from __future__ import annotations

from datetime import datetime, timezone

from fastmcp import FastMCP

from app.telegram_client import TelegramReader
from app.whitelist import Whitelist


def _parse_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _rows(records) -> list[dict]:
    return [record.to_dict() for record in records]


def build_mcp(whitelist: Whitelist, reader: TelegramReader) -> FastMCP:
    """Build the read-only MCP surface.

    Production reads are on-demand and go directly to Telegram. The local SQLite
    database is no longer the source of truth for MCP answers.
    """
    mcp = FastMCP("Telegram News Reader")

    @mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
    def telegram_list_allowed_chats() -> list[dict]:
        """List Telegram chats allowed by the current server whitelist."""
        return [{"chat_id": item.chat_id, "name": item.name} for item in whitelist.list_allowed()]

    @mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
    async def telegram_get_recent(chat_id: int, limit: int = 20) -> list[dict]:
        """Read the newest messages directly from one allowed Telegram chat."""
        whitelist.assert_allowed(chat_id)
        records = await reader.get_recent_messages(chat_id, min(max(limit, 1), 500))
        return _rows(records)

    @mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
    async def telegram_get_messages(
        chat_id: int,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 200,
    ) -> list[dict]:
        """Read messages directly from Telegram, optionally inside a date range."""
        whitelist.assert_allowed(chat_id)
        page_limit = min(max(limit, 1), 1000)
        low = _parse_datetime(date_from)
        high = _parse_datetime(date_to)
        if low is None and high is None:
            return _rows(await reader.get_recent_messages(chat_id, page_limit))
        high = high or datetime.now(timezone.utc)
        low = low or datetime(1970, 1, 1, tzinfo=timezone.utc)
        return _rows(
            await reader.get_messages_between(
                chat_id,
                low,
                high,
                limit=page_limit,
            )
        )

    @mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
    async def telegram_search(
        query: str,
        chat_ids: list[int] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Search Telegram on demand across allowed chats and return newest matches."""
        ids = chat_ids or [item.chat_id for item in whitelist.list_allowed()]
        for chat_id in ids:
            whitelist.assert_allowed(chat_id)

        total_limit = min(max(limit, 1), 1000)
        low = _parse_datetime(date_from)
        high = _parse_datetime(date_to)
        records = []
        for chat_id in ids:
            records.extend(
                await reader.search_messages(
                    chat_id,
                    query,
                    date_from=low,
                    date_to=high,
                    limit=total_limit,
                )
            )
        records.sort(key=lambda item: item.datetime, reverse=True)
        return _rows(records[:total_limit])

    @mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
    async def telegram_get_message(chat_id: int, message_id: int) -> dict | None:
        """Read one message directly from Telegram by chat and message ID."""
        whitelist.assert_allowed(chat_id)
        record = await reader.get_message(chat_id, message_id)
        return record.to_dict() if record else None

    return mcp
