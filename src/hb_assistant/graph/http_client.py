"""GraphHttpClient: central, token-injected, paged, retried HTTP client for Microsoft Graph.

Phase 2 base implementation per 06_Graph_Integration_Specification:
- Uses requests (no ad-hoc calls elsewhere)
- Token via injectable getter (from auth providers)
- $select, paging via @odata.nextLink
- Retry policy: 429 + 5xx (max 5, respect Retry-After, exponential backoff)
- Sanitized errors: never log Authorization, full bodies, or tokens
- No mutation methods in Phase 2
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

import requests

from hb_assistant.auth.classifier import require_delegated
from hb_assistant.auth.exceptions import AuthError

# Retry policy (from 06 spec)
MAX_RETRIES = 5
BASE_BACKOFF = 2.0
MAX_BACKOFF = 60.0
RETRY_STATUSES = {429, 500, 502, 503, 504}
NON_RETRY_STATUSES = {400, 401, 403, 404}


class GraphHttpError(Exception):
    """Sanitized Graph error (no tokens, headers, or full bodies)."""

    def __init__(self, method: str, url: str, status: int, message: str) -> None:
        self.method = method
        self.url = url
        self.status = status
        self.message = message
        super().__init__(f"{method} {url} -> {status}: {message}")


class GraphHttpClient:
    """Thin wrapper around requests for Graph with auth + resilience."""

    GRAPH_ROOT = "https://graph.microsoft.com/v1.0"

    def __init__(
        self,
        token_getter: Callable[[Optional[List[str]]], Dict[str, Any]],
        *,
        timeout: float = 30.0,
        user_agent: str = "hb-personal-assistant/0.2.0 (local-first)",
    ) -> None:
        self._get_token = token_getter
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": user_agent})

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        scopes: Optional[List[str]] = None,
        headers: Optional[Dict[str, str]] = None,
        data: Any = None,
        json: Any = None,
        stream: bool = False,
    ) -> requests.Response:
        url = f"{self.GRAPH_ROOT}/{path.lstrip('/')}" if not path.startswith("http") else path
        token = self._get_token(scopes)
        require_delegated(token.get("id_token_claims") or token.get("claims"), context=f"{method} {path}")

        req_headers = {"Authorization": f"Bearer {token['access_token']}"}
        if headers:
            req_headers.update(headers)
        # Prefer immutable IDs where supported (harmless if not)
        if "Prefer" not in req_headers:
            req_headers["Prefer"] = 'IdType="ImmutableId"'

        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = self._session.request(
                    method,
                    url,
                    params=params,
                    headers=req_headers,
                    data=data,
                    json=json,
                    timeout=self._timeout,
                    stream=stream,
                )
            except requests.RequestException as e:
                if attempt == MAX_RETRIES:
                    raise GraphHttpError(method, url, 0, str(e)) from e
                time.sleep(min(BASE_BACKOFF * (2 ** attempt), MAX_BACKOFF))
                continue

            if resp.status_code in NON_RETRY_STATUSES:
                # Sanitize: do not include body or auth info
                msg = resp.json().get("error", {}).get("message", resp.reason) if resp.content else resp.reason
                raise GraphHttpError(method, url, resp.status_code, str(msg)[:200])

            if resp.status_code in RETRY_STATUSES and attempt < MAX_RETRIES:
                retry_after = resp.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else min(BASE_BACKOFF * (2 ** attempt), MAX_BACKOFF)
                time.sleep(delay)
                continue

            return resp

        raise GraphHttpError(method, url, 0, "Max retries exceeded")

    def get(
        self,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        scopes: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """GET and return JSON (single page or first page)."""
        resp = self._request("GET", path, params=params, scopes=scopes)
        resp.raise_for_status()
        return resp.json()

    def get_all_pages(
        self,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        scopes: Optional[List[str]] = None,
    ) -> Iterator[Dict[str, Any]]:
        """Yield every item across @odata.nextLink pages (safe for bounded queries)."""
        p = dict(params or {})
        while True:
            data = self.get(path, params=p, scopes=scopes)
            for item in data.get("value", []):
                yield item
            next_link = data.get("@odata.nextLink")
            if not next_link:
                break
            # Continue from nextLink (Graph provides full URL)
            path = next_link  # will be absolute in next call
            p = {}  # params already embedded

    def close(self) -> None:
        self._session.close()

    def download_to_file(
        self,
        path: str,
        target: Path,
        *,
        max_bytes: Optional[int] = None,
        scopes: Optional[List[str]] = None,
        chunk_size: int = 8192,
    ) -> int:
        """Stream binary content from Graph to target file (retry policy, size guard, no full body in memory).

        Checks Content-Length header upfront if present. Streams chunks, aborts on exceed.
        Returns bytes_written. Raises GraphHttpError or ValueError on violation/IO error.
        Never logs or returns full content; only size and status.
        """
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Request with stream=True so we control consumption
        resp = self._request("GET", path, scopes=scopes, stream=True)
        try:
            # Size guard from header (if provided by Graph)
            cl = resp.headers.get("Content-Length")
            if cl is not None:
                try:
                    declared = int(cl)
                    if max_bytes is not None and declared > max_bytes:
                        raise ValueError(f"declared_size {declared} exceeds max_bytes {max_bytes}")
                except (ValueError, TypeError):
                    pass  # proceed, will check during stream

            written = 0
            with target.open("wb") as f:
                for chunk in resp.iter_content(chunk_size=chunk_size):
                    if not chunk:
                        continue
                    f.write(chunk)
                    written += len(chunk)
                    if max_bytes is not None and written > max_bytes:
                        raise ValueError(f"stream_exceeded max_bytes {max_bytes} (written={written})")
            return written
        finally:
            resp.close()
