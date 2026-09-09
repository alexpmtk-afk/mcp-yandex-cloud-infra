from __future__ import annotations

import asyncio
import os
import secrets
from urllib.parse import urlparse


class WebSocketRelayAdapter:
    """Manage the local MTProto proxy that tunnels through a Cloudflare Worker."""

    def __init__(self, base_url: str, token: str = "", port: int = 18888) -> None:
        self.base_url = base_url.strip()
        self.token = token
        self.port = port
        self.secret = secrets.token_hex(16)
        self._process: asyncio.subprocess.Process | None = None

    @property
    def worker_domain(self) -> str:
        value = self.base_url
        if "://" not in value:
            value = f"https://{value}"
        parsed = urlparse(value)
        if not parsed.hostname:
            raise RuntimeError("Invalid TELEGRAM_WS_RELAY_URL")
        return parsed.hostname

    def mtproxy_tuple(self) -> tuple[str, int, str]:
        return ("127.0.0.1", self.port, self.secret)

    async def start(self) -> None:
        if self._process is not None and self._process.returncode is None:
            return

        binary = os.getenv("TELEGRAM_TG_WS_PROXY_BINARY", "/usr/local/bin/tg-ws-proxy")
        self._process = await asyncio.create_subprocess_exec(
            binary,
            "--host",
            "127.0.0.1",
            "--port",
            str(self.port),
            "--secret",
            self.secret,
            "--cf-worker-domain",
            self.worker_domain,
            "--cf-priority",
            "--quiet",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await self._wait_until_ready()

    async def stop(self) -> None:
        process = self._process
        self._process = None
        if process is None or process.returncode is not None:
            return
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=3)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()

    async def _wait_until_ready(self) -> None:
        process = self._process
        if process is None:
            raise RuntimeError("Telegram relay process did not start")
        for _ in range(50):
            if process.returncode is not None:
                raise RuntimeError("Telegram relay process exited during startup")
            try:
                reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
                writer.close()
                await writer.wait_closed()
                return
            except OSError:
                await asyncio.sleep(0.1)
        await self.stop()
        raise RuntimeError("Telegram relay process did not become ready")
