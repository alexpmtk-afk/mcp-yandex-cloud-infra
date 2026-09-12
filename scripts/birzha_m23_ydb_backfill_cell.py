from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import ydb

from birzha.application.historical_data import HistoricalDataService
from birzha.application.market_data import MarketDataService
from birzha.application.upstream_control import ProcessUpstreamControlPlane
from birzha.application.validation_readiness import required_price_ranges
from birzha.storage.ydb_historical_store import YdbHistoricalCandleStore
from birzha.storage.ydb_rate_gate import YdbSlotPacingGate

SCHEMA = "BIRZHA_M23_BACKFILL_CELL_V1"


def _write(path: str, payload: dict[str, object]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Resumable single-cell M23 YDB backfill")
    parser.add_argument("--connection-string-file", required=True)
    parser.add_argument("--token-file", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--timeframe", required=True, choices=("D1", "H1", "M15"))
    parser.add_argument("--validation-start", default="2021-01-01")
    parser.add_argument("--validation-end", default="2024-12-31")
    parser.add_argument("--app-sha", required=True)
    parser.add_argument("--workflow-sha", required=True)
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--attempts", type=int, default=3)
    args = parser.parse_args()

    ranges = {
        timeframe: (left, right)
        for timeframe, left, right in required_price_ranges(
            args.validation_start, args.validation_end
        )
    }
    left, right = ranges[args.timeframe]
    connection = Path(args.connection_string_file).read_text().strip()
    token = Path(args.token_file).read_text().strip()

    base: dict[str, object] = {
        "schema": SCHEMA,
        "app_sha": args.app_sha,
        "workflow_sha": args.workflow_sha,
        "symbol": args.symbol,
        "timeframe": args.timeframe,
        "from_date": left,
        "till_date": right,
    }

    driver = ydb.Driver(
        connection_string=connection,
        credentials=ydb.AccessTokenCredentials(token),
    )
    driver.wait(timeout=20, fail_fast=True)
    pool = ydb.QuerySessionPool(driver)
    try:
        control = ProcessUpstreamControlPlane(
            gate_factory=lambda provider_key: YdbSlotPacingGate(
                pool,
                provider_key=provider_key,
            ),
            require_distributed_gate=True,
        )
        market = MarketDataService.default(control_plane=control)
        history = HistoricalDataService(
            market_data=market,
            store=YdbHistoricalCandleStore(pool),
        )

        if history.is_range_verified(
            args.symbol,
            timeframe=args.timeframe,
            from_date=left,
            till_date=right,
        ):
            payload = {
                **base,
                "status": "PASS",
                "mode": "REUSED_VERIFIED_RANGE",
                "attempt": 0,
            }
            _write(args.artifact, payload)
            print(json.dumps(payload, sort_keys=True), flush=True)
            return 0

        last_error: Exception | None = None
        for attempt in range(1, args.attempts + 1):
            try:
                result = history.sync(
                    args.symbol,
                    timeframe=args.timeframe,
                    from_date=left,
                    till_date=right,
                )
                verified = history.is_range_verified(
                    args.symbol,
                    timeframe=args.timeframe,
                    from_date=left,
                    till_date=right,
                )
                if not verified:
                    raise RuntimeError("sync returned but current-version verification is still false")
                payload = {
                    **base,
                    "status": "PASS",
                    "mode": "SYNCED",
                    "attempt": attempt,
                    "result": result.to_dict(),
                }
                _write(args.artifact, payload)
                print(
                    json.dumps(
                        {
                            "status": "PASS",
                            "symbol": args.symbol,
                            "timeframe": args.timeframe,
                            "attempt": attempt,
                            "fetched_candles": result.fetched_candles,
                            "stored_candles": result.stored_candles,
                            "reused_verified_range": result.reused_verified_range,
                        },
                        sort_keys=True,
                    ),
                    flush=True,
                )
                return 0
            except Exception as exc:
                last_error = exc
                interim = {
                    **base,
                    "status": "RETRY" if attempt < args.attempts else "ERROR",
                    "attempt": attempt,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:2000],
                }
                _write(args.artifact, interim)
                print(json.dumps(interim, sort_keys=True), flush=True)
                if attempt < args.attempts:
                    time.sleep(min(60, attempt * 15))

        assert last_error is not None
        return 2
    finally:
        pool.stop()
        driver.stop(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
