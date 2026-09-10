from __future__ import annotations

import asyncio

from app.runtime import build_runtime


async def main() -> None:
    settings, _whitelist, reader, _storage = build_runtime()
    try:
        await reader.client.connect()
        authorized = bool(await reader.client.is_user_authorized())
        transport = settings.proxy_type or "direct"
        print(f"TRANSPORT=PASS MODE={transport} AUTHORIZED={str(authorized).upper()}")
    finally:
        await reader.client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
