"""Procore OAuth 2.0 token acquisition (OOB Installed-Apps flow).

This module owns the **only** legitimate call site for
:func:`hb_assistant.procore.config.get_procore_client_secret`. The bearer-token
boundary established in Phase 04 Prompts 01–02 is preserved: the GET-only HTTP
client never reads the client secret; OAuth `/oauth/token` POSTs are isolated
here and use a dedicated HTTP transport.

Surfaces:

- :class:`TokenSet` — frozen dataclass carrying access/refresh tokens and
  expiry metadata. ``__repr__`` and ``__str__`` never include the token value.
- :class:`ProcoreOAuthError` — fail-closed error type; never carries the
  request body, response body, or any token-shaped value.
- :class:`ProcoreOAuthClient` —

  * ``build_authorization_url()`` returns the operator-facing OOB authorize URL.
  * ``exchange_authorization_code(code)`` performs the first-time code → token
    exchange.
  * ``refresh_access_token(refresh_token)`` performs the ongoing refresh.

  The transport is injectable for tests; the production default wraps
  ``requests.request`` with ``timeout`` and ``allow_redirects=False``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping, Optional
from urllib.parse import urlencode

from hb_assistant.procore.config import (
    ENVIRONMENTS,
    get_procore_client_secret,
    load_procore_app_profile,
)
from hb_assistant.procore.errors import ProcoreAPIError

AuthTransport = Callable[..., Any]
"""(method, url, *, headers, data, timeout) -> response-like.

