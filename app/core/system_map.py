"""Canonical architecture map exposed by the MCP server itself."""
from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

ARCHITECTURE_VERSION = "2026-09-14.v16"

SYSTEM_MAP: dict[str, Any] = {
    "architecture_version": ARCHITECTURE_VERSION,
    "status": "CANONICAL",
    "scope": "Marketplaces MCP runtime and multi-dataset marketplace archive",
    "runtime": {
        "cloud": "Yandex Cloud only",
        "entry": "ChatGPT/Codex -> marketplaces-yandex -> Yandex API Gateway -> Yandex Serverless Container",
        "secrets": "Yandex Lockbox",
        "shared_rate_limit_and_locks": "Yandex Managed Redis/Valkey",
        "marketplace_sources": ["Wildberries official API", "Ozon official API", "Ozon Performance official API"],
    },
    "storage_policy": {
        "primary_archive_storage": "Google Drive",
        "canonical_archive_data": "annual marketplace dataset CSV files plus reports registry",
        "google_drive_root": "MCP архив базы данных",
        "google_drive_auth": "owner-operated Google Apps Script web-app bridge; shared bridge secret kept in Yandex Lockbox; no Google OAuth refresh token is stored in Yandex",
        "google_drive_bridge": "Apps Script executes as the Drive owner, handles small archive operations, brokers official Drive resumable-session creation, and performs narrow SHA256-verified promotion inside the fixed archive root",
        "google_drive_large_upload": "Apps Script starts the official Drive resumable session using its effective-user token; Yandex uploads bounded chunks directly to an opaque session URI into a deterministic staging filename, verifies exact Drive size/SHA256, writes the Yandex backup, then asks Apps Script to promote the verified staging file to canonical",
        "yandex_object_storage": "durable archive job state, staging, resumable-upload state, immutable candidate, and byte-for-byte backup of canonical files",
        "yandex_archive_auth": "Serverless Container runtime service-account IAM token from metadata; no static archive key",
        "archive_write_order": "PREPARE immutable candidate in Yandex Object Storage -> Drive staging resumable upload -> exact Drive size/SHA256 verification -> byte-for-byte Yandex backup -> verified Apps Script promotion to canonical -> COMMIT registry/job progress",
        "read_through_migration": "if a canonical file is absent on Drive but exists in Yandex Object Storage, copy it to Drive before use",
        "google_cloud": "not part of the runtime architecture; no Google Cloud OAuth runtime dependency is required",
        "client_local_files": "never authoritative for shared server state",
    },
    "archive_policy": {
        "shared_server_state": True,
        "multi_dataset": True,
        "no_single_report_is_complete_database": True,
        "default_update_scope": "all configured marketplace cabinets for the selected dataset",
        "idempotent": True,
        "registry_required": True,
        "canonical_source_of_truth": "Google Drive annual dataset CSV files plus reports registry",
        "initial_history_backfill": 2026,
        "planned_history_floor": 2024,
        "annual_partitioning": "one logical annual dataset per marketplace/cabinet/dataset/year",
        "annual_csv_pattern": "<cabinet>__<dataset>__<year>.csv",
        "large_file_upload": {
            "transport": "Google Drive API resumable upload",
            "session_broker": "Google Apps Script bridge",
            "yandex_google_oauth_refresh_token": "forbidden/not required",
            "apps_script_large_base64_upload": "forbidden",
            "worker_model": "one bounded chunk per worker step",
            "resume_state": "resumable session URI plus Drive-confirmed byte offset persisted in durable Yandex job state; session URI is bearer-like and must never be logged",
            "chunk_rule": "non-final chunks are multiples of 256 KiB; default 4 MiB; hard maximum 32 MiB",
            "canonical_protection": "large upload always targets a non-canonical deterministic staging filename; existing canonical remains untouched until exact verification and backup pass",
            "verification_rule": "Drive staged file must match expected byte size and sha256Checksum exactly",
            "backup_rule": "byte-for-byte Yandex backup is written and verified before canonical promotion",
            "promotion_rule": "Apps Script promote_verified is archive-root-scoped, exact-ID and size/SHA256 guarded, and retry-safe after an uncertain post-rename response",
            "restart_rule": "unusable non-rate-limit 4xx sessions are discarded and restarted from the immutable Yandex candidate; 408/5xx use Drive-confirmed offset before any resend; rate limits use bounded backoff/Retry-After",
            "redirect_rule": "direct resumable session requests never follow redirects",
            "commit_rule": "COMMIT only after staged Drive verification, Yandex backup, and verified canonical promotion",
        },
        "wb_weekly_finance_main": {
            "status": "FIRST DATASET ONLY; not the complete WB business database",
            "period": "weekly",
            "report_type": 1,
            "meaning": "Основной",
            "logical_week": "Monday-Sunday",
            "month_boundary": "multiple WB reportId fragments may belong to one logical week and must be combined logically",
            "report_type_2": "По выкупам; separate dataset, never mixed into main",
            "row_deduplication": "(reportId, rrdId)",
            "registry_deduplication": "(cabinet, dataset, report_id)",
            "not_authoritative_for": [
                "customer orders/order events",
                "stock-on-date history",
                "promotion/advertising metrics",
                "sales-funnel analytics",
            ],
        },
        "planned_dataset_families": {
            "wildberries": ["orders", "stock snapshots", "promotion/advertising", "sales funnel"],
            "ozon": ["finance", "orders/shipments", "stock snapshots", "promotion/performance", "sales funnel"],
        },
    },
    "advertising_policy": {
        "current_scope": "Wildberries only; Ozon advertising is explicitly out of scope for this phase",
        "phase": "WB Advertising M0 read-only",
        "credential_service": "wb_ads",
        "credentials": "Promotion-scoped WB credentials are server-side only and must be injected from Yandex Lockbox; never stored on Drive/GitHub",
        "live_state_source": "Wildberries Promotion API",
        "active_campaign_status": 9,
        "m0_tools": ["wb_ads_list_active_campaigns", "wb_ads_get_campaign_stats", "wb_ads_audit_active"],
        "m0_default_audit_period": "last 7 full Europe/Moscow calendar days ending yesterday",
        "m0_batch_limit": "at most 50 campaign IDs in one /adv/v3/fullstats request; fail closed instead of returning a partial audit",
        "metric_class": "advertising_attribution_operational",
        "profitability_boundary": "advertising attribution metrics are not actual business profit; real profitability requires approved joins to sales/buyouts, returns, finance and unit economics",
        "archive_domain": "База данных/WB/<cabinet>/<year>/advertising",
        "archive_status": "2026 Drive category scaffold (stats/state/finance/config/audit) exists for wb_dmitrieva, wb_novokshenov and wb_laser_master; ingestion/coverage/registry integration is not yet implemented or accepted",
        "planned_datasets": ["ads_campaign_daily", "ads_product_daily", "ads_search_cluster_daily", "ads_campaign_snapshots", "ads_expenses", "ads_payments", "ads_bid_history", "ads_product_membership_history", "ads_placement_history", "ads_minus_phrase_history", "ads_mcp_actions"],
        "historical_routing": "when Advertising Archive V1 is implemented and coverage is proven, closed historical periods must be archive-first; current state/control stays live",
        "write_control_status": "not accepted in M0; dedicated start/pause/stop/bid/budget/product/cluster control tools require a later safety-reviewed phase",
        "safety_override": "provider GET endpoints that mutate campaign state (start/pause/stop/delete) are WRITE/DESTRUCTIVE at MCP level regardless of HTTP verb",
    },
    "data_routing_policy": {
        "canonical_catalog_tool": "marketplace_data_catalog",
        "canonical_metric_router_tool": "marketplace_metric_route",
        "required_flow": "request -> business metric -> data catalog -> dataset/source -> coverage -> query -> calculation",
        "generic_sales_is_ambiguous": "'sales/продажи' must be resolved to business meaning such as orders or financial realization before reading data",
        "orders_vs_realization": "orders are customer order events and must never be silently calculated from the weekly financial realization dataset",
        "missing_dataset": "surface the gap or use the matching official provider API; never substitute a different archived dataset",
        "dataset_contract_required": ["marketplace", "business metrics", "provider source", "grain", "time semantics", "schema/fields policy", "storage dataset path", "coverage/status"],
        "provenance_required": "answers from archive analytics must identify the dataset/source used",
    },
    "routing_policy": {
        "update_database": "route to the server archive update workflow for the selected dataset; compare canonical Drive registry and fetch only missing provider data",
        "historical_queries": "first route the business metric; use only the matching canonical Google Drive archive dataset when its period is covered",
        "current_or_uncovered": "use the matching official provider API or explicit gap/backfill workflow",
        "advertising_live_vs_archive": "campaign state/current control is live; closed advertising analytics becomes archive-first only after the ad dataset binding and coverage are implemented and proven",
        "multi_client": "all clients must see the same remote canonical Drive state and data catalog; no chat-local architecture decisions",
    },
    "change_control": {
        "new_cloud_provider": "FORBIDDEN without explicit architecture change",
        "new_primary_storage": "FORBIDDEN without explicit architecture change",
        "bypass_registry_or_idempotency": "FORBIDDEN",
        "new_dataset_requires": [
            "add/update canonical data catalog entry and metric routes",
            "define source, grain, time semantics, schema policy and storage path",
            "add archive/update/query implementation or mark it explicitly not archived",
            "add guardrail tests",
        ],
        "architecture_change_requires": [
            "update SYSTEM_MAP and server instructions",
            "update canonical data catalog",
            "update architecture documentation",
            "update guardrail tests",
            "pass CI/security/deployment acceptance",
        ],
    },
}

