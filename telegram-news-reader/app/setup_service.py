from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import urllib.request
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

from app.formatting import dialog_type
from app.ws_relay import WebSocketRelayAdapter

SETUP_TOKEN_SHA256 = os.getenv("SETUP_TOKEN_SHA256", "").strip().lower()
LOCKBOX_SECRET_ID = os.getenv("TELEGRAM_CREDENTIALS_SECRET_ID", "").strip()
SESSION_PATH = Path(os.getenv("TELEGRAM_SESSION_PATH", "/state/telegram_news"))
WHITELIST_PATH = Path(os.getenv("TELEGRAM_WHITELIST_PATH", "/state/allowed_chats.yaml"))
COMPLETE_MARKER = Path(os.getenv("SETUP_COMPLETE_MARKER", "/state/setup.complete"))
WS_RELAY_URL = os.getenv("TELEGRAM_WS_RELAY_URL", "").strip()
WS_RELAY_TOKEN = os.getenv("TELEGRAM_WS_RELAY_TOKEN", "").strip()
WS_RELAY_PORT = int(os.getenv("TELEGRAM_WS_RELAY_LOCAL_PORT", "18888"))


class BeginPayload(BaseModel):
    api_id: int
    api_hash: str
    phone: str


class CodePayload(BaseModel):
    code: str


class PasswordPayload(BaseModel):
    password: str


class WhitelistPayload(BaseModel):
    chat_ids: list[int]


class SetupState:
    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.client: TelegramClient | None = None
        self.api_id: int | None = None
        self.api_hash: str | None = None
        self.phone: str | None = None
        self.phone_code_hash: str | None = None
        self.dialogs: dict[int, dict[str, object]] = {}
        self.relay: WebSocketRelayAdapter | None = None

    async def clear(self) -> None:
        if self.client is not None:
            await self.client.disconnect()
        if self.relay is not None:
            await self.relay.stop()
        self.client = None
        self.relay = None
        self.api_id = None
        self.api_hash = None
        self.phone = None
        self.phone_code_hash = None
        self.dialogs = {}


state = SetupState()
app = FastAPI(title="Telegram Reader One-Time Setup", docs_url=None, redoc_url=None)


def _token_ok(request: Request) -> bool:
    supplied = request.headers.get("x-setup-token") or request.query_params.get("token", "")
    if not supplied or not SETUP_TOKEN_SHA256:
        return False
    digest = hashlib.sha256(supplied.encode("utf-8")).hexdigest()
    return hmac.compare_digest(digest, SETUP_TOKEN_SHA256)


@app.middleware("http")
async def setup_auth(request: Request, call_next):
    if request.url.path == "/healthz":
        return await call_next(request)
    if COMPLETE_MARKER.exists():
        return JSONResponse({"detail": "SETUP_COMPLETE"}, status_code=410)
    if not _token_ok(request):
        return JSONResponse({"detail": "UNAUTHORIZED"}, status_code=401)
    return await call_next(request)


@app.get("/healthz")
async def healthz():
    return {"status": "complete" if COMPLETE_MARKER.exists() else "setup_required"}


@app.get("/", response_class=HTMLResponse)
async def setup_page():
    return HTMLResponse(_PAGE)


@app.post("/begin")
async def begin(payload: BeginPayload):
    async with state.lock:
        await state.clear()
        SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
        relay = None
        proxy = None
        if WS_RELAY_URL and WS_RELAY_TOKEN:
            relay = WebSocketRelayAdapter(WS_RELAY_URL, WS_RELAY_TOKEN, WS_RELAY_PORT)
            await relay.start()
            proxy = relay.proxy_mapping()
        client = TelegramClient(str(SESSION_PATH), payload.api_id, payload.api_hash, proxy=proxy)
        try:
            await client.connect()
        except Exception:
            if relay is not None:
                await relay.stop()
            raise
        state.relay = relay
        state.client = client
        state.api_id = payload.api_id
        state.api_hash = payload.api_hash
        state.phone = payload.phone
        if await client.is_user_authorized():
            await _load_dialogs()
            return {"status": "select_chats"}
        try:
            sent = await client.send_code_request(payload.phone)
        except Exception:
            await state.clear()
            raise HTTPException(400, "TELEGRAM_AUTH_START_FAILED")
        state.phone_code_hash = sent.phone_code_hash
        return {"status": "code_sent"}