The response object must expose ``status_code`` (int) and ``json()`` (callable
returning a mapping). Matches ``requests.Response`` and the in-memory fakes
the test suite already uses elsewhere.
"""


# ---------------------------------------------------------------------------
# Result + error types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TokenSet:
    """Immutable result of an OAuth exchange or refresh."""

    access_token: str
    refresh_token: Optional[str]
    expires_at: datetime
    obtained_at: datetime

    def expires_in_seconds(self) -> int:
        """Seconds until ``expires_at`` (negative if already expired)."""
        delta = self.expires_at - datetime.now(timezone.utc)
        return int(delta.total_seconds())

    def __repr__(self) -> str:
        return (
            f"<TokenSet present=True refresh_present={self.refresh_token is not None} "
            f"expires_in_s={self.expires_in_seconds()}>"
        )

    def __str__(self) -> str:
        return self.__repr__()


class ProcoreOAuthError(ProcoreAPIError):
    """Raised when an OAuth exchange or refresh fails.

    Constructed with only the HTTP status code, a redacted error category, and
    a correlation id — never the request body, response body, or any
    token-shaped value.
    """

    def __init__(
        self,
        *,
        status: int,
        message: str = "oauth_error",
        correlation_id: Optional[str] = None,
    ) -> None:
        super().__init__(
            status=status,
            code="oauth_error",
            message=message,
            correlation_id=correlation_id,
        )


# ---------------------------------------------------------------------------
# Production default transport
# ---------------------------------------------------------------------------


def _default_requests_transport(
    method: str,
    url: str,
    *,
    headers: Mapping[str, str],
    data: Mapping[str, str],
    timeout: float,
) -> Any:
    """Default transport: ``requests.request`` with no session reuse.

    Imported lazily so unit tests that inject a mock transport never load
    ``requests``.
    """
    import requests  # local import keeps the module light when tests inject

    return requests.request(
        method,
        url,
        headers=dict(headers),
        data=dict(data),
        timeout=timeout,
        allow_redirects=False,
    )


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


_DEFAULT_TIMEOUT_S = 15.0
_TOKEN_PATH = "/oauth/token"
_AUTHORIZE_PATH = "/oauth/authorize"


class ProcoreOAuthClient:
    """Procore OOB Installed-Apps OAuth client.

    The client secret is read at request time only; it is never stored on the
    instance.
    """

    def __init__(
        self,
        *,
        environment: str = "sandbox",
        transport: Optional[AuthTransport] = None,
        timeout: float = _DEFAULT_TIMEOUT_S,
    ) -> None:
        if environment not in ENVIRONMENTS:
            raise ValueError(
                f"environment must be one of {sorted(ENVIRONMENTS.keys())}; got {environment!r}"
            )
        self.environment = environment
        self._transport: AuthTransport = transport or _default_requests_transport
        self._timeout = timeout
        profile = load_procore_app_profile()
        self._client_id = profile.client_id
        self._redirect_uri = profile.redirect_uri
        self._oauth_base = ENVIRONMENTS[environment]["oauth_base"].rstrip("/")

    @property
    def token_url(self) -> str:
        return f"{self._oauth_base}{_TOKEN_PATH}"

    @property
    def authorize_url_base(self) -> str:
        return f"{self._oauth_base}{_AUTHORIZE_PATH}"

    @property
    def client_id(self) -> str:
        return self._client_id

    @property
    def redirect_uri(self) -> str:
        return self._redirect_uri

    def build_authorization_url(self) -> str:
        """Return the operator-facing OOB authorization URL.

        The operator opens this URL in a browser, signs in to Procore, and is
        shown an authorization code to paste back into ``procore auth login``.
        """
        params = {
            "response_type": "code",
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
        }
        return f"{self.authorize_url_base}?{urlencode(params)}"

    def exchange_authorization_code(self, code: str) -> TokenSet:
        """Exchange a one-time authorization code for an access + refresh token."""
        if not code or not code.strip():
            raise ValueError("authorization code must be a non-empty string")
        body = {
            "grant_type": "authorization_code",
            "code": code.strip(),
            "client_id": self._client_id,
            "client_secret": get_procore_client_secret(),
            "redirect_uri": self._redirect_uri,
        }
        return self._post_token(body)

    def refresh_access_token(self, refresh_token: str) -> TokenSet:
        """Use a refresh token to obtain a fresh access token (and rotated refresh)."""
        if not refresh_token or not refresh_token.strip():
            raise ValueError("refresh_token must be a non-empty string")
        body = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token.strip(),
            "client_id": self._client_id,
            "client_secret": get_procore_client_secret(),
        }
        return self._post_token(body)

    # ---- internals ------------------------------------------------------

    def _post_token(self, body: Mapping[str, str]) -> TokenSet:
        correlation_id = str(uuid.uuid4())
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Correlation-ID": correlation_id,
        }
        obtained_at = datetime.now(timezone.utc)
        response = self._transport(
            "POST",
            self.token_url,
            headers=headers,
            data=dict(body),
            timeout=self._timeout,
        )
        status = getattr(response, "status_code", 0)
        if status < 200 or status >= 300:
            raise ProcoreOAuthError(
                status=int(status),
                message=f"oauth_token_endpoint_returned_{int(status)}",
                correlation_id=correlation_id,
            )
        try:
            payload = response.json()
        except Exception as exc:  # noqa: BLE001 — boundary
            raise ProcoreOAuthError(
                status=int(status),
                message="oauth_response_not_json",
                correlation_id=correlation_id,
            ) from exc
        if not isinstance(payload, dict):
            raise ProcoreOAuthError(
                status=int(status),
                message="oauth_response_not_object",
                correlation_id=correlation_id,
            )
        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise ProcoreOAuthError(
                status=int(status),
                message="oauth_response_missing_access_token",
                correlation_id=correlation_id,
            )
        refresh_token_resp = payload.get("refresh_token")
        if refresh_token_resp is not None and not isinstance(refresh_token_resp, str):
            raise ProcoreOAuthError(
                status=int(status),
                message="oauth_response_refresh_token_not_string",
                correlation_id=correlation_id,
            )
        expires_in = payload.get("expires_in")
        if not isinstance(expires_in, (int, float)) or expires_in <= 0:
            # Procore returns expires_in seconds; default to 1 hour if absent.
            expires_in = 3600
        expires_at = obtained_at + timedelta(seconds=int(expires_in))
        return TokenSet(
            access_token=access_token,
            refresh_token=refresh_token_resp,
            expires_at=expires_at,
            obtained_at=obtained_at,
        )


__all__ = [
    "AuthTransport",
    "ProcoreOAuthClient",
    "ProcoreOAuthError",
    "TokenSet",
]
