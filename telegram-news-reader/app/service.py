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
    if request.url.path.startswith("/manage"):
        query_token = request.query_params.get("token", "")
        digest = hashlib.sha256(query_token.encode("utf-8")).hexdigest() if query_token else ""
        if manage_token_sha256 and hmac.compare_digest(digest, manage_token_sha256):
            return await call_next(request)
    expected = f"Bearer {service_settings.api_token}"
    if not hmac.compare_digest(supplied, expected):
        return JSONResponse({"detail": "UNAUTHORIZED"}, status_code=401)
    return await call_next(request)


class ManageWhitelistPayload(BaseModel):
    chat_ids: list[int]


MANAGE_PAGE = """<!doctype html><html lang=ru><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>Telegram Reader — каналы</title><style>body{font:16px system-ui;max-width:900px;margin:30px auto;padding:0 16px}input[type=search]{width:100%;padding:12px;margin:12px 0}button{padding:10px 16px;margin-right:8px}.row{padding:8px 0;border-bottom:1px solid #ddd}.muted{color:#666}.ok{color:green;font-weight:600}</style></head><body><h1>Каналы Telegram Reader</h1><p class=muted>Галочка — канал читается. Снимите галочку, чтобы исключить его. Добавленные позже в Telegram каналы появятся после «Обновить список».</p><input id=q type=search placeholder='Поиск по названию'><div><button onclick='save()'>Сохранить изменения</button><button onclick='load(false)'>Обновить список</button></div><p id=status></p><div id=list>Загрузка…</div><script>const token=new URLSearchParams(location.search).get('token')||'';let items=[];let selected=new Set();async function load(initial=true){if(initial)status.textContent='Загрузка…';let r=await fetch('/manage/dialogs?token='+encodeURIComponent(token));if(!r.ok){status.textContent='Ошибка загрузки: '+r.status;return}items=await r.json();selected=new Set(items.filter(x=>x.selected).map(x=>x.chat_id));render();if(initial)status.textContent='';}function render(){let f=document.getElementById('q').value.toLowerCase();list.innerHTML=items.filter(x=>(x.title||'').toLowerCase().includes(f)).map(x=>`<label class=row style='display:block'><input type=checkbox data-id='${x.chat_id}' ${selected.has(x.chat_id)?'checked':''}> ${esc(x.title)} <span class=muted>(${esc(x.type||'')})</span></label>`).join('');document.querySelectorAll('input[type=checkbox]').forEach(x=>x.onchange=()=>{let id=Number(x.dataset.id);x.checked?selected.add(id):selected.delete(id)});}function esc(s){return String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}async function save(){status.textContent='Сохраняю…';let r=await fetch('/manage/whitelist?token='+encodeURIComponent(token),{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({chat_ids:[...selected]})});let j=await r.json();if(!r.ok){status.textContent='Ошибка: '+(j.detail||r.status);return}await load(false);status.innerHTML=`<span class=ok>Сохранено. Активных каналов: ${j.allowed_chats}</span>`;}q.oninput=render;load();</script></body></html>"""


@app.get("/manage", response_class=HTMLResponse)
async def manage_page():
    return HTMLResponse(MANAGE_PAGE)


@app.get("/manage/dialogs")
async def manage_dialogs():
    selected = {item.chat_id for item in whitelist.list_allowed()}
    dialogs = await reader.list_dialogs()
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
async def manage_whitelist(payload: ManageWhitelistPayload):
    dialogs = {d.chat_id: d for d in await reader.list_dialogs()}
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
