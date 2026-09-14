"""Server-side natural-language business routing through Semantic Core.

The TEST runtime keeps the existing infra-specific data catalog and archive
transport. This module adds the single canonical high-level business entry point
without inventing a second tool or silently substituting legacy metrics.
"""
from __future__ import annotations

import json
from datetime import date
from typing import Any, Optional

from .errors import make_error
from .semantic_archive import (
    SemanticArchiveExecutionError,
    execute_semantic_archive_question,
    load_semantic_execution,
)
from .semantic_resolver import resolve_semantic_question


def _j(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str)


def _parse_day(value: str, field: str) -> date:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an ISO calendar date (YYYY-MM-DD)") from exc


def _semantic_error(message: str, *, resolution: dict[str, Any], question: str, error_type: str = "source_not_suitable", extra: dict[str, Any] | None = None) -> dict:
    details: dict[str, Any] = {"question": question, "semantic_resolution": resolution}
    if extra:
        details.update(extra)
    return make_error(error_type, message, operation_id="marketplace_business_query", retryable=False, details=details)


async def execute_business_query(
    modules: dict[str, Any],
    *,
    marketplace: str,
    seller: str,
    date_from: str,
    date_to: str,
    metric: str = "",
    question: str = "",
    nm_ids: Optional[list[int]] = None,
) -> dict:
    marketplace_key = str(marketplace or "").strip().lower()
    try:
        start = _parse_day(date_from, "date_from")
        end = _parse_day(date_to, "date_to")
    except ValueError as exc:
        return make_error("invalid_params", str(exc), retryable=False)
    if start > end:
        return make_error("invalid_params", "date_from must be <= date_to", retryable=False)

    natural_question = str(question or "").strip()
    if not natural_question:
        return make_error(
            "invalid_params",
            "Provide the original business question. The TEST Semantic Core does not guess from a legacy metric hint.",
            operation_id="marketplace_business_query",
            retryable=False,
            details={"legacy_metric": str(metric or "").strip() or None},
        )

    if marketplace_key not in {"wb", "wildberries"}:
        return make_error(
            "source_not_suitable",
            "Natural-language Semantic Core execution is currently approved only for Wildberries weekly archive capabilities.",
            operation_id="marketplace_business_query",
            retryable=False,
            details={
                "question": natural_question,
                "marketplace": marketplace_key,
                "semantic_status": "REQUIRES_OTHER_SOURCE",
                "required_source_id": "ozon_reports" if marketplace_key in {"ozon", "озон"} else None,
            },
        )

    resolution = resolve_semantic_question(natural_question)
    if resolution.get("resolution_type") != "CAPABILITY":
        return _semantic_error(
            resolution.get("reason") or resolution.get("guardrail") or "The question cannot be safely answered from an approved current source.",
            resolution=resolution,
            question=natural_question,
        )

    capability_id = str(resolution.get("capability_id") or "")
    execution = load_semantic_execution()
    if capability_id not in execution["executors"]:
        return _semantic_error(
            f"The question was understood as {capability_id!r}, but this capability does not yet have an approved executable calculation contract.",
            resolution=resolution,
            question=natural_question,
            extra={"capability_id": capability_id},
        )

    archive_store = modules.get("_archive_store")
    if archive_store is None:
        return _semantic_error(
            "The approved semantic calculation requires the canonical marketplace archive, but archive storage is not configured.",
            resolution=resolution,
            question=natural_question,
            extra={"capability_id": capability_id, "required": "canonical Google Drive archive"},
        )

    try:
        result = await execute_semantic_archive_question(
            archive_store,
            question=natural_question,
            seller=seller,
            date_from=start,
            date_to=end,
            nm_ids=nm_ids,
        )
    except SemanticArchiveExecutionError as exc:
        return _semantic_error(
            str(exc),
            resolution=resolution,
            question=natural_question,
            error_type="invalid_params",
            extra={"capability_id": capability_id},
        )

    if isinstance(result, dict):
        result.setdefault("route", "semantic_archive")
        result["semantic_question"] = natural_question
        result["semantic_resolution"] = resolution
    return result


def register_business_query_tool(combined: Any, modules: dict[str, Any]) -> None:
    @combined.tool(
        name="marketplace_business_query",
        annotations={
            "title": "Marketplace business query (semantic server-side routing)",
            "readOnlyHint": True,
            "openWorldHint": True,
        },
    )
    async def marketplace_business_query(
        marketplace: str,
        seller: str,
        date_from: str,
        date_to: str,
        question: str = "",
        metric: str = "",
        nm_ids: Optional[list[int]] = None,
    ) -> str:
        """Resolve the original business question through Semantic Core.

        The server selects only approved semantics and executes archive queries
        only after FULL_COVERAGE is proven. Unsupported/current-state concepts
        fail closed rather than being replaced with a similar metric.
        """
        return _j(await execute_business_query(
            modules,
            marketplace=marketplace,
            seller=seller,
            date_from=date_from,
            date_to=date_to,
            question=question,
            metric=metric,
            nm_ids=nm_ids,
        ))
