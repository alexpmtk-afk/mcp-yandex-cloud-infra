from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.models import MessageRecord


SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS messages (
    chat_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    chat_title TEXT NOT NULL,
    datetime TEXT NOT NULL,
    sender_id INTEGER,
    text TEXT NOT NULL,
    url TEXT,
    media_type TEXT,
    views INTEGER,
    forwards INTEGER,
    reply_to_message_id INTEGER,
    collected_at TEXT NOT NULL,
    PRIMARY KEY (chat_id, message_id)
);
CREATE INDEX IF NOT EXISTS idx_messages_datetime ON messages(datetime);
CREATE INDEX IF NOT EXISTS idx_messages_chat_datetime ON messages(chat_id, datetime);
CREATE TABLE IF NOT EXISTS sync_state (
    chat_id INTEGER PRIMARY KEY,
    last_message_id INTEGER NOT NULL,
    last_message_datetime TEXT,
    last_collected_at TEXT NOT NULL
);
"""


class Storage:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    def insert_messages(self, messages: list[MessageRecord]) -> int:
        if not messages:
            return 0
        now = datetime.now(timezone.utc).isoformat()
        rows = [
            (
                m.chat_id,
                m.message_id,
                m.chat_title,
                m.datetime.isoformat(),
                m.sender_id,
                m.text,
                m.url,
                m.media_type,
                m.views,
                m.forwards,
                m.reply_to_message_id,
                now,
            )
            for m in messages
        ]
        with self._connect() as conn:
            before = conn.total_changes
            conn.executemany(
                """
                INSERT OR IGNORE INTO messages (
                    chat_id, message_id, chat_title, datetime, sender_id, text,
                    url, media_type, views, forwards, reply_to_message_id, collected_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            return conn.total_changes - before

    def get_last_message_id(self, chat_id: int) -> int | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT last_message_id FROM sync_state WHERE chat_id = ?", (chat_id,)
            ).fetchone()
            return int(row[0]) if row else None

    def update_sync_state(self, chat_id: int, messages: list[MessageRecord]) -> None:
        if not messages:
            return
        newest = max(messages, key=lambda item: item.message_id)
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sync_state (
                    chat_id, last_message_id, last_message_datetime, last_collected_at
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    last_message_id = excluded.last_message_id,
                    last_message_datetime = excluded.last_message_datetime,
                    last_collected_at = excluded.last_collected_at
                """,
                (chat_id, newest.message_id, newest.datetime.isoformat(), now),
            )

    def search_local(
        self,
        query: str,
        *,
        chat_ids: list[int] | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 100,
    ) -> list[dict]:
        clauses = ["text LIKE ?"]
        params: list[object] = [f"%{query}%"]
        if chat_ids:
            placeholders = ",".join("?" for _ in chat_ids)
            clauses.append(f"chat_id IN ({placeholders})")
            params.extend(chat_ids)
        if date_from:
            clauses.append("datetime >= ?")
            params.append(date_from.isoformat())
        if date_to:
            clauses.append("datetime <= ?")
            params.append(date_to.isoformat())
        params.append(max(1, int(limit)))
        sql = f"""
            SELECT chat_id, message_id, chat_title, datetime, sender_id, text,
                   url, media_type, views, forwards, reply_to_message_id, collected_at
            FROM messages
            WHERE {' AND '.join(clauses)}
            ORDER BY datetime DESC
            LIMIT ?
        """
        with self._connect() as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

    def get_recent_local(self, chat_id: int, limit: int = 20) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT chat_id, message_id, chat_title, datetime, sender_id, text,
                       url, media_type, views, forwards, reply_to_message_id, collected_at
                FROM messages
                WHERE chat_id = ?
                ORDER BY datetime DESC
                LIMIT ?
                """,
                (int(chat_id), max(1, int(limit))),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_messages_local(
        self,
        chat_id: int,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 200,
    ) -> list[dict]:
        clauses = ["chat_id = ?"]
        params: list[object] = [int(chat_id)]
        if date_from:
            clauses.append("datetime >= ?")
            params.append(date_from.isoformat())
        if date_to:
            clauses.append("datetime <= ?")
            params.append(date_to.isoformat())
        params.append(max(1, int(limit)))
        sql = f"""
            SELECT chat_id, message_id, chat_title, datetime, sender_id, text,
                   url, media_type, views, forwards, reply_to_message_id, collected_at
            FROM messages
            WHERE {' AND '.join(clauses)}
            ORDER BY datetime DESC
            LIMIT ?
        """
        with self._connect() as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

    def get_message_local(self, chat_id: int, message_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT chat_id, message_id, chat_title, datetime, sender_id, text,
                       url, media_type, views, forwards, reply_to_message_id, collected_at
                FROM messages
                WHERE chat_id = ? AND message_id = ?
                """,
                (int(chat_id), int(message_id)),
            ).fetchone()
            return dict(row) if row else None

    def count_messages(self, chat_id: int | None = None) -> int:
        with self._connect() as conn:
            if chat_id is None:
                row = conn.execute("SELECT COUNT(*) FROM messages").fetchone()
            else:
                row = conn.execute(
                    "SELECT COUNT(*) FROM messages WHERE chat_id = ?", (chat_id,)
                ).fetchone()
            return int(row[0])
