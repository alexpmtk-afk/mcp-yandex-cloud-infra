from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_periodic_collector_is_disabled_by_default():
    service = (ROOT / "app" / "service.py").read_text(encoding="utf-8")
    assert 'os.getenv("COLLECTOR_ENABLED", "false")' in service


def test_mcp_reads_are_direct_telegram_reads():
    source = (ROOT / "app" / "mcp_server.py").read_text(encoding="utf-8")
    assert "await reader.get_recent_messages" in source
    assert "await reader.get_messages_between" in source
    assert "await reader.search_messages" in source
    assert "await reader.get_message" in source
    assert "storage.get_recent_local" not in source
    assert "storage.get_messages_local" not in source
    assert "storage.search_local" not in source
    assert "storage.get_message_local" not in source


def test_http_reads_are_direct_telegram_reads():
    source = (ROOT / "app" / "service.py").read_text(encoding="utf-8")
    assert '"read_mode": "on_demand"' in source
    assert "await reader.get_recent_messages" in source
    assert "await reader.get_messages_between" in source
    assert "await reader.search_messages" in source
    assert "await reader.get_message" in source
