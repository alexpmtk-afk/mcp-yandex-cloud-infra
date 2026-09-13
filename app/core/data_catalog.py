"""Canonical marketplace data catalog and business-metric routing layer.

The archive is intentionally multi-dataset. No single provider report is allowed
be treated as the complete business database. This module tells agents which
business metric belongs to which dataset and whether that dataset is already
archived, still planned, or must be read from the provider API.
"""
from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

DATA_CATALOG_VERSION = "2026-09-14.v1"

DATA_CATALOG: dict[str, Any] = {
    "version": DATA_CATALOG_VERSION,
    "status": "CANONICAL",
    "principles": {
        "multi_dataset_archive": True,
        "no_single_report_is_complete_database": True,
        "route_business_metric_before_reading_data": True,
        "never_substitute_another_dataset_silently": True,
        "unknown_or_ambiguous_metric": "fail closed and surface the ambiguity/gap",
        "initial_history_backfill": 2026,
        "planned_history_floor": 2024,
    },
    "request_flow": [
        "user request",
        "business metric interpretation",
        "marketplace data catalog lookup",
        "dataset/source selection",
        "archive coverage check",
        "archive query if covered; otherwise provider API or explicit backfill/gap",
        "business calculation",
        "answer with source/dataset provenance",
    ],
    "datasets": {
        "wb_weekly_finance_main": {
            "marketplace": "wb",
            "status": "ACTIVE_FIRST_DATASET",
            "archive_implemented": True,
            "provider_source": "WB weekly realization report, reportType=1 (Основной)",
            "grain": "provider realization-report row",
            "time_semantics": "weekly financial realization/settlement report; not an order-event timeline",
            "schema_policy": "preserve all provider columns verbatim; business formulas live above raw archive",
            "historical_scope": {"initial": 2026, "planned_floor": 2024},
            "authoritative_for": [
                "financial realization report details",
                "financial settlement facts represented by the provider report",
                "report-level rows, deductions, returns and other finance fields when present in provider columns",
            ],
            "not_authoritative_for": [
                "orders placed by customers",
                "daily order-event counts",
                "stock balance on each date",
                "advertising campaign statistics",
                "sales funnel analytics",
            ],
            "storage_dataset_path": "WB/<cabinet>/<year>/finance/weekly/main",
        },
        "wb_orders_daily": {
            "marketplace": "wb",
            "status": "PLANNED_NOT_ARCHIVED",
            "archive_implemented": False,
            "purpose": "customer order events by date/product; separate from financial realization",
            "authoritative_for": ["ordered units", "order events", "order value where provider fields support it"],
            "storage_dataset_path": "WB/<cabinet>/<year>/orders/daily",
        },
        "wb_stock_snapshots_daily": {
            "marketplace": "wb",
            "status": "PLANNED_NOT_ARCHIVED",
            "archive_implemented": False,
            "purpose": "historical stock balance snapshots by date/product/warehouse",
            "authoritative_for": ["stock on date", "stock history"],
            "storage_dataset_path": "WB/<cabinet>/<year>/stocks/daily",
        },
        "wb_promotion": {
            "marketplace": "wb",
            "status": "PLANNED_NOT_ARCHIVED",
            "archive_implemented": False,
            "purpose": "promotion/advertising campaign history and performance metrics",
            "authoritative_for": ["ad spend", "campaign metrics", "promotion performance where provider API supports it"],
            "storage_dataset_path": "WB/<cabinet>/<year>/promotion",
        },
        "wb_sales_funnel": {
            "marketplace": "wb",
            "status": "PLANNED_NOT_ARCHIVED",
            "archive_implemented": False,
            "purpose": "sales funnel and conversion analytics",
            "authoritative_for": ["funnel metrics", "conversion metrics where provider API supports them"],
            "storage_dataset_path": "WB/<cabinet>/<year>/analytics/funnel",
        },
        "ozon_finance": {
            "marketplace": "ozon",
            "status": "PLANNED_NOT_ARCHIVED",
            "archive_implemented": False,
            "purpose": "Ozon finance/accrual/realization history",
            "authoritative_for": ["Ozon financial realization", "Ozon accruals and finance facts"],
            "storage_dataset_path": "OZON/<cabinet>/<year>/finance",
        },
        "ozon_orders_daily": {
            "marketplace": "ozon",
            "status": "PLANNED_NOT_ARCHIVED",
            "archive_implemented": False,
            "purpose": "Ozon order/shipment events by date/product",
            "authoritative_for": ["ordered units", "order events", "shipments where selected contract supports them"],
            "storage_dataset_path": "OZON/<cabinet>/<year>/orders/daily",
        },
        "ozon_stock_snapshots_daily": {
            "marketplace": "ozon",
            "status": "PLANNED_NOT_ARCHIVED",
            "archive_implemented": False,
            "purpose": "Ozon historical stock balance snapshots",
            "authoritative_for": ["stock on date", "stock history"],
            "storage_dataset_path": "OZON/<cabinet>/<year>/stocks/daily",
        },
        "ozon_promotion": {
            "marketplace": "ozon",
            "status": "PLANNED_NOT_ARCHIVED",
            "archive_implemented": False,
            "purpose": "Ozon Performance/promotion campaign history",
            "authoritative_for": ["ad spend", "campaign metrics", "promotion performance where provider API supports it"],
            "storage_dataset_path": "OZON/<cabinet>/<year>/promotion",
        },
        "ozon_sales_funnel": {
            "marketplace": "ozon",
            "status": "PLANNED_NOT_ARCHIVED",
            "archive_implemented": False,
            "purpose": "Ozon sales funnel and conversion analytics",
            "authoritative_for": ["funnel metrics", "conversion metrics where provider API supports them"],
            "storage_dataset_path": "OZON/<cabinet>/<year>/analytics/funnel",
        },
    },
    "metric_routes": {
        "financial_realization": {"wb": "wb_weekly_finance_main", "ozon": "ozon_finance"},
        "ordered_units": {"wb": "wb_orders_daily", "ozon": "ozon_orders_daily"},
        "order_events": {"wb": "wb_orders_daily", "ozon": "ozon_orders_daily"},
        "stock_on_date": {"wb": "wb_stock_snapshots_daily", "ozon": "ozon_stock_snapshots_daily"},
        "stock_history": {"wb": "wb_stock_snapshots_daily", "ozon": "ozon_stock_snapshots_daily"},
        "ad_spend": {"wb": "wb_promotion", "ozon": "ozon_promotion"},
        "campaign_performance": {"wb": "wb_promotion", "ozon": "ozon_promotion"},
        "sales_funnel": {"wb": "wb_sales_funnel", "ozon": "ozon_sales_funnel"},
        "conversion": {"wb": "wb_sales_funnel", "ozon": "ozon_sales_funnel"},
    },
}