@app.post("/code")
async def submit_code(payload: CodePayload):
    async with state.lock:
        if not state.client or not state.phone or not state.phone_code_hash:
            raise HTTPException(409, "SETUP_NOT_STARTED")
        try:
            await state.client.sign_in(
                phone=state.phone,
                code=payload.code.strip(),
                phone_code_hash=state.phone_code_hash,
            )
        except SessionPasswordNeededError:
            return {"status": "password_required"}
        except Exception:
            raise HTTPException(400, "TELEGRAM_CODE_REJECTED")
        await _load_dialogs()
        return {"status": "select_chats"}


@app.post("/password")
async def submit_password(payload: PasswordPayload):
    async with state.lock:
        if not state.client:
            raise HTTPException(409, "SETUP_NOT_STARTED")
        try:
            await state.client.sign_in(password=payload.password)
        except Exception:
            raise HTTPException(400, "TELEGRAM_PASSWORD_REJECTED")
        await _load_dialogs()
        return {"status": "select_chats"}


@app.get("/dialogs")
async def dialogs():
    if not state.client or not await state.client.is_user_authorized():
        raise HTTPException(409, "TELEGRAM_NOT_AUTHORIZED")
    if not state.dialogs:
        await _load_dialogs()
    return sorted(state.dialogs.values(), key=lambda item: str(item["title"]).casefold())


@app.post("/whitelist")
async def save_whitelist(payload: WhitelistPayload):
    async with state.lock:
        if not state.client or not await state.client.is_user_authorized():
            raise HTTPException(409, "TELEGRAM_NOT_AUTHORIZED")
        selected = []
        for chat_id in dict.fromkeys(payload.chat_ids):
            dialog = state.dialogs.get(int(chat_id))
            if dialog is None:
                raise HTTPException(400, "UNKNOWN_CHAT_ID")
            selected.append(
                {"chat_id": int(chat_id), "name": str(dialog["title"]), "enabled": True}
            )
        if not selected:
            raise HTTPException(400, "SELECT_AT_LEAST_ONE_CHAT")
        _write_whitelist(selected)
        await _finish_setup()
        return {"status": "complete", "allowed_chats": len(selected)}


async def _load_dialogs() -> None:
    if not state.client or not await state.client.is_user_authorized():
        raise HTTPException(409, "TELEGRAM_NOT_AUTHORIZED")
    result: dict[int, dict[str, object]] = {}
    async for dialog in state.client.iter_dialogs():
        entity = dialog.entity
        chat_id = int(dialog.id)
        result[chat_id] = {
            "chat_id": chat_id,
            "title": str(dialog.name or chat_id),
            "username": getattr(entity, "username", None),
            "type": dialog_type(entity),
        }
    state.dialogs = result


async def _finish_setup() -> None:
    if state.api_id is None or not state.api_hash:
        raise HTTPException(500, "SETUP_STATE_INVALID")
    await asyncio.to_thread(_store_credentials, state.api_id, state.api_hash)
    COMPLETE_MARKER.write_text("authorized\n", encoding="utf-8")
    COMPLETE_MARKER.chmod(0o600)
    await state.clear()


