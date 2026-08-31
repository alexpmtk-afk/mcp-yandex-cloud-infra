"""Async HTTP client shared by every marketplace server.

Responsibilities:
- Load credentials from environment variables (never from code/args).
- Build service-specific auth headers.
- Execute a request described by an EndpointSpec (or a raw path).
- Retry on 429 with exponential backoff, honouring Retry-After.
- Return parsed JSON on success, or the canonical error envelope on failure.

Service differences (WB vs Ozon) are isolated in a ServiceConfig object so the
request/backoff/pagination logic is written exactly once.
"""
from __future__ import annotations

import asyncio
import email.utils
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import httpx

from .credentials import CredentialStore
from .errors import classify_status, error_from_exception, make_error
from .rate_limit import (
    GlobalRateController,
    RateLimitUnavailable,
    build_rules,
    key_prefix,
)
from .registry import EndpointSpec

DEFAULT_TIMEOUT = 30.0
MAX_RETRIES = 4
BACKOFF_BASE = 1.5


@dataclass
class ServiceConfig:
    name: str
    scheme: str
    fields: list[str]
    env_map: dict[str, str]
    build_headers: Callable[[dict[str, str]], dict[str, str]]
    store: CredentialStore = field(default_factory=CredentialStore)
    user_agent: str = "marketplace-mcp/0.1 (+https://github.com/)"
    allowed_host_suffixes: list[str] = field(default_factory=list)
    token_url: str = ""
    oauth_id_field: str = "client_id"
    oauth_secret_field: str = "client_secret"
    whoami: Optional[tuple[str, list[str]]] = None

    @property
    def is_oauth(self) -> bool:
        return bool(self.token_url)

    def resolve_creds(self) -> tuple[dict[str, str], str]:
        return self.store.resolve(self.name, self.fields, self.env_map)

    def missing_creds(self) -> list[str]:
        return self.store.missing(self.name, self.fields, self.env_map)

    def host_allowed(self, host: str) -> bool:
        if not self.allowed_host_suffixes:
            return True
        h = host.strip().lower()
        for pre in ("https://", "http://"):
            if h.startswith(pre):
                h = h[len(pre):]
        h = h.strip("/").split("/")[0].split(":")[0]
        for suf in self.allowed_host_suffixes:
            bare = suf.lstrip(".")
            if h == bare or h.endswith("." + bare):
                return True
        return False


