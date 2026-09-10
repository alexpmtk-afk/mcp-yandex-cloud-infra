from pathlib import Path

import pytest

from app.ws_relay import WebSocketRelayAdapter


def test_worker_domain_is_extracted_from_wss_url():
    relay = WebSocketRelayAdapter(
        "wss://telegram-reader-relay.example.workers.dev",
        port=18888,
    )
    assert relay.worker_domain == "telegram-reader-relay.example.workers.dev"
    host, port, secret = relay.mtproxy_tuple()
    assert host == "127.0.0.1"
    assert port == 18888
    assert len(secret) == 32


@pytest.mark.asyncio
async def test_relay_starts_local_proxy(monkeypatch, tmp_path: Path):
    calls = []

    class Process:
        returncode = None

        def terminate(self):
            self.returncode = 0

        async def wait(self):
            return self.returncode

        def kill(self):
            self.returncode = -9

    async def fake_exec(*args, **kwargs):
        calls.append((args, kwargs))
        return Process()

    relay = WebSocketRelayAdapter("https://relay.example.workers.dev", port=17777)
    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)

    async def ready():
        return None

    monkeypatch.setattr(relay, "_wait_until_ready", ready)
    await relay.start()

    args = calls[0][0]
    assert args[0] == "/usr/local/bin/tg-ws-proxy"
    assert "127.0.0.1" in args
    assert "relay.example.workers.dev" in args
    assert "--cf-priority" in args
    await relay.stop()
