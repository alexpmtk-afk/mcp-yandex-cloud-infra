"""Runtime guardrails for the canonical Marketplaces MCP architecture map."""
from __future__ import annotations

import asyncio

from mcp.server.fastmcp import FastMCP

from core.system_map import ARCHITECTURE_VERSION, SYSTEM_INSTRUCTIONS, SYSTEM_MAP, register_system_map_tool


def test_canonical_map_fixes_storage_boundaries():
    assert SYSTEM_MAP["status"] == "CANONICAL"
    assert SYSTEM_MAP["runtime"]["cloud"] == "Yandex Cloud only"
    storage = SYSTEM_MAP["storage_policy"]
    assert storage["primary_archive_storage"] == "Google Drive"
    assert storage["google_drive_root"] == "MCP архив базы данных"
    assert "Apps Script" in storage["google_drive_auth"]
    assert "Yandex Lockbox" in storage["google_drive_auth"]
    assert "resumable" in storage["google_drive_large_upload"]
    assert "job state" in storage["yandex_object_storage"]
    assert "backup" in storage["yandex_object_storage"]
    assert "runtime service-account IAM token" in storage["yandex_archive_auth"]
    assert "not part of the runtime architecture" in storage["google_cloud"]
    assert SYSTEM_MAP["archive_policy"]["canonical_source_of_truth"] == "Google Drive annual dataset CSV files plus reports registry"
    large = SYSTEM_MAP["archive_policy"]["large_file_upload"]
    assert large["transport"] == "Google Drive API resumable upload"
    assert large["apps_script_large_upload"] == "forbidden"
    assert "256 KiB" in large["chunk_rule"]
    assert "COMMIT" in large["commit_rule"]
    assert SYSTEM_MAP["archive_policy"]["wb_weekly_finance_main"]["report_type"] == 1
    assert SYSTEM_MAP["archive_policy"]["wb_weekly_finance_main"]["row_deduplication"] == "(reportId, rrdId)"


def test_archive_is_explicitly_multi_dataset_and_finance_is_partial():
    assert SYSTEM_MAP["archive_policy"]["multi_dataset"] is True
    assert SYSTEM_MAP["archive_policy"]["no_single_report_is_complete_database"] is True
    assert SYSTEM_MAP["archive_policy"]["initial_history_backfill"] == 2026
    assert SYSTEM_MAP["archive_policy"]["planned_history_floor"] == 2024
    excluded = SYSTEM_MAP["archive_policy"]["wb_weekly_finance_main"]["not_authoritative_for"]
    assert "customer orders/order events" in excluded
    assert "stock-on-date history" in excluded
    assert "promotion/advertising metrics" in excluded
    assert SYSTEM_MAP["data_routing_policy"]["canonical_metric_router_tool"] == "marketplace_metric_route"
    assert "orders are customer order events" in SYSTEM_MAP["data_routing_policy"]["orders_vs_realization"]


def test_wb_advertising_m0_boundaries_are_explicit():
    policy = SYSTEM_MAP["advertising_policy"]
    assert policy["current_scope"].startswith("Wildberries only")
    assert policy["phase"] == "WB Advertising M0 read-only"
    assert policy["credential_service"] == "wb_ads"
    assert policy["active_campaign_status"] == 9
    assert "wb_ads_list_active_campaigns" in policy["m0_tools"]
    assert "wb_ads_get_campaign_stats" in policy["m0_tools"]
    assert "wb_ads_audit_active" in policy["m0_tools"]
    assert policy["metric_class"] == "advertising_attribution_operational"
    assert "not actual business profit" in policy["profitability_boundary"]
    assert policy["archive_domain"] == "База данных/WB/<cabinet>/<year>/advertising"
    assert "not yet implemented" in policy["archive_status"]
    assert policy["write_control_status"].startswith("not accepted in M0")
    assert "WRITE/DESTRUCTIVE" in policy["safety_override"]


def test_server_instructions_contain_hard_boundaries():
    assert ARCHITECTURE_VERSION == "2026-09-14.v6"
    assert ARCHITECTURE_VERSION in SYSTEM_INSTRUCTIONS
    assert "Google Drive" in SYSTEM_INSTRUCTIONS
    assert "Apps Script" in SYSTEM_INSTRUCTIONS
    assert "Yandex Object Storage" in SYSTEM_INSTRUCTIONS
    assert "temporary IAM token" in SYSTEM_INSTRUCTIONS
    assert "Yandex Lockbox" in SYSTEM_INSTRUCTIONS
    assert "Google Cloud is not part" in SYSTEM_INSTRUCTIONS
    assert "resumable upload" in SYSTEM_INSTRUCTIONS
    assert "MULTI-DATASET" in SYSTEM_INSTRUCTIONS
    assert "NOT authoritative for customer orders" in SYSTEM_INSTRUCTIONS
    assert "marketplace_metric_route" in SYSTEM_INSTRUCTIONS
    assert "WB Advertising M0" in SYSTEM_INSTRUCTIONS
    assert "wb_ads" in SYSTEM_INSTRUCTIONS
    assert "actual business profit" in SYSTEM_INSTRUCTIONS
    assert "source of truth" in SYSTEM_INSTRUCTIONS
    assert "fail closed" in SYSTEM_INSTRUCTIONS


def test_system_map_tool_is_registered():
    mcp = FastMCP("architecture-map-test")
    register_system_map_tool(mcp)
    names = {tool.name for tool in asyncio.run(mcp.list_tools())}
    assert "marketplace_system_map" in names