def _parse_retry_after(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        pass
    try:
        dt = email.utils.parsedate_to_datetime(value)
    except (ValueError, TypeError):
        return None
    if dt is None:
        return None
    return max(0.0, dt.timestamp() - time.time())


def _marketplace_retry_delay(resp: httpx.Response, attempt: int) -> float:
    candidates = [
        _parse_retry_after(resp.headers.get("Retry-After")),
        _parse_retry_after(resp.headers.get("X-Ratelimit-Retry")),
    ]
    valid = [value for value in candidates if value is not None]
    return max(valid) if valid else BACKOFF_BASE * (2**attempt)


TOKEN_EXPIRY_SKEW = 60.0


class MarketplaceClient:
    def __init__(self, config: ServiceConfig,
                 rate_controller: Optional[GlobalRateController] = None):
        self.config = config
        self.rate_controller = rate_controller or GlobalRateController()
        self._tokens: dict[str, tuple[str, float]] = {}
        self._token_lock = asyncio.Lock()

    @staticmethod
    def _creds_key(config: ServiceConfig, creds: dict[str, str]) -> str:
        raw = json.dumps({f: creds.get(f, "") for f in config.fields}, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _creds_or_error(self) -> tuple[Optional[dict[str, str]], Optional[dict]]:
        creds, _source = self.config.resolve_creds()
        missing = [f for f in self.config.fields if not creds.get(f)]
        if missing:
            return None, make_error(
                "auth",
                f"Missing credentials for fields: {', '.join(missing)}. "
                f"Add a cabinet with {self.config.name}_add_cabinet, run install.py, "
                "or set the matching environment variables.",
                retryable=False,
            )
        return creds, None

    async def _ensure_token(self, creds: dict[str, str]) -> tuple[Optional[str], Optional[dict]]:
        key = self._creds_key(self.config, creds)
        now = time.monotonic()
        cached = self._tokens.get(key)
        if cached and now < cached[1]:
            return cached[0], None
        async with self._token_lock:
            cached = self._tokens.get(key)
            now = time.monotonic()
            if cached and now < cached[1]:
                return cached[0], None
            return await self._fetch_token(creds, key)

    async def _fetch_token(self, creds: dict[str, str],
                             key: str) -> tuple[Optional[str], Optional[dict]]:
        cfg = self.config
        payload = {
            "client_id": creds.get(cfg.oauth_id_field, ""),
            "client_secret": creds.get(cfg.oauth_secret_field, ""),
            "grant_type": "client_credentials",
        }
        rules = build_rules(
            service=cfg.name, cabinet_key=key, host=cfg.token_url,
            operation_id="oauth_token",
        )
        try:
            await self.rate_controller.acquire(rules)
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                resp = await client.post(
                    cfg.token_url,
                    json=payload,
                    headers={"User-Agent": cfg.user_agent,
                             "Content-Type": "application/json",
                             "Accept": "application/json"},
                )
        except RateLimitUnavailable as exc:
            return None, make_error(
                "rate_limit", f"Global request controller unavailable: {exc}",
                operation_id="oauth_token", endpoint=cfg.token_url,
                retryable=True,
            )
        except Exception as exc:
            return None, error_from_exception(
                exc, operation_id="oauth_token", endpoint=cfg.token_url)

        if not resp.is_success:
            etype, retryable = classify_status(resp.status_code)
            return None, make_error(
                etype,
                f"{cfg.name.upper()} token endpoint returned {resp.status_code}: "
                f"{_short_body(resp)}",
                code=resp.status_code,
                operation_id="oauth_token",
                endpoint=cfg.token_url,
                retryable=retryable,
            )
        body = _parse_body(resp)
        if not isinstance(body, dict) or not body.get("access_token"):
            return None, make_error(
                "auth",
                f"{cfg.name.upper()} token response had no access_token: {str(body)[:200]}",
                operation_id="oauth_token", endpoint=cfg.token_url, retryable=False,
            )
        token = body["access_token"]
        try:
            ttl = float(body.get("expires_in", 1800))
        except (TypeError, ValueError):
            ttl = 1800.0
        self._tokens[key] = (token, time.monotonic() + max(0.0, ttl - TOKEN_EXPIRY_SKEW))
        return token, None

    def _invalidate_token(self, creds: dict[str, str]) -> None:
        self._tokens.pop(self._creds_key(self.config, creds), None)

    def _url(self, host: str, path: str) -> str:
        h = host.strip()
        for pre in ("https://", "http://"):
            if h.startswith(pre):
                h = h[len(pre):]
        h = h.strip("/")
        return f"{self.config.scheme}://{h}{path}"

    async def request(
        self,
        method: str,
        host: str,
        path: str,
        *,
        query: Optional[dict[str, Any]] = None,
        json_body: Optional[Any] = None,
        operation_id: Optional[str] = None,
        rate_limit: str = "",
        rate_scope: str = "",
        timeout: float = DEFAULT_TIMEOUT,
        creds_override: Optional[dict[str, str]] = None,
    ) -> dict:
        if not isinstance(path, str) or not path.startswith("/"):
            return make_error(
                "invalid_params",
                f"path must be a string beginning with '/', got {path!r}. "
                "A path that does not start with '/' can smuggle a different host "
                "onto the URL — refused before sending.",
                operation_id=operation_id, endpoint=path, retryable=False,
            )
        if not self.config.host_allowed(host):
            return make_error(
                "forbidden",
                f"Host {host!r} is not in the {self.config.name} allowlist "
                f"({', '.join(self.config.allowed_host_suffixes)}). Refused before "
                "sending so credentials never leave for an untrusted host.",
                operation_id=operation_id, endpoint=path, retryable=False,
            )
        if creds_override is not None:
            creds, err = creds_override, None
        else:
            creds, err = self._creds_or_error()
        if err:
            return err
        cabinet_key = self._creds_key(self.config, creds or {})
        rules = build_rules(
            service=self.config.name,
            cabinet_key=cabinet_key,
            host=host,
            operation_id=operation_id,
            scope=rate_scope,
            catalog_rate_limit=rate_limit,
        )
        headers = {"User-Agent": self.config.user_agent, "Accept": "application/json"}
        if self.config.is_oauth:
            token, terr = await self._ensure_token(creds or {})
            if terr:
                return terr
            headers["Authorization"] = f"Bearer {token}"
            headers["Content-Type"] = "application/json"
        else:
            headers.update(self.config.build_headers(creds or {}))
        url = self._url(host, path)

        attempt = 0
        while True:
            try:
                await self.rate_controller.acquire(rules)
            except RateLimitUnavailable as exc:
                return make_error(
                    "rate_limit",
                    f"Global request controller unavailable; HTTP request was not sent: {exc}",
                    operation_id=operation_id, endpoint=path, retryable=True,
                )
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.request(
                        method.upper(), url, params=query or None,
                        json=json_body if json_body is not None else None,
                        headers=headers,
                    )
            except Exception as exc:
                connect_phase = isinstance(
                    exc, (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout))
                read_phase = isinstance(exc, (httpx.ReadTimeout, httpx.WriteTimeout))
                safe_verb = method.upper() in ("GET", "HEAD")
                if attempt < MAX_RETRIES and (connect_phase or (read_phase and safe_verb)):
                    await asyncio.sleep(BACKOFF_BASE * (2**attempt))
                    attempt += 1
                    continue
                return error_from_exception(exc, operation_id=operation_id, endpoint=path)

            if resp.status_code == 401 and self.config.is_oauth:
                self._invalidate_token(creds or {})

            if resp.status_code == 429 and attempt < MAX_RETRIES:
                delay = min(_marketplace_retry_delay(resp, attempt), 3600.0)
                try:
                    await self.rate_controller.defer(rules, delay)
                except RateLimitUnavailable as exc:
                    return make_error(
                        "rate_limit",
                        f"Marketplace returned 429 and the shared cooldown could not be stored: {exc}",
                        code=429, operation_id=operation_id, endpoint=path,
                        retryable=True, retry_after_seconds=delay,
                    )
                attempt += 1
                continue

            if resp.is_success:
                return {"ok": True, "status": resp.status_code, "data": _parse_body(resp)}

            etype, retryable = classify_status(resp.status_code)
            msg = f"{self.config.name.upper()} API returned {resp.status_code}: {_short_body(resp)}"
            if etype == "auth":
                msg += (f" — the key may be expired or revoked. Rotate it: "
                        f"{self.config.name}_set_key (chat) or re-run the installer.")
            return make_error(
                etype, msg, code=resp.status_code,
                operation_id=operation_id, endpoint=path, retryable=retryable,
                retry_after_seconds=(
                    _marketplace_retry_delay(resp, attempt)
                    if resp.status_code == 429 else
                    _parse_retry_after(resp.headers.get("Retry-After"))
                ),
                details=_capped_details(resp),
            )

    async def rate_limit_status(self) -> dict:
        creds, source = self.config.resolve_creds()
        missing = [field for field in self.config.fields if not creds.get(field)]
        if missing:
            return make_error(
                "auth", f"Missing credentials for fields: {', '.join(missing)}.",
                operation_id="rate_limit_status", retryable=False,
            )
        cabinet_key = self._creds_key(self.config, creds)
        global_rule = build_rules(
            service=self.config.name, cabinet_key=cabinet_key, host="",
            operation_id="rate_limit_status",
        )[0]
        try:
            state = await self.rate_controller.snapshot(key_prefix(self.config.name, cabinet_key))
        except RateLimitUnavailable as exc:
            return make_error(
                "rate_limit", f"Global request controller unavailable: {exc}",
                operation_id="rate_limit_status", retryable=True,
            )
        return {
            "ok": True,
            "service": self.config.name,
            "credential_source": source,
            "configured_global_rps": round(1.0 / global_rule.interval_seconds, 3),
            **state,
        }

    async def call_spec(
        self,
        spec: EndpointSpec,
        *,
        path_values: Optional[dict[str, Any]] = None,
        query: Optional[dict[str, Any]] = None,
        json_body: Optional[Any] = None,
        creds_override: Optional[dict[str, str]] = None,
    ) -> dict:
        try:
            path = spec.render_path(path_values or {})
        except KeyError as missing:
            return make_error(
                "invalid_params",
                f"Missing path parameter '{missing.args[0]}' for {spec.operation_id}. "
                f"Path template: {spec.path}",
                operation_id=spec.operation_id, endpoint=spec.path,
            )
        return await self.request(
            spec.method, spec.host, path, query=query, json_body=json_body,
            operation_id=spec.operation_id, rate_limit=spec.rate_limit,
            rate_scope=spec.scope, creds_override=creds_override,
        )


def _parse_body(resp: httpx.Response) -> Any:
    ctype = resp.headers.get("Content-Type", "")
    if "application/json" in ctype:
        try:
            return resp.json()
        except Exception:
            return resp.text
    if ctype.startswith(("image/", "application/pdf")):
        return {"_binary": True, "content_type": ctype, "bytes": len(resp.content)}
    return resp.text


def _short_body(resp: httpx.Response, limit: int = 300) -> str:
    body = _parse_body(resp)
    s = body if isinstance(body, str) else str(body)
    return s[:limit]


def _capped_details(resp: httpx.Response, limit: int = 2000) -> Any:
    body = _parse_body(resp)
    if isinstance(body, str) and len(body) > limit:
        return body[:limit] + f"... [truncated {len(body) - limit} chars]"
    return body
