from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any

import httpx

import compare_marketplaces_v1_v3 as base


# The first diagnostic treated a transient Apps Script 404 as fatal, while the
# real Marketplaces v3 client retries 404/5xx. Make the comparison equivalent
# to production behaviour before judging v3.
async def v3_call_with_production_retries(
    self: base.V3,
    action: str,
    *,
    expect_ok: bool = True,
    **payload: Any,
) -> dict[str, Any]:
    statuses = {404, 408, 425, 429, 500, 502, 503, 504}
    last_exc: BaseException | None = None
    for attempt in range(1, 4):
        try:
            response = await self.client.post(
                self.url,
                json={"secret": self.secret, "action": action, **payload},
                headers={"Accept": "application/json"},
            )
            if response.status_code in statuses and attempt < 3:
                await asyncio.sleep(0.75 * attempt)
                continue
            response.raise_for_status()
            data = response.json()
            if expect_ok and data.get("ok") is not True:
                if bool(data.get("retryable")) and attempt < 3:
                    await asyncio.sleep(0.75 * attempt)
                    continue
                raise RuntimeError(f"v3 {action} rejected: {data.get('error')}")
            return data
        except (httpx.HTTPError, asyncio.TimeoutError) as exc:
            last_exc = exc
            if attempt < 3:
                await asyncio.sleep(0.75 * attempt)
                continue
            raise
    raise RuntimeError(type(last_exc).__name__ if last_exc else "v3 transport failed")


base.V3.call = v3_call_with_production_retries


# Protocol v1 metadata_by_id currently returns metadata under result.file.
# The first diagnostic compared the envelope rather than the nested file and
# therefore reported a false negative even though promotion/download succeeded.
_original_metadata = base.GoogleDriveBridgeClient.metadata_by_id


async def flattened_metadata(self, file_id: str) -> dict[str, Any]:
    result = await _original_metadata(self, file_id)
    nested = result.get("file") if isinstance(result, dict) else None
    return dict(nested) if isinstance(nested, dict) else dict(result)


base.GoogleDriveBridgeClient.metadata_by_id = flattened_metadata


# Track replay identity without exposing bearer-like session URIs. Safe replay
# does not require byte-identical session URLs if it remains bound to the same
# staging file; record both file/staging identity and a one-way URI fingerprint.
_original_resumable_start = base.GoogleDriveBridgeClient.resumable_start
_replay_records: list[dict[str, str]] = []


async def tracked_resumable_start(self, *args, **kwargs) -> dict[str, Any]:
    result = await _original_resumable_start(self, *args, **kwargs)
    uri = str(result.get("session_uri") or "")
    _replay_records.append(
        {
            "file_id": str(result.get("file_id") or ""),
            "staging_filename": str(result.get("staging_filename") or ""),
            "session_fingerprint": hashlib.sha256(uri.encode("utf-8")).hexdigest()[:16] if uri else "",
        }
    )
    return result


base.GoogleDriveBridgeClient.resumable_start = tracked_resumable_start


async def main() -> None:
    await base.main()
    first_two = _replay_records[:2]
    safe_same_target = (
        len(first_two) == 2
        and bool(first_two[0]["file_id"])
        and first_two[0]["file_id"] == first_two[1]["file_id"]
        and first_two[0]["staging_filename"] == first_two[1]["staging_filename"]
    )
    print(
        "V1_RESUMABLE_REPLAY_IDENTITY="
        + json.dumps(
            {
                "safe_same_target": safe_same_target,
                "same_session_fingerprint": (
                    len(first_two) == 2
                    and first_two[0]["session_fingerprint"] == first_two[1]["session_fingerprint"]
                ),
                "records": first_two,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
