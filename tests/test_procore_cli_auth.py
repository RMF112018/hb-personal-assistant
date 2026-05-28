"""Phase 04 Prompt 02 OAuth acquisition — CLI tests for
``hb-assistant procore auth login / refresh / logout / status``.

The OAuth client is patched at the CLI module's call site so no real Procore
HTTP is performed. The auth cache directory is redirected to a per-test
``tmp_path`` via the ``PathPolicy`` shim already used by other token-provider
tests.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.main import app
from hb_assistant.procore.oauth import ProcoreOAuthError, TokenSet
from hb_assistant.procore.token_provider import AUTH_TOKEN_FILE_NAME, write_token_cache

pytestmark = pytest.mark.usefixtures("isolated_hb_pa_config")


SYNTHETIC_ACCESS = "synthetic-cli-access-token"
SYNTHETIC_REFRESH = "synthetic-cli-refresh-token"
SYNTHETIC_CODE = "synthetic-cli-auth-code"


@pytest.fixture
def auth_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect both token_provider and (transitively) the CLI to a temp auth dir."""
    target = tmp_path / "auth"
    monkeypatch.setattr(
        "hb_assistant.procore.token_provider.PathPolicy",
        lambda: type("X", (), {"get_auth_dir": lambda self: target})(),
    )
    return target


def _runner() -> CliRunner:
    return CliRunner()


def _fresh_token_set(*, expires_in: int = 3600) -> TokenSet:
    now = datetime.now(timezone.utc)
    return TokenSet(
        access_token=SYNTHETIC_ACCESS,
        refresh_token=SYNTHETIC_REFRESH,
        expires_at=now + timedelta(seconds=expires_in),
        obtained_at=now,
    )


# --- login --------------------------------------------------------------------


def test_login_with_explicit_code_writes_cache(auth_dir: Path) -> None:
    fake_client = MagicMock()
    fake_client.exchange_authorization_code.return_value = _fresh_token_set()
    with patch("hb_assistant.cli.procore._build_oauth_client", return_value=fake_client):
        res = _runner().invoke(
            app,
            ["procore", "auth", "login", "--code", SYNTHETIC_CODE, "--json"],
            catch_exceptions=False,
        )
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["ok"] is True
    assert payload["kind"] == "oauth_login"
    assert payload["access_token_cached"] is True
    assert payload["refresh_token_cached"] is True
    assert isinstance(payload["expires_in_seconds"], int)
    # Cache exists at the redirected path.
    cache_file = auth_dir / AUTH_TOKEN_FILE_NAME
    assert cache_file.exists()
    fake_client.exchange_authorization_code.assert_called_once_with(SYNTHETIC_CODE)
    # No token literal leaked into stdout.
    assert SYNTHETIC_ACCESS not in res.output
    assert SYNTHETIC_REFRESH not in res.output


def test_login_missing_client_secret_emits_clean_envelope(auth_dir: Path) -> None:
    """SecretNotAvailableError must surface as a redacted envelope, never a
    traceback. Operator hint should point at the security command.
    """
    from hb_assistant.procore.config import SecretNotAvailableError

    fake_client = MagicMock()
    fake_client.exchange_authorization_code.side_effect = SecretNotAvailableError("no secret")
    with patch("hb_assistant.cli.procore._build_oauth_client", return_value=fake_client):
        res = _runner().invoke(
            app,
            ["procore", "auth", "login", "--code", SYNTHETIC_CODE, "--json"],
            catch_exceptions=False,
        )
    assert res.exit_code == 1
    payload = json.loads(res.output)
    assert payload["ok"] is False
    assert payload["kind"] == "secret_not_configured"
    assert "security add-generic-password" in payload["hint"]
    # No traceback markers in output.
    assert "Traceback" not in res.output


def test_login_oauth_error_emits_redacted_envelope(auth_dir: Path) -> None:
    fake_client = MagicMock()
    fake_client.exchange_authorization_code.side_effect = ProcoreOAuthError(
        status=400, message="oauth_token_endpoint_returned_400", correlation_id="abc-123"
    )
    with patch("hb_assistant.cli.procore._build_oauth_client", return_value=fake_client):
        res = _runner().invoke(
            app,
            ["procore", "auth", "login", "--code", SYNTHETIC_CODE, "--json"],
            catch_exceptions=False,
        )
    assert res.exit_code == 1
    payload = json.loads(res.output)
    assert payload["ok"] is False
    assert payload["kind"] == "oauth_login_failed"
    assert payload["status"] == 400
    assert payload["correlation_id"] == "abc-123"


