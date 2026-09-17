from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ServiceSettings:
    api_token: str
    collect_interval_seconds: int
    bootstrap_limit: int


def load_service_settings() -> ServiceSettings:
    token = os.getenv("READER_API_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Missing READER_API_TOKEN")
    interval = max(15, int(os.getenv("COLLECT_INTERVAL_SECONDS", "60")))
    bootstrap = max(1, int(os.getenv("COLLECT_BOOTSTRAP_LIMIT", "200")))
    return ServiceSettings(token, interval, bootstrap)
