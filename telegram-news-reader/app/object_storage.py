from __future__ import annotations

import hashlib
import hmac
import json
import mimetypes
import os
import time
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


_METADATA_TOKEN_URL = (
    "http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token"
)


class ObjectStorage:
    """Private Yandex Object Storage access via the VM service-account IAM token."""

    def __init__(self):
        self.bucket = os.getenv("TELEGRAM_MEDIA_BUCKET", "").strip()
        self.endpoint = os.getenv(
            "TELEGRAM_MEDIA_S3_ENDPOINT", "https://storage.yandexcloud.net"
        ).strip().rstrip("/")
        self.prefix = os.getenv("TELEGRAM_MEDIA_PREFIX", "telegram-media").strip("/")
        self.url_ttl = max(300, int(os.getenv("TELEGRAM_MEDIA_URL_TTL", "7200")))
        self.public_base = os.getenv("TELEGRAM_PUBLIC_BASE_URL", "").strip().rstrip("/")
        self.link_secret = (
            os.getenv("TELEGRAM_MEDIA_LINK_SECRET", "").strip()
            or os.getenv("READER_API_TOKEN", "").strip()
        )

    @property
    def enabled(self) -> bool:
        return bool(self.bucket)

    def _iam_token(self) -> str:
        request = Request(_METADATA_TOKEN_URL, headers={"Metadata-Flavor": "Google"})
        with urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        token = str(payload.get("access_token") or "")
        if not token:
            raise RuntimeError("Yandex VM service-account IAM token is unavailable")
        return token

    def _object_url(self, key: str) -> str:
        return f"{self.endpoint}/{quote(self.bucket, safe='')}/{quote(key, safe='/')}"

    def upload(
        self,
        path: str | Path,
        *,
        chat_id: int,
        message_id: int,
        variant: str | None = None,
    ) -> tuple[str, str | None] | None:
        if not self.enabled:
            return None
        source = Path(path)
        suffix = source.suffix.lower()
        stem = str(message_id) if not variant else f"{message_id}.{variant.strip('.') }"
        key = f"{self.prefix}/{chat_id}/{stem}{suffix}"
        content_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
        request = Request(
            self._object_url(key),
            data=source.read_bytes(),
            method="PUT",
            headers={
                "Authorization": f"Bearer {self._iam_token()}",
                "Content-Type": content_type,
            },
        )
        with urlopen(request, timeout=30) as response:
            if response.status not in {200, 201}:
                raise RuntimeError(f"Object Storage upload failed: HTTP {response.status}")
        return key, self.signed_proxy_url(key)

    def get_object(self, key: str) -> tuple[bytes, str]:
        if not self.enabled:
            raise RuntimeError("Object Storage is disabled")
        request = Request(
            self._object_url(key),
            headers={"Authorization": f"Bearer {self._iam_token()}"},
        )
        with urlopen(request, timeout=30) as response:
            data = response.read()
            content_type = response.headers.get_content_type() or "application/octet-stream"
        return data, content_type

    def signed_proxy_url(self, key: str | None) -> str | None:
        if not self.enabled or not key or not self.public_base or not self.link_secret:
            return None
        expires = int(time.time()) + self.url_ttl
        signature = self._signature(key, expires)
        query = urlencode({"key": key, "expires": expires, "sig": signature})
        return f"{self.public_base}/media/object?{query}"

    def verify_proxy_link(self, key: str, expires: int, signature: str) -> bool:
        if not self.link_secret or int(expires) < int(time.time()):
            return False
        return hmac.compare_digest(self._signature(key, int(expires)), signature)

    def _signature(self, key: str, expires: int) -> str:
        message = f"{key}\n{int(expires)}".encode("utf-8")
        return hmac.new(self.link_secret.encode("utf-8"), message, hashlib.sha256).hexdigest()

    def presigned_url(self, key: str | None) -> str | None:
        """Compatibility name used by the JSON exporter."""
        return self.signed_proxy_url(key)
