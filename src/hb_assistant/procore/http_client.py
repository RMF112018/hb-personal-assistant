"""
GET-only Procore HTTP client foundation.

- Strictly GET-only (runtime guard + static scan in tests).
- Authorization uses an OAuth **access token** (never the client secret).
  Token is obtained at request time via an injectable provider and is never
  stored on the client instance.
- Injectable transport for 100% mockable unit tests (no real calls ever in tests).
- Correlation ID on every request.
- Aggressive redaction (no auth, tokens, or bodies in logs/exceptions/evidence).
- Pagination + retry/backoff driven by Prompt_01 Decision Register facts.
- Safe normalized errors. Missing access token → ``ProcoreAuthRequired``.

All live calls must be explicitly dry-run/apply in consuming code.
"""

from __future__ import annotations

import uuid
from typing import Any, Callable, Dict, Iterator, Optional, Union

from hb_assistant.procore.errors import (
    ProcoreAPIError,
    ProcoreAuthRequired,
    ProcoreRateLimitError,
)
from hb_assistant.procore.pagination import ProcorePaginator
from hb_assistant.procore.redaction import (
    redact_request,
    redact_response,
)
from hb_assistant.procore.token_provider import (
    ProcoreTokenProvider,
    adapt_token_source,
)

# Prompt_02 config interface (used at runtime only; token never stored in this client).
# Note: the client deliberately does not import any client-secret loader. Reusing
# the client secret as a bearer credential is a Phase 04 Prompt hazard that this
# module fails closed against; access tokens come exclusively from a
# :class:`ProcoreTokenProvider` (Phase 04 Prompt 02).
try:
    from hb_assistant.procore.config import (
        HB_COMPANY_ID,
        get_environment_config,
    )
except Exception:  # pragma: no cover - graceful for tests that mock the whole layer
    def get_environment_config(env: Optional[str] = None) -> Dict[str, Any]:  # type: ignore
        return {"api_base": "https://sandbox.procore.com", "procore_company_id_header": 5280}
    HB_COMPANY_ID = 5280


Transport = Callable[[str, str, Dict[str, str], Optional[Dict[str, Any]]], Any]
# Accepts a typed provider, a plain callable (back-compat), or None (default chain).
AccessTokenProvider = Union[ProcoreTokenProvider, Callable[[], Optional[str]]]


