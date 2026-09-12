from __future__ import annotations

import argparse
import json
import time
from datetime import date, timedelta
from pathlib import Path

import ydb

from birzha.application.historical_data import _verification_symbol
from birzha.application.market_data import is_futures_root_symbol
from birzha.application.validation_readiness import (
    CORE_VALIDATION_SYMBOLS,
    required_price_ranges,
)
from birzha.storage.ydb_historical_store import _row_value, _rows, _utf8

MINIMUM_ACCEPTANCE_OBSERVATIONS = 20
HORIZONS = (5, 10, 20)
SCHEMA = "BIRZHA_M23_YDB_READONLY_AUDIT_V2"


def _execute(pool: ydb.QuerySessionPool, query: str, parameters: dict[str, object]):
    last_error: Exception | None = None
    for attempt in range(1, 7):
        try:
            return pool.execute_with_retries(
                query,
                parameters,
                retry_settings=ydb.RetrySettings(idempotent=True),
            )
        except Exception as exc:
            last_error = exc
            print(
                f"YDB_READ_RETRY attempt={attempt} error={type(exc).__name__}",
                flush=True,
            )
            if attempt == 6:
                raise
            time.sleep(min(30, 2**attempt))
    raise RuntimeError("unreachable") from last_error


def _is_verified(
    pool: ydb.QuerySessionPool,
    symbol: str,
    timeframe: str,
    from_date: str,
    till_date: str,
) -> bool:
    result = _execute(
        pool,
        """
        DECLARE $symbol AS Utf8;
        DECLARE $timeframe AS Utf8;
        DECLARE $from_date AS Utf8;
        DECLARE $till_date AS Utf8;
        SELECT 1 AS found FROM `historical_candles_verified_ranges`
        WHERE symbol=$symbol AND timeframe=$timeframe
          AND from_date<=$from_date AND till_date>=$till_date
        LIMIT 1;
        """,
        {
            "$symbol": _utf8(symbol),
            "$timeframe": _utf8(timeframe),
            "$from_date": _utf8(from_date),
            "$till_date": _utf8(till_date),
        },
    )
    return bool(_rows(result))


def _sessions_verified(
    pool: ydb.QuerySessionPool,
    symbol: str,
    from_date: str,
    till_date: str,
) -> bool:
    result = _execute(
        pool,
        """
        DECLARE $symbol AS Utf8;
        DECLARE $from_date AS Utf8;
        DECLARE $till_date AS Utf8;
        SELECT 1 AS found FROM `historical_candles_session_verified_ranges`
        WHERE symbol=$symbol AND from_date<=$from_date AND till_date>=$till_date
        LIMIT 1;
        """,
        {
            "$symbol": _utf8(symbol),
            "$from_date": _utf8(from_date),
            "$till_date": _utf8(till_date),
        },
    )
    return bool(_rows(result))


def _session_contracts(
    pool: ydb.QuerySessionPool,
    symbol: str,
    from_date: str,
    till_date: str,
) -> tuple[tuple[str, str], ...]:
    result = _execute(
        pool,
        """
        DECLARE $symbol AS Utf8;
        DECLARE $from_date AS Utf8;
        DECLARE $till_date AS Utf8;
        SELECT trade_date, secid FROM `historical_candles_sessions`
        WHERE symbol=$symbol AND trade_date>=$from_date AND trade_date<=$till_date
        ORDER BY trade_date, secid;
        """,
        {
            "$symbol": _utf8(symbol),
            "$from_date": _utf8(from_date),
            "$till_date": _utf8(till_date),
        },
    )
    return tuple(
        (str(_row_value(row, "trade_date")), str(_row_value(row, "secid")))
        for row in _rows(result)
    )


