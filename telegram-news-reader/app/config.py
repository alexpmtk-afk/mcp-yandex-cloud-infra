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
    proxy_type: str | None = None
    proxy_host: str | None = None
    proxy_port: int | None = None
    proxy_username: str | None = None
    proxy_password: str | None = None

    def telethon_proxy(self) -> dict[str, object] | None:
        """Return a Telethon-compatible proxy mapping without logging secrets."""
        if self.proxy_type is None:
            return None
        return {
            "proxy_type": self.proxy_type,
            "addr": self.proxy_host,
            "port": self.proxy_port,
            "username": self.proxy_username,
            "password": self.proxy_password,
            "rdns": True,
        }


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

    proxy_type, proxy_host, proxy_port, proxy_username, proxy_password = _load_proxy()

    return Settings(
        api_id=api_id,
        api_hash=api_hash,
        phone=phone,
        session_path=Path(os.getenv("TELEGRAM_SESSION_PATH", "data/telegram_news")),
        database_path=Path(os.getenv("TELEGRAM_DATABASE_PATH", "data/telegram.db")),
        whitelist_path=Path(
            os.getenv("TELEGRAM_WHITELIST_PATH", "config/allowed_chats.yaml")
        ),
        proxy_type=proxy_type,
        proxy_host=proxy_host,
        proxy_port=proxy_port,
        proxy_username=proxy_username,
        proxy_password=proxy_password,
    )


def _load_proxy() -> tuple[str | None, str | None, int | None, str | None, str | None]:
    proxy_type = os.getenv("TELEGRAM_PROXY_TYPE", "").strip().lower() or None
    proxy_host = os.getenv("TELEGRAM_PROXY_HOST", "").strip() or None
    proxy_port_raw = os.getenv("TELEGRAM_PROXY_PORT", "").strip()
    proxy_username = os.getenv("TELEGRAM_PROXY_USERNAME", "").strip() or None
    proxy_password = os.getenv("TELEGRAM_PROXY_PASSWORD", "").strip() or None

    configured = any(
        [proxy_type, proxy_host, proxy_port_raw, proxy_username, proxy_password]
    )
    if not configured:
        return None, None, None, None, None

    if proxy_type not in {"socks5", "http"}:
        raise RuntimeError("TELEGRAM_PROXY_TYPE supports 'socks5' or 'http'")
    if not proxy_host or not proxy_port_raw:
        raise RuntimeError(
            "Proxy requires TELEGRAM_PROXY_HOST and TELEGRAM_PROXY_PORT"
        )
    try:
        proxy_port = int(proxy_port_raw)
    except ValueError as exc:
        raise RuntimeError("TELEGRAM_PROXY_PORT must be an integer") from exc
    if not 1 <= proxy_port <= 65535:
        raise RuntimeError("TELEGRAM_PROXY_PORT must be between 1 and 65535")
    if bool(proxy_username) != bool(proxy_password):
        raise RuntimeError(
            "TELEGRAM_PROXY_USERNAME and TELEGRAM_PROXY_PASSWORD must be set together"
        )

    return proxy_type, proxy_host, proxy_port, proxy_username, proxy_password
