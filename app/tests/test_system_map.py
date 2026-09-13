"""Runtime guardrails for the canonical Marketplaces MCP architecture map."""
from __future__ import annotations

import asyncio

from mcp.server.fastmcp import FastMCP

from core.system_map import ARCHITECTURE_VERSION, SYSTEM_INSTRUCTIONS, SYSTEM_MAP, register_system_map_tool


def test_canonical_map_fixes_yandex_runtime_boundaries():
    assert SYSTEM_MAP["status"] == "CANONICAL"
    assert SYSTEM_MAP["runtime"]["cloud"] == "Yandex Cloud only"
    assert SYSTEM_MAP["storage_policy"]["primary_runtime_storage"] == "Yandex Object Storage"
    assert "runtime service-account IAM token" in SYSTEM_MAP["storage_policy"]["archive_auth"]
    assert SYSTEM_MAP["storage_policy"]["google_cloud"] == "not part of the runtime architecture"
    assert "optional export/mirror only" in SYSTEM_MAP["storage_policy"]["google_drive"]
    assert SYSTEM_MAP["archive_policy"]["wb_weekly_finance_main"]["report_type"] == 1


def test_server_instructions_contain_hard_boundaries():
    assert ARCHITECTURE_VERSION == "2026-09-13.v2"
    assert ARCHITECTURE_VERSION in SYSTEM_INSTRUCTIONS
    assert "Yandex Object Storage" in SYSTEM_INSTRUCTIONS
    assert "temporary IAM token" in SYSTEM_INSTRUCTIONS
    assert "Google Cloud is not part" in SYSTEM_INSTRUCTIONS
    assert "fail closed" in SYSTEM_INSTRUCTIONS


def test_system_map_tool_is_registered():
    mcp = FastMCP("architecture-map-test")
    register_system_map_tool(mcp)
    names = {tool.name for tool in asyncio.run(mcp.list_tools())}
    assert "marketplace_system_map" in names