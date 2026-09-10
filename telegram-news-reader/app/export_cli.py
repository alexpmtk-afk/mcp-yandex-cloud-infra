from __future__ import annotations

import os

from app.exporter import TelegramNewsExporter
from app.runtime import build_runtime


def main() -> None:
    output_path = os.getenv(
        "TELEGRAM_NEWS_EXPORT_PATH",
        "/state/exports/TELEGRAM_NEWS_LATEST.json",
    )
    window_hours = max(1, int(os.getenv("TELEGRAM_NEWS_WINDOW_HOURS", "36")))
    _, whitelist, _, storage = build_runtime()
    result = TelegramNewsExporter(storage, whitelist, output_path).export_latest_window(
        hours=window_hours
    )
    print(f"EXPORT_PASS messages={result['messages']} path={result['path']}")


if __name__ == "__main__":
    main()
