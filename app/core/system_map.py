"""Canonical architecture map exposed by the MCP server itself."""
from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

ARCHITECTURE_VERSION = "2026-09-16.v19"

SYSTEM_MAP: dict[str, Any] = {
    "architecture_version": ARCHITECTURE_VERSION,
    "status": "CANONICAL",
    "scope": "Marketplaces MCP runtime, multi-dataset marketplace archive, advertising archive, and fail-closed Semantic Core routing",
    "runtime": {
        "cloud": "Yandex Cloud only",
        "entry": "ChatGPT/Codex -> marketplaces-yandex -> Yandex API Gateway -> Yandex Serverless Container",
        "secrets": "Yandex Lockbox",
        "shared_rate_limit_and_locks": "Yandex Managed Redis/Valkey",
        "marketplace_sources": ["Wildberries official API", "Ozon official API", "Ozon Performance official API"],
    },
    "storage_policy": {
        "primary_archive_storage": "Google Drive",
        "canonical_archive_data": "annual marketplace dataset CSV files plus dataset-specific coverage registries",
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
        "canonical_source_of_truth": "Google Drive annual dataset CSV files plus dataset-specific coverage registries",
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
        "wb_advertising_v1": {
            "status": "CANONICAL_ARCHIVE_IMPLEMENTED",
            "registry": "dataset_coverage_registry.csv",
            "datasets": [
                "ads_campaign_roster_snapshots",
                "ads_campaign_daily",
                "ads_product_daily",
                "ads_search_cluster_daily",
                "ads_campaign_snapshots",
                "ads_expenses",
                "ads_payments",
            ],
            "semantic_execution_dataset": "ads_campaign_daily",
            "semantic_coverage_dependency": "ads_campaign_roster_snapshots",
            "campaign_daily_deduplication": "(date, campaign_id)",
            "coverage_rule": "roster plus fullstats FULL_COVERAGE for every expected eligible campaign over the full requested closed period",
        },
        "planned_dataset_families": {
            "wildberries": ["orders", "stock snapshots", "sales funnel"],
            "ozon": ["finance", "orders/shipments", "stock snapshots", "promotion/performance", "sales funnel"],
        },
    },
    "advertising_policy": {
        "current_scope": "Wildberries only; Ozon advertising is explicitly out of scope for this phase",
        "phase": "WB Advertising M0 live read-only + Advertising Archive V1 historical read-only",
        "credential_service": "wb_ads",
        "credentials": "Promotion-scoped WB credentials are server-side only and must be injected from Yandex Lockbox; never stored on Drive/GitHub",
        "live_state_source": "Wildberries Promotion API",
        "active_campaign_status": 9,
        "m0_tools": ["wb_ads_list_active_campaigns", "wb_ads_get_campaign_stats", "wb_ads_audit_active"],
        "m0_default_audit_period": "last 7 full Europe/Moscow calendar days ending yesterday",
        "m0_batch_limit": "at most 50 campaign IDs in one /adv/v3/fullstats request; fail closed instead of returning a partial audit",
        "metric_class": "advertising_attribution_operational",
        "semantic_metric_contract": "wb_ads_m0.v1",
        "profitability_boundary": "advertising attribution metrics are not actual business profit; real profitability requires approved joins to sales/buyouts, returns, finance and unit economics",
        "archive_domain": "База данных/WB/<cabinet>/<year>/advertising",
        "archive_status": "Advertising Archive V1 canonical annual datasets and dataset_coverage_registry.csv are implemented; historical Semantic Core execution is coverage-gated",
        "archive_v1_datasets": [
            "ads_campaign_roster_snapshots",
            "ads_campaign_daily",
            "ads_product_daily",
            "ads_search_cluster_daily",
            "ads_campaign_snapshots",
            "ads_expenses",
            "ads_payments",
        ],
        "historical_routing": "closed cabinet-level campaign advertising analytics are archive-first only when roster plus campaign fullstats FULL_COVERAGE is proven; current state/control stays live",
        "semantic_v1_scope": "cabinet-level ads_campaign_daily only; product/nm_id questions fail closed until ads_product_daily receives its own Semantic execution contract; campaign-scoped selectors/grouping are also fail-closed",
        "write_control_status": "not accepted in M0; dedicated start/pause/stop/bid/budget/product/cluster control tools require a later safety-reviewed phase",
        "safety_override": "provider GET endpoints that mutate campaign state (start/pause/stop/delete) are WRITE/DESTRUCTIVE at MCP level regardless of HTTP verb",
    },
    "semantic_core": {
        "status": "TEST_RUNTIME_WIRED",
        "runtime_entry": "marketplace_business_query",
        "registry": "core/semantic_registry.yaml + validated core/semantic_registry_extensions.yaml",
        "intent_catalog": "core/semantic_intents.yaml",
        "business_query_parser": "core/business_query_parser.py normalizes metric-independent measure/grouping/period/filter dimensions before source selection",
        "resolver": "core/semantic_resolver.py",
        "execution_registry": "core/semantic_execution.yaml for weekly finance",
        "archive_executor": "core/semantic_archive.py for weekly finance; core/semantic_advertising.py for advertising",
        "operational_executor": "core/semantic_current_stock.py for seller-aware current WB stock; ORDERS uses the approved legacy operational executor",
        "approved_operational_business_metrics": ["ORDERS", "CURRENT_STOCK"],
        "current_stock_source": "WB Seller Analytics current stocks endpoint; Base-token fallback is the official asynchronous warehouse-remains report",
        "current_archive_datasets": ["wb_weekly_finance_main", "ads_campaign_daily", "ads_campaign_roster_snapshots"],
        "current_archive_schema": "92 official-help-audited weekly-finance columns plus WB Advertising V1 campaign-daily and roster schemas",
        "source_revision": "alexpmtk-afk/marketplaces-mcp-ru@303b7f6e732e8c6b0047ab4e81c43169acd6f040",
        "approved_archive_executors": [
            "penalties",
            "storage_charge",
            "acceptance_charge",
            "sale_and_return_operations",
            "logistics",
            "deductions_and_adjustments",
            "commission_and_wb_reward",
            "acquiring_and_payment_processing",
            "observed_fulfillment_method",
            "warehouse_tariff_context",
            "advertising_performance",
        ],
        "execution_gate": "FULL_COVERAGE from the dataset-specific canonical registry plus canonical annual-file presence; weekly finance uses reports_registry.csv, advertising uses dataset_coverage_registry.csv with roster/fullstats scope proof",
        "question_policy": {
            "preferred_input": "preserve the user's original natural-language question",
            "legacy_metric": "retained only for backward compatibility",
            "precedence": "question overrides a conflicting legacy metric",
            "current_state_precedence": "a specific registered operational business metric may outrank the generic current-state guard only for its explicitly approved live/operational source",
            "clarification": "fail closed when meaning/source cannot be safely resolved; never silently substitute a similar metric",
        },
        "fail_closed_for": [
            "complete marketplace order flow from weekly-finance orderDt/orderUid",
            "historical stock requested from the current WB stock snapshot",
            "current stock from historical finance rows",
            "current fulfillment configuration from historical deliveryMethod",
            "current live warehouse tariff from historical dlvPrc/warehouseLogisticsCoeff",
            "Ozon semantics until a dedicated approved source binding exists",
            "unknown provider fields such as agencyVat until explicitly audited and bound",
            "advertising product/nm_id questions until ads_product_daily gets an approved Semantic contract",
            "advertising campaign-scoped selectors or breakdowns until selector/grouping contracts are approved",
            "current-day advertising from the closed historical archive",
            "historical advertising when roster/fullstats FULL_COVERAGE is not proven",
        ],
        "operational_rules": [
            "business_query_parser extracts measure/grouping/period/filter before source selection and does not choose provider fields",
            "ordinary ORDERS questions, including today, use the approved operational WB Statistics Orders source; explicit complete-order-flow wording remains separate and fail-closed without a complete order-feed source",
            "CURRENT_STOCK uses the seller-aware live WB Seller Analytics stock source for the named cabinet; Base tokens may use the official asynchronous warehouse-remains report fallback",
            "CURRENT_STOCK is a present snapshot only; any past-date stock request fails closed until a separate historical stock source/contract is approved",
            "the generic current-state marker is only a fallback and must not block a more specific registered operational metric",
        ],
        "advertising_guardrail": "DRR/ROAS and attributed order metrics under advertising_performance are WB advertising-attribution metrics, not total seller revenue, complete orders, or business profitability",
        "money_policy": "never combine different currencies and never silently net unrelated financial components",
        "dlvPrc_policy": "historical coefficient fixed when the supply was planned; not proof of the coefficient actually charged after fixation expiry and never current tariff truth",
        "schema_drift_policy": "provider fields outside the audited 92-column weekly-finance archive, including agencyVat, are not executable merely because the live API exposes them",
        "runtime_integration": "marketplace_business_query preserves the original question and normalizes source-independent business dimensions before source selection; approved historical archive capabilities remain FULL_COVERAGE-gated, ORDERS routes to the operational WB Statistics Orders source, and CURRENT_STOCK routes to the seller-aware live WB stock executor without substituting today's snapshot for historical dates",
    },
    "data_routing_policy": {
        "canonical_catalog_tool": "marketplace_data_catalog",
        "canonical_metric_router_tool": "marketplace_metric_route",
        "canonical_business_query_tool": "marketplace_business_query",
        "required_flow": "original question -> Semantic Core -> approved business meaning/source -> data catalog/coverage -> query -> calculation -> provenance",
        "generic_sales_is_ambiguous": "generic sales wording must be resolved to an explicit business meaning before reading data; an approved Semantic Core route may resolve it to weekly financial realization, but must never silently reinterpret it as customer orders",
        "orders_vs_realization": "orders are customer order events and must never be silently calculated from the weekly financial realization dataset",
        "missing_dataset": "surface the gap or use the matching official provider API; never substitute a different archived dataset",
        "dataset_contract_required": ["marketplace", "business metrics", "provider source", "grain", "time semantics", "schema/fields policy", "storage dataset path", "coverage/status"],
        "provenance_required": "answers from archive analytics must identify the dataset/source used",
    },
    "routing_policy": {
        "update_database": "route to the server archive update workflow for the selected dataset; compare canonical Drive registry and fetch only missing provider data",
        "natural_business_question": "preserve the user's original wording, normalize business dimensions, and resolve through Semantic Core before selecting or executing a source",
        "historical_queries": "execute an approved Semantic Core archive capability only after matching source semantics and FULL_COVERAGE are proven",
        "current_or_uncovered": "use an explicitly suitable live/provider source or return a controlled source/coverage gap; never fall back to a similar historical field",
        "complete_orders": "never use weekly-finance orderDt/orderUid as the complete customer-order flow; explicit complete-order wording must not be silently substituted with operational Statistics Orders",
        "current_stock": "CURRENT_STOCK uses the current WB Seller Analytics stock snapshot for the named cabinet; historical stock dates require a separate approved source and never receive today's snapshot",
        "current_tariffs": "never use historical dlvPrc or warehouseLogisticsCoeff as current live tariff truth",
        "advertising_live_vs_archive": "campaign state/current control remains live; closed cabinet-level advertising analytics are archive-first after roster/fullstats FULL_COVERAGE proof; product-level and campaign-scoped semantic requests remain fail-closed until separately approved",
        "multi_client": "all clients must see the same remote canonical Drive state, data catalog and Semantic Core rules; no chat-local architecture decisions",
    },
    "change_control": {
        "new_cloud_provider": "FORBIDDEN without explicit architecture change",
        "new_primary_storage": "FORBIDDEN without explicit architecture change",
        "bypass_registry_or_idempotency": "FORBIDDEN",
        "bypass_semantic_guardrails": "FORBIDDEN",
        "bypass_full_coverage_gate": "FORBIDDEN",
        "new_dataset_requires": [
            "add/update canonical data catalog entry and metric routes",
            "define source, grain, time semantics, schema policy and storage path",
            "add archive/update/query implementation or mark it explicitly not archived",
            "add guardrail tests",
        ],
        "architecture_change_requires": [
            "update SYSTEM_MAP and server instructions",
            "update canonical data catalog or explicitly document why no catalog contract changes",
            "update architecture documentation",
            "update guardrail tests",
            "pass CI/security/deployment acceptance",
        ],
    },
}