_EXACT_ALIASES = {
    "заказанные единицы": "ordered_units",
    "количество заказов": "order_events",
    "заказы": "order_events",
    "остатки на дату": "stock_on_date",
    "остаток на дату": "stock_on_date",
    "история остатков": "stock_history",
    "рекламные расходы": "ad_spend",
    "расходы на рекламу": "ad_spend",
    "воронка продаж": "sales_funnel",
    "конверсия": "conversion",
    "финансовая реализация": "financial_realization",
    "реализация": "financial_realization",
    "выкупы": "financial_realization",
}


def _interpret_metric(text: str) -> dict[str, Any]:
    value = " ".join(str(text).strip().lower().split())
    if not value:
        return {"status": "UNKNOWN", "reason": "empty metric"}
    if value in DATA_CATALOG["metric_routes"]:
        return {"status": "RESOLVED", "metric": value}
    if value in _EXACT_ALIASES:
        return {"status": "RESOLVED", "metric": _EXACT_ALIASES[value]}

    if "заказ" in value:
        metric = "ordered_units" if any(x in value for x in ("штук", "единиц", "количество товара", "товаров")) else "order_events"
        return {"status": "RESOLVED", "metric": metric}
    if "остат" in value:
        return {"status": "RESOLVED", "metric": "stock_on_date" if "дат" in value else "stock_history"}
    if any(x in value for x in ("реклам", "продвиж", "кампан")):
        return {"status": "RESOLVED", "metric": "ad_spend" if any(x in value for x in ("расход", "затрат", "деньг")) else "campaign_performance"}
    if any(x in value for x in ("ворон", "конверс")):
        return {"status": "RESOLVED", "metric": "sales_funnel" if "ворон" in value else "conversion"}
    if any(x in value for x in ("реализац", "выкуп", "финанс")):
        return {"status": "RESOLVED", "metric": "financial_realization"}
    if "продаж" in value:
        return {
            "status": "AMBIGUOUS",
            "reason": "'sales/продажи' may mean customer orders or financially realized sales; choose business meaning first",
            "candidates": ["ordered_units", "financial_realization"],
        }
    return {"status": "UNKNOWN", "reason": "metric is not mapped in the canonical data catalog"}


