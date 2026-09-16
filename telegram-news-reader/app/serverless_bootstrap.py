from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

import uvicorn
import yaml

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


def materialize_whitelist_from_peer_map() -> None:
    """Use the donor-derived peer map as the canonical serverless whitelist.

    TELEGRAM_PEER_MAP_JSON was created strictly from the old production
    whitelist, so its keys are exactly the allowed chat ids.  This avoids
    keeping a second, drifting whitelist copy inside the immutable image.
    """

    raw = os.getenv("TELEGRAM_PEER_MAP_JSON", "").strip()
    if not raw:
        return
    try:
        peers = json.loads(raw)
    except ValueError as exc:
        raise RuntimeError("Invalid TELEGRAM_PEER_MAP_JSON") from exc
    if not isinstance(peers, dict) or not peers:
        raise RuntimeError("TELEGRAM_PEER_MAP_JSON must be a non-empty object")

    allowed = []
    for raw_chat_id, peer in peers.items():
        if not isinstance(peer, dict):
            raise RuntimeError("Invalid peer-map entry")
        chat_id = int(raw_chat_id)
        name = str(peer.get("name") or f"telegram:{chat_id}")
        allowed.append({"chat_id": chat_id, "name": name, "enabled": True})

    target = Path("/tmp/allowed_chats.yaml")
    target.write_text(
        yaml.safe_dump({"allowed_chats": allowed}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    os.environ["TELEGRAM_WHITELIST_PATH"] = str(target)


if __name__ == "__main__":
    load_runtime_secret()
    materialize_whitelist_from_peer_map()
    uvicorn.run("app.service:app", host="0.0.0.0", port=8080, workers=1)
