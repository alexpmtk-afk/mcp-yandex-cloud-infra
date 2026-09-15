"""Runtime guardrails for the canonical Marketplaces MCP architecture map."""
from __future__ import annotations

import asyncio

from mcp.server.fastmcp import FastMCP

from core.system_map import ARCHITECTURE_VERSION, SYSTEM_INSTRUCTIONS, SYSTEM_MAP, register_system_map_tool


def test_canonical_map_fixes_storage_boundaries():
    assert ARCHITECTURE_VERSION == "2026-09-15.v17"
    assert SYSTEM_MAP["status"] == "CANONICAL"
    assert SYSTEM_MAP["runtime"]["cloud"] == "Yandex Cloud only"
    storage = SYSTEM_MAP["storage_policy"]
    assert storage["primary_archive_storage"] == "Google Drive"
    assert storage["google_drive_root"] == "MCP архив базы данных"
    assert "Apps Script" in storage["google_drive_auth"]
    assert "Yandex Lockbox" in storage["google_drive_auth"]
    assert "no Google OAuth refresh token" in storage["google_drive_auth"]
    assert "staging filename" in storage["google_drive_large_upload"]
    assert "SHA256" in storage["google_drive_large_upload"]
    assert "promote" in storage["google_drive_large_upload"]
    assert "immutable candidate" in storage["yandex_object_storage"]
    assert "backup" in storage["yandex_object_storage"]
    assert "runtime service-account IAM token" in storage["yandex_archive_auth"]
    assert "no Google Cloud OAuth runtime dependency" in storage["google_cloud"]
    assert "verified Apps Script promotion" in storage["archive_write_order"]


def test_large_file_policy_is_staged_sha256_guarded_and_resumable():
    policy = SYSTEM_MAP["archive_policy"]["large_file_upload"]
    assert policy["transport"] == "Google Drive API resumable upload"
    assert policy["session_broker"] == "Google Apps Script bridge"
    assert policy["yandex_google_oauth_refresh_token"] == "forbidden/not required"
    assert policy["apps_script_large_base64_upload"] == "forbidden"
    assert "one bounded chunk" in policy["worker_model"]
    assert "Drive-confirmed byte offset" in policy["resume_state"]
    assert "256 KiB" in policy["chunk_rule"]
    assert "4 MiB" in policy["chunk_rule"]
    assert "32 MiB" in policy["chunk_rule"]
    assert "non-canonical" in policy["canonical_protection"]
    assert "sha256Checksum" in policy["verification_rule"]
    assert "before canonical promotion" in policy["backup_rule"]
    assert "promote_verified" in policy["promotion_rule"]
    assert "never follow redirects" in policy["redirect_rule"]
    assert "COMMIT" in policy["commit_rule"]


def test_archive_is_multi_dataset_and_finance_is_not_advertising():
    archive = SYSTEM_MAP["archive_policy"]
    assert archive["multi_dataset"] is True
    assert archive["no_single_report_is_complete_database"] is True
    finance = archive["wb_weekly_finance_main"]
    assert "promotion/advertising metrics" in finance["not_authoritative_for"]
    ads = archive["wb_advertising_v1"]
    assert ads["status"] == "CANONICAL_ARCHIVE_IMPLEMENTED"
    assert ads["registry"] == "dataset_coverage_registry.csv"
    assert "ads_campaign_daily" in ads["datasets"]
    assert ads["coverage_rule"].startswith("roster plus fullstats FULL_COVERAGE")
    assert SYSTEM_MAP["data_routing_policy"]["canonical_metric_router_tool"] == "marketplace_metric_route"
    assert SYSTEM_MAP["data_routing_policy"]["canonical_business_query_tool"] == "marketplace_business_query"


def test_semantic_core_includes_advertising_and_keeps_fail_closed_boundaries():
    semantic = SYSTEM_MAP["semantic_core"]
    assert semantic["status"] == "TEST_RUNTIME_WIRED"
    assert semantic["runtime_entry"] == "marketplace_business_query"
    assert "semantic_registry_extensions.yaml" in semantic["registry"]
    assert "core/semantic_advertising.py" in semantic["archive_executor"]
    assert semantic["source_revision"].endswith("833eab826bfaa4691a05a21a5d00f1e8e0ba1b37")
    assert "advertising_performance" in semantic["approved_archive_executors"]
    assert "FULL_COVERAGE" in semantic["execution_gate"]
    assert any("product/nm_id" in item for item in semantic["fail_closed_for"])
    assert any("campaign-scoped" in item for item in semantic["fail_closed_for"])
    assert any("current-day advertising" in item for item in semantic["fail_closed_for"])
    assert any("roster/fullstats FULL_COVERAGE" in item for item in semantic["fail_closed_for"])
    assert "advertising-attribution" in semantic["advertising_guardrail"]
    assert "agencyVat" in semantic["schema_drift_policy"]
    assert SYSTEM_MAP["change_control"]["bypass_semantic_guardrails"] == "FORBIDDEN"
    assert SYSTEM_MAP["change_control"]["bypass_full_coverage_gate"] == "FORBIDDEN"


def test_wb_advertising_live_and_archive_boundaries_are_explicit():
    policy = SYSTEM_MAP["advertising_policy"]
    assert policy["current_scope"].startswith("Wildberries only")
    assert policy["phase"] == "WB Advertising M0 live read-only + Advertising Archive V1 historical read-only"
    assert policy["credential_service"] == "wb_ads"
    assert policy["live_state_source"] == "Wildberries Promotion API"
    assert policy["metric_class"] == "advertising_attribution_operational"
    assert policy["semantic_metric_contract"] == "wb_ads_m0.v1"
    assert "not actual business profit" in policy["profitability_boundary"]
    assert "dataset_coverage_registry.csv" in policy["archive_status"]
    assert "roster plus campaign fullstats FULL_COVERAGE" in policy["historical_routing"]
    assert "cabinet-level" in policy["semantic_v1_scope"]
    assert "product/nm_id" in policy["semantic_v1_scope"]
    assert policy["write_control_status"].startswith("not accepted in M0")
    assert "WRITE/DESTRUCTIVE" in policy["safety_override"]


def test_server_instructions_contain_hard_boundaries():
    assert ARCHITECTURE_VERSION in SYSTEM_INSTRUCTIONS
    for required in (
        "Google Drive", "Apps Script", "resumable-session", "no Google OAuth refresh token",
        "non-canonical staging filename", "size/SHA256", "byte-for-byte Yandex backup",
        "never blindly resends", "never logs the bearer-like session URI", "Yandex Object Storage",
        "temporary IAM token", "Yandex Lockbox", "Google Cloud is not part", "MULTI-DATASET",
        "marketplace_business_query", "Semantic Core", "FULL_COVERAGE", "orderDt/orderUid",
        "dlvPrc", "agencyVat", "marketplace_metric_route", "Advertising Archive V1",
        "wb_ads_m0.v1", "product/nm_id", "actual business profit", "fail closed",
    ):
        assert required in SYSTEM_INSTRUCTIONS


def test_system_map_tool_is_registered():
    mcp = FastMCP("architecture-map-test")
    register_system_map_tool(mcp)
    names = {tool.name for tool in asyncio.run(mcp.list_tools())}
    assert "marketplace_system_map" in names
