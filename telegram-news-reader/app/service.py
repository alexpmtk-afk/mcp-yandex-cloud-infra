from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from app.admin_page import ADMIN_PAGE
from app.collector import Collector
from app.errors import AccessDenied, AuthorizationRequired
from app.mcp_server import build_mcp
from app.runtime import build_runtime
from app.service_config import load_service_settings
from app.whitelist import AllowedChat

service_settings = load_service_settings()
manage_token_sha256 = os.getenv("MANAGE_TOKEN_SHA256", "").strip().lower()
settings, whitelist, reader, storage = build_runtime()
collector = Collector(reader, storage)
mcp = build_mcp(whitelist, storage)
mcp_app = mcp.http_app(path="/", stateless_http=True)

DIALOGS_TIMEOUT_SECONDS = 25
CONNECT_TIMEOUT_SECONDS = 25
RECONNECT_DELAY_SECONDS = 30
_telegram_connect_lock = asyncio.Lock()


async def _collector_loop() -> None:
    while True:
        try:
            await collector.sync_all_allowed(service_settings.bootstrap_limit)
        except Exception as exc:
            print(f"collector_error={type(exc).__name__}")
        await asyncio.sleep(service_settings.collect_interval_seconds)


async def _connect_reader_once() -> bool:
    async with _telegram_connect_lock:
        if reader.is_connected():
            return True
        try:
            await asyncio.wait_for(
                reader.connect(interactive_login=False), timeout=CONNECT_TIMEOUT_SECONDS
            )
            print("telegram_connect=ok")
            return True
        except AuthorizationRequired:
            print("telegram_session=authorization_required")
            return False
        except asyncio.TimeoutError:
            print("telegram_connect_error=TimeoutError")
            try:
                await asyncio.wait_for(reader.disconnect(), timeout=5)
            except Exception:
                pass
            return False
        except Exception as exc:
            print(f"telegram_connect_error={type(exc).__name__}")
            try:
                await asyncio.wait_for(reader.disconnect(), timeout=5)
            except Exception:
                pass
            return False


async def _telegram_runtime_loop() -> None:
    """Keep Telegram connectivity alive without blocking HTTP application startup."""
    collector_task: asyncio.Task | None = None
    try:
        while True:
            if not reader.is_connected():
                connected = await _connect_reader_once()
                if connected and collector_task is None:
                    collector_task = asyncio.create_task(_collector_loop())
            await asyncio.sleep(RECONNECT_DELAY_SECONDS)
    finally:
        if collector_task:
            collector_task.cancel()
            try:
                await collector_task
            except asyncio.CancelledError:
                pass


