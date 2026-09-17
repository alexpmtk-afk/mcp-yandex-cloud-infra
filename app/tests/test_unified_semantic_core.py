from __future__ import annotations

import asyncio

from mcp.server.fastmcp import FastMCP

from core import system_map
from core.semantic_core import (
    SEMANTIC_CORE_VERSION,
    build_semantic_core_snapshot,
    register_semantic_core_tool,
    semantic_core_view,
)


def test_unified_brain_cross_validates_all_existing_logic_layers():
    brain = build_semantic_core_snapshot()

    assert brain["version"] == "marketplace_semantic_core.v1"
    assert brain["status"] == "CANONICAL_BRAIN"
    assert brain["validated"] is True
    assert brain["canonical_flow"] == [
        "UNDERSTAND", "RESOLVE", "PLAN_SOURCE", "CLARIFY", "DISPATCH",
        "EXECUTE", "JOIN", "CALCULATE_IF_REGISTERED", "ANSWER_WITH_PROVENANCE",
    ]
    assert brain["data_semantics"]["policy"]["fail_closed"] is True
    assert brain["understanding"]["intents"]["policy"]["fail_closed_on_unknown"] is True
    assert brain["execution"]["archive_execution_registry"]["policy"]["require_full_coverage"] is True
    assert brain["planning"]["source_family_before_provider_field"] is True
    assert brain["planning"]["silent_substitution_forbidden"] is True
    assert brain["execution"]["dispatch"]["required_legs_all_or_nothing"] is True


def test_unified_brain_reads_join_and_calculation_contracts_not_copies():
    brain = build_semantic_core_snapshot()

    assert brain["join_control"]["registered_contract_ids"] == [
        "wb_sales_vs_advertising_side_by_side.v1"
    ]
    contract = brain["join_control"]["contracts"][0]
    assert contract["comparison_mode"] == "SIDE_BY_SIDE_ONLY"
    assert contract["arithmetic_allowed"] is False
    assert brain["calculation_control"]["registered_calculation_ids"] == []
    assert brain["calculation_control"]["registered_calculation_count"] == 0
    assert brain["calculation_control"]["arithmetic_enabled"] is False
    assert brain["calculation_control"]["policy"]["currency_alignment"] == "EXPLICIT_ONLY"
    assert brain["calculation_control"]["policy"]["implicit_currency_conversion_forbidden"] is True


def test_unified_brain_keeps_real_source_gaps_visible():
    summary = semantic_core_view("summary")
    planning = semantic_core_view("planning")

    assert summary["counts"]["known_source_gaps"] > 0
    assert planning["availability_facts"]["wb_orders_historical_archive"] is False
    assert planning["availability_facts"]["wb_stock_historical_archive"] is False
    assert summary["safety"]["fail_closed"] is True


def test_system_map_separates_brain_authority_from_executor_coverage():
    semantic = system_map.SYSTEM_MAP["semantic_core"]

    assert semantic["status"] == "NATURAL_QUESTION_ROUTING_PARTIALLY_WIRED"
    assert semantic["brain_status"] == "CANONICAL_BRAIN"
    assert semantic["brain_version"] == SEMANTIC_CORE_VERSION
    assert semantic["brain_runtime_entry"] == "marketplace_semantic_core"
    assert "marketplace_semantic_core is the canonical composed business brain" in system_map.SYSTEM_INSTRUCTIONS


def test_brain_tool_is_read_only_and_registered():
    mcp = FastMCP("semantic-core-test")
    register_semantic_core_tool(mcp)
    tools = {tool.name: tool for tool in asyncio.run(mcp.list_tools())}

    tool = tools["marketplace_semantic_core"]
    assert tool.annotations.readOnlyHint is True
    assert tool.annotations.openWorldHint is False
