import asyncio

from app.runtime import build_runtime


async def main() -> None:
    _, _, reader, _ = build_runtime()
    try:
        await reader.connect(interactive_login=True)
        print("AUTHORIZED")
    finally:
        await reader.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