SYSTEM_INSTRUCTIONS = f"""CANONICAL MARKETPLACES MCP ARCHITECTURE — {ARCHITECTURE_VERSION}
Treat marketplace_system_map and marketplace_data_catalog as server-side sources of truth.
Runtime infrastructure is Yandex Cloud. Google Cloud is not part of the runtime architecture and no Google Cloud OAuth runtime dependency is required.
Canonical marketplace archive data is stored on Google Drive under the server-owned `MCP архив базы данных` root: annual dataset CSV files and the reports registry are the source of truth.
Yandex Object Storage remains required for durable queue/job state, immutable candidates, staging, resumable-upload state, and a secondary byte-for-byte backup of canonical Drive files. It uses the Serverless Container runtime service account and a temporary IAM token; no static archive key is required.
Google Drive access uses the owner's Google Apps Script web-app bridge; its shared bridge secret remains in Yandex Lockbox. No Google OAuth refresh token is stored in Yandex.
Large annual CSV files must NOT be transported through Apps Script/base64. Apps Script only brokers the official Google Drive API resumable-session start and narrow verified promotion; Yandex uploads bounded chunks directly to the returned Google session URI.
Large writes must target a non-canonical staging filename first. The existing canonical file remains untouched until Drive size/SHA256 verification and the byte-for-byte Yandex backup pass; then Apps Script promotes the verified staging file and only afterward may COMMIT advance registry/job progress.
The large-file worker trusts Drive-confirmed offsets, never blindly resends after ambiguous interruption, restarts unusable sessions from the immutable candidate, applies bounded backoff to throttling/transient errors, and never logs the bearer-like session URI.
The marketplace archive is MULTI-DATASET. No single report or annual CSV is the complete WB/Ozon business database.
The current WB weekly reportType=1 archive is only the first financial-realization dataset. It is NOT authoritative for customer orders, daily stock history, advertising/promotion metrics, or sales-funnel metrics.
Before answering a historical business question, interpret the requested business metric and route it through marketplace_metric_route / marketplace_data_catalog to the correct dataset. Generic 'sales/продажи' is ambiguous unless its business meaning is clear.
Never silently substitute the weekly finance dataset for orders, stocks, advertising, funnels, or any other missing dataset. Surface the gap or use the matching official provider API/backfill path.
Initial historical backfill is 2026; planned archive depth is through 2024 where provider history allows it. The same multi-dataset principle applies to both Wildberries and Ozon.
For database/archive tasks, use server-owned shared state, canonical Drive files, registry/idempotent update logic, and official WB/Ozon APIs. Do not invent chat-local storage, bypass Drive with another source of truth, or introduce a new architecture path.
WB Advertising M0 is Wildberries-only and read-only: use dedicated server-side wb_ads Promotion credentials; current campaign state is live from WB Promotion API; M0 advertising-attribution metrics must never be presented as actual business profit.
The advertising Drive folder scaffold is not proof that Advertising Archive V1 ingestion or historical coverage exists. Do not route historical ad analytics to the archive until dataset bindings, registry coverage and validation are implemented and accepted.
Provider GET endpoints that change advertising state are WRITE/DESTRUCTIVE at MCP level regardless of HTTP verb.
If a requested implementation conflicts with the canonical map or data catalog, fail closed and surface the conflict instead of silently changing architecture.
"""


def register_system_map_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        name="marketplace_system_map",
        annotations={"title": "Canonical Marketplaces MCP architecture map", "readOnlyHint": True, "openWorldHint": False},
    )
    async def marketplace_system_map() -> str:
        """Return the canonical server-side architecture and routing rules."""
        return json.dumps(SYSTEM_MAP, ensure_ascii=False, indent=2)