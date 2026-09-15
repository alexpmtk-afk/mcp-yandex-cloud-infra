"""Live TEST acceptance for the Marketplaces Semantic Core MCP surface."""
from __future__ import annotations

import itertools
import json
import os
import time

import httpx


def _unpack(response: httpx.Response):
    response.raise_for_status()
    for line in response.text.splitlines():
        if line.startswith("data:"):
            return json.loads(line[5:].strip())
    return response.json() if response.text.strip() else None


def _tool_json(result: dict):
    if result.get("isError"):
        raise AssertionError(result)
    text = next((x.get("text") for x in result.get("content", []) if x.get("type") == "text"), None)
    if text is None:
        raise AssertionError(result)
    return json.loads(text)


def main() -> None:
    url = os.environ["MCP_URL"]
    bearer = os.environ["MCP_BEARER"]
    base_headers = {
        "Authorization": f"Bearer {bearer}",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    timeout = httpx.Timeout(connect=10, read=90, write=30, pool=10)
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        init = None
        init_response = None
        for attempt in range(1, 25):
            try:
                response = client.post(
                    url,
                    headers=base_headers,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2025-06-18",
                            "capabilities": {},
                            "clientInfo": {"name": "semantic-bootstrap-e2e", "version": "3"},
                        },
                    },
                )
                if response.status_code == 200:
                    candidate = _unpack(response)
                    if candidate and "result" in candidate:
                        init = candidate
                        init_response = response
                        break
                print(f"initialize attempt {attempt}/24 status={response.status_code}", flush=True)
            except Exception as exc:  # diagnostic retry only
                print(f"initialize attempt {attempt}/24 error={type(exc).__name__}", flush=True)
            time.sleep(5)
        if init is None or init_response is None:
            raise AssertionError("MCP initialize never became healthy")
        print("MCP_INITIALIZE=PASS", flush=True)

        headers = dict(base_headers)
        session_id = init_response.headers.get("mcp-session-id")
        if session_id:
            headers["Mcp-Session-Id"] = session_id
        headers["MCP-Protocol-Version"] = init["result"].get("protocolVersion", "2025-06-18")
        notification = client.post(url, headers=headers, json={"jsonrpc": "2.0", "method": "notifications/initialized"})
        if notification.status_code not in (200, 202):
            raise AssertionError(notification.status_code)

        ids = itertools.count(2)

        def rpc(method: str, params: dict | None = None):
            response = client.post(
                url,
                headers=headers,
                json={"jsonrpc": "2.0", "id": next(ids), "method": method, "params": params or {}},
            )
            data = _unpack(response)
            if not data or "result" not in data:
                raise AssertionError((method, response.status_code, data))
            return data["result"]

        names = {tool.get("name") for tool in rpc("tools/list").get("tools", [])}
        if "marketplace_business_query" not in names or "marketplace_system_map" not in names:
            raise AssertionError(sorted(names))
        print(f"MCP_TOOLS_LIST=PASS count={len(names)}", flush=True)

        system_map = _tool_json(rpc("tools/call", {"name": "marketplace_system_map", "arguments": {}}))
        if "semantic" not in json.dumps(system_map, ensure_ascii=False).lower():
            raise AssertionError(system_map)
        print("SEMANTIC_SYSTEM_MAP=PASS", flush=True)

        fail_closed = _tool_json(
            rpc(
                "tools/call",
                {
                    "name": "marketplace_business_query",
                    "arguments": {
                        "marketplace": "wb",
                        "seller": "wb_novokshenov",
                        "date_from": "2026-09-01",
                        "date_to": "2026-09-14",
                        "question": "Какие остатки сейчас?",
                    },
                },
            )
        )
        details = fail_closed.get("details") or {}
        if not fail_closed.get("error") or not (details.get("semantic_resolution") or details.get("semantic_status")):
            raise AssertionError(fail_closed)
        print("SEMANTIC_FAIL_CLOSED=PASS", flush=True)

        supported = _tool_json(
            rpc(
                "tools/call",
                {
                    "name": "marketplace_business_query",
                    "arguments": {
                        "marketplace": "wb",
                        "seller": "wb_novokshenov",
                        "date_from": "2026-08-01",
                        "date_to": "2026-08-31",
                        "question": "Сколько штрафов было у ИП Новокшенов в августе 2026?",
                    },
                },
            )
        )
        resolution = supported.get("semantic_resolution") or ((supported.get("details") or {}).get("semantic_resolution") or {})
        if resolution.get("capability_id") != "penalties":
            raise AssertionError(supported)
        if supported.get("error"):
            print("SEMANTIC_SUPPORTED_ROUTE=PASS_FAIL_CLOSED_AFTER_RESOLUTION", flush=True)
        else:
            if supported.get("route") != "semantic_archive":
                raise AssertionError(supported)
            print("SEMANTIC_SUPPORTED_ROUTE=PASS_EXECUTED", flush=True)


if __name__ == "__main__":
    main()