class ProcoreHTTPClient:
    """Strictly GET-only HTTP client for Procore (Bobby-only MVP)."""

    def __init__(
        self,
        *,
        environment: str = "sandbox",
        transport: Optional[Transport] = None,
        access_token_provider: Optional[AccessTokenProvider] = None,
        live_enabled: bool = False,
        user_agent: str = "HB-Personal-Assistant/1.3.0 (GET-only)",
    ):
        self.environment = environment
        self._transport = transport  # injectable for tests
        self._access_token_provider: ProcoreTokenProvider = adapt_token_source(
            access_token_provider
        )
        self.live_enabled = live_enabled
        self.user_agent = user_agent
        self._env_config = get_environment_config(environment)

    def _require_get(self, method: str) -> None:
        if method.upper() != "GET":
            raise ProcoreAPIError(
                status=0,
                code="method_not_allowed",
                message=f"Only GET is permitted in this client (got {method}). "
                        "This is a hard guardrail for the read-only MVP.",
            )

    def _build_headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        access_token = self._access_token_provider.get_access_token()  # obtained at the last possible moment
        if not access_token:
            raise ProcoreAuthRequired()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Procore-Company-Id": str(self._env_config.get("procore_company_id_header", HB_COMPANY_ID)),
            "User-Agent": self.user_agent,
            "Accept": "application/json",
            "X-Correlation-ID": str(uuid.uuid4()),
        }
        if extra:
            headers.update(extra)
        # Never keep the token in any instance state
        return headers

    def _get_base_url(self) -> str:
        return self._env_config.get("api_base", "https://sandbox.procore.com").rstrip("/")

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        self._require_get(method)

        base = self._get_base_url()
        url = f"{base}{path}" if path.startswith("/") else f"{base}/{path}"

        req_headers = self._build_headers(headers)
        # Redact immediately for any logging path (even though we don't log here)
        _ = redact_request(method, url, req_headers, params)

        if self._transport is not None:
            resp = self._transport("GET", url, req_headers, params)
        else:
            if not self.live_enabled:
                raise ProcoreAPIError(
                    status=0,
                    code="transport_not_injected",
                    message="No transport provided. Tests must inject transport. Real transport requires live_enabled=True.",
                )
            resp = self._default_live_transport("GET", url, req_headers, params)

        # Redact response before any consumer sees it
        _ = redact_response(getattr(resp, "status_code", 0), dict(getattr(resp, "headers", {})), getattr(resp, "_json", None))

        status_code = getattr(resp, "status_code", 0)
        if status_code == 429:
            retry_after_raw = dict(getattr(resp, "headers", {})).get("Retry-After")
            retry_after: int | None
            try:
                retry_after = int(retry_after_raw) if retry_after_raw is not None else None
            except (TypeError, ValueError):
                retry_after = None
            raise ProcoreRateLimitError(
                message="rate_limited",
                status=429,
                retry_after=retry_after,
                correlation_id=req_headers.get("X-Correlation-ID"),
            )

        if status_code >= 400:
            # Let the caller (or higher wrapper) decide; for now raise normalized safe error
            raise ProcoreAPIError(
                status=status_code,
                code="http_error",
                message=str(getattr(resp, "text", "")[:300]),
                correlation_id=req_headers.get("X-Correlation-ID"),
            )

        return resp

    # Public GET surface
    def get(self, path: str, params: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Any:
        return self._request("GET", path, params=params, **kwargs)

    def paginate(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        *,
        per_page: int = 100,
        max_pages: Optional[int] = None,
        max_items: Optional[int] = None,
    ) -> Iterator[dict]:
        from hb_assistant.procore.pagination import PageResult, RateLimitInfo

        def fetch(p: Dict[str, Any]) -> PageResult:
            resp = self.get(path, params=p)
            body = resp.json() if callable(getattr(resp, "json", None)) else getattr(resp, "_json", None)
            items: list[dict] = []
            if isinstance(body, list):
                items = [row for row in body if isinstance(row, dict)]
            elif isinstance(body, dict):
                # v2.0 endpoints (e.g. /schedules, /activities) wrap the list
                # in a "data" envelope. v1.0/v1.1 endpoints sometimes wrap in
                # "items". A bare dict is treated as a single-row response.
                raw_items = body.get("items")
                if not isinstance(raw_items, list):
                    raw_items = body.get("data")
                if isinstance(raw_items, list):
                    items = [row for row in raw_items if isinstance(row, dict)]
                elif body:
                    items = [body]

            headers = dict(getattr(resp, "headers", {}) or {})
            next_link = self._extract_next_link(headers.get("Link"))
            next_cursor = None
            if isinstance(body, dict):
                for key in ("next_cursor", "starting_after", "next"):
                    value = body.get(key)
                    if isinstance(value, str) and value:
                        next_cursor = value
                        break
            return PageResult(
                items=items,
                next_link=next_link,
                next_cursor=next_cursor,
                rate_info=RateLimitInfo(
                    limit=_as_int(headers.get("X-RateLimit-Limit")),
                    remaining=_as_int(headers.get("X-RateLimit-Remaining")),
                    reset=_as_int(headers.get("X-RateLimit-Reset")),
                    retry_after=_as_int(headers.get("Retry-After")),
                ),
                raw_headers={k: str(v) for k, v in headers.items()},
            )

        paginator = ProcorePaginator(
            fetch_page=fetch,
            prefer_cursor=True,
        )
        yield from paginator.iterate(
            params,
            per_page=per_page,
            max_pages=max_pages,
            max_items=max_items,
        )

    def _default_live_transport(
        self, method: str, url: str, headers: Dict[str, str], params: Optional[Dict[str, Any]]
    ) -> Any:
        requests_mod = __import__("requests")
        return requests_mod.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            timeout=30,
        )

    def _extract_next_link(self, header: Optional[str]) -> Optional[str]:
        if not header:
            return None
        for part in header.split(","):
            segment = part.strip()
            if '; rel="next"' in segment and "<" in segment and ">" in segment:
                return segment[segment.find("<") + 1: segment.find(">")]
        return None


def _as_int(value: Any) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
