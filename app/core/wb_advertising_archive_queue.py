"""Durable queue/state model for the WB Advertising Archive V1."""
from __future__ import annotations

import hashlib
import json
import math
import time
from datetime import date, datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from .archive_coverage import coverage_key, parse_registry
from .business_registry import resolve_business_cabinet
from .rate_limit import redis_connection_kwargs, redis_url_from_env
from .tools import resolve_named_cabinet
from .wb_advertising import resolve_ads_cabinet
from .wb_advertising_archive import (
    ARCHIVE_CABINETS,
    DATASETS,
    canonical_location,
    coverage_registry_location,
    encode_csv,
    parse_csv,
)

QUEUE_KEY = "marketplace-archive:v2:wb-advertising:due"
JOB_FOLDER = ("app", "jobs", "wb-advertising")
JOB_VERSION = 1
MOSCOW_TZ = ZoneInfo("Europe/Moscow")
FULLSTATS_MAX_DAYS = 31
FULLSTATS_MAX_IDS = 50


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _closed_date_to(year: int) -> str:
    today_msk = datetime.now(MOSCOW_TZ).date()
    end = min(date(int(year), 12, 31), today_msk.fromordinal(today_msk.toordinal() - 1))
    return end.isoformat()


def _year_start(year: int) -> str:
    return date(int(year), 1, 1).isoformat()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _normalize_campaign_id(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _campaign_ids_from_roster(rows: list[dict[str, Any]]) -> tuple[list[int], list[int]]:
    all_ids: set[int] = set()
    fullstats_ids: set[int] = set()
    for row in rows:
        campaign_id = _normalize_campaign_id(row.get("campaign_id"))
        if campaign_id <= 0:
            continue
        all_ids.add(campaign_id)
        if str(row.get("fullstats_eligible") or "").strip().lower() in {"true", "1", "yes"}:
            fullstats_ids.add(campaign_id)
    return sorted(all_ids), sorted(fullstats_ids)


def _build_fullstats_plan(campaign_ids: list[int], date_from: str, date_to: str) -> list[dict[str, Any]]:
    if not campaign_ids:
        return []
    start = date.fromisoformat(date_from)
    end = date.fromisoformat(date_to)
    plan: list[dict[str, Any]] = []
    cursor = start
    while cursor <= end:
        chunk_end = min(end, cursor.fromordinal(cursor.toordinal() + FULLSTATS_MAX_DAYS - 1))
        for index in range(0, len(campaign_ids), FULLSTATS_MAX_IDS):
            ids = campaign_ids[index:index + FULLSTATS_MAX_IDS]
            plan.append({
                "operation_id": "wb_ads_fullstats",
                "date_from": cursor.isoformat(),
                "date_to": chunk_end.isoformat(),
                "campaign_ids": ids,
            })
        cursor = chunk_end.fromordinal(chunk_end.toordinal() + 1)
    return plan


class WBAdvertisingArchiveJobQueue:
    """Persistent advertising archive queue with one provider request per step."""

    def __init__(self, wb_module: Any, store: Any) -> None:
        self.wb = wb_module
        self.store = store

    @staticmethod
    def normalize_cabinet(seller: str) -> str:
        normalized = str(seller).strip()
        if normalized in ARCHIVE_CABINETS:
            return normalized
        entry = resolve_business_cabinet("wb", normalized)
        if entry is None or entry.cabinet not in ARCHIVE_CABINETS:
            raise ValueError(f"Unknown WB seller/cabinet: {seller}")
        return entry.cabinet

    @staticmethod
    def job_id(cabinet: str, year: int) -> str:
        return f"wb-advertising-{cabinet}-{int(year)}"

    async def _redis(self):
        url = redis_url_from_env()
        if not url:
            raise RuntimeError("Shared Redis is required for advertising archive scheduling")
        import redis.asyncio as redis_async
        return redis_async.Redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=10,
            **redis_connection_kwargs(url),
        )

    async def _schedule(self, job_id: str, delay_seconds: float = 0.0) -> None:
        client = await self._redis()
        try:
            await client.zadd(QUEUE_KEY, {job_id: time.time() + max(0.0, float(delay_seconds))})
        finally:
            await client.aclose()

    async def _unschedule(self, job_id: str) -> None:
        client = await self._redis()
        try:
            await client.zrem(QUEUE_KEY, job_id)
        finally:
            await client.aclose()

    async def next_due(self) -> tuple[str | None, float]:
        client = await self._redis()
        try:
            now = time.time()
            due = await client.zrangebyscore(QUEUE_KEY, "-inf", now, start=0, num=1)
            if due:
                return str(due[0]), 0.0
            upcoming = await client.zrange(QUEUE_KEY, 0, 0, withscores=True)
            if not upcoming:
                return None, 0.0
            return None, max(0.0, float(upcoming[0][1]) - now)
        finally:
            await client.aclose()

    async def _job_location(self, job_id: str) -> tuple[str, str]:
        folder = await self.store.ensure_folder_path(JOB_FOLDER)
        return folder, f"{job_id}.json"

    async def _load(self, job_id: str) -> dict[str, Any] | None:
        folder, name = await self._job_location(job_id)
        item, raw = await self.store.download_named(folder, name)
        if item is None or raw is None:
            return None
        return json.loads(raw.decode("utf-8"))

    async def _save(self, state: dict[str, Any]) -> None:
        state["updated_at_utc"] = _utc_now()
        folder, name = await self._job_location(str(state["job_id"]))
        payload = json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        await self.store.upload_bytes(folder, name, payload, mime_type="application/json")

    async def load(self, job_id: str) -> dict[str, Any] | None:
        return await self._load(job_id)

    async def save(self, state: dict[str, Any]) -> None:
        await self._save(state)

    async def schedule(self, job_id: str, delay_seconds: float = 0.0) -> None:
        await self._schedule(job_id, delay_seconds)

    async def unschedule(self, job_id: str) -> None:
        await self._unschedule(job_id)

    async def _stage_location(self, job_id: str, dataset: str) -> tuple[str, str]:
        folder = await self.store.ensure_folder_path([*JOB_FOLDER, job_id, "staging"])
        return folder, f"{dataset}.csv"

    async def stage_dataset(self, job_id: str, dataset: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        if dataset not in DATASETS:
            raise ValueError(f"Unknown advertising archive dataset: {dataset}")
        folder, name = await self._stage_location(job_id, dataset)
        item, raw = await self.store.download_named(folder, name)
        headers, existing = parse_csv(raw)
        _ = item
        combined = existing + [dict(row) for row in rows]
        if combined:
            headers = list(dict.fromkeys([*headers, *(key for row in combined for key in row.keys())]))
        payload = encode_csv(headers, combined)
        obj = await self.store.upload_bytes(folder, name, payload, mime_type="text/csv")
        return {
            "dataset": dataset,
            "rows": len(combined),
            "bytes": len(payload),
            "sha256": _sha256(payload),
            "object_id": obj.id,
        }

    async def read_staged_dataset(self, job_id: str, dataset: str) -> list[dict[str, Any]]:
        folder, name = await self._stage_location(job_id, dataset)
        _, raw = await self.store.download_named(folder, name)
        _, rows = parse_csv(raw)
        return rows

    async def _coverage_records(self) -> list[dict[str, str]]:
        parts, name = coverage_registry_location()
        folder = await self.store.ensure_folder_path(parts)
        _, raw = await self.store.download_named(folder, name)
        return parse_registry(raw)

    async def _is_covered(self, *, cabinet: str, dataset: str, operation_id: str, date_from: str, date_to: str, scope: dict[str, Any]) -> bool:
        request_key = coverage_key(
            marketplace="wb",
            cabinet=cabinet,
            dataset=dataset,
            operation_id=operation_id,
            date_from=date_from,
            date_to=date_to,
            scope=scope,
        )
        for row in await self._coverage_records():
            if row.get("request_key") != request_key:
                continue
            if row.get("status") != "COMPLETE":
                continue
            if row.get("quality_status") not in {"PASS", "PASS_WITH_FLAGS"}:
                continue
            return True
        return False

    def _resolve_ads_creds(self, cabinet: str) -> tuple[dict[str, str] | None, dict[str, Any] | None]:
        entry = resolve_ads_cabinet(cabinet)
        if entry is None:
            return None, {
                "ok": False,
                "error": "wb_ads_credential_not_configured",
                "message": f"No WB advertising credential mapping is configured for cabinet {cabinet!r}.",
            }
        return resolve_named_cabinet(self.wb.client, entry.credential_name, service="wb_ads")

    def _resolve_finance_creds(self, cabinet: str) -> tuple[dict[str, str] | None, dict[str, Any] | None]:
        return resolve_named_cabinet(self.wb.client, cabinet)

    async def enqueue(self, *, year: int, seller: str) -> dict[str, Any]:
        year = int(year)
        if year < 2024 or year > date.today().year:
            raise ValueError("year must be between 2024 and the current year")
        cabinet = self.normalize_cabinet(seller)
        job_id = self.job_id(cabinet, year)
        existing = await self._load(job_id)
        if existing is not None:
            if existing.get("status") != "COMPLETE":
                await self._schedule(job_id, 0)
            return {
                "ok": True,
                "job_id": job_id,
                "created": False,
                "status": existing.get("status"),
                "phase": existing.get("phase"),
                "cabinet": cabinet,
                "year": year,
            }

        now = _utc_now()
        state = {
            "version": JOB_VERSION,
            "job_id": job_id,
            "marketplace": "wb",
            "dataset_family": "advertising",
            "cabinet": cabinet,
            "year": year,
            "status": "QUEUED",
            "phase": "DISCOVER",
            "provider_calls": 0,
            "last_error": None,
            "last_retry_after_seconds": 0,
            "campaign_ids": [],
            "fullstats_campaign_ids": [],
            "fetch_plan": [],
            "fetch_index": 0,
            "cluster_plan": [],
            "cluster_index": 0,
            "completed_requests": [],
            "staged_datasets": {},
            "created_at_utc": now,
            "updated_at_utc": now,
        }
        await self._save(state)
        await self._schedule(job_id, 0)
        return {
            "ok": True,
            "job_id": job_id,
            "created": True,
            "status": state["status"],
            "phase": state["phase"],
            "cabinet": cabinet,
            "year": year,
        }

    async def status(self, job_id: str) -> dict[str, Any]:
        state = await self._load(str(job_id))
        if state is None:
            return {"ok": False, "error": "archive_job_not_found", "job_id": job_id}
        return {
            "ok": True,
            "job_id": state["job_id"],
            "status": state.get("status"),
            "phase": state.get("phase"),
            "marketplace": state.get("marketplace"),
            "dataset_family": state.get("dataset_family"),
            "cabinet": state.get("cabinet"),
            "year": state.get("year"),
            "provider_calls": int(state.get("provider_calls", 0) or 0),
            "campaigns_total": len(state.get("campaign_ids") or []),
            "fullstats_campaigns_total": len(state.get("fullstats_campaign_ids") or []),
            "fetch_total": len(state.get("fetch_plan") or []),
            "fetch_index": int(state.get("fetch_index", 0) or 0),
            "cluster_total": len(state.get("cluster_plan") or []),
            "cluster_index": int(state.get("cluster_index", 0) or 0),
            "completed_requests": len(state.get("completed_requests") or []),
            "last_retry_after_seconds": int(math.ceil(float(state.get("last_retry_after_seconds", 0) or 0))),
            "last_error": state.get("last_error"),
            "created_at_utc": state.get("created_at_utc"),
            "updated_at_utc": state.get("updated_at_utc"),
        }

    async def initialize_fetch_plan(self, state: dict[str, Any], roster_rows: list[dict[str, Any]]) -> None:
        cabinet = str(state["cabinet"])
        year = int(state["year"])
        date_from = _year_start(year)
        date_to = _closed_date_to(year)
        campaign_ids, fullstats_ids = _campaign_ids_from_roster(roster_rows)
        state["campaign_ids"] = campaign_ids
        state["fullstats_campaign_ids"] = fullstats_ids
        plan: list[dict[str, Any]] = []

        roster_scope: dict[str, Any] = {"mode": "status_roster"}
        if not await self._is_covered(
            cabinet=cabinet,
            dataset="ads_campaign_roster_snapshots",
            operation_id="wb_get_adv_promotion_count",
            date_from=date_from,
            date_to=date_to,
            scope=roster_scope,
        ):
            plan.append({
                "dataset": "ads_campaign_roster_snapshots",
                "operation_id": "wb_get_adv_promotion_count",
                "date_from": date_from,
                "date_to": date_to,
                "scope": roster_scope,
            })

        for item in _build_fullstats_plan(fullstats_ids, date_from, date_to):
            campaign_scope = {"campaign_ids": item["campaign_ids"]}
            if await self._is_covered(
                cabinet=cabinet,
                dataset="ads_campaign_daily",
                operation_id=item["operation_id"],
                date_from=item["date_from"],
                date_to=item["date_to"],
                scope=campaign_scope,
            ):
                continue
            plan.append({
                "dataset": "ads_campaign_daily",
                **item,
                "scope": campaign_scope,
            })

        state["fetch_plan"] = plan
        state["fetch_index"] = 0
        state["phase"] = "FETCH"
        state["status"] = "QUEUED"
        await self._save(state)
        await self._schedule(str(state["job_id"]), 0)

    async def set_failed(self, state: dict[str, Any], error: str) -> dict[str, Any]:
        state["status"] = "FAILED"
        state["last_error"] = str(error)[:1000]
        await self._save(state)
        await self._unschedule(str(state["job_id"]))
        return {
            "ok": False,
            "job_id": state["job_id"],
            "status": "FAILED",
            "phase": state.get("phase"),
            "error": state["last_error"],
        }

    async def set_waiting(self, state: dict[str, Any], seconds: float, error: str | None = None) -> dict[str, Any]:
        delay = max(1.0, float(seconds))
        state["status"] = "WAITING_RETRY"
        state["last_retry_after_seconds"] = delay
        state["last_error"] = None if error is None else str(error)[:1000]
        await self._save(state)
        await self._schedule(str(state["job_id"]), delay)
        return {
            "ok": True,
            "job_id": state["job_id"],
            "status": state["status"],
            "phase": state.get("phase"),
            "action": "waiting_retry",
            "retry_after_seconds": int(math.ceil(delay)),
            "last_error": state["last_error"],
        }

    @staticmethod
    def request_fingerprint(item: dict[str, Any]) -> str:
        return hashlib.sha256(_stable_json(item).encode("utf-8")).hexdigest()
