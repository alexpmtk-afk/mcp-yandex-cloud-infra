from __future__ import annotations

import asyncio
from urllib.parse import quote

import websockets


TELEGRAM_DC_ROUTES = {
    "149.154.175.50": "dc1",
    "149.154.167.51": "dc2",
    "149.154.175.100": "dc3",
    "149.154.167.91": "dc4",
    "91.108.56.130": "dc5",
}


class WebSocketRelayAdapter:
    """Loopback HTTP CONNECT adapter backed by an authenticated WSS relay."""

    def __init__(self, base_url: str, token: str, port: int = 18888) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.port = port
        self._server: asyncio.AbstractServer | None = None

    async def start(self) -> None:
        if self._server is not None:
            return
        self._server = await asyncio.start_server(self._handle, "127.0.0.1", self.port)

    async def stop(self) -> None:
        if self._server is None:
            return
        self._server.close()
        await self._server.wait_closed()
        self._server = None

    def proxy_mapping(self) -> dict[str, object]:
        return {
            "proxy_type": "http",
            "addr": "127.0.0.1",
            "port": self.port,
            "username": None,
            "password": None,
            "rdns": True,
        }

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        ws = None
        try:
            head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=5)
            first = head.split(b"\r\n", 1)[0].decode("ascii", errors="replace")
            parts = first.split()
            if len(parts) < 2 or parts[0].upper() != "CONNECT":
                return
            target = parts[1]
            host = target.rsplit(":", 1)[0].strip("[]")
            route = TELEGRAM_DC_ROUTES.get(host)
            if route is None:
                writer.write(b"HTTP/1.1 403 Forbidden\r\n\r\n")
                await writer.drain()
                return

            url = f"{self.base_url}/{route}?t={quote(self.token, safe='')}"
            ws = await asyncio.wait_for(
                websockets.connect(url, open_timeout=20, ping_interval=20), timeout=25
            )
            writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            await writer.drain()

            async def tcp_to_ws() -> None:
                while True:
                    data = await reader.read(65536)
                    if not data:
                        return
                    await ws.send(data)

            async def ws_to_tcp() -> None:
                async for data in ws:
                    if isinstance(data, str):
                        data = data.encode()
                    writer.write(data)
                    await writer.drain()

            await asyncio.gather(tcp_to_ws(), ws_to_tcp())
        except (asyncio.IncompleteReadError, asyncio.TimeoutError, ConnectionError):
            pass
        except Exception:
            pass
        finally:
            if ws is not None:
                try:
                    await ws.close()
                except Exception:
                    pass
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