def _capacity(
    pool: ydb.QuerySessionPool,
    symbol: str,
    from_date: str,
    till_date: str,
    *,
    step_sessions: int,
    max_points: int,
) -> dict[str, object]:
    verification_symbol = _verification_symbol(
        symbol,
        "D1",
        is_root=is_futures_root_symbol(symbol),
    )
    if not _sessions_verified(pool, verification_symbol, from_date, till_date):
        return {
            "status": "SESSION_RANGE_NOT_VERIFIED",
            "sessions": 0,
            "mature_raw_candidates": 0,
            "non_overlapping_observations": {str(h): 0 for h in HORIZONS},
        }

    pairs = _session_contracts(pool, verification_symbol, from_date, till_date)
    grouped: dict[str, set[str]] = {}
    for trade_date, secid in pairs:
        grouped.setdefault(trade_date[:10], set()).add(secid)
    sessions = sorted(grouped)
    ambiguous = [item for item in sessions if len(grouped[item]) != 1]
    if ambiguous:
        return {
            "status": "AMBIGUOUS_CONTRACT_MAP",
            "invalid_dates": ambiguous[:20],
        }

    longest = max(HORIZONS)
    mature = 0
    for index in range(0, max(0, len(sessions) - longest), step_sessions):
        window = sessions[index : index + longest + 1]
        secids = {next(iter(grouped[item])) for item in window}
        if len(secids) != 1:
            continue
        mature += 1
        if mature >= max_points:
            break

    observations: dict[str, int] = {}
    for horizon in HORIZONS:
        stride = max(1, (horizon + step_sessions - 1) // step_sessions)
        observations[str(horizon)] = (mature + stride - 1) // stride
    return {
        "status": "COMPUTED",
        "sessions": len(sessions),
        "mature_raw_candidates": mature,
        "non_overlapping_observations": observations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only M23 YDB readiness audit")
    parser.add_argument("--connection-string-file", required=True)
    parser.add_argument("--token-file", required=True)
    parser.add_argument("--validation-start", default="2021-01-01")
    parser.add_argument("--split-date", default="2022-12-31")
    parser.add_argument("--validation-end", default="2024-12-31")
    parser.add_argument("--step-sessions", type=int, default=5)
    parser.add_argument("--max-points", type=int, default=80)
    parser.add_argument("--app-sha", required=True)
    parser.add_argument("--workflow-sha", required=True)
    parser.add_argument("--artifact", required=True)
    args = parser.parse_args()

    if not args.validation_start < args.split_date < args.validation_end:
        raise ValueError("expected validation_start < split_date < validation_end")
    if args.step_sessions <= 0 or args.max_points <= 0:
        raise ValueError("step_sessions and max_points must be positive")

    connection = Path(args.connection_string_file).read_text().strip()
    token = Path(args.token_file).read_text().strip()
    driver = ydb.Driver(
        connection_string=connection,
        credentials=ydb.AccessTokenCredentials(token),
    )
    driver.wait(timeout=20, fail_fast=True)
    pool = ydb.QuerySessionPool(driver)
    try:
        requirements: list[dict[str, object]] = []
        for symbol in CORE_VALIDATION_SYMBOLS:
            root = is_futures_root_symbol(symbol)
            for timeframe, left, right in required_price_ranges(
                args.validation_start, args.validation_end
            ):
                verification_symbol = _verification_symbol(
                    symbol,
                    timeframe,
                    is_root=root,
                )
                price_ok = _is_verified(
                    pool, verification_symbol, timeframe, left, right
                )
                session_ok = (
                    True
                    if timeframe != "D1"
                    else _sessions_verified(pool, verification_symbol, left, right)
                )
                requirements.append(
                    {
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "from_date": left,
                        "till_date": right,
                        "verification_symbol": verification_symbol,
                        "price_verified": price_ok,
                        "session_verified": session_ok,
                        "verified": bool(price_ok and session_ok),
                    }
                )

        holdout_start = (
            date.fromisoformat(args.split_date) + timedelta(days=1)
        ).isoformat()
        periods = {
            "development": (args.validation_start, args.split_date),
            "holdout": (holdout_start, args.validation_end),
        }
        capacity = {
            period: {
                symbol: _capacity(
                    pool,
                    symbol,
                    left,
                    right,
                    step_sessions=args.step_sessions,
                    max_points=args.max_points,
                )
                for symbol in CORE_VALIDATION_SYMBOLS
            }
            for period, (left, right) in periods.items()
        }

        missing = [item for item in requirements if not bool(item["verified"])]
        shortfall: dict[str, object] = {}
        for period, data in capacity.items():
            period_shortfall: dict[str, object] = {}
            for symbol, item in data.items():
                observations = item.get("non_overlapping_observations") or {}
                below = {
                    str(horizon): int(count)
                    for horizon, count in observations.items()
                    if int(count) < MINIMUM_ACCEPTANCE_OBSERVATIONS
                }
                if item.get("status") != "COMPUTED" or below:
                    period_shortfall[symbol] = {
                        "status": item.get("status"),
                        "below_20": below,
                    }
            if period_shortfall:
                shortfall[period] = period_shortfall

        payload = {
            "schema": SCHEMA,
            "mode": "READ_ONLY",
            "app_sha": args.app_sha,
            "workflow_sha": args.workflow_sha,
            "validation_start": args.validation_start,
            "split_date": args.split_date,
            "validation_end": args.validation_end,
            "required": len(requirements),
            "verified": len(requirements) - len(missing),
            "missing_count": len(missing),
            "readiness_status": "READY" if not missing else "NOT_READY",
            "requirements": requirements,
            "capacity": capacity,
            "capacity_shortfall": shortfall,
            "capacity_status": "READY" if not shortfall else "INSUFFICIENT_DATA",
        }
        target = Path(args.artifact)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "app_sha": args.app_sha,
                    "required": len(requirements),
                    "verified": len(requirements) - len(missing),
                    "missing_count": len(missing),
                    "missing": [
                        f"{item['symbol']}:{item['timeframe']}" for item in missing
                    ],
                    "readiness_status": payload["readiness_status"],
                    "capacity_status": payload["capacity_status"],
                    "capacity_shortfall": shortfall,
                },
                sort_keys=True,
                ensure_ascii=False,
            ),
            flush=True,
        )
        return 0
    finally:
        pool.stop()
        driver.stop(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