SYSTEM_INSTRUCTIONS = f"""CANONICAL MARKETPLACES MCP ARCHITECTURE — {ARCHITECTURE_VERSION}
Treat marketplace_system_map, marketplace_data_catalog and the server-side Semantic Core as sources of truth for business routing.
Runtime infrastructure is Yandex Cloud. Google Cloud is not part of the runtime architecture and no Google Cloud OAuth runtime dependency is required.
Canonical marketplace archive data is stored on Google Drive under the server-owned `MCP архив базы данных` root: annual dataset CSV files and dataset-specific coverage registries are the source of truth.
Yandex Object Storage remains required for durable queue/job state, immutable candidates, staging, resumable-upload state, and a secondary byte-for-byte backup of canonical Drive files. It uses the Serverless Container runtime service account and a temporary IAM token; no static archive key is required.
Google Drive access uses the owner's Google Apps Script web-app bridge; its shared bridge secret remains in Yandex Lockbox. No Google OAuth refresh token is stored in Yandex.
Large annual CSV files must NOT be transported through Apps Script/base64. Apps Script only brokers the official Google Drive API resumable-session start and narrow verified promotion; Yandex uploads bounded chunks directly to the returned Google session URI.
Large writes must target a non-canonical staging filename first. The existing canonical file remains untouched until Drive size/SHA256 verification and the byte-for-byte Yandex backup pass; then Apps Script promotes the verified staging file and only afterward may COMMIT advance registry/job progress.
The large-file worker trusts Drive-confirmed offsets, never blindly resends after ambiguous interruption, restarts unusable sessions from the immutable candidate, applies bounded backoff to throttling/transient errors, and never logs the bearer-like session URI.
The marketplace archive is MULTI-DATASET. No single report or annual CSV is the complete WB/Ozon business database.
For natural-language business questions, preserve the user's original wording and route it through marketplace_business_query / Semantic Core. The server first normalizes source-independent measure/grouping/period/filter dimensions; only explicitly approved archive capabilities or operational business metrics may execute.
The generic words `today/current/сегодня/текущий` are a fail-closed fallback, not a global veto: a more specific registered operational business metric may outrank them only for its explicitly approved live/operational source.
Ordinary WB ORDERS questions, including today, use the approved operational WB Statistics Orders source. That source is operational/preliminary and must never be described as the complete marketplace order flow; explicit complete-order-flow wording remains a separate fail-closed concept until a complete source is approved.
CURRENT_STOCK uses the seller-aware current WB Seller Analytics stock snapshot for the named cabinet. Base-token cabinets may use the official asynchronous warehouse-remains report fallback. It is present-state only: a historical stock date must fail closed and must never receive today's snapshot.
The current WB weekly reportType=1 archive is only the first financial-realization dataset. It is NOT authoritative for the complete customer-order flow, daily stock history, advertising/promotion metrics, or sales-funnel metrics.
Weekly-finance orderDt/orderUid are context attached to reported financial operations and must never be used as the complete customer-order funnel.
Archive calculations require FULL_COVERAGE from the dataset-specific canonical registry plus the canonical annual file. Different currencies are never combined and unrelated financial components are never silently netted.
Historical deliveryMethod may describe observed fulfillment only. Historical dlvPrc is the coefficient fixed when the supply was planned; after fixation expiry it is not proof of the coefficient actually charged and it is never current tariff truth. warehouseLogisticsCoeff is also historical context, not a current tariff source.
Current-state questions without an approved operational source, complete-order-flow questions, unsupported Ozon semantics and unknown fields fail closed rather than falling back to similar weekly-finance data.
The current provider API may expose agencyVat, but it is not part of the audited 92-column canonical archive and has no approved Semantic Core binding; do not execute it until it is explicitly audited and registered.
Before answering other historical business questions, use marketplace_metric_route / marketplace_data_catalog to identify the correct dataset. Generic 'sales/продажи' must have an explicit business meaning and must never be silently reinterpreted as customer orders.
Never silently substitute the weekly finance dataset for orders, stocks, advertising, funnels, or any other missing dataset. Surface the gap or use the matching official provider API/backfill path.
Initial historical backfill is 2026; planned archive depth is through 2024 where provider history allows it. The same multi-dataset principle applies to both Wildberries and Ozon.
For database/archive tasks, use server-owned shared state, canonical Drive files, registry/idempotent update logic, and official WB/Ozon APIs. Do not invent chat-local storage, bypass Drive with another source of truth, or introduce a new architecture path.
WB Advertising M0 is Wildberries-only and read-only. Current campaign state/control remains live through dedicated server-side wb_ads Promotion credentials.
Advertising Archive V1 is the canonical closed-history source for approved cabinet-level advertising_performance. It requires roster plus fullstats FULL_COVERAGE from dataset_coverage_registry.csv before any calculation.
Semantic Advertising V1 is cabinet_total only. Product/nm_id questions, specific-campaign selectors, campaign breakdowns, incomplete coverage, and current-day requests must fail closed rather than being substituted with cabinet historical totals.
Advertising metrics use the wb_ads_m0.v1 advertising-attribution contract. DRR/ROAS, ad orders and attributed order amount are NOT actual business profit, complete seller orders or realized seller revenue.
Provider GET endpoints that change advertising state are WRITE/DESTRUCTIVE at MCP level regardless of HTTP verb.
If a requested implementation conflicts with the canonical map, data catalog or Semantic Core guardrails, fail closed and surface the conflict instead of silently changing architecture.
"""


def register_system_map_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        name="marketplace_system_map",
        annotations={"title": "Canonical Marketplaces MCP architecture map", "readOnlyHint": True, "openWorldHint": False},
    )
    async def marketplace_system_map() -> str:
        """Return the canonical server-side architecture and routing rules."""
        return json.dumps(SYSTEM_MAP, ensure_ascii=False, indent=2)
