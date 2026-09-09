from pathlib import Path

import pytest

from app.config import Settings, load_settings


def test_settings_without_proxy_returns_none(tmp_path: Path):
    settings = Settings(
        api_id=1,
        api_hash="hash",
        phone=None,
        session_path=tmp_path / "session",
        database_path=tmp_path / "telegram.db",
        whitelist_path=tmp_path / "allowed.yaml",
    )

    assert settings.telethon_proxy() is None


def test_socks5_proxy_mapping_does_not_require_credentials(tmp_path: Path):
    settings = Settings(
        api_id=1,
        api_hash="hash",
        phone=None,
        session_path=tmp_path / "session",
        database_path=tmp_path / "telegram.db",
        whitelist_path=tmp_path / "allowed.yaml",
        proxy_type="socks5",
        proxy_host="proxy.example",
        proxy_port=1080,
    )

    assert settings.telethon_proxy() == {
        "proxy_type": "socks5",
        "addr": "proxy.example",
        "port": 1080,
        "username": None,
        "password": None,
        "rdns": True,
    }


def test_http_proxy_mapping_does_not_require_credentials(tmp_path: Path):
    settings = Settings(
        api_id=1,
        api_hash="hash",
        phone=None,
        session_path=tmp_path / "session",
        database_path=tmp_path / "telegram.db",
        whitelist_path=tmp_path / "allowed.yaml",
        proxy_type="http",
        proxy_host="proxy.example",
        proxy_port=3128,
    )

    assert settings.telethon_proxy() == {
        "proxy_type": "http",
        "addr": "proxy.example",
        "port": 3128,
        "username": None,
        "password": None,
        "rdns": True,
    }


def test_load_settings_rejects_incomplete_proxy(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("TELEGRAM_API_ID", "12345")
    monkeypatch.setenv("TELEGRAM_API_HASH", "hash")
    monkeypatch.setenv("TELEGRAM_PROXY_TYPE", "socks5")
    monkeypatch.setenv("TELEGRAM_PROXY_HOST", "proxy.example")
    monkeypatch.delenv("TELEGRAM_PROXY_PORT", raising=False)
    monkeypatch.delenv("TELEGRAM_PROXY_USERNAME", raising=False)
    monkeypatch.delenv("TELEGRAM_PROXY_PASSWORD", raising=False)

    with pytest.raises(RuntimeError, match="TELEGRAM_PROXY_PORT"):
        load_settings(tmp_path / "missing.env")


def test_load_settings_accepts_authenticated_socks5(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("TELEGRAM_API_ID", "12345")
    monkeypatch.setenv("TELEGRAM_API_HASH", "hash")
    monkeypatch.setenv("TELEGRAM_PROXY_TYPE", "socks5")
    monkeypatch.setenv("TELEGRAM_PROXY_HOST", "proxy.example")
    monkeypatch.setenv("TELEGRAM_PROXY_PORT", "1080")
    monkeypatch.setenv("TELEGRAM_PROXY_USERNAME", "reader")
    monkeypatch.setenv("TELEGRAM_PROXY_PASSWORD", "secret")

    settings = load_settings(tmp_path / "missing.env")

    assert settings.proxy_type == "socks5"
    assert settings.proxy_host == "proxy.example"
    assert settings.proxy_port == 1080
    assert settings.proxy_username == "reader"
    assert settings.proxy_password == "secret"


def test_load_settings_accepts_authenticated_http(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("TELEGRAM_API_ID", "12345")
    monkeypatch.setenv("TELEGRAM_API_HASH", "hash")
    monkeypatch.setenv("TELEGRAM_PROXY_TYPE", "http")
    monkeypatch.setenv("TELEGRAM_PROXY_HOST", "proxy.example")
    monkeypatch.setenv("TELEGRAM_PROXY_PORT", "3128")
    monkeypatch.setenv("TELEGRAM_PROXY_USERNAME", "reader")
    monkeypatch.setenv("TELEGRAM_PROXY_PASSWORD", "secret")

    settings = load_settings(tmp_path / "missing.env")

    assert settings.proxy_type == "http"
    assert settings.proxy_host == "proxy.example"
    assert settings.proxy_port == 3128
    assert settings.proxy_username == "reader"
    assert settings.proxy_password == "secret"