async def _list_dialogs_resilient():
    """Fetch dialogs with a hard timeout and one clean reconnect attempt."""
    if not reader.is_connected():
        connected = await _connect_reader_once()
        if not connected:
            raise HTTPException(503, "TELEGRAM_UNAVAILABLE")

    try:
        return await asyncio.wait_for(reader.list_dialogs(), timeout=DIALOGS_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        print("telegram_dialogs_timeout=first_attempt")
    except Exception as exc:
        print(f"telegram_dialogs_error=first_attempt:{type(exc).__name__}")

    async with _telegram_connect_lock:
        try:
            await asyncio.wait_for(reader.disconnect(), timeout=5)
        except Exception:
            pass

        try:
            await asyncio.wait_for(
                reader.connect(interactive_login=False), timeout=CONNECT_TIMEOUT_SECONDS
            )
        except AuthorizationRequired:
            raise HTTPException(503, "TELEGRAM_AUTHORIZATION_REQUIRED")
        except asyncio.TimeoutError:
            print("telegram_dialogs_timeout=reconnect_attempt")
            raise HTTPException(504, "TELEGRAM_DIALOGS_TIMEOUT")
        except Exception as exc:
            print(f"telegram_dialogs_error=reconnect_attempt:{type(exc).__name__}")
            raise HTTPException(503, f"TELEGRAM_UNAVAILABLE:{type(exc).__name__}")

    try:
        return await asyncio.wait_for(reader.list_dialogs(), timeout=DIALOGS_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        raise HTTPException(504, "TELEGRAM_DIALOGS_TIMEOUT")
    except Exception as exc:
        raise HTTPException(503, f"TELEGRAM_UNAVAILABLE:{type(exc).__name__}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    runtime_task = None
    async with mcp_app.lifespan(app):
        runtime_task = asyncio.create_task(_telegram_runtime_loop())
        try:
            yield
        finally:
            if runtime_task:
                runtime_task.cancel()
                try:
                    await runtime_task
                except asyncio.CancelledError:
                    pass
            try:
                await asyncio.wait_for(reader.disconnect(), timeout=5)
            except Exception:
                pass


app = FastAPI(title="Telegram News Reader", lifespan=lifespan)


def _admin_token_ok(request: Request) -> bool:
    supplied = request.headers.get("x-admin-token", "") or request.query_params.get("token", "")
    if not supplied or not manage_token_sha256:
        return False
    digest = hashlib.sha256(supplied.encode("utf-8")).hexdigest()
    return hmac.compare_digest(digest, manage_token_sha256)


@app.middleware("http")
async def bearer_auth(request: Request, call_next):
    if request.url.path == "/health":
        return await call_next(request)
    if request.url.path == "/manage" or request.url.path.startswith("/api/admin/"):
        if _admin_token_ok(request):
            return await call_next(request)
        if request.url.path == "/manage":
            # Allow the login shell to load without exposing any Telegram data.
            return await call_next(request)
        return JSONResponse({"detail": "UNAUTHORIZED"}, status_code=401)
    supplied = request.headers.get("authorization", "")
    expected = f"Bearer {service_settings.api_token}"
    if not hmac.compare_digest(supplied, expected):
        return JSONResponse({"detail": "UNAUTHORIZED"}, status_code=401)
    return await call_next(request)


class ManageWhitelistPayload(BaseModel):
    chat_ids: list[int]


@app.get("/manage", response_class=HTMLResponse)
async def manage_page():
    return HTMLResponse(ADMIN_PAGE)


@app.get("/api/admin/dialogs")
async def admin_dialogs():
    selected = {item.chat_id for item in whitelist.list_allowed()}
    dialogs = await _list_dialogs_resilient()
    return {
        "dialogs": [
            {
                "chat_id": d.chat_id,
                "title": d.title,
                "type": d.type,
                "username": d.username,
            }
            for d in dialogs
        ],
        "selected": list(selected),
    }


@app.post("/api/admin/whitelist")
async def admin_whitelist(payload: ManageWhitelistPayload):
    dialogs = {d.chat_id: d for d in await _list_dialogs_resilient()}
    chosen: list[AllowedChat] = []
    for chat_id in dict.fromkeys(payload.chat_ids):
        dialog = dialogs.get(int(chat_id))
        if dialog is None:
            raise HTTPException(400, "UNKNOWN_CHAT_ID")
        chosen.append(AllowedChat(chat_id=dialog.chat_id, name=dialog.title, enabled=True))
    whitelist.replace(chosen)
    return {"status": "saved", "allowed_chats": len(chosen)}


# Backward-compatible endpoints for old bookmarked manager pages.
@app.get("/manage/dialogs")
async def manage_dialogs_legacy(request: Request):
    if not _admin_token_ok(request):
        raise HTTPException(401, "UNAUTHORIZED")
    selected = {item.chat_id for item in whitelist.list_allowed()}
    dialogs = await _list_dialogs_resilient()
    return [
        {
            "chat_id": d.chat_id,
            "title": d.title,
            "type": d.type,
            "username": d.username,
            "selected": d.chat_id in selected,
        }
        for d in dialogs
    ]


@app.post("/manage/whitelist")
async def manage_whitelist_legacy(payload: ManageWhitelistPayload, request: Request):
    if not _admin_token_ok(request):
        raise HTTPException(401, "UNAUTHORIZED")
    dialogs = {d.chat_id: d for d in await _list_dialogs_resilient()}
    chosen: list[AllowedChat] = []
    for chat_id in dict.fromkeys(payload.chat_ids):
        dialog = dialogs.get(int(chat_id))
        if dialog is None:
            raise HTTPException(400, "UNKNOWN_CHAT_ID")
        chosen.append(AllowedChat(chat_id=dialog.chat_id, name=dialog.title, enabled=True))
    whitelist.replace(chosen)
    return {"status": "saved", "allowed_chats": len(chosen)}


@app.exception_handler(AccessDenied)
async def access_denied_handler(request: Request, exc: AccessDenied):
    return JSONResponse({"detail": "ACCESS_DENIED"}, status_code=403)


@app.get("/health")
async def health():
    connected = reader.is_connected()
    if not connected:
        authorized = False
        telegram_status = "unavailable:disconnected"
    else:
        try:
            authorized = await asyncio.wait_for(reader.is_authorized(), timeout=3)
            telegram_status = "ok" if authorized else "authorization_required"
        except asyncio.TimeoutError:
            authorized = False
            telegram_status = "unavailable:timeout"
        except Exception as exc:
            authorized = False
            telegram_status = f"unavailable:{type(exc).__name__}"
    return {
        "status": "ok",
        "telegram_status": telegram_status,
        "telegram_connected": connected,
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
    query: str,
    chat_ids: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 100,
):
    ids = (
        [int(item) for item in chat_ids.split(",") if item.strip()]
        if chat_ids
        else [item.chat_id for item in whitelist.list_allowed()]
    )
    for chat_id in ids:
        whitelist.assert_allowed(chat_id)
    return storage.search_local(
        query,
        chat_ids=ids,
        date_from=date_from,
        date_to=date_to,
        limit=min(max(limit, 1), 1000),
    )


app.mount("/mcp", mcp_app)