def _write_whitelist(items: list[dict[str, object]]) -> None:
    WHITELIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = WHITELIST_PATH.with_suffix(".tmp")
    temporary.write_text(
        yaml.safe_dump({"allowed_chats": items}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    temporary.chmod(0o600)
    temporary.replace(WHITELIST_PATH)


def _store_credentials(api_id: int, api_hash: str) -> None:
    if not LOCKBOX_SECRET_ID:
        raise RuntimeError("Missing TELEGRAM_CREDENTIALS_SECRET_ID")
    iam_token = _metadata_iam_token()
    url = (
        "https://lockbox.api.cloud.yandex.net/lockbox/v1/secrets/"
        f"{LOCKBOX_SECRET_ID}:addVersion"
    )
    body = json.dumps(
        {
            "description": "Telegram Reader authorized bootstrap",
            "payloadEntries": [
                {"key": "api_id", "textValue": str(api_id)},
                {"key": "api_hash", "textValue": api_hash},
            ],
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Authorization": f"Bearer {iam_token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        if response.status != 200:
            raise RuntimeError("Lockbox update failed")


def _metadata_iam_token() -> str:
    request = urllib.request.Request(
        "http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token",
        headers={"Metadata-Flavor": "Google"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        payload = json.load(response)
    token = str(payload.get("access_token") or "")
    if not token:
        raise RuntimeError("Metadata IAM token unavailable")
    return token


_PAGE = r"""<!doctype html>
<html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Telegram Reader — настройка</title>
<style>
body{font:16px system-ui;max-width:680px;margin:32px auto;padding:0 16px}input,button{font:inherit;padding:10px;margin:6px 0;width:100%;box-sizing:border-box}button{cursor:pointer}.hidden{display:none}#status{white-space:pre-wrap;margin:14px 0}.chat{display:flex;gap:10px;align-items:center;padding:7px 0;border-bottom:1px solid #ddd}.chat input{width:auto;margin:0}.muted{opacity:.65;font-size:13px}
</style>
<h2>Telegram News Reader</h2><p>Одноразовая настройка. Секреты и коды не попадают в GitHub или ChatGPT.</p>
<div id="credentials"><input id="api_id" inputmode="numeric" placeholder="API ID"><input id="api_hash" type="password" autocomplete="off" placeholder="API Hash"><input id="phone" autocomplete="tel" placeholder="+7..."><button onclick="begin()">Отправить код Telegram</button></div>
<div id="codebox" class="hidden"><input id="code_value" inputmode="numeric" autocomplete="one-time-code" placeholder="Код Telegram"><button onclick="sendCode()">Подтвердить код</button></div>
<div id="passwordbox" class="hidden"><input id="password_value" type="password" autocomplete="current-password" placeholder="Пароль 2FA"><button onclick="sendPassword()">Подтвердить 2FA</button></div>
<div id="chooser" class="hidden"><h3>Выбери каналы и чаты для чтения</h3><div id="dialogs"></div><button onclick="saveChats()">Сохранить и запустить Reader</button></div><div id="status"></div>
<script>
const token=new URLSearchParams(location.search).get('token')||'';const headers={'Content-Type':'application/json','X-Setup-Token':token};
async function req(path,opt={}){opt.headers={...(opt.headers||{}),'X-Setup-Token':token};const r=await fetch('/setup/'+path,opt);const j=await r.json();if(!r.ok)throw new Error(j.detail||'Ошибка');return j}
async function post(path,body){return req(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})}
function status(s){document.getElementById('status').textContent=s}
async function begin(){try{status('Подключаю Telegram...');const r=await post('begin',{api_id:Number(api_id.value),api_hash:api_hash.value,phone:phone.value});if(r.status==='code_sent'){codebox.classList.remove('hidden');status('Код отправлен в Telegram.')}else if(r.status==='select_chats')await showChats()}catch(e){status(e.message)}}
async function sendCode(){try{const r=await post('code',{code:code_value.value});if(r.status==='password_required'){passwordbox.classList.remove('hidden');status('Нужен пароль 2FA.')}else if(r.status==='select_chats')await showChats()}catch(e){status(e.message)}}
async function sendPassword(){try{const r=await post('password',{password:password_value.value});if(r.status==='select_chats')await showChats()}catch(e){status(e.message)}}
async function showChats(){api_hash.value='';password_value.value='';code_value.value='';credentials.classList.add('hidden');codebox.classList.add('hidden');passwordbox.classList.add('hidden');status('Загружаю список...');const items=await req('dialogs');dialogs.innerHTML='';for(const d of items){const row=document.createElement('label');row.className='chat';const cb=document.createElement('input');cb.type='checkbox';cb.value=d.chat_id;const txt=document.createElement('span');txt.textContent=d.title+' ';const meta=document.createElement('span');meta.className='muted';meta.textContent=(d.username?'@'+d.username+' · ':'')+d.type;txt.appendChild(meta);row.append(cb,txt);dialogs.append(row)}chooser.classList.remove('hidden');status('Отметь только источники, которые Reader может читать.')}
async function saveChats(){try{const ids=[...dialogs.querySelectorAll('input:checked')].map(x=>Number(x.value));const r=await post('whitelist',{chat_ids:ids});chooser.classList.add('hidden');status('Готово. Reader запущен. Разрешено источников: '+r.allowed_chats+'. Эту страницу можно закрыть.')}catch(e){status(e.message)}}
</script></html>"""
