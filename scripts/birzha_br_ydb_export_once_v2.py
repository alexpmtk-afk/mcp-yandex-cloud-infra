from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import ydb


def _rows(result):
    out = []
    for part in result or []:
        rows = getattr(part, "rows", None)
        if rows:
            out.extend(rows)
    return out


def _get(row, key: str):
    if isinstance(row, dict):
        return row.get(key)
    try:
        return row[key]
    except Exception:
        return getattr(row, key, None)


def _utf8(value: str):
    return (value, ydb.PrimitiveType.Utf8)


def _execute(pool, query: str, params: dict[str, object]):
    return pool.execute_with_retries(
        query,
        params,
        retry_settings=ydb.RetrySettings(idempotent=True),
    )


def main() -> int:
    p = argparse.ArgumentParser(description="Read-only BR D1 export from YDB")
    p.add_argument("--connection-string-file", required=True)
    p.add_argument("--token-file", required=True)
    p.add_argument("--from-date", default="2021-01-01")
    p.add_argument("--till-date", default="2024-12-31")
    p.add_argument("--csv", required=True)
    p.add_argument("--summary", required=True)
    args = p.parse_args()

    connection = Path(args.connection_string_file).read_text(encoding="utf-8").strip()
    token = Path(args.token_file).read_text(encoding="utf-8").strip()
    if not connection or not token:
        raise RuntimeError("YDB connection/token is empty")

    driver = ydb.Driver(
        connection_string=connection,
        credentials=ydb.AccessTokenCredentials(token),
    )
    driver.wait(timeout=20, fail_fast=True)
    pool = ydb.QuerySessionPool(driver)
    try:
        all_sessions_result = _execute(
            pool,
            """
            DECLARE $from_date AS Utf8;
            DECLARE $till_date AS Utf8;
            SELECT symbol, trade_date, secid FROM `historical_candles_sessions`
            WHERE trade_date>=$from_date AND trade_date<=$till_date
            ORDER BY symbol, trade_date, secid;
            """,
            {
                "$from_date": _utf8(args.from_date),
                "$till_date": _utf8(args.till_date),
            },
        )
        by_symbol: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for row in _rows(all_sessions_result):
            symbol = str(_get(row, "symbol") or "")
            trade_date = str(_get(row, "trade_date") or "")[:10]
            secid = str(_get(row, "secid") or "")
            if symbol and trade_date and secid:
                by_symbol[symbol].append((trade_date, secid))

        br_candidates = sorted(
            symbol for symbol, pairs in by_symbol.items()
            if symbol.upper().startswith("BR") and pairs
        )
        print(
            "BR_SESSION_KEY_CANDIDATES="
            + json.dumps(
                {symbol: len(by_symbol[symbol]) for symbol in br_candidates},
                ensure_ascii=False,
                sort_keys=True,
            ),
            flush=True,
        )
        if len(br_candidates) != 1:
            raise RuntimeError(
                f"expected exactly one populated BR session key, found {br_candidates}"
            )
        session_symbol = br_candidates[0]

        session_map: dict[str, set[str]] = defaultdict(set)
        for trade_date, secid in by_symbol[session_symbol]:
            session_map[trade_date].add(secid)
        ambiguous = {d: sorted(v) for d, v in session_map.items() if len(v) != 1}
        if ambiguous:
            raise RuntimeError(f"ambiguous BR contract map: {list(ambiguous.items())[:10]}")

        secids = sorted({next(iter(v)) for v in session_map.values()})
        candle_map: dict[tuple[str, str], dict[str, object]] = {}
        upper = (date.fromisoformat(args.till_date) + timedelta(days=1)).isoformat()
        for secid in secids:
            result = _execute(
                pool,
                """
                DECLARE $secid AS Utf8;
                DECLARE $timeframe AS Utf8;
                DECLARE $from_date AS Utf8;
                DECLARE $upper AS Utf8;
                SELECT begin, end_time, payload_json, source
                FROM `historical_candles`
                WHERE secid=$secid AND timeframe=$timeframe
                  AND begin>=$from_date AND begin<$upper
                ORDER BY begin;
                """,
                {
                    "$secid": _utf8(secid),
                    "$timeframe": _utf8("D1"),
                    "$from_date": _utf8(args.from_date),
                    "$upper": _utf8(upper),
                },
            )
            for row in _rows(result):
                payload = json.loads(str(_get(row, "payload_json")))
                candle = payload.get("candle") or {}
                begin = str(candle.get("begin") or _get(row, "begin") or "")
                key = (secid, begin[:10])
                if key in candle_map:
                    raise RuntimeError(f"duplicate D1 candle for {secid} {begin[:10]}")
                candle_map[key] = {
                    "candle": candle,
                    "source": str(_get(row, "source") or ""),
                }

        headers = [
            "record_key","calendar_date","trade_session_date","session_id",
            "bar_start_time","bar_end_time","available_at","available_at_confidence",
            "contract_code","open","high","low","close","volume","number_of_trades",
            "turnover","is_complete","source_interval","source_candles","source_id",
        ]
        output_rows: list[dict[str, object]] = []
        missing: list[str] = []
        for trade_date in sorted(session_map):
            secid = next(iter(session_map[trade_date]))
            item = candle_map.get((secid, trade_date))
            if item is None:
                missing.append(f"{trade_date}:{secid}")
                continue
            c = item["candle"]
            begin = str(c.get("begin") or "")
            end = str(c.get("end") or "")
            output_rows.append({
                "record_key": f"BR|D1|{secid}|{begin}",
                "calendar_date": trade_date,
                "trade_session_date": trade_date,
                "session_id": "",
                "bar_start_time": begin,
                "bar_end_time": end,
                "available_at": end,
                "available_at_confidence": "INFERRED",
                "contract_code": secid,
                "open": c.get("open"),
                "high": c.get("high"),
                "low": c.get("low"),
                "close": c.get("close"),
                "volume": c.get("volume"),
                "number_of_trades": "",
                "turnover": c.get("value"),
                "is_complete": bool(c.get("completed", True)),
                "source_interval": "D1",
                "source_candles": "",
                "source_id": item["source"],
            })
        if missing:
            raise RuntimeError(f"missing active-contract D1 candles: {missing[:20]} total={len(missing)}")

        target = Path(args.csv)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(output_rows)

        summary = {
            "schema": "BIRZHA_BR_YDB_EXPORT_V2",
            "mode": "READ_ONLY",
            "symbol": "BR",
            "session_symbol": session_symbol,
            "timeframe": "D1",
            "from_date": args.from_date,
            "till_date": args.till_date,
            "rows": len(output_rows),
            "contracts": len(secids),
            "first_date": output_rows[0]["calendar_date"] if output_rows else None,
            "last_date": output_rows[-1]["calendar_date"] if output_rows else None,
        }
        Path(args.summary).write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print("BR_EXPORT_SUMMARY=" + json.dumps(summary, ensure_ascii=False, sort_keys=True), flush=True)
        for i in range(0, len(output_rows), 100):
            print(
                "BR_EXPORT_CHUNK="
                + json.dumps(output_rows[i:i+100], ensure_ascii=False, separators=(",", ":")),
                flush=True,
            )
        return 0
    finally:
        pool.stop()
        driver.stop(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
