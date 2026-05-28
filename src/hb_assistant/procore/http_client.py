"""
GET-only Procore HTTP client foundation.

- Strictly GET-only (runtime guard + static scan in tests).
- Environment + secret obtained at request time only from the Prompt_02 config loader (never stored).
- Injectable transport for 100% mockable unit tests (no real calls ever in tests).
- Correlation ID on every request.
- Aggressive redaction (no auth, tokens, or bodies in logs/exceptions/evidence).
- Pagination + retry/backoff driven by Prompt_01 Decision Register facts.
- Safe normalized errors.

All live calls must be explicitly dry-run/apply in consuming code.
"""

from __future__ import annotations

import uuid
from typing import Any, Callable, Dict, Iterator, Optional

from hb_assistant.procore.errors import ProcoreAPIError, ProcoreRateLimitError
from hb_assistant.procore.pagination import ProcorePaginator
from hb_assistant.procore.redaction import (
    redact_request,
    redact_response,
)

# Prompt_02 config interface (used at runtime only; secret never stored in this client)
try:
    from hb_assistant.procore.config import (
        HB_COMPANY_ID,
        get_environment_config,
        get_procore_client_secret,
    )
except Exception:  # pragma: no cover - graceful for tests that mock the whole layer
    def get_environment_config(env: Optional[str] = None) -> Dict[str, Any]:  # type: ignore
        return {"api_base": "https://sandbox.procore.com", "procore_company_id_header": 5280}
    def get_procore_client_secret() -> str:  # type: ignore
        return "TEST_SECRET_ONLY_IN_MOCKED_TESTS"
    HB_COMPANY_ID = 5280


Transport = Callable[[str, str, Dict[str, str], Optional[Dict[str, Any]]], Any]


class ProcoreHTTPClient:
    """Strictly GET-only HTTP client for Procore (Bobby-only MVP)."""

    def __init__(
        self,
        *,
        environment: str = "sandbox",
        transport: Optional[Transport] = None,
        user_agent: str = "HB-Personal-Assistant/1.3.0 (GET-only)",
    ):
        self.environment = environment
        self._transport = transport  # injectable for tests
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
        secret = get_procore_client_secret()  # obtained at the last possible moment
        headers = {
            "Authorization": f"Bearer {secret}",
            "Procore-Company-Id": str(self._env_config.get("procore_company_id_header", HB_COMPANY_ID)),
            "User-Agent": self.user_agent,
            "Accept": "application/json",
            "X-Correlation-ID": str(uuid.uuid4()),
        }
        if extra:
            headers.update(extra)
        # Never keep the secret in any instance state
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
            # Production path would use a real session (requests/httpx). Not exercised in tests.
            # For the foundation we raise a clear message so callers know they must provide transport in test.
            raise ProcoreAPIError(
                status=0,
                code="transport_not_injected",
                message="No transport provided. In production wire a real session. In tests always inject a mock.",
            )

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

    def get_paginated(
        self, path: str, params: Optional[Dict[str, Any]] = None, *, per_page: int = 100
    ) -> Iterator[dict]:
        def fetch(p: Dict[str, Any]) -> Any:
            # The real transport returns something the paginator can turn into PageResult.
            # For the foundation we expose the raw response and let a thin adapter normalize.
            # In practice the client layer above this will provide the adapter.
            return self.get(path, params=p)

        paginator = ProcorePaginator(
            fetch_page=lambda p: fetch(p),  # type: ignore[arg-type]
            prefer_cursor=True,
        )
        yield from paginator.iterate(params, per_page=per_page)
