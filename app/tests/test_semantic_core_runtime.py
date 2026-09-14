from __future__ import annotations

import asyncio

from core.business_router import execute_business_query
from core.semantic_archive import load_semantic_execution
from core.semantic_registry import get_dataset, get_field
from core.semantic_resolver import resolve_semantic_question


def test_semantic_registry_keeps_audited_92_column_contract():
    dataset = get_dataset("wb_weekly_finance_main")
    assert dataset["field_count"] == 92
    assert len(dataset["fields"]) == 92
    assert set(dataset["fields"]) == set(dataset["field_catalog"])
    assert "agencyVat" not in dataset["fields"]


def test_dlvprc_is_recorded_fixed_coefficient_not_current_or_applied_truth():
    field = get_field("wb_weekly_finance_main", "dlvPrc")
    text = (field["meaning_ru"] + " " + " ".join(field.get("limitations") or [])).lower()
    assert "планирован" in text
    assert "не считать" in text
    assert "текущ" in text


def test_current_tariff_and_complete_orders_fail_closed():
    current = resolve_semantic_question("Какой актуальный коэффициент склада сейчас?")
    assert current["resolution_type"] == "NOT_COVERED"
    assert current["route_id"] == "current_warehouse_tariff"

    orders = resolve_semantic_question("Сколько всего заказов было за период?")
    assert orders["resolution_type"] == "NOT_COVERED"
    assert orders["concept_id"] == "all_orders_placed"


def test_unknown_provider_schema_drift_field_is_not_executable():
    result = resolve_semantic_question("agencyVat")
    assert result["resolution_type"] == "UNKNOWN"
    assert result["execution_allowed"] is False


def test_execution_registry_contains_only_explicit_approved_capabilities():
    execution = load_semantic_execution()
    assert set(execution["executors"]) == {
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
    }
    assert execution["policy"]["require_full_coverage"] is True


def test_business_query_never_falls_back_from_current_state_to_archive():
    result = asyncio.run(
        execute_business_query(
            {},
            marketplace="wb",
            seller="wb_novokshenov",
            date_from="2026-09-01",
            date_to="2026-09-07",
            question="Какой актуальный коэффициент склада сейчас?",
        )
    )
    assert result["ok"] is False
    assert result["error"]["type"] == "source_not_suitable"
