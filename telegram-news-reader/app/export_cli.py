from __future__ import annotations

import os

from app.exporter import TelegramNewsExporter
from app.runtime import build_runtime


def main() -> None:
    output_path = os.getenv(
        "TELEGRAM_NEWS_EXPORT_PATH",
        "/state/exports/TELEGRAM_NEWS_LATEST.json",
    )
    # Eight days keeps a full seven-day analysis window even when the scheduled
    # bridge or a query lands near a day boundary.
    window_hours = max(1, int(os.getenv("TELEGRAM_NEWS_WINDOW_HOURS", "192")))
    limit = max(1, int(os.getenv("TELEGRAM_NEWS_EXPORT_LIMIT", "20000")))
    _, whitelist, _, storage = build_runtime()
    result = TelegramNewsExporter(storage, whitelist, output_path).export_latest_window(
        hours=window_hours,
        limit=limit,
    )
    print(f"EXPORT_PASS messages={result['messages']} path={result['path']}")


if __name__ == "__main__":
    main()
