from __future__ import annotations

from app.config import load_settings
from app.storage import Storage
from app.telegram_client import TelegramReader
from app.whitelist import Whitelist


def build_runtime():
    settings = load_settings()
    whitelist = Whitelist(settings.whitelist_path)
    reader = TelegramReader(settings, whitelist)
    storage = Storage(settings.database_path)
    return settings, whitelist, reader, storage
