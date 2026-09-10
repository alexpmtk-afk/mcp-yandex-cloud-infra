from __future__ import annotations

import os

from app.exporter import TelegramNewsExporter
from app.runtime import build_runtime


def main() -> None:
    output_path = os.getenv(
        "TELEGRAM_NEWS_EXPORT_PATH",
        "/state/exports/TELEGRAM_NEWS_LATEST.json",
    )
    _, whitelist, _, storage = build_runtime()
    result = TelegramNewsExporter(storage, whitelist, output_path).export_incremental()
    print(
        f"EXPORT_PASS messages={result['messages']} cursor={result['cursor']} path={result['path']}"
    )


if __name__ == "__main__":
    main()