# --- refresh ------------------------------------------------------------------


def test_refresh_without_cache_returns_1(auth_dir: Path) -> None:
    res = _runner().invoke(app, ["procore", "auth", "refresh", "--json"], catch_exceptions=False)
    assert res.exit_code == 1
    payload = json.loads(res.output)
    assert payload["ok"] is False
    assert payload["kind"] == "oauth_refresh_unavailable"
    assert payload["reason"] == "no_refresh_token_in_cache"


def test_refresh_missing_client_secret_emits_clean_envelope(auth_dir: Path) -> None:
    from hb_assistant.procore.config import SecretNotAvailableError

    write_token_cache(_fresh_token_set(expires_in=1))
    fake_client = MagicMock()
    fake_client.refresh_access_token.side_effect = SecretNotAvailableError("no secret")
    with patch("hb_assistant.cli.procore._build_oauth_client", return_value=fake_client):
        res = _runner().invoke(
            app, ["procore", "auth", "refresh", "--json"], catch_exceptions=False
        )
    assert res.exit_code == 1
    payload = json.loads(res.output)
    assert payload["kind"] == "secret_not_configured"
    assert "Traceback" not in res.output


def test_refresh_with_cache_calls_oauth_client_and_updates_cache(auth_dir: Path) -> None:
    write_token_cache(_fresh_token_set(expires_in=1))
    fake_client = MagicMock()
    fake_client.refresh_access_token.return_value = _fresh_token_set(expires_in=7200)
    with patch("hb_assistant.cli.procore._build_oauth_client", return_value=fake_client):
        res = _runner().invoke(
            app, ["procore", "auth", "refresh", "--json"], catch_exceptions=False
        )
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["ok"] is True
    assert payload["kind"] == "oauth_refresh"
    fake_client.refresh_access_token.assert_called_once_with(SYNTHETIC_REFRESH)


# --- logout -------------------------------------------------------------------


def test_logout_removes_cache_when_present(auth_dir: Path) -> None:
    write_token_cache(_fresh_token_set())
    cache_file = auth_dir / AUTH_TOKEN_FILE_NAME
    assert cache_file.exists()
    res = _runner().invoke(app, ["procore", "auth", "logout", "--json"], catch_exceptions=False)
    assert res.exit_code == 0
    payload = json.loads(res.output)
    assert payload["ok"] is True
    assert payload["kind"] == "oauth_logout"
    assert payload["removed"] is True
    assert not cache_file.exists()


def test_logout_when_cache_missing_reports_removed_false(auth_dir: Path) -> None:
    res = _runner().invoke(app, ["procore", "auth", "logout", "--json"], catch_exceptions=False)
    payload = json.loads(res.output)
    assert payload["removed"] is False


# --- status (extended envelope) -----------------------------------------------


def test_status_envelope_includes_phase04_fields(auth_dir: Path) -> None:
    write_token_cache(_fresh_token_set(expires_in=900))
    res = _runner().invoke(app, ["procore", "auth", "status", "--json"], catch_exceptions=False)
    assert res.exit_code == 0
    payload = json.loads(res.output)
    for key in (
        "cache_present",
        "access_token_present",
        "refresh_token_present",
        "expires_in_seconds_if_known",
        "chain_order",
    ):
        assert key in payload, f"missing {key}"
    assert payload["cache_present"] is True
    assert payload["access_token_present"] is True
    assert payload["refresh_token_present"] is True
    assert isinstance(payload["expires_in_seconds_if_known"], int)
    assert payload["chain_order"] == ["env_or_keychain", "oauth_refreshing", "missing"]
    # No token literal leaked.
    assert SYNTHETIC_ACCESS not in res.output
    assert SYNTHETIC_REFRESH not in res.output


def test_status_without_cache_reports_empty(auth_dir: Path) -> None:
    res = _runner().invoke(app, ["procore", "auth", "status", "--json"], catch_exceptions=False)
    payload: dict[str, Any] = json.loads(res.output)
    assert payload["cache_present"] is False
    assert payload["access_token_present"] is False
    assert payload["refresh_token_present"] is False
    assert payload["expires_in_seconds_if_known"] is None
