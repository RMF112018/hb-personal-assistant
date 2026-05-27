"""
Reusable pagination + retry/backoff helper for the GET-only Procore HTTP client.

Design directly from subagent exploration (019e6b5b-021c-79c3-9f75-23da9743c694) grounded in the
Prompt_01 augmented Decision Register (Link headers primary, cursor for V2, X-RateLimit-*/Retry-After,
dual rate windows, V1 vs V2 shapes, 429 semantics).

Fully mockable via the FetchPage protocol. No real HTTP, no secrets.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterator, Optional, Protocol


@dataclass(frozen=True)
class RateLimitInfo:
    limit: Optional[int] = None
    remaining: Optional[int] = None
    reset: Optional[int] = None
    retry_after: Optional[int] = None


@dataclass(frozen=True)
class PageResult:
    items: list[dict]
    next_link: Optional[str] = None
    next_cursor: Optional[str] = None
    rate_info: RateLimitInfo = field(default_factory=RateLimitInfo)
    raw_headers: dict[str, str] = field(default_factory=dict)


class FetchPage(Protocol):
    """Injectable, fully mockable page fetcher."""

    def __call__(self, params: Dict[str, Any]) -> PageResult: ...


@dataclass
class RetryPolicy:
    max_retries: int = 5
    base_delay: float = 1.0
    max_delay: float = 60.0
    jitter: bool = True
    retry_on_status: tuple[int, ...] = (429, 500, 502, 503, 504)


class ProcorePaginator:
    def __init__(
        self,
        fetch_page: FetchPage,
        retry_policy: Optional[RetryPolicy] = None,
        default_per_page: int = 100,
        prefer_cursor: bool = False,
    ):
        self.fetch_page = fetch_page
        self.retry_policy = retry_policy or RetryPolicy()
        self.default_per_page = default_per_page
        self.prefer_cursor = prefer_cursor

    def _backoff(self, attempt: int, rate_info: RateLimitInfo) -> None:
        if rate_info.retry_after:
            delay = float(rate_info.retry_after)
        else:
            delay = min(self.retry_policy.base_delay * (2 ** attempt), self.retry_policy.max_delay)
            if self.retry_policy.jitter:
                delay = delay * (0.5 + random.random())
        time.sleep(delay)

    def _extract_next(self, result: PageResult, current_params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if result.next_link:
            # Simple extraction of query params from the full next URL (Procore returns usable links)
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(result.next_link)
            next_params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
            return next_params or None

        if result.next_cursor:
            p = dict(current_params)
            p["starting_after"] = result.next_cursor
            return p

        # Traditional page increment fallback
        page = int(current_params.get("page", 1))
        p = dict(current_params)
        p["page"] = page + 1
        return p

    def iterate(self, base_params: Optional[Dict[str, Any]] = None, *, per_page: Optional[int] = None) -> Iterator[dict]:
        params: Dict[str, Any] = dict(base_params or {})
        params.setdefault("per_page", per_page or self.default_per_page)

        while True:
            for attempt in range(self.retry_policy.max_retries + 1):
                try:
                    result = self.fetch_page(params)
                    break
                except Exception as exc:  # noqa: BLE001 - transport raises its own normalized errors
                    if attempt == self.retry_policy.max_retries:
                        raise
                    # Simple heuristic: treat transport-level 429/5xx as retryable
                    self._backoff(attempt, RateLimitInfo())
                    continue

            for item in result.items:
                yield item

            next_params = self._extract_next(result, params)
            if not next_params:
                break
            params = next_params

    def get_all(self, base_params: Optional[Dict[str, Any]] = None, *, per_page: Optional[int] = None) -> list[dict]:
        return list(self.iterate(base_params, per_page=per_page))
