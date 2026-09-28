from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS news_cursors (
    profile TEXT NOT NULL,
    chat_id INTEGER NOT NULL,
    chat_name TEXT NOT NULL,
    confirmed_message_id INTEGER NOT NULL,
    confirmed_message_datetime TEXT,
    confirmed_at TEXT NOT NULL,
    last_checked_at TEXT,
    PRIMARY KEY (profile, chat_id)
);

CREATE TABLE IF NOT EXISTS news_checks (
    profile TEXT NOT NULL,
    chat_id INTEGER NOT NULL,
    chat_name TEXT NOT NULL,
    last_checked_at TEXT NOT NULL,
    latest_seen_message_id INTEGER,
    latest_seen_message_datetime TEXT,
    PRIMARY KEY (profile, chat_id)
);

CREATE TABLE IF NOT EXISTS news_batches (
    batch_id TEXT PRIMARY KEY,
    profile TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('prepared', 'confirmed')),
    created_at TEXT NOT NULL,
    confirmed_at TEXT,
    repeat_count INTEGER NOT NULL DEFAULT 0
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_news_one_prepared_per_profile
ON news_batches(profile)
WHERE status = 'prepared';

CREATE TABLE IF NOT EXISTS news_batch_chats (
    batch_id TEXT NOT NULL,
    chat_id INTEGER NOT NULL,
    chat_name TEXT NOT NULL,
    from_message_id INTEGER NOT NULL,
    to_message_id INTEGER NOT NULL,
    to_message_datetime TEXT,
    message_count INTEGER NOT NULL,
    PRIMARY KEY (batch_id, chat_id),
    FOREIGN KEY (batch_id) REFERENCES news_batches(batch_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS news_batch_messages (
    batch_id TEXT NOT NULL,
    chat_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    message_datetime TEXT,
    payload_json TEXT NOT NULL,
    used_in_answer INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (batch_id, chat_id, message_id),
    FOREIGN KEY (batch_id) REFERENCES news_batches(batch_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_news_batches_profile_created
ON news_batches(profile, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_news_batch_messages_batch
ON news_batch_messages(batch_id, chat_id, message_id);
"""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_profile(profile: str) -> str:
    value = str(profile or "").strip()
    if not value:
        raise ValueError("profile must not be empty")
    if len(value) > 120:
        raise ValueError("profile is too long")
    return value


class NewsJournal:
    """Durable cursor/journal for sequential Telegram news blocks.

    This database tracks what was checked and what was delivered without changing
    Telegram itself. A prepared batch does not advance the confirmed cursor. The
    cursor advances only when that prepared batch is explicitly confirmed (normally
    when the user asks for the *next* block).
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    def cursor(self, profile: str, chat_id: int) -> dict | None:
        profile = _clean_profile(profile)
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT profile, chat_id, chat_name, confirmed_message_id,
                       confirmed_message_datetime, confirmed_at, last_checked_at
                FROM news_cursors
                WHERE profile = ? AND chat_id = ?
                """,
                (profile, int(chat_id)),
            ).fetchone()
            return dict(row) if row else None

    def record_check(
        self,
        profile: str,
        chat_id: int,
        chat_name: str,
        *,
        latest_seen_message_id: int | None,
        latest_seen_message_datetime: str | None,
    ) -> None:
        profile = _clean_profile(profile)
        now = _utcnow()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO news_checks (
                    profile, chat_id, chat_name, last_checked_at,
                    latest_seen_message_id, latest_seen_message_datetime
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(profile, chat_id) DO UPDATE SET
                    chat_name = excluded.chat_name,
                    last_checked_at = excluded.last_checked_at,
                    latest_seen_message_id = excluded.latest_seen_message_id,
                    latest_seen_message_datetime = excluded.latest_seen_message_datetime
                """,
                (
                    profile,
                    int(chat_id),
                    str(chat_name),
                    now,
                    int(latest_seen_message_id) if latest_seen_message_id is not None else None,
                    latest_seen_message_datetime,
                ),
            )
            conn.execute(
                """
                UPDATE news_cursors
                SET last_checked_at = ?
                WHERE profile = ? AND chat_id = ?
                """,
                (now, profile, int(chat_id)),
            )

    def get_prepared(self, profile: str, *, increment_repeat: bool = False) -> dict | None:
        profile = _clean_profile(profile)
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT batch_id
                FROM news_batches
                WHERE profile = ? AND status = 'prepared'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (profile,),
            ).fetchone()
            if not row:
                return None
            batch_id = str(row["batch_id"])
            if increment_repeat:
                conn.execute(
                    "UPDATE news_batches SET repeat_count = repeat_count + 1 WHERE batch_id = ?",
                    (batch_id,),
                )
            return self._load_batch(conn, batch_id)

    def create_prepared(
        self,
        profile: str,
        chat_ranges: list[dict],
        messages: Iterable[dict],
    ) -> dict:
        profile = _clean_profile(profile)
        existing = self.get_prepared(profile)
        if existing is not None:
            return existing

        ranges = [dict(item) for item in chat_ranges]
        rows = [dict(item) for item in messages]
        if not rows:
            raise ValueError("cannot create empty prepared batch")

        batch_id = uuid.uuid4().hex
        now = _utcnow()
        try:
            with self._connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                existing_row = conn.execute(
                    """
                    SELECT batch_id
                    FROM news_batches
                    WHERE profile = ? AND status = 'prepared'
                    LIMIT 1
                    """,
                    (profile,),
                ).fetchone()
                if existing_row:
                    return self._load_batch(conn, str(existing_row["batch_id"]))

                conn.execute(
                    """
                    INSERT INTO news_batches (batch_id, profile, status, created_at)
                    VALUES (?, ?, 'prepared', ?)
                    """,
                    (batch_id, profile, now),
                )
                for item in ranges:
                    conn.execute(
                        """
                        INSERT INTO news_batch_chats (
                            batch_id, chat_id, chat_name, from_message_id,
                            to_message_id, to_message_datetime, message_count
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            batch_id,
                            int(item["chat_id"]),
                            str(item["chat_name"]),
                            int(item["from_message_id"]),
                            int(item["to_message_id"]),
                            item.get("to_message_datetime"),
                            int(item["message_count"]),
                        ),
                    )
                for item in rows:
                    conn.execute(
                        """
                        INSERT INTO news_batch_messages (
                            batch_id, chat_id, message_id, message_datetime, payload_json
                        ) VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            batch_id,
                            int(item["chat_id"]),
                            int(item["message_id"]),
                            item.get("datetime"),
                            json.dumps(item, ensure_ascii=False, separators=(",", ":")),
                        ),
                    )
                return self._load_batch(conn, batch_id)
        except sqlite3.IntegrityError:
            prepared = self.get_prepared(profile)
            if prepared is None:
                raise
            return prepared

    def mark_used(self, batch_id: str, message_refs: list[str]) -> dict:
        refs: set[tuple[int, int]] = set()
        for raw in message_refs:
            parts = str(raw).split(":", 1)
            if len(parts) != 2:
                raise ValueError(f"invalid message ref: {raw}")
            refs.add((int(parts[0]), int(parts[1])))

        with self._connect() as conn:
            batch = conn.execute(
                "SELECT batch_id, status FROM news_batches WHERE batch_id = ?",
                (str(batch_id),),
            ).fetchone()
            if not batch:
                raise KeyError("unknown batch_id")
            if batch["status"] != "prepared":
                raise ValueError("only a prepared batch can be marked")

            conn.execute(
                "UPDATE news_batch_messages SET used_in_answer = 0 WHERE batch_id = ?",
                (str(batch_id),),
            )
            valid = {
                (int(row["chat_id"]), int(row["message_id"]))
                for row in conn.execute(
                    "SELECT chat_id, message_id FROM news_batch_messages WHERE batch_id = ?",
                    (str(batch_id),),
                ).fetchall()
            }
            unknown = sorted(refs - valid)
            if unknown:
                raise ValueError(f"message refs not in batch: {unknown}")
            for chat_id, message_id in refs:
                conn.execute(
                    """
                    UPDATE news_batch_messages
                    SET used_in_answer = 1
                    WHERE batch_id = ? AND chat_id = ? AND message_id = ?
                    """,
                    (str(batch_id), chat_id, message_id),
                )
            return self._load_batch(conn, str(batch_id))

    def confirm_prepared(self, profile: str) -> dict | None:
        profile = _clean_profile(profile)
        now = _utcnow()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            batch = conn.execute(
                """
                SELECT batch_id
                FROM news_batches
                WHERE profile = ? AND status = 'prepared'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (profile,),
            ).fetchone()
            if not batch:
                return None
            batch_id = str(batch["batch_id"])
            ranges = conn.execute(
                """
                SELECT chat_id, chat_name, to_message_id, to_message_datetime
                FROM news_batch_chats
                WHERE batch_id = ?
                """,
                (batch_id,),
            ).fetchall()
            for item in ranges:
                check = conn.execute(
                    """
                    SELECT last_checked_at
                    FROM news_checks
                    WHERE profile = ? AND chat_id = ?
                    """,
                    (profile, int(item["chat_id"])),
                ).fetchone()
                conn.execute(
                    """
                    INSERT INTO news_cursors (
                        profile, chat_id, chat_name, confirmed_message_id,
                        confirmed_message_datetime, confirmed_at, last_checked_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(profile, chat_id) DO UPDATE SET
                        chat_name = excluded.chat_name,
                        confirmed_message_id = excluded.confirmed_message_id,
                        confirmed_message_datetime = excluded.confirmed_message_datetime,
                        confirmed_at = excluded.confirmed_at,
                        last_checked_at = COALESCE(excluded.last_checked_at, news_cursors.last_checked_at)
                    """,
                    (
                        profile,
                        int(item["chat_id"]),
                        str(item["chat_name"]),
                        int(item["to_message_id"]),
                        item["to_message_datetime"],
                        now,
                        check["last_checked_at"] if check else None,
                    ),
                )
            conn.execute(
                """
                UPDATE news_batches
                SET status = 'confirmed', confirmed_at = ?
                WHERE batch_id = ?
                """,
                (now, batch_id),
            )
            return self._load_batch(conn, batch_id)

    def status(self, profile: str) -> dict:
        profile = _clean_profile(profile)
        with self._connect() as conn:
            cursors = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT c.profile, c.chat_id, c.chat_name, c.confirmed_message_id,
                           c.confirmed_message_datetime, c.confirmed_at,
                           COALESCE(k.last_checked_at, c.last_checked_at) AS last_checked_at,
                           k.latest_seen_message_id, k.latest_seen_message_datetime
                    FROM news_cursors c
                    LEFT JOIN news_checks k
                      ON k.profile = c.profile AND k.chat_id = c.chat_id
                    WHERE c.profile = ?
                    ORDER BY c.chat_name COLLATE NOCASE, c.chat_id
                    """,
                    (profile,),
                ).fetchall()
            ]
            known = {int(item["chat_id"]) for item in cursors}
            checks = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT profile, chat_id, chat_name, last_checked_at,
                           latest_seen_message_id, latest_seen_message_datetime
                    FROM news_checks
                    WHERE profile = ?
                    ORDER BY chat_name COLLATE NOCASE, chat_id
                    """,
                    (profile,),
                ).fetchall()
                if int(row["chat_id"]) not in known
            ]
            prepared = self.get_prepared(profile)
            last_confirmed = conn.execute(
                """
                SELECT batch_id, created_at, confirmed_at, repeat_count
                FROM news_batches
                WHERE profile = ? AND status = 'confirmed'
                ORDER BY confirmed_at DESC
                LIMIT 1
                """,
                (profile,),
            ).fetchone()
            return {
                "profile": profile,
                "database": str(self.path),
                "cursors": cursors,
                "checked_without_cursor": checks,
                "prepared_batch": prepared,
                "last_confirmed_batch": dict(last_confirmed) if last_confirmed else None,
            }

    def _load_batch(self, conn: sqlite3.Connection, batch_id: str) -> dict:
        batch = conn.execute(
            """
            SELECT batch_id, profile, status, created_at, confirmed_at, repeat_count
            FROM news_batches
            WHERE batch_id = ?
            """,
            (str(batch_id),),
        ).fetchone()
        if not batch:
            raise KeyError("unknown batch_id")
        chats = [
            dict(row)
            for row in conn.execute(
                """
                SELECT chat_id, chat_name, from_message_id, to_message_id,
                       to_message_datetime, message_count
                FROM news_batch_chats
                WHERE batch_id = ?
                ORDER BY chat_name COLLATE NOCASE, chat_id
                """,
                (str(batch_id),),
            ).fetchall()
        ]
        messages = []
        used_refs = []
        for row in conn.execute(
            """
            SELECT chat_id, message_id, payload_json, used_in_answer
            FROM news_batch_messages
            WHERE batch_id = ?
            ORDER BY message_datetime ASC, chat_id ASC, message_id ASC
            """,
            (str(batch_id),),
        ).fetchall():
            payload = json.loads(str(row["payload_json"]))
            payload["journal_used_in_answer"] = bool(row["used_in_answer"])
            messages.append(payload)
            if row["used_in_answer"]:
                used_refs.append(f'{int(row["chat_id"])}:{int(row["message_id"])}')
        return {
            **dict(batch),
            "chats": chats,
            "messages": messages,
            "used_message_refs": used_refs,
        }
