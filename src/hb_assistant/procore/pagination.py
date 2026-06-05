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

from hb_assistant.procore.errors import ProcoreAPIError, ProcoreRateLimitError


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
        sleep_fn: Optional[Callable[[float], None]] = None,
        random_fn: Optional[Callable[[], float]] = None,
    ):
        self.fetch_page = fetch_page
        self.retry_policy = retry_policy or RetryPolicy()
        self.default_per_page = default_per_page
        self.prefer_cursor = prefer_cursor
        self._sleep_fn = sleep_fn or time.sleep
        self._random_fn = random_fn or random.random

    def _backoff(self, attempt: int, rate_info: RateLimitInfo) -> None:
        if rate_info.retry_after:
            delay = float(rate_info.retry_after)
        else:
            delay = min(self.retry_policy.base_delay * (2**attempt), self.retry_policy.max_delay)
            if self.retry_policy.jitter:
                delay = delay * (0.5 + self._random_fn())
        self._sleep_fn(delay)

    def _extract_next(
        self, result: PageResult, current_params: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        if result.next_link:
            # Simple extraction of query params from the full next URL (Procore returns usable links)
            from urllib.parse import parse_qs, urlparse

            parsed = urlparse(result.next_link)
            next_params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
            return next_params or None

        if result.next_cursor:
            p = dict(current_params)
            p["starting_after"] = result.next_cursor
            return p

        # Procore signals continuation with a Link header or a cursor token.
        # Do not invent page=N+1 when no continuation signal is present; many
        # endpoints return the full unfiltered set in one response.
        return None

    def _retryable(self, exc: Exception) -> tuple[bool, RateLimitInfo]:
        if isinstance(exc, ProcoreRateLimitError):
            return True, RateLimitInfo(retry_after=exc.retry_after)
        if isinstance(exc, ProcoreAPIError):
            return (
                exc.status in self.retry_policy.retry_on_status,
                RateLimitInfo(),
            )
        return False, RateLimitInfo()

    def iterate(
        self,
        base_params: Optional[Dict[str, Any]] = None,
        *,
        per_page: Optional[int] = None,
        max_pages: Optional[int] = None,
        max_items: Optional[int] = None,
    ) -> Iterator[dict]:
        params: Dict[str, Any] = dict(base_params or {})
        params.setdefault("per_page", per_page or self.default_per_page)
        pages_seen = 0
        items_seen = 0

        while True:
            if max_pages is not None and pages_seen >= max_pages:
                break
            for attempt in range(self.retry_policy.max_retries + 1):
                try:
                    result = self.fetch_page(params)
                    break
                except Exception as exc:  # noqa: BLE001 - normalized errors from transport
                    should_retry, rate_info = self._retryable(exc)
                    if not should_retry:
                        raise
                    if attempt == self.retry_policy.max_retries:
                        raise
                    self._backoff(attempt, rate_info)
                    continue
            pages_seen += 1

            for item in result.items:
                if max_items is not None and items_seen >= max_items:
                    return
                yield item
                items_seen += 1

            next_params = self._extract_next(result, params)
            if not next_params:
                break
            params = next_params

    def get_all(
        self,
        base_params: Optional[Dict[str, Any]] = None,
        *,
        per_page: Optional[int] = None,
        max_pages: Optional[int] = None,
        max_items: Optional[int] = None,
    ) -> list[dict]:
        return list(
            self.iterate(
                base_params,
                per_page=per_page,
                max_pages=max_pages,
                max_items=max_items,
            )
        )
