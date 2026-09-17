"""Guardrails for the Semantic Core-backed catalog compatibility view."""
from __future__ import annotations

import asyncio

from mcp.server.fastmcp import FastMCP

from core.data_catalog import (
    DATA_CATALOG_VERSION,
    build_data_catalog,
    register_data_catalog_tools,
    route_business_metric,
)
from core.semantic_core import SEMANTIC_CORE_VERSION, semantic_core_view


def test_catalog_is_not_an_independent_business_rule_registry():
    catalog = build_data_catalog()
    registry = semantic_core_view("registry")
    planning = semantic_core_view("planning")

    assert DATA_CATALOG_VERSION == "marketplace_data_catalog.semantic_core_view.v1"
    assert catalog["status"] == "SEMANTIC_CORE_VIEW"
    assert catalog["source_of_truth"] == "marketplace_semantic_core"
    assert catalog["semantic_core_version"] == SEMANTIC_CORE_VERSION
    assert catalog["policy"]["independent_metric_routes_forbidden"] is True
    assert catalog["sources"] == registry["sources"]
    assert catalog["datasets"] == registry["datasets"]
    assert catalog["capabilities"] == registry["capabilities"]
    assert catalog["availability_facts"] == planning["availability_facts"]


def test_advertising_route_uses_semantic_resolver_and_source_router():
    result = route_business_metric("рекламные расходы", "wb")

    assert result["ok"] is True
    assert result["source_of_truth"] == "marketplace_semantic_core"
    assert result["semantic_resolution"]["resolution_type"] == "CAPABILITY"
    assert result["semantic_resolution"]["capability_id"] == "advertising_performance"
    assert result["plans"]["wb"]["source_family"] == "CANONICAL_ARCHIVE"


def test_unknown_meaning_is_exposed_not_guessed():
    result = route_business_metric("совершенно неизвестная бизнес-метрика", "wb")

    assert result["ok"] is False
    assert result["source_of_truth"] == "marketplace_semantic_core"


def test_catalog_tools_are_registered():
    mcp = FastMCP("data-catalog-test")
    register_data_catalog_tools(mcp)
    names = {tool.name for tool in asyncio.run(mcp.list_tools())}
    assert names == {"marketplace_data_catalog", "marketplace_metric_route"}
