from __future__ import annotations

import asyncio
import os

from fastapi import FastAPI
import websockets

app = FastAPI(title="Telegram Relay Serverless Probe")
RELAY_URL = os.getenv("RELAY_URL", "wss://telegram-reader-relay.alexpmtk.workers.dev")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/probe")
async def probe():
    try:
        async with asyncio.timeout(15):
            async with websockets.connect(RELAY_URL, open_timeout=10, close_timeout=3) as ws:
                return {
                    "status": "pass",
                    "relay": RELAY_URL,
                    "websocket_open": True,
                    "subprotocol": ws.subprotocol,
                }
    except Exception as exc:
        return {
            "status": "fail",
            "relay": RELAY_URL,
            "websocket_open": False,
            "error_type": type(exc).__name__,
            "error": str(exc)[:300],
        }
