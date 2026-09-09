from datetime import datetime, timezone
from pathlib import Path

from app.models import MessageRecord
from app.storage import Storage


def msg(message_id: int, text: str = "Wildberries event") -> MessageRecord:
    return MessageRecord(
        message_id=message_id,
        chat_id=-1001,
        chat_title="News",
        datetime=datetime(2026, 9, 9, 7, message_id, tzinfo=timezone.utc),
        text=text,
        sender_id=None,
        views=100,
        forwards=2,
        reply_to_message_id=None,
        media_type=None,
        url=f"https://t.me/news/{message_id}",
    )


def test_storage_deduplicates_and_tracks_state(tmp_path: Path):
    storage = Storage(tmp_path / "telegram.db")
    rows = [msg(1), msg(2)]
    assert storage.insert_messages(rows) == 2
    assert storage.insert_messages(rows) == 0
    assert storage.count_messages() == 2
    storage.update_sync_state(-1001, rows)
    assert storage.get_last_message_id(-1001) == 2


def test_local_search(tmp_path: Path):
    storage = Storage(tmp_path / "telegram.db")
    storage.insert_messages([msg(1, "Wildberries warehouse"), msg(2, "Brent oil")])
    rows = storage.search_local("Wildberries", chat_ids=[-1001])
    assert len(rows) == 1
    assert rows[0]["message_id"] == 1
