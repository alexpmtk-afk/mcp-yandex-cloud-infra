from app.config import load_settings


def test_runtime_config_does_not_require_phone(monkeypatch, tmp_path):
    monkeypatch.setenv("TELEGRAM_API_ID", "12345")
    monkeypatch.setenv("TELEGRAM_API_HASH", "dummy")
    monkeypatch.delenv("TELEGRAM_PHONE", raising=False)
    settings = load_settings(tmp_path / "missing.env")
    assert settings.phone is None
