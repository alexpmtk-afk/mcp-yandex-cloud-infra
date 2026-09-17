from pathlib import Path

from app.config import load_settings


def test_runtime_config_does_not_require_phone(monkeypatch, tmp_path):
    monkeypatch.setenv("TELEGRAM_API_ID", "12345")
    monkeypatch.setenv("TELEGRAM_API_HASH", "dummy")
    monkeypatch.delenv("TELEGRAM_PHONE", raising=False)
    settings = load_settings(tmp_path / "missing.env")
    assert settings.phone is None


def test_one_time_setup_does_not_persist_phone_to_lockbox():
    source = (
        Path(__file__).resolve().parents[1] / "app" / "setup_service.py"
    ).read_text(encoding="utf-8")
    assert '"key": "api_id"' in source
    assert '"key": "api_hash"' in source
    assert '"key": "phone"' not in source
    assert "SETUP_TOKEN_SHA256" in source
