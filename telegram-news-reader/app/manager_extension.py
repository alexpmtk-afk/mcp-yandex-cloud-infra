from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime, timezone

from fastapi import HTTPException
from telethon.tl.types import Channel, Chat, User

from app.lockbox_runtime import get_runtime_payload, persist_runtime_entry
from app.service import (
    ManageWhitelistPayload,
    _ensure_reader_ready,
    _list_dialogs_resilient,
    app,
    reader,
    whitelist,
)
from app.whitelist import AllowedChat

_SYNC_INTERVAL_SECONDS = 15.0
_SAFE_DIRECT_PAGE_SIZE = 250
_sync_lock = asyncio.Lock()
_last_sync_at = 0.0
_last_peer_map_raw = os.getenv("TELEGRAM_PEER_MAP_JSON", "").strip()


def _allowed_from_peer_map(peers: dict) -> list[AllowedChat]:
    allowed: list[AllowedChat] = []
    for raw_chat_id, peer in peers.items():
        if not isinstance(peer, dict):
            raise ValueError("invalid peer-map entry")
        chat_id = int(raw_chat_id)
        name = str(peer.get("name") or f"telegram:{chat_id}")
        allowed.append(AllowedChat(chat_id=chat_id, name=name, enabled=True))
    if not allowed:
        raise ValueError("empty peer map")
    return allowed


def _apply_peer_map(raw: str) -> None:
    global _last_peer_map_raw
    peers = json.loads(raw)
    if not isinstance(peers, dict) or not peers:
        raise ValueError("TELEGRAM_PEER_MAP_JSON must be a non-empty object")
    whitelist.replace(_allowed_from_peer_map(peers))
    os.environ["TELEGRAM_PEER_MAP_JSON"] = raw
    reader._runtime_entities.clear()
    _last_peer_map_raw = raw


async def _sync_whitelist_from_lockbox(*, force: bool = False) -> None:
    global _last_sync_at
    now = time.monotonic()
    if not force and now - _last_sync_at < _SYNC_INTERVAL_SECONDS:
        return
    async with _sync_lock:
        now = time.monotonic()
        if not force and now - _last_sync_at < _SYNC_INTERVAL_SECONDS:
            return
        try:
            payload = await asyncio.to_thread(get_runtime_payload)
            raw = str(payload.get("TELEGRAM_PEER_MAP_JSON") or "").strip()
            if not raw:
                raise RuntimeError("TELEGRAM_PEER_MAP_JSON missing from Lockbox")
            if raw != _last_peer_map_raw:
                _apply_peer_map(raw)
            _last_sync_at = time.monotonic()
        except Exception as exc:
            print(f"whitelist_sync_error={type(exc).__name__}")
            raise HTTPException(503, "WHITELIST_SYNC_UNAVAILABLE") from exc


async def _build_peer_map(chat_ids: list[int]) -> dict[str, dict]:
    wanted = {int(value) for value in chat_ids}
    if not wanted:
        raise HTTPException(400, "AT_LEAST_ONE_CHAT_REQUIRED")

    await _ensure_reader_ready()
    peers: dict[str, dict] = {}
    try:
        async for dialog in reader.client.iter_dialogs(limit=None):
            chat_id = int(dialog.id)
            if chat_id not in wanted:
                continue
            entity = dialog.entity
            name = str(dialog.name or "")
            if isinstance(entity, Channel):
                access_hash = getattr(entity, "access_hash", None)
                if access_hash is None:
                    raise RuntimeError("channel access_hash missing")
                item = {
                    "kind": "channel",
                    "peer_id": int(entity.id),
                    "access_hash": int(access_hash),
                    "name": name,
                }
            elif isinstance(entity, User):
                access_hash = getattr(entity, "access_hash", None)
                if access_hash is None:
                    raise RuntimeError("user access_hash missing")
                item = {
                    "kind": "user",
                    "peer_id": int(entity.id),
                    "access_hash": int(access_hash),
                    "name": name,
                }
            elif isinstance(entity, Chat):
                item = {
                    "kind": "chat",
                    "peer_id": int(entity.id),
                    "name": name,
                }
            else:
                raise RuntimeError("unsupported Telegram peer type")
            peers[str(chat_id)] = item
            if len(peers) == len(wanted):
                break
    except HTTPException:
        raise
    except Exception as exc:
        print(f"manager_peer_map_error={type(exc).__name__}")
        raise HTTPException(502, "TELEGRAM_DIALOG_RESOLUTION_FAILED") from exc

    missing = wanted - {int(value) for value in peers.keys()}
    if missing:
        raise HTTPException(400, "UNKNOWN_CHAT_ID")
    return peers


