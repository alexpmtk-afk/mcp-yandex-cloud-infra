from __future__ import annotations

import asyncio
import hmac
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.collector import Collector
from app.errors import AccessDenied, AuthorizationRequired
from app.mcp_server import build_mcp
from app.runtime import build_runtime
from app.service_config import load_service_settings

service_settings = load_service_settings()
settings, whitelist, reader, storage = build_runtime()
collector = Collector(reader, storage)
mcp = build_mcp(whitelist, storage)
mcp_app = mcp.http_app(path="/", stateless_http=True)


async def _collector_loop() -> None:
    while True:
        try:
            await collector.sync_all_allowed(service_settings.bootstrap_limit)
        except Exception as exc:
            print(f"collector_error={type(exc).__name__}")
        await asyncio.sleep(service_settings.collect_interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = None
    async with mcp_app.lifespan(app):
        try:
            await reader.connect(interactive_login=False)
            task = asyncio.create_task(_collector_loop())
        except AuthorizationRequired:
            print("telegram_session=authorization_required")
        except Exception as exc:
            print(f"telegram_connect_error={type(exc).__name__}")
        try:
            yield
        finally:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            try:
                await reader.disconnect()
            except Exception:
                pass


app = FastAPI(title="Telegram News Reader", lifespan=lifespan)


@app.middleware("http")
async def bearer_auth(request: Request, call_next):
    if request.url.path == "/health":
        return await call_next(request)
    supplied = request.headers.get("authorization", "")
    expected = f"Bearer {service_settings.api_token}"
    if not hmac.compare_digest(supplied, expected):
        return JSONResponse({"detail": "UNAUTHORIZED"}, status_code=401)
    return await call_next(request)


@app.exception_handler(AccessDenied)
async def access_denied_handler(request: Request, exc: AccessDenied):
    return JSONResponse({"detail": "ACCESS_DENIED"}, status_code=403)


@app.get("/health")
async def health():
    try:
        authorized = await reader.is_authorized()
        telegram_status = "ok" if authorized else "authorization_required"
    except Exception as exc:
        authorized = False
        telegram_status = f"unavailable:{type(exc).__name__}"
    return {
        "status": "ok",
        "telegram_status": telegram_status,
        "telegram_authorized": authorized,
        "allowed_chats": len(whitelist.list_allowed()),
        "messages": storage.count_messages(),
    }


@app.get("/api/chats")
async def list_chats():
    return [{"chat_id": item.chat_id, "name": item.name} for item in whitelist.list_allowed()]


@app.get("/api/chats/{chat_id}/recent")
async def recent(chat_id: int, limit: int = 20):
    whitelist.assert_allowed(chat_id)
    return storage.get_recent_local(chat_id, min(max(limit, 1), 500))


@app.get("/api/chats/{chat_id}/messages")
async def messages(
    chat_id: int, date_from: datetime | None = None, date_to: datetime | None = None, limit: int = 200
):
    whitelist.assert_allowed(chat_id)
    return storage.get_messages_local(
        chat_id, date_from=date_from, date_to=date_to, limit=min(max(limit, 1), 1000)
    )


@app.get("/api/messages/{chat_id}/{message_id}")
async def message(chat_id: int, message_id: int):
    whitelist.assert_allowed(chat_id)
    record = storage.get_message_local(chat_id, message_id)
    if record is None:
        raise HTTPException(404, "NOT_FOUND")
    return record


@app.get("/api/search")
async def search(
    query: str, chat_ids: str | None = None, date_from: datetime | None = None, date_to: datetime | None = None, limit: int = 100
):
    ids = (
        [int(item) for item in chat_ids.split(",") if item.strip()]
        if chat_ids
        else [item.chat_id for item in whitelist.list_allowed()]
    )
    for chat_id in ids:
        whitelist.assert_allowed(chat_id)
    return storage.search_local(
        query, chat_ids=ids, date_from=date_from, date_to=date_to, limit=min(max(limit, 1), 1000)
    )


app.mount("/mcp", mcp_app)
