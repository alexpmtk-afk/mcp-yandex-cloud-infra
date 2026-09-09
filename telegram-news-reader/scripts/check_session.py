import asyncio

from app.runtime import build_runtime


async def main() -> None:
    _, _, reader, _ = build_runtime()
    print("AUTHORIZED" if await reader.is_authorized() else "NOT_AUTHORIZED")


if __name__ == "__main__":
    asyncio.run(main())
