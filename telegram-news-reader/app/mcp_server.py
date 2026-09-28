from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastmcp import FastMCP

from app.news_journal import NewsJournal
from app.telegram_client import TelegramReader
from app.whitelist import Whitelist


def _parse_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _rows(records) -> list[dict]:
    return [record.to_dict() for record in records]


def build_mcp(whitelist: Whitelist, reader: TelegramReader, news_journal: NewsJournal) -> FastMCP:
    """Build the Telegram read surface plus the local news-block journal.

    Telegram operations remain read-only. Journal tools only mutate the local
    REMOTE journal so sequential news blocks can resume without duplicate or
    skipped Telegram messages.
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

    @mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False})
    async def telegram_news_prepare(
        profile: str = "default",
        chat_ids: list[int] | None = None,
        confirm_previous: bool = False,
        initial_lookback_hours: int = 48,
        max_messages_per_chat: int = 100,
    ) -> dict:
        """Prepare the next sequential news block and journal exactly what was checked.

        Normal use:
        - First/current request: confirm_previous=false. If a prepared block already
          exists (for example after an interrupted ChatGPT answer), that exact block
          is returned again and the cursor is NOT advanced.
        - A later request for a *new* block: confirm_previous=true. The previous
          prepared block is confirmed first, then reading starts strictly after its
          last confirmed Telegram message ID.

        On first use of a profile/chat, there is no historical cursor yet, so the
        initial block is built from the requested recent lookback window.
        """
        profile = str(profile or "").strip()
        if not profile:
            raise ValueError("profile must not be empty")

        existing = news_journal.get_prepared(profile)
        if existing is not None and not confirm_previous:
            existing["journal_action"] = "reused_prepared"
            return existing
        if existing is not None and confirm_previous:
            news_journal.confirm_prepared(profile)

        allowed = {int(item.chat_id): item for item in whitelist.list_allowed()}
        ids = [int(value) for value in (chat_ids or list(allowed))]
        ids = list(dict.fromkeys(ids))
        if not ids:
            raise ValueError("at least one chat_id is required")
        for chat_id in ids:
            whitelist.assert_allowed(chat_id)

        per_chat_limit = min(max(int(max_messages_per_chat), 1), 500)
        lookback_hours = min(max(int(initial_lookback_hours), 1), 24 * 30)
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=lookback_hours)

        all_rows: list[dict] = []
        ranges: list[dict] = []
        checks: list[dict] = []

        for chat_id in ids:
            allowed_chat = allowed[chat_id]
            cursor = news_journal.cursor(profile, chat_id)
            more_pending = False
            initial_truncated = False

            if cursor is not None:
                fetched = await reader.get_messages_after_id(
                    chat_id,
                    int(cursor["confirmed_message_id"]),
                    limit=per_chat_limit + 1,
                )
                more_pending = len(fetched) > per_chat_limit
                selected = fetched[:per_chat_limit]
                latest_seen_id = (
                    int(selected[-1].message_id)
                    if selected
                    else int(cursor["confirmed_message_id"])
                )
                latest_seen_datetime = (
                    selected[-1].datetime.isoformat()
                    if selected
                    else cursor.get("confirmed_message_datetime")
                )
            else:
                # First use has no cursor. Walk the requested lookback window all
                # the way backwards before choosing the oldest page. This prevents
                # high-volume channels from silently skipping older messages.
                page_size = min(max(per_chat_limit * 5, 250), 500)
                max_initial_scan = 10000
                fetched = []
                before_id: int | None = None
                while True:
                    remaining = max_initial_scan - len(fetched)
                    if remaining <= 0:
                        probe = await reader.get_messages_between(
                            chat_id,
                            cutoff,
                            now,
                            limit=1,
                            before_id=before_id,
                        )
                        if probe:
                            raise RuntimeError(
                                "INITIAL_LOOKBACK_TOO_LARGE: reduce initial_lookback_hours"
                            )
                        break
                    current_limit = min(page_size, remaining)
                    page = await reader.get_messages_between(
                        chat_id,
                        cutoff,
                        now,
                        limit=current_limit,
                        before_id=before_id,
                    )
                    if not page:
                        break
                    fetched.extend(page)
                    oldest_id = min(int(item.message_id) for item in page)
                    if before_id is not None and oldest_id >= before_id:
                        raise RuntimeError("INITIAL_LOOKBACK_CURSOR_STALLED")
                    before_id = oldest_id
                    if len(page) < current_limit:
                        break

                by_id = {int(item.message_id): item for item in fetched}
                fetched = sorted(by_id.values(), key=lambda item: item.message_id)
                selected = fetched[:per_chat_limit]
                more_pending = len(fetched) > per_chat_limit
                latest_record = fetched[-1] if fetched else None
                latest_seen_id = int(latest_record.message_id) if latest_record else None
                latest_seen_datetime = (
                    latest_record.datetime.isoformat() if latest_record else None
                )

            news_journal.record_check(
                profile,
                chat_id,
                allowed_chat.name,
                latest_seen_message_id=latest_seen_id,
                latest_seen_message_datetime=latest_seen_datetime,
            )

            checks.append(
                {
                    "chat_id": chat_id,
                    "chat_name": allowed_chat.name,
                    "last_confirmed_message_id": (
                        int(cursor["confirmed_message_id"]) if cursor else None
                    ),
                    "new_messages_in_batch": len(selected),
                    "more_pending": more_pending,
                    "initial_window_truncated": initial_truncated,
                }
            )

            if not selected:
                continue

            selected = sorted(selected, key=lambda item: item.message_id)
            rows = _rows(selected)
            all_rows.extend(rows)
            ranges.append(
                {
                    "chat_id": chat_id,
                    "chat_name": allowed_chat.name,
                    "from_message_id": int(selected[0].message_id),
                    "to_message_id": int(selected[-1].message_id),
                    "to_message_datetime": selected[-1].datetime.isoformat(),
                    "message_count": len(selected),
                }
            )

        if not all_rows:
            return {
                "profile": profile,
                "status": "no_new_messages",
                "journal_action": "checked_no_batch",
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "checks": checks,
                "messages": [],
            }

        batch = news_journal.create_prepared(profile, ranges, all_rows)
        batch["journal_action"] = "created_prepared"
        batch["checks"] = checks
        return batch

    @mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False})
    def telegram_news_mark_used(batch_id: str, message_refs: list[str]) -> dict:
        """Record which prepared messages were actually used in the ChatGPT answer.

        message_refs use the exact form "chat_id:message_id". This does NOT advance
        any cursor, so a failed/aborted ChatGPT response can still be repeated safely.
        """
        result = news_journal.mark_used(batch_id, message_refs)
        result["journal_action"] = "marked_used"
        return result

    @mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False})
    def telegram_news_repeat(profile: str = "default") -> dict | None:
        """Return the exact still-prepared block again without advancing the cursor."""
        result = news_journal.get_prepared(profile, increment_repeat=True)
        if result is not None:
            result["journal_action"] = "repeated_prepared"
        return result

    @mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
    def telegram_news_profiles() -> list[dict]:
        """List existing news-journal profiles and their last activity.

        A fresh ChatGPT conversation should use this to discover and reuse the same
        profile instead of inventing a new cursor namespace for an existing news feed.
        """
        return news_journal.list_profiles()

    @mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
    def telegram_news_status(profile: str = "default") -> dict:
        """Show confirmed cursors, last check times and any still-prepared news block."""
        return news_journal.status(profile)

    return mcp
