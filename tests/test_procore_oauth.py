"""Phase 04 Prompt 02 OAuth acquisition — offline tests for
``ProcoreOAuthClient`` and ``TokenSet``.

The Procore client secret is provided through a monkeypatched stub so no
real Keychain or env access is required. All HTTP interaction is through an
injected ``AuthTransport`` — no ``requests`` call is ever made.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from hb_assistant.procore.oauth import (
    ProcoreOAuthClient,
    ProcoreOAuthError,
    TokenSet,
)

SYNTHETIC_ACCESS_TOKEN = "synthetic-access-token-x"
SYNTHETIC_REFRESH_TOKEN = "synthetic-refresh-token-y"
SYNTHETIC_AUTH_CODE = "synthetic-auth-code-1"
SYNTHETIC_CLIENT_SECRET = "synthetic-client-secret-not-real"


@pytest.fixture(autouse=True)
def _patch_client_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide a synthetic client secret so OAuth code paths can run offline."""
    monkeypatch.setattr(
        "hb_assistant.procore.oauth.get_procore_client_secret",
        lambda: SYNTHETIC_CLIENT_SECRET,
    )


class _FakeResponse:
    def __init__(self, status_code: int, payload: Any) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> Any:
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def _record_transport(response: _FakeResponse) -> tuple[Any, list[dict[str, Any]]]:
    calls: list[dict[str, Any]] = []

    def transport(method: str, url: str, *, headers: dict, data: dict, timeout: float) -> _FakeResponse:
        calls.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers),
                "data": dict(data),
                "timeout": timeout,
            }
        )
        return response

    return transport, calls


# --- authorization URL --------------------------------------------------------


def test_build_authorization_url_contains_required_oauth_params() -> None:
    client = ProcoreOAuthClient(environment="sandbox")
    url = client.build_authorization_url()
    assert url.startswith("https://login-sandbox.procore.com/oauth/authorize?")
    assert "response_type=code" in url
    assert "client_id=" in url
    assert "redirect_uri=urn%3Aietf%3Awg%3Aoauth%3A2.0%3Aoob" in url


# --- exchange_authorization_code ---------------------------------------------


def test_exchange_authorization_code_posts_form_body_to_token_endpoint() -> None:
    response = _FakeResponse(
        200,
        {
            "access_token": SYNTHETIC_ACCESS_TOKEN,
            "refresh_token": SYNTHETIC_REFRESH_TOKEN,
            "expires_in": 7200,
        },
    )
    transport, calls = _record_transport(response)
    client = ProcoreOAuthClient(environment="sandbox", transport=transport)

    token_set = client.exchange_authorization_code(SYNTHETIC_AUTH_CODE)

    assert len(calls) == 1
    call = calls[0]
    assert call["method"] == "POST"
    assert call["url"].endswith("/oauth/token")
    assert call["headers"]["Content-Type"] == "application/x-www-form-urlencoded"
    assert "X-Correlation-ID" in call["headers"]
    body = call["data"]
    assert body["grant_type"] == "authorization_code"
    assert body["code"] == SYNTHETIC_AUTH_CODE
    assert "client_id" in body
    assert "client_secret" in body
    assert body["redirect_uri"].startswith("urn:ietf:wg:oauth:2.0:oob")

    assert isinstance(token_set, TokenSet)
    assert token_set.access_token == SYNTHETIC_ACCESS_TOKEN
    assert token_set.refresh_token == SYNTHETIC_REFRESH_TOKEN
    # Expiry should sit close to (now + 7200s); allow a couple of seconds slack.
    expected_min = datetime.now(timezone.utc).timestamp() + 7100
    assert token_set.expires_at.timestamp() >= expected_min


def test_exchange_rejects_empty_code() -> None:
    client = ProcoreOAuthClient(environment="sandbox")
    with pytest.raises(ValueError, match="non-empty"):
        client.exchange_authorization_code("   ")


# --- refresh_access_token -----------------------------------------------------


def test_refresh_access_token_uses_refresh_token_grant() -> None:
    response = _FakeResponse(
        200,
        {
            "access_token": "synthetic-refreshed-access-token",
            "refresh_token": "synthetic-refreshed-refresh-token",
            "expires_in": 3600,
        },
    )
    transport, calls = _record_transport(response)
    client = ProcoreOAuthClient(environment="sandbox", transport=transport)

    token_set = client.refresh_access_token(SYNTHETIC_REFRESH_TOKEN)

    body = calls[0]["data"]
    assert body["grant_type"] == "refresh_token"
    assert body["refresh_token"] == SYNTHETIC_REFRESH_TOKEN
    assert "client_secret" in body
    assert token_set.access_token == "synthetic-refreshed-access-token"
    assert token_set.refresh_token == "synthetic-refreshed-refresh-token"


def test_refresh_rejects_empty_token() -> None:
    client = ProcoreOAuthClient(environment="sandbox")
    with pytest.raises(ValueError, match="non-empty"):
        client.refresh_access_token("")


# --- error semantics ----------------------------------------------------------


def test_4xx_response_raises_redacted_oauth_error() -> None:
    response = _FakeResponse(400, {"error": "invalid_grant", "error_description": "..."})
    transport, _ = _record_transport(response)
    client = ProcoreOAuthClient(environment="sandbox", transport=transport)

    with pytest.raises(ProcoreOAuthError) as exc_info:
        client.exchange_authorization_code(SYNTHETIC_AUTH_CODE)

    err = exc_info.value
    assert err.status == 400
    assert err.code == "oauth_error"
    rendered = repr(err) + str(err)
    for forbidden in (
        SYNTHETIC_AUTH_CODE,
        SYNTHETIC_ACCESS_TOKEN,
        SYNTHETIC_REFRESH_TOKEN,
        SYNTHETIC_CLIENT_SECRET,
    ):
        assert forbidden not in rendered


def test_non_json_response_raises_oauth_error() -> None:
    response = _FakeResponse(200, ValueError("not json"))
    transport, _ = _record_transport(response)
    client = ProcoreOAuthClient(environment="sandbox", transport=transport)
    with pytest.raises(ProcoreOAuthError, match="oauth_response_not_json"):
        client.refresh_access_token(SYNTHETIC_REFRESH_TOKEN)


def test_response_missing_access_token_raises_oauth_error() -> None:
    response = _FakeResponse(200, {"expires_in": 3600})
    transport, _ = _record_transport(response)
    client = ProcoreOAuthClient(environment="sandbox", transport=transport)
    with pytest.raises(ProcoreOAuthError, match="missing_access_token"):
        client.refresh_access_token(SYNTHETIC_REFRESH_TOKEN)


# --- TokenSet redaction -------------------------------------------------------


def test_token_set_repr_and_str_never_include_token_value() -> None:
    obtained = datetime.now(timezone.utc)
    token = TokenSet(
        access_token=SYNTHETIC_ACCESS_TOKEN,
        refresh_token=SYNTHETIC_REFRESH_TOKEN,
        expires_at=obtained,
        obtained_at=obtained,
    )
    rendered = repr(token) + str(token)
    assert SYNTHETIC_ACCESS_TOKEN not in rendered
    assert SYNTHETIC_REFRESH_TOKEN not in rendered


def test_token_set_expires_in_seconds_handles_past() -> None:
    past = datetime(2000, 1, 1, tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    token = TokenSet(
        access_token="x", refresh_token=None, expires_at=past, obtained_at=now
    )
    assert token.expires_in_seconds() < 0
