from pathlib import Path

from app.news_journal import NewsJournal


def _message(chat_id: int, message_id: int, when: str, text: str = "news") -> dict:
    return {
        "chat_id": chat_id,
        "message_id": message_id,
        "chat_title": f"chat-{chat_id}",
        "datetime": when,
        "text": text,
        "sender_id": None,
        "views": None,
        "forwards": None,
        "reply_to_message_id": None,
        "media_type": None,
        "url": None,
    }


def test_prepared_batch_does_not_advance_cursor_until_confirmed(tmp_path: Path):
    journal = NewsJournal(tmp_path / "news_journal.sqlite3")
    profile = "main-news"
    messages = [
        _message(-1001, 10, "2026-09-28T08:00:00+00:00"),
        _message(-1001, 11, "2026-09-28T08:05:00+00:00"),
    ]
    batch = journal.create_prepared(
        profile,
        [
            {
                "chat_id": -1001,
                "chat_name": "Test",
                "from_message_id": 10,
                "to_message_id": 11,
                "to_message_datetime": "2026-09-28T08:05:00+00:00",
                "message_count": 2,
            }
        ],
        messages,
    )

    assert batch["status"] == "prepared"
    assert journal.cursor(profile, -1001) is None

    confirmed = journal.confirm_prepared(profile)
    assert confirmed is not None
    assert confirmed["status"] == "confirmed"
    cursor = journal.cursor(profile, -1001)
    assert cursor is not None
    assert cursor["confirmed_message_id"] == 11


def test_existing_prepared_batch_is_reused(tmp_path: Path):
    journal = NewsJournal(tmp_path / "news_journal.sqlite3")
    profile = "main-news"
    ranges = [
        {
            "chat_id": -1001,
            "chat_name": "Test",
            "from_message_id": 20,
            "to_message_id": 20,
            "to_message_datetime": "2026-09-28T09:00:00+00:00",
            "message_count": 1,
        }
    ]
    first = journal.create_prepared(
        profile, ranges, [_message(-1001, 20, "2026-09-28T09:00:00+00:00")]
    )
    second = journal.create_prepared(
        profile, ranges, [_message(-1001, 21, "2026-09-28T09:05:00+00:00")]
    )

    assert second["batch_id"] == first["batch_id"]
    assert [item["message_id"] for item in second["messages"]] == [20]


def test_mark_used_and_repeat_are_persistent_without_confirming(tmp_path: Path):
    journal = NewsJournal(tmp_path / "news_journal.sqlite3")
    profile = "main-news"
    batch = journal.create_prepared(
        profile,
        [
            {
                "chat_id": -1001,
                "chat_name": "Test",
                "from_message_id": 30,
                "to_message_id": 31,
                "to_message_datetime": "2026-09-28T10:05:00+00:00",
                "message_count": 2,
            }
        ],
        [
            _message(-1001, 30, "2026-09-28T10:00:00+00:00"),
            _message(-1001, 31, "2026-09-28T10:05:00+00:00"),
        ],
    )

    marked = journal.mark_used(batch["batch_id"], ["-1001:31"])
    assert marked["used_message_refs"] == ["-1001:31"]
    assert journal.cursor(profile, -1001) is None

    repeated = journal.get_prepared(profile, increment_repeat=True)
    assert repeated is not None
    assert repeated["repeat_count"] == 1
    assert repeated["used_message_refs"] == ["-1001:31"]
    assert journal.cursor(profile, -1001) is None


def test_check_time_is_recorded_even_without_confirmed_cursor(tmp_path: Path):
    journal = NewsJournal(tmp_path / "news_journal.sqlite3")
    journal.record_check(
        "main-news",
        -1002,
        "Quiet chat",
        latest_seen_message_id=7,
        latest_seen_message_datetime="2026-09-28T07:00:00+00:00",
    )
    status = journal.status("main-news")
    assert status["cursors"] == []
    assert status["checked_without_cursor"][0]["chat_id"] == -1002
    assert status["checked_without_cursor"][0]["last_checked_at"]
    profiles = journal.list_profiles()
    assert profiles[0]["profile"] == "main-news"
    assert profiles[0]["checked_chat_count"] == 1


def test_mcp_contract_exposes_journal_without_changing_telegram_read_only_policy():
    root = Path(__file__).resolve().parents[1]
    source = (root / "app" / "mcp_server.py").read_text(encoding="utf-8")
    service = (root / "app" / "service.py").read_text(encoding="utf-8")

    assert "telegram_news_prepare" in source
    assert "telegram_news_mark_used" in source
    assert "telegram_news_repeat" in source
    assert "telegram_news_status" in source
    assert "telegram_news_profiles" in source
    assert "confirm_previous" in source
    assert "news_journal.sqlite3" in service
    assert '"news_journal": "enabled"' in service
