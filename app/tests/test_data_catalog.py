"""Guardrails for marketplace business-metric routing."""
from __future__ import annotations

import asyncio

from mcp.server.fastmcp import FastMCP

from core.data_catalog import DATA_CATALOG, register_data_catalog_tools, route_business_metric


def test_weekly_finance_is_first_dataset_not_complete_database():
    principles = DATA_CATALOG["principles"]
    assert principles["multi_dataset_archive"] is True
    assert principles["no_single_report_is_complete_database"] is True
    finance = DATA_CATALOG["datasets"]["wb_weekly_finance_main"]
    assert finance["archive_implemented"] is True
    assert "orders placed by customers" in finance["not_authoritative_for"]
    assert "stock balance on each date" in finance["not_authoritative_for"]


def test_orders_route_away_from_weekly_finance():
    result = route_business_metric("заказанные единицы", "wb")
    assert result["ok"] is True
    assert result["business_metric"] == "ordered_units"
    assert result["routes"]["wb"]["dataset"] == "wb_orders_daily"
    assert result["routes"]["wb"]["archive_implemented"] is False


def test_stock_and_ad_metrics_route_to_separate_datasets():
    stock = route_business_metric("остатки на дату", "wb")
    ads = route_business_metric("расходы на рекламу", "ozon")
    assert stock["routes"]["wb"]["dataset"] == "wb_stock_snapshots_daily"
    assert ads["routes"]["ozon"]["dataset"] == "ozon_promotion"


def test_generic_sales_is_ambiguous_not_silently_finance():
    result = route_business_metric("продажи за 2025 год", "wb")
    assert result["ok"] is False
    assert result["status"] == "AMBIGUOUS"
    assert "ordered_units" in result["candidates"]
    assert "financial_realization" in result["candidates"]


def test_catalog_tools_are_registered():
    mcp = FastMCP("data-catalog-test")
    register_data_catalog_tools(mcp)
    names = {tool.name for tool in asyncio.run(mcp.list_tools())}
    assert "marketplace_data_catalog" in names
    assert "marketplace_metric_route" in names
