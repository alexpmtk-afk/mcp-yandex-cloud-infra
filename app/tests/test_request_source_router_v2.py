from __future__ import annotations

from datetime import date

from core.request_source_router import plan_marketplace_request

TODAY = date(2026, 9, 16)


def _plan(question: str, **kwargs):
    return plan_marketplace_request(question, today=TODAY, **kwargs)


def test_current_stock_is_ready_single_source():
    plan = _plan(
        "Сколько остатков сейчас на Wildberries?",
        marketplace="wb", seller="wb_novokshenov",
        date_from="2026-09-16", date_to="2026-09-16",
    )
    execution = plan["execution_plan"]
    assert plan["planner"] == "marketplace_query_plan.v2"
    assert execution["version"] == "marketplace_execution_plan.v2"
    assert execution["mode"] == "SINGLE_SOURCE"
    assert execution["status"] == "READY"
    assert execution["legs"][0]["executor"] == "marketplace_business_query"


def test_missing_marketplace_needs_context_instead_of_guessing():
    plan = _plan("Сколько заказов сегодня?", seller="shop")
    execution = plan["execution_plan"]
    assert execution["status"] == "NEEDS_CONTEXT"
    assert execution["can_start_execution"] is False
    assert execution["blockers"][0]["type"] == "MISSING_CONTEXT"
    assert "marketplace" in execution["blockers"][0]["details"]


def test_historical_sales_and_ads_are_separate_gated_legs():
    plan = _plan(
        "Сравни продажи и рекламные расходы за август",
        marketplace="wb", seller="wb_novokshenov",
        date_from="2026-08-01", date_to="2026-08-31",
    )
    execution = plan["execution_plan"]
    assert execution["mode"] == "MULTI_SOURCE"
    assert execution["status"] == "READY_WITH_GATES"
    assert execution["join"]["strategy"] == "SIDE_BY_SIDE_COMPARISON"
    assert execution["join"]["allow_partial_answer"] is False
    assert execution["join"]["arithmetic_allowed_without_explicit_semantic_contract"] is False
    assert {leg["purpose"] for leg in execution["legs"]} >= {"advertising", "sales_or_finance"}
    assert all(leg["coverage_gate"] == "FULL_COVERAGE" for leg in execution["legs"])


def test_public_price_plus_historical_stock_blocks_join():
    plan = _plan(
        "Сравни цену на сайте и остатки товара на 1 сентября",
        marketplace="wb", seller="wb_novokshenov",
        date_from="2026-09-01", date_to="2026-09-01",
    )
    execution = plan["execution_plan"]
    assert execution["mode"] == "MULTI_SOURCE"
    assert execution["status"] == "BLOCKED"
    stock = next(leg for leg in execution["legs"] if leg["purpose"] == "current_stock")
    public = next(leg for leg in execution["legs"] if leg["purpose"] == "public_card")
    assert stock["source_family"] == "UNAVAILABLE"
    assert stock["source_status"] == "HISTORICAL_SOURCE_ABSENT"
    assert public["source_family"] == "PUBLIC_MARKETPLACE_SOURCE"
    assert execution["join"]["missing_required_leg_behavior"] == "FAIL_CLOSED"
