"""P02 — /api/sources/graph/* Microsoft Graph safe status + auth bridge tests.

Proves the Graph source-status + auth routes are metadata-only, perform no mail/calendar/files
content API call, never leak tokens/secrets/cache paths, and report correct not-connected /
connected / stale / missing-scope states. Mirrors the auth-onboarding test harness.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.store.migrator import SQLiteMigrator

FORBIDDEN = (
    "BEGIN PRIVATE",
    "access_token",
    "refresh_token",
    "client_secret",
    "raw_body",
    "raw_prompt",
    "raw_response",
    "synthetic-access-token",
)


class _FakeCache:
    has_state_changed = True


class _FakeMsalApp:
    token_cache = _FakeCache()
    acquire_mode: str = "success"  # success | pending | expired | fail

    def initiate_device_flow(self, scopes: list[str]) -> dict[str, Any]:
        assert scopes
        return {
            "user_code": "ABCD-EFGH",
            "verification_uri": "https://microsoft.com/devicelogin",
            "verification_uri_complete": "https://microsoft.com/devicelogin?code=ABCD-EFGH",
            "expires_in": 900,
            "interval": 5,
            "message": "Open browser and enter code",
        }

    def get_accounts(self) -> list[dict[str, Any]]:
        return [{"username": "operator@example.com", "home_account_id": "fake"}]

    def _result(self) -> dict[str, Any]:
        mode = getattr(_FakeMsalApp, "acquire_mode", "success")
        if mode == "pending":
            return {"error": "authorization_pending", "error_description": "waiting"}
        if mode == "expired":
            return {"error": "expired_token", "error_description": "expired"}
        if mode == "fail":
            return {"error": "access_denied", "error_description": "cancelled"}
        return {
            "access_token": "synthetic-access-token",
            "expires_in": 3600,
            "scope": "User.Read",
            "id_token_claims": {"upn": "operator@example.com", "tid": "tenant", "scp": "User.Read"},
        }

    def acquire_token_silent(
        self, scopes=None, account=None, force_refresh=False
    ) -> dict[str, Any]:
        return self._result()

    def acquire_token_by_device_flow(self, flow: dict[str, Any]) -> dict[str, Any]:
        return self._result()


def _install_graph_fake(monkeypatch: pytest.MonkeyPatch) -> list[bool]:
    saves: list[bool] = []
    _FakeMsalApp.acquire_mode = "success"

    monkeypatch.setattr(
        "hb_assistant.auth.providers.DelegatedAuthProvider._get_app",
        lambda self: _FakeMsalApp(),
    )
    monkeypatch.setattr(
        "hb_assistant.auth.token_cache_manager.TokenCacheManager.save_cache",
        lambda self, cache, app_only=False: saves.append(bool(cache)),
    )

    def _fake_check_permissions(self):  # type: ignore[no-untyped-def]
        present = bool(saves)
        return {
            "msal-token-cache.bin": {"exists": present, "mode": 0o600, "perms_ok": True},
            "path_status": {"has_ensure_report": False},
        }

    monkeypatch.setattr(
        "hb_assistant.auth.token_cache_manager.TokenCacheManager.check_permissions",
        _fake_check_permissions,
    )
    return saves


def _client(tmp_path: Path) -> TestClient:
    db = str(tmp_path / "graph-bridge.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return TestClient(create_app(db_path=db))


def _assert_safe(payload: Any) -> None:
    serialized = json.dumps(payload, default=str)
    for marker in FORBIDDEN:
        assert marker not in serialized


def _connect(client: TestClient) -> None:
    """Drive the legacy device-login flow so the fake cache reports present."""
    headers = {"X-HB-UI-Role": "operator"}
    start = client.post("/auth/graph/device-login/start", headers=headers)
    assert start.status_code == 200
    fid = start.json()["flow_id"]
    done = client.post("/auth/graph/device-login/complete", headers=headers, json={"flow_id": fid})
    assert done.status_code == 200


def test_status_metadata_only_and_safe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_graph_fake(monkeypatch)
    client = _client(tmp_path)
    r = client.get("/api/sources/graph/status")

    assert r.status_code == 200
    payload = r.json()
    assert payload["surface"] == "analytics.sources.graph.status"
    assert payload["system"] == "microsoft_365_graph"
    assert payload["guardrails"]["graph_data_api_called"] is False
    assert payload["guardrails"]["tokens_returned"] is False
    _assert_safe(payload)


def test_status_never_constructs_graph_data_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_graph_fake(monkeypatch)

    def _boom(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("status must not construct a Graph data client")

    monkeypatch.setattr("hb_assistant.graph.http_client.GraphHttpClient", _boom)
    client = _client(tmp_path)
    assert client.get("/api/sources/graph/status").status_code == 200


def test_status_not_connected_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_graph_fake(monkeypatch)  # no save -> cache absent
    client = _client(tmp_path)
    payload = client.get("/api/sources/graph/status").json()

    assert payload["state"] == "not_connected"
    assert payload["next_step"] == "start_graph_device_login"


def test_status_connected_valid_after_login(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_graph_fake(monkeypatch)
    client = _client(tmp_path)
    _connect(client)

    payload = client.get("/api/sources/graph/status").json()
    assert payload["state"] == "connected_valid"
    assert payload["token_type"] == "delegated"
    assert payload["account"] == "operator@example.com"
    _assert_safe(payload)


def test_status_stale_reauth_required(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_graph_fake(monkeypatch)
    client = _client(tmp_path)
    _connect(client)  # cache now present

    _FakeMsalApp.acquire_mode = "fail"  # silent verify fails -> stale
    payload = client.get("/api/sources/graph/status").json()
    assert payload["classification"] == "stale_reauth_required"
    assert payload["state"] == "reauth_required"


def test_status_missing_scope_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    crafted = {
        "surface": "analytics.auth_onboarding.graph_status",
        "token_type": "delegated",
        "classification": "delegated_verified",
        "account": "operator@example.com",
        "tenant": "tenant",
        "scopes": [],
        "expires_in_seconds_if_known": 3600,
        "scope_diagnostics": {"configured_scopes": ["user.read"]},
        "next_step": None,
        "guardrails": {"tokens_returned": False, "graph_data_api_called": False},
    }
    monkeypatch.setattr(
        "hb_assistant.construction.analytics.auth_onboarding.AuthOnboardingService.graph_status",
        lambda self: dict(crafted),
    )
    client = _client(tmp_path)
    payload = client.get("/api/sources/graph/status").json()

    missing = payload["scope_presence"]["missing"]
    assert "mail.read" in missing
    assert "calendars.read" in missing
    assert "files.read.all" in missing
    assert payload["scope_presence"]["all_present"] is False


def test_auth_start_then_poll(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_graph_fake(monkeypatch)
    client = _client(tmp_path)
    headers = {"X-HB-UI-Role": "operator"}

    started = client.post("/api/sources/graph/auth/start", headers=headers)
    assert started.status_code == 200
    s = started.json()
    assert "flow_id" in s and s["verification_uri"].startswith("https://")
    assert "user_code" in s
    _assert_safe(s)
    fid = s["flow_id"]

    _FakeMsalApp.acquire_mode = "pending"
    pending = client.get(f"/api/sources/graph/auth/status?flow_id={fid}", headers=headers).json()
    assert pending["status"] == "pending"
    _assert_safe(pending)

    _FakeMsalApp.acquire_mode = "success"
    complete = client.get(f"/api/sources/graph/auth/status?flow_id={fid}", headers=headers).json()
    assert complete["status"] == "complete"
    assert complete["account"]["account_hint"] == "operator@example.com"
    _assert_safe(complete)


def test_auth_refresh_is_safe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_graph_fake(monkeypatch)
    client = _client(tmp_path)
    r = client.post("/api/sources/graph/auth/refresh", headers={"X-HB-UI-Role": "operator"})

    assert r.status_code == 200
    payload = r.json()
    assert payload["surface"] == "analytics.settings.connections.auth.refresh"
    assert payload["results"][0]["source"] == "graph"
    _assert_safe(payload)


def test_role_gating(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_graph_fake(monkeypatch)
    client = _client(tmp_path)
    viewer = {"X-HB-UI-Role": "viewer"}

    # status is viewer-safe
    assert client.get("/api/sources/graph/status", headers=viewer).status_code == 200
    # auth actions are operator+
    assert client.post("/api/sources/graph/auth/start", headers=viewer).status_code == 403
    assert client.get("/api/sources/graph/auth/status?flow_id=x", headers=viewer).status_code == 403
    assert client.post("/api/sources/graph/auth/refresh", headers=viewer).status_code == 403
