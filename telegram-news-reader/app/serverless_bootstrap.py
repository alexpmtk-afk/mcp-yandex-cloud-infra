from __future__ import annotations

import json
import os
import urllib.request

import uvicorn

METADATA_TOKEN_URL = "http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token"
LOCKBOX_PAYLOAD_URL = "https://payload.lockbox.api.cloud.yandex.net/lockbox/v1/secrets/{secret_id}/payload"


def _get_json(url: str, headers: dict[str, str]) -> dict:
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def load_runtime_secret() -> None:
    secret_id = os.getenv("LOCKBOX_RUNTIME_SECRET_ID", "").strip()
    if not secret_id:
        raise RuntimeError("Missing LOCKBOX_RUNTIME_SECRET_ID")

    token_doc = _get_json(METADATA_TOKEN_URL, {"Metadata-Flavor": "Google"})
    token = str(token_doc.get("access_token") or "")
    if not token:
        raise RuntimeError("Metadata service did not return IAM token")

    payload = _get_json(
        LOCKBOX_PAYLOAD_URL.format(secret_id=secret_id),
        {"Authorization": f"Bearer {token}"},
    )
    entries = payload.get("entries") or []
    loaded = 0
    for entry in entries:
        key = str(entry.get("key") or "").strip()
        value = entry.get("textValue")
        if key and value is not None:
            os.environ[key] = str(value)
            loaded += 1
    if loaded == 0:
        raise RuntimeError("Lockbox payload contains no text entries")


if __name__ == "__main__":
    load_runtime_secret()
    uvicorn.run("app.service:app", host="0.0.0.0", port=8080, workers=1)
