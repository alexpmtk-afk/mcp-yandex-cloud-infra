from __future__ import annotations

import os
from pathlib import Path

import boto3


class ObjectStorage:
    def __init__(self):
        self.bucket = os.getenv("TELEGRAM_MEDIA_BUCKET", "").strip()
        self.endpoint = os.getenv(
            "TELEGRAM_MEDIA_S3_ENDPOINT", "https://storage.yandexcloud.net"
        ).strip()
        self.prefix = os.getenv("TELEGRAM_MEDIA_PREFIX", "telegram-media").strip("/")
        self.url_ttl = max(300, int(os.getenv("TELEGRAM_MEDIA_URL_TTL", "7200")))
        self._client = None

    @property
    def enabled(self) -> bool:
        return bool(self.bucket)

    def _s3(self):
        if self._client is None:
            self._client = boto3.client(
                "s3",
                endpoint_url=self.endpoint,
                aws_access_key_id=os.getenv("TELEGRAM_MEDIA_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("TELEGRAM_MEDIA_SECRET_ACCESS_KEY"),
                region_name="ru-central1",
            )
        return self._client

    def upload(self, path: str | Path, *, chat_id: int, message_id: int) -> tuple[str, str] | None:
        if not self.enabled:
            return None
        source = Path(path)
        key = f"{self.prefix}/{chat_id}/{message_id}{source.suffix.lower()}"
        self._s3().upload_file(str(source), self.bucket, key)
        url = self._s3().generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=self.url_ttl,
        )
        return key, url

    def presigned_url(self, key: str | None) -> str | None:
        if not self.enabled or not key:
            return None
        return self._s3().generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=self.url_ttl,
        )
