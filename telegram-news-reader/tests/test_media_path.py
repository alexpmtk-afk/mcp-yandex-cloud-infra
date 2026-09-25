from types import SimpleNamespace

from app.media_pipeline import MediaPipeline


def _reader_for(database_path):
    return SimpleNamespace(settings=SimpleNamespace(database_path=database_path))


def test_media_root_defaults_to_database_data_directory(monkeypatch, tmp_path):
    monkeypatch.delenv("TELEGRAM_MEDIA_PATH", raising=False)
    pipeline = MediaPipeline(_reader_for(tmp_path / "telegram.db"))
    assert pipeline.root == tmp_path / "media"


def test_media_root_honors_explicit_environment(monkeypatch, tmp_path):
    target = tmp_path / "custom-media"
    monkeypatch.setenv("TELEGRAM_MEDIA_PATH", str(target))
    pipeline = MediaPipeline(_reader_for(tmp_path / "telegram.db"))
    assert pipeline.root == target
