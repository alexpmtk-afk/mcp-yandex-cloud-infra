from __future__ import annotations

from typing import Any


def dialog_type(entity: Any) -> str:
    name = entity.__class__.__name__.lower()
    if "channel" in name:
        return "channel"
    if "chat" in name:
        return "group"
    if "user" in name:
        return "user"
    return name or "unknown"


def media_type(message: Any) -> str | None:
    if getattr(message, "media", None) is None:
        return None
    media = message.media
    name = media.__class__.__name__.lower()
    if "photo" in name:
        return "photo"
    if "document" in name:
        document = getattr(media, "document", None)
        mime = (getattr(document, "mime_type", None) or "").lower()
        attributes = getattr(document, "attributes", None) or []
        if any("animated" in item.__class__.__name__.lower() for item in attributes):
            return "animation"
        if mime == "image/gif":
            return "gif"
        if mime.startswith("image/"):
            return "image"
        if mime.startswith("video/"):
            return "video"
        if mime.startswith("audio/"):
            return "audio"
        return "document"
    if "webpage" in name:
        return "webpage"
    return name.removeprefix("message") or "media"


def public_message_url(username: str | None, message_id: int) -> str | None:
    if not username:
        return None
    return f"https://t.me/{username}/{message_id}"
