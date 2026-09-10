import asyncio
import json

from app.runtime import build_runtime


async def main() -> None:
    _, _, reader, _ = build_runtime()
    try:
        await reader.connect()
        rows = await reader.list_dialogs()
        print(json.dumps([row.to_dict() for row in rows], ensure_ascii=False, indent=2))
    finally:
        await reader.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
