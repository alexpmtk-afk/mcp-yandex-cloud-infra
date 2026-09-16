from __future__ import annotations

from fastapi import FastAPI, HTTPException, Response

from app.object_storage import ObjectStorage

app = FastAPI(title="Telegram Reader Media Proxy")
objects = ObjectStorage()


@app.get("/health")
async def health():
    return {"status": "ok", "media_storage": "enabled" if objects.enabled else "disabled"}


@app.get("/media/object")
async def media_object(key: str, expires: int, sig: str):
    if not objects.verify_proxy_link(key, expires, sig):
        raise HTTPException(403, "MEDIA_LINK_INVALID_OR_EXPIRED")
    try:
        data, content_type = objects.get_object(key)
    except Exception as exc:
        print(f"media_fetch_error={type(exc).__name__}")
        raise HTTPException(502, "MEDIA_UNAVAILABLE")
    return Response(content=data, media_type=content_type, headers={"Cache-Control": "private, max-age=300"})
