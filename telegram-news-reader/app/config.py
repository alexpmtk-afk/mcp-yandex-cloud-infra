from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    api_id: int
    api_hash: str
    phone: str | None
    session_path: Path
    database_path: Path
    whitelist_path: Path


def load_settings(env_file: str | Path = ".env") -> Settings:
    load_dotenv(dotenv_path=env_file, override=False)
    api_id_raw = os.getenv("TELEGRAM_API_ID", "").strip()
    api_hash = os.getenv("TELEGRAM_API_HASH", "").strip()
    phone = os.getenv("TELEGRAM_PHONE", "").strip() or None
    if not api_id_raw or not api_hash:
        raise RuntimeError("Missing TELEGRAM_API_ID / TELEGRAM_API_HASH")
    try:
        api_id = int(api_id_raw)
    except ValueError as exc:
        raise RuntimeError("TELEGRAM_API_ID must be an integer") from exc

    return Settings(
        api_id=api_id,
        api_hash=api_hash,
        phone=phone,
        session_path=Path(os.getenv("TELEGRAM_SESSION_PATH", "data/telegram_news")),
        database_path=Path(os.getenv("TELEGRAM_DATABASE_PATH", "data/telegram.db")),
        whitelist_path=Path(
            os.getenv("TELEGRAM_WHITELIST_PATH", "config/allowed_chats.yaml")
        ),
    )