def route_business_metric(metric_text: str, marketplace: str = "all") -> dict[str, Any]:
    interpreted = _interpret_metric(metric_text)
    if interpreted["status"] != "RESOLVED":
        return {"ok": False, "input": metric_text, **interpreted}

    metric = interpreted["metric"]
    routes = DATA_CATALOG["metric_routes"].get(metric, {})
    requested = str(marketplace).strip().lower()
    if requested in {"wildberries", "wb"}:
        services = ("wb",)
    elif requested in {"ozon", "озон"}:
        services = ("ozon",)
    elif requested in {"all", "both", "оба", ""}:
        services = ("wb", "ozon")
    else:
        return {"ok": False, "status": "UNKNOWN_MARKETPLACE", "marketplace": marketplace}

    selected: dict[str, Any] = {}
    for service in services:
        dataset_id = routes.get(service)
        if not dataset_id:
            selected[service] = {"available": False, "reason": "no dataset route declared"}
            continue
        dataset = DATA_CATALOG["datasets"][dataset_id]
        selected[service] = {
            "dataset": dataset_id,
            "status": dataset["status"],
            "archive_implemented": dataset["archive_implemented"],
            "storage_dataset_path": dataset["storage_dataset_path"],
            "purpose": dataset.get("purpose") or dataset.get("provider_source"),
        }
    return {
        "ok": True,
        "status": "RESOLVED",
        "business_metric": metric,
        "routes": selected,
        "rule": "Do not substitute a different dataset when the routed dataset is not archived yet.",
    }


def register_data_catalog_tools(mcp: FastMCP) -> None:
    @mcp.tool(
        name="marketplace_data_catalog",
        annotations={
            "title": "Marketplace archive data catalog",
            "readOnlyHint": True,
            "openWorldHint": False,
        },
    )
    async def marketplace_data_catalog() -> str:
        """Return the canonical map of archive datasets, coverage and exclusions."""
        return json.dumps(DATA_CATALOG, ensure_ascii=False, indent=2)

    @mcp.tool(
        name="marketplace_metric_route",
        annotations={
            "title": "Route a business metric to its canonical dataset",
            "readOnlyHint": True,
            "openWorldHint": False,
        },
    )
    async def marketplace_metric_route(metric: str, marketplace: str = "all") -> str:
        """Interpret a business metric and return the canonical data source route.

        This must be consulted before answering historical business questions from
        the archive. In particular, generic "sales/продажи" is intentionally
        treated as ambiguous unless the request clearly means orders or financial
        realization. Missing datasets are surfaced as gaps; another dataset must
        never be used as a silent substitute.
        """
        return json.dumps(route_business_metric(metric, marketplace), ensure_ascii=False, indent=2)
