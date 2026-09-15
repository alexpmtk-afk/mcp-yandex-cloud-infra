from __future__ import annotations

import asyncio

from core.semantic_business_router import execute_business_query
from core.semantic_archive import load_semantic_execution
from core.semantic_registry import get_capability, get_dataset, get_field, load_semantic_registry
from core.semantic_resolver import resolve_semantic_question


def test_semantic_registry_keeps_audited_92_column_contract():
    dataset = get_dataset("wb_weekly_finance_main")
    assert dataset["field_count"] == 92
    assert len(dataset["fields"]) == 92
    assert set(dataset["fields"]) == set(dataset["field_catalog"])
    assert "agencyVat" not in dataset["fields"]


def test_advertising_registry_extension_is_loaded_without_weakening_base_contract():
    registry = load_semantic_registry()
    assert registry["sources"]["wb_ads_data"]["database_presence"] == "AVAILABLE_IN_CANONICAL_ARCHIVE"
    ads = get_dataset("ads_campaign_daily", registry)
    assert ads["field_count"] == 10
    assert ads["row_dedup_key"] == ["date", "campaign_id"]
    assert ads["coverage"]["archive_route_requirement"] == "FULL_COVERAGE"
    capability = get_capability("advertising_performance", registry)
    assert capability["status"] == "AVAILABLE_WITH_LIMITATION"
    assert capability["scope"] == "historical_advertising_attribution_operational"
    assert "advertising_performance" not in registry["not_covered"]


def test_dlvprc_is_recorded_fixed_coefficient_not_current_or_applied_truth():
    field = get_field("wb_weekly_finance_main", "dlvPrc")
    text = (field["meaning_ru"] + " " + " ".join(field.get("limitations") or [])).lower()
    assert "планирован" in text
    assert "не считать" in text
    assert "текущ" in text


def test_current_tariff_complete_orders_and_current_advertising_fail_closed():
    current = resolve_semantic_question("Какой актуальный коэффициент склада сейчас?")
    assert current["resolution_type"] == "NOT_COVERED"
    assert current["route_id"] == "current_warehouse_tariff"

    orders = resolve_semantic_question("Сколько всего заказов было за период?")
    assert orders["resolution_type"] == "NOT_COVERED"
    assert orders["concept_id"] == "all_orders_placed"

    current_ads = resolve_semantic_question("Какая реклама сейчас работает сегодня?")
    assert current_ads["resolution_type"] in {"NOT_COVERED", "CAPABILITY"}
    # Even if lexical routing reaches advertising_performance first, the executor
    # must reject the current day before reading historical archive totals.


def test_historical_advertising_routes_to_explicit_capability():
    ads = resolve_semantic_question("Какой ДРР и рекламные расходы были за период?")
    assert ads["resolution_type"] == "CAPABILITY"
    assert ads["capability_id"] == "advertising_performance"
    assert ads["dataset_id"] == "ads_campaign_daily"


def test_unknown_provider_schema_drift_field_is_not_executable():
    result = resolve_semantic_question("agencyVat")
    assert result["resolution_type"] == "UNKNOWN"
    assert result["execution_allowed"] is False


def test_weekly_execution_registry_remains_explicit_and_advertising_is_domain_executor():
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
    assert get_capability("advertising_performance")["source_id"] == "wb_ads_data"


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
    assert result["error"] == "source_not_suitable"
