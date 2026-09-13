"""Canonical architecture map exposed by the MCP server itself."""
from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

ARCHITECTURE_VERSION = "2026-09-14.v1"

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
        "primary_runtime_storage": "Yandex Object Storage",
        "archive_auth": "Serverless Container runtime service-account IAM token from metadata; no static archive key",
        "archive_layout": "private dedicated bucket; server-owned annual dataset files plus registry",
        "google_drive": "optional export/mirror only; never a required runtime dependency or source of truth",
        "google_cloud": "not part of the runtime architecture",
        "client_local_files": "never authoritative for shared server state",
    },
    "archive_policy": {
        "shared_server_state": True,
        "multi_dataset": True,
        "no_single_report_is_complete_database": True,
        "default_update_scope": "all configured marketplace cabinets for the selected dataset",
        "idempotent": True,
        "registry_required": True,
        "initial_history_backfill": 2026,
        "planned_history_floor": 2024,
        "annual_partitioning": "one logical annual dataset per marketplace/cabinet/dataset/year",
        "annual_csv_pattern": "<cabinet>__<dataset>__<year>.csv",
        "wb_weekly_finance_main": {
            "status": "FIRST DATASET ONLY; not the complete WB business database",
            "period": "weekly",
            "report_type": 1,
            "meaning": "Основной",
            "logical_week": "Monday-Sunday",
            "month_boundary": "multiple WB reportId fragments may belong to one logical week and must be combined logically",
            "report_type_2": "По выкупам; separate dataset, never mixed into main",
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
    "data_routing_policy": {
        "canonical_catalog_tool": "marketplace_data_catalog",
        "canonical_metric_router_tool": "marketplace_metric_route",
        "required_flow": "request -> business metric -> data catalog -> dataset/source -> coverage -> query -> calculation",
        "generic_sales_is_ambiguous": "'sales/продажи' must be resolved to business meaning such as orders or financial realization before reading data",
        "orders_vs_realization": "orders are customer order events and must never be silently calculated from the weekly financial realization dataset",
        "missing_dataset": "surface the gap or use the matching official provider API; never substitute a different archived dataset",
        "dataset_contract_required": [
            "marketplace",
            "business metrics",
            "provider source",
            "grain",
            "time semantics",
            "schema/fields policy",
            "storage dataset path",
            "coverage/status",
        ],
        "provenance_required": "answers from archive analytics must identify the dataset/source used",
    },
    "routing_policy": {
        "update_database": "route to the server archive update workflow for the selected dataset; compare registry and fetch only missing provider data",
        "historical_queries": "first route the business metric; use only the matching shared archive dataset when its period is covered",
        "current_or_uncovered": "use the matching official provider API or explicit gap/backfill workflow",
        "multi_client": "all clients must see the same remote state and canonical data catalog; no chat-local architecture decisions",
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
Runtime infrastructure is Yandex Cloud. Google Cloud is not part of the runtime architecture.
Primary shared archive storage is Yandex Object Storage, accessed by the Serverless Container runtime service account with a temporary IAM token. Do not introduce a static archive key unless the canonical architecture is explicitly changed.
Google Drive may only be an optional export/mirror and must never become a required runtime dependency or source of truth.
The marketplace archive is MULTI-DATASET. No single report or annual CSV is the complete WB/Ozon business database.
The current WB weekly reportType=1 archive is only the first financial-realization dataset. It is NOT authoritative for customer orders, daily stock history, advertising/promotion metrics, or sales-funnel metrics.
Before answering a historical business question, interpret the requested business metric and route it through marketplace_metric_route / marketplace_data_catalog to the correct dataset. Generic 'sales/продажи' is ambiguous unless its business meaning is clear.
Never silently substitute the weekly finance dataset for orders, stocks, advertising, funnels, or any other missing dataset. Surface the gap or use the matching official provider API/backfill path.
Initial historical backfill is 2026; planned archive depth is through 2024 where provider history allows it. The same multi-dataset principle applies to both Wildberries and Ozon.
For database/archive tasks, use server-owned shared state, registry/idempotent update logic, and official WB/Ozon APIs. Do not invent chat-local storage, a new cloud provider, or a new architecture path.
If a requested implementation conflicts with the canonical map or data catalog, fail closed and surface the conflict instead of silently changing architecture.
"""


def register_system_map_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        name="marketplace_system_map",
        annotations={
            "title": "Canonical Marketplaces MCP architecture map",
            "readOnlyHint": True,
            "openWorldHint": False,
        },
    )
    async def marketplace_system_map() -> str:
        """Return the canonical server-side architecture and routing rules.

        Agents should consult this tool before architecture, storage, deployment,
        archive, routing, or cross-client state changes. The returned map is the
        MCP source of truth and overrides chat-local assumptions.
        """
        return json.dumps(SYSTEM_MAP, ensure_ascii=False, indent=2)