def _remove_route(path: str, method: str) -> None:
    keep = []
    for route in app.router.routes:
        methods = getattr(route, "methods", set()) or set()
        if getattr(route, "path", None) == path and method.upper() in methods:
            continue
        keep.append(route)
    app.router.routes[:] = keep


_remove_route("/api/admin/dialogs", "GET")
_remove_route("/api/admin/whitelist", "POST")
_remove_route("/internal/chats/{chat_id}/messages", "GET")


@app.middleware("http")
async def refresh_managed_whitelist(request, call_next):
    path = request.url.path
    if path == "/health" or path.startswith("/internal/") or path.startswith("/api/admin/"):
        await _sync_whitelist_from_lockbox()
    return await call_next(request)


@app.get("/api/admin/dialogs")
async def durable_admin_dialogs():
    await _sync_whitelist_from_lockbox(force=True)
    selected = {item.chat_id for item in whitelist.list_allowed()}
    dialogs = await _list_dialogs_resilient()
    return {
        "dialogs": [
            {"chat_id": d.chat_id, "title": d.title, "type": d.type, "username": d.username}
            for d in dialogs
        ],
        "selected": list(selected),
    }


@app.post("/api/admin/whitelist")
async def durable_admin_whitelist(payload: ManageWhitelistPayload):
    chosen_ids = list(dict.fromkeys(int(value) for value in payload.chat_ids))
    if not chosen_ids:
        raise HTTPException(400, "AT_LEAST_ONE_CHAT_REQUIRED")

    peers = await _build_peer_map(chosen_ids)
    raw = json.dumps(peers, ensure_ascii=False, separators=(",", ":"), sort_keys=True)

    try:
        current = await asyncio.to_thread(get_runtime_payload)
        current_raw = str(current.get("TELEGRAM_PEER_MAP_JSON") or "").strip()
        if current_raw != raw:
            await asyncio.to_thread(
                persist_runtime_entry,
                "TELEGRAM_PEER_MAP_JSON",
                raw,
                description="Telegram Reader allowed chats updated from manager",
            )
        _apply_peer_map(raw)
        global _last_sync_at
        _last_sync_at = time.monotonic()
    except Exception as exc:
        print(f"manager_persist_error={type(exc).__name__}")
        raise HTTPException(503, "WHITELIST_PERSIST_FAILED") from exc

    return {"status": "saved", "allowed_chats": len(peers)}


@app.get("/internal/chats/{chat_id}/messages")
async def durable_internal_messages(
    chat_id: int,
    date_from: datetime,
    date_to: datetime | None = None,
    limit: int = 2000,
    before_id: int | None = None,
):
    """Return a bounded page so long Telegram windows cannot exhaust one Serverless request."""
    whitelist.assert_allowed(chat_id)
    await _ensure_reader_ready()
    high = date_to or datetime.now(timezone.utc)
    requested_limit = min(max(int(limit), 1), 2000)
    page_limit = min(requested_limit, _SAFE_DIRECT_PAGE_SIZE)
    try:
        records = await reader.get_messages_between(
            chat_id,
            date_from,
            high,
            limit=page_limit,
            before_id=before_id,
        )
    except Exception as exc:
        raise HTTPException(502, f"TELEGRAM_DIRECT_READ_FAILED:{type(exc).__name__}")

    messages = []
    for record in records:
        row = record.to_dict()
        row["media_asset"] = None
        messages.append(row)
    next_before_id = min((int(row["message_id"]) for row in messages), default=None)
    return {
        "chat_id": chat_id,
        "date_from": date_from.isoformat(),
        "date_to": high.isoformat(),
        "requested_limit": requested_limit,
        "effective_page_limit": page_limit,
        "message_count": len(messages),
        "page_full": len(messages) >= page_limit,
        "next_before_id": next_before_id,
        "messages": messages,
    }


__all__ = ["app"]