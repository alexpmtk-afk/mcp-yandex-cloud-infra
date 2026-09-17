from __future__ import annotations

import json
import os
import urllib.request

METADATA_TOKEN_URL = "http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token"
PAYLOAD_URL = "https://payload.lockbox.api.cloud.yandex.net/lockbox/v1/secrets/{secret_id}/payload"
ADD_VERSION_URL = "https://lockbox.api.cloud.yandex.net/lockbox/v1/secrets/{secret_id}:addVersion"


def _iam_token() -> str:
    req = urllib.request.Request(METADATA_TOKEN_URL, headers={"Metadata-Flavor": "Google"})
    with urllib.request.urlopen(req, timeout=10) as response:
        data = json.loads(response.read().decode("utf-8"))
    token = str(data.get("access_token") or "")
    if not token:
        raise RuntimeError("Metadata service did not return IAM token")
    return token


def _secret_id() -> str:
    value = os.getenv("LOCKBOX_RUNTIME_SECRET_ID", "").strip()
    if not value:
        raise RuntimeError("Missing LOCKBOX_RUNTIME_SECRET_ID")
    return value


def get_runtime_payload() -> dict[str, str]:
    token = _iam_token()
    req = urllib.request.Request(
        PAYLOAD_URL.format(secret_id=_secret_id()),
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
    result: dict[str, str] = {}
    for entry in payload.get("entries") or []:
        key = str(entry.get("key") or "").strip()
        value = entry.get("textValue")
        if key and value is not None:
            result[key] = str(value)
    return result


def persist_runtime_entry(key: str, value: str, *, description: str) -> None:
    token = _iam_token()
    body = json.dumps(
        {
            "description": description,
            "payloadEntries": [{"key": key, "textValue": value}],
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        ADD_VERSION_URL.format(secret_id=_secret_id()),
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        if response.status not in {200, 201}:
            raise RuntimeError(f"Lockbox addVersion failed: HTTP {response.status}")
        response.read()
