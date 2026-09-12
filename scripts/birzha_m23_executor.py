from __future__ import annotations

import os
import traceback
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
import uvicorn

from birzha.application.historical_data import HistoricalDataService
from birzha.application.market_data import MarketDataService
from birzha.application.upstream_control import ProcessUpstreamControlPlane
from birzha.application.validation_readiness import required_price_ranges
from birzha.storage.ydb_historical_store import YdbHistoricalCandleStore
from birzha.storage.ydb_rate_gate import YdbSlotPacingGate
from birzha.storage.ydb_state import YdbRuntime

ALLOWED_SYMBOLS = frozenset({"SBER", "Si", "BR", "GOLD", "IMOEX", "RTSI"})
ALLOWED_TIMEFRAMES = frozenset({"D1", "H1", "M15"})
APP_SHA = os.environ.get("EXECUTOR_APP_SHA", "").strip()
VALIDATION_START = os.environ.get("VALIDATION_START", "2021-01-01")
VALIDATION_END = os.environ.get("VALIDATION_END", "2024-12-31")
YDB_CONNECTION_STRING = os.environ.get("YDB_CONNECTION_STRING", "").strip()

if not APP_SHA:
    raise RuntimeError("EXECUTOR_APP_SHA is required")
if not YDB_CONNECTION_STRING:
    raise RuntimeError("YDB_CONNECTION_STRING is required")

_runtime = YdbRuntime.connect(YDB_CONNECTION_STRING, wait_timeout=20.0)
_control = ProcessUpstreamControlPlane(
    gate_factory=lambda provider_key: YdbSlotPacingGate(
        _runtime.pool,
        provider_key=provider_key,
    ),
    require_distributed_gate=True,
)
_market = MarketDataService.default(control_plane=_control)
_history = HistoricalDataService(
    market_data=_market,
    store=YdbHistoricalCandleStore(_runtime.pool),
)
_ranges = {
    timeframe: (left, right)
    for timeframe, left, right in required_price_ranges(
        VALIDATION_START,
        VALIDATION_END,
    )
}


def _error(exc: Exception, *, status_code: int = 500) -> JSONResponse:
    return JSONResponse(
        {
            "status": "ERROR",
            "app_sha": APP_SHA,
            "error_type": type(exc).__name__,
            "error": str(exc)[:2000],
        },
        status_code=status_code,
    )


async def health(_: Request) -> JSONResponse:
    return JSONResponse(
        {
            "status": "ok",
            "executor": "BIRZHA_M23_HISTORICAL_SYNC_V1",
            "app_sha": APP_SHA,
            "mode": "PRIVATE_ONE_SHOT",
        }
    )


async def run_cell(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
        symbol = str(payload.get("symbol") or "")
        timeframe = str(payload.get("timeframe") or "")
        if symbol not in ALLOWED_SYMBOLS:
            raise ValueError(f"unsupported symbol: {symbol!r}")
        if timeframe not in ALLOWED_TIMEFRAMES:
            raise ValueError(f"unsupported timeframe: {timeframe!r}")
        left, right = _ranges[timeframe]

        if _history.is_range_verified(
            symbol,
            timeframe=timeframe,
            from_date=left,
            till_date=right,
        ):
            return JSONResponse(
                {
                    "status": "PASS",
                    "mode": "REUSED_VERIFIED_RANGE",
                    "app_sha": APP_SHA,
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "from_date": left,
                    "till_date": right,
                }
            )

        result = _history.sync(
            symbol,
            timeframe=timeframe,
            from_date=left,
            till_date=right,
        )
        verified = _history.is_range_verified(
            symbol,
            timeframe=timeframe,
            from_date=left,
            till_date=right,
        )
        if not verified:
            raise RuntimeError(
                "sync completed but current-version verification marker is absent"
            )
        return JSONResponse(
            {
                "status": "PASS",
                "mode": "SYNCED",
                "app_sha": APP_SHA,
                "symbol": symbol,
                "timeframe": timeframe,
                "from_date": left,
                "till_date": right,
                "fetched_candles": result.fetched_candles,
                "stored_candles": result.stored_candles,
                "reused_verified_range": result.reused_verified_range,
                "contract_count": len(result.contracts),
            }
        )
    except ValueError as exc:
        return _error(exc, status_code=400)
    except Exception as exc:
        traceback.print_exc()
        return _error(exc)


app = Starlette(
    routes=[
        Route("/healthz", health, methods=["GET"]),
        Route("/run", run_cell, methods=["POST"]),
    ]
)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
