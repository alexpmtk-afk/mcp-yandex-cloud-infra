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
from telethon import TelegramClient, connection
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
        kwargs: dict[str, object] = {}
        if WS_RELAY_URL:
            relay = WebSocketRelayAdapter(WS_RELAY_URL, WS_RELAY_TOKEN, WS_RELAY_PORT)
            try:
                await relay.start()
            except Exception as exc:
                await state.clear()
                raise HTTPException(502, f"TELEGRAM_RELAY_START_FAILED:{type(exc).__name__}")
            kwargs["connection"] = connection.ConnectionTcpMTProxyAbridged
            kwargs["proxy"] = relay.mtproxy_tuple()
        client = TelegramClient(str(SESSION_PATH), payload.api_id, payload.api_hash, **kwargs)
        try:
            await client.connect()
        except Exception as exc:
            if relay is not None:
                await relay.stop()
            raise HTTPException(502, f"TELEGRAM_CONNECT_FAILED:{type(exc).__name__}")
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
            await state.client.sign_in(phone=state.phone, code=payload.code.strip(), phone_code_hash=state.phone_code_hash)
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
            selected.append({"chat_id": int(chat_id), "name": str(dialog["title"]), "enabled": True})
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
    temporary.write_text(yaml.safe_dump({"allowed_chats": items}, allow_unicode=True, sort_keys=False), encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(WHITELIST_PATH)


def _store_credentials(api_id: int, api_hash: str) -> None:
    if not LOCKBOX_SECRET_ID:
        raise RuntimeError("Missing TELEGRAM_CREDENTIALS_SECRET_ID")
    iam_token = _metadata_iam_token()
    url = "https://lockbox.api.cloud.yandex.net/lockbox/v1/secrets/" f"{LOCKBOX_SECRET_ID}:addVersion"
    body = json.dumps({"description": "Telegram Reader authorized bootstrap", "payloadEntries": [{"key": "api_id", "textValue": str(api_id)}, {"key": "api_hash", "textValue": api_hash}]}).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST", headers={"Authorization": f"Bearer {iam_token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        if response.status >= 300:
            raise RuntimeError("Unable to store Telegram credentials")


def _metadata_iam_token() -> str:
    request = urllib.request.Request("http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token", headers={"Metadata-Flavor": "Google"})
    with urllib.request.urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    token = str(payload.get("access_token") or "").strip()
    if not token:
        raise RuntimeError("Unable to obtain VM IAM token")
    return token


_PAGE = '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Telegram Reader</title><style>body{font-family:Arial;max-width:700px;margin:30px auto;padding:0 15px}input,button{font-size:16px;padding:10px;margin:5px 0;width:100%;box-sizing:border-box}.hide{display:none}.chat{display:block;padding:6px}.chat input{width:auto}</style><h1>Настройка Telegram Reader</h1><p>Данные Telegram API идут только на ваш сервер по HTTPS.</p><div id="s">Готов к настройке.</div><div id="a"><input id="i" placeholder="API ID"><input id="h" placeholder="API Hash"><input id="p" placeholder="Телефон +7..."><button onclick="b()">Продолжить</button></div><div id="c" class="hide"><input id="cv" placeholder="Код из Telegram"><button onclick="cc()">Подтвердить код</button></div><div id="w" class="hide"><input id="pw" type="password" placeholder="Пароль 2FA"><button onclick="pp()">Подтвердить пароль</button></div><div id="d" class="hide"><h2>Выберите каналы и чаты</h2><div id="l"></div><button onclick="sv()">Сохранить</button></div><script>const t=new URLSearchParams(location.search).get(\'token\')||\'\',S=x=>s.textContent=x,sh=x=>document.getElementById(x).classList.remove(\'hide\');async function q(x,o){let r=await fetch(x+\'?token=\'+encodeURIComponent(t),o||{}),j=await r.json();if(!r.ok)throw Error(j.detail||\'Ошибка\');return j}async function post(x,o){return q(x,{method:\'POST\',headers:{\'content-type\':\'application/json\'},body:JSON.stringify(o)})}async function b(){try{S(\'Подключаюсь...\');let j=await post(\'begin\',{api_id:+i.value,api_hash:h.value.trim(),phone:p.value.trim()});h.value=\'\';if(j.status===\'select_chats\')return ld();sh(\'c\');S(\'Введите код из Telegram.\')}catch(e){S(\'Ошибка: \'+e.message)}}async function cc(){try{let j=await post(\'code\',{code:cv.value.trim()});if(j.status===\'password_required\'){sh(\'w\');S(\'Введите пароль 2FA.\')}else await ld()}catch(e){S(\'Ошибка: \'+e.message)}}async function pp(){try{await post(\'password\',{password:pw.value});pw.value=\'\';await ld()}catch(e){S(\'Ошибка: \'+e.message)}}async function ld(){try{S(\'Загружаю список чатов...\');let a=await q(\'dialogs\');l.innerHTML=\'\';for(const x of a){let z=document.createElement(\'label\');z.className=\'chat\';z.innerHTML=\'<input type="checkbox" value="\'+x.chat_id+\'">\'+e(x.title)+(x.username?\' (@\'+e(x.username)+\')\':\'\');l.appendChild(z)}sh(\'d\');S(\'Выберите нужные каналы и чаты.\')}catch(e1){S(\'Ошибка: \'+e1.message)}}async function sv(){try{let ids=[...document.querySelectorAll(\'#l input:checked\')].map(x=>+x.value),j=await post(\'whitelist\',{chat_ids:ids});S(\'Готово. Выбрано чатов: \'+j.allowed_chats+\'. Сервис запускается автоматически.\')}catch(e1){S(\'Ошибка: \'+e1.message)}}function e(x){return String(x).replace(/[&<>"\']/g,c=>({\'&\':\'&amp;\',\'<\':\'&lt;\',\'>\':\'&gt;\',\'"\':\'&quot;\',"\'":\'&#39;\'}[c]))}if(!t)S(\'Откройте ссылку настройки, которую дал ChatGPT.\');</script>'
