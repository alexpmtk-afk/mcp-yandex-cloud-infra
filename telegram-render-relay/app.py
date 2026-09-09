import asyncio
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()
TOKEN = os.environ.get("RELAY_TOKEN", "")
TARGET_HOST = os.environ.get("TARGET_HOST", "149.154.167.51")
TARGET_PORT = int(os.environ.get("TARGET_PORT", "443"))


@app.get("/healthz")
async def healthz():
    return {"ok": True}


@app.websocket("/relay")
async def relay(ws: WebSocket):
    token = ws.query_params.get("token", "")
    if not TOKEN or token != TOKEN:
        await ws.close(code=4401)
        return

    await ws.accept()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(TARGET_HOST, TARGET_PORT), timeout=10
        )
    except Exception:
        await ws.close(code=1011)
        return

    async def ws_to_tcp():
        try:
            while True:
                data = await ws.receive_bytes()
                writer.write(data)
                await writer.drain()
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def tcp_to_ws():
        try:
            while True:
                data = await reader.read(65536)
                if not data:
                    break
                await ws.send_bytes(data)
        except Exception:
            pass
        finally:
            try:
                await ws.close()
            except Exception:
                pass

    await asyncio.gather(ws_to_tcp(), tcp_to_ws())
