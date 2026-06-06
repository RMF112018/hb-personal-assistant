"""Prompt 03 — optional FastAPI auth onboarding surfaces."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.procore.oauth import TokenSet
from hb_assistant.store.migrator import SQLiteMigrator

FORBIDDEN = (
    "client_secret",
    "raw_body",
    "raw_prompt",
    "raw_response",
    "BEGIN PRIVATE",
)


class _FakeCache:
    has_state_changed = True


class _FakeMsalApp:
    token_cache = _FakeCache()

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

    def acquire_token_by_device_flow(self, flow: dict[str, Any]) -> dict[str, Any]:
        assert flow["user_code"] == "ABCD-EFGH"
        return {
            "access_token": "synthetic-access-token",
            "expires_in": 3600,
            "id_token_claims": {
                "upn": "operator@example.com",
                "tid": "tenant",
                "scp": "User.Read",
            },
        }


def _client(tmp_path: Path) -> TestClient:
    db = str(tmp_path / "auth-api.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return TestClient(create_app(db_path=db))


def _install_graph_fake(monkeypatch: pytest.MonkeyPatch) -> list[bool]:
    saves: list[bool] = []

    monkeypatch.setattr(
        "hb_assistant.auth.providers.DelegatedAuthProvider._get_app",
        lambda self: _FakeMsalApp(),
    )
    monkeypatch.setattr(
        "hb_assistant.auth.token_cache_manager.TokenCacheManager.save_cache",
        lambda self, cache, app_only=False: saves.append(bool(cache)),
    )
    return saves


def test_graph_status_with_no_cache_is_safe(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = client.get("/auth/graph/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["surface"] == "analytics.auth_onboarding.graph_status"
    assert payload["guardrails"]["tokens_returned"] is False
    assert payload["next_step"] in {"none", "start_graph_device_login"}
    serialized = json.dumps(payload, default=str)
    for marker in FORBIDDEN:
        assert marker not in serialized


def test_graph_device_flow_start_and_complete_are_redacted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    saves = _install_graph_fake(monkeypatch)
    client = _client(tmp_path)
    headers = {"X-HB-UI-Role": "operator"}

    start = client.post("/auth/graph/device-login/start", headers=headers)
    assert start.status_code == 200
    started = start.json()
    assert started["ok"] is True
    assert started["user_code"] == "ABCD-EFGH"
    assert started["verification_uri"].startswith("https://")
    assert "flow_id" in started

    complete = client.post(
        "/auth/graph/device-login/complete",
        headers=headers,
        json={"flow_id": started["flow_id"]},
    )
    assert complete.status_code == 200
    payload = complete.json()
    assert payload["ok"] is True
    assert payload["account"] == "operator@example.com"
    assert saves == [True]

    serialized = json.dumps({"start": started, "complete": payload}, default=str)
    for marker in FORBIDDEN:
        assert marker not in serialized


def test_viewer_cannot_start_or_complete_auth(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_graph_fake(monkeypatch)
    client = _client(tmp_path)

    assert client.post("/auth/graph/device-login/start").status_code == 403
    assert client.post(
        "/auth/graph/device-login/complete", json={"flow_id": "missing"}
    ).status_code == 403
    assert client.post("/auth/procore/oauth/start").status_code == 403
    assert client.post("/auth/procore/oauth/exchange", json={"code": "x"}).status_code == 403


class _FakeProcoreClient:
    environment = "sandbox"
    redirect_uri = "urn:ietf:wg:oauth:2.0:oob"

    def build_authorization_url(self) -> str:
        return "https://login-sandbox.procore.com/oauth/authorize?response_type=code"

    def exchange_authorization_code(self, code: str) -> TokenSet:
        assert code == "synthetic-code"
        now = datetime.now(timezone.utc)
        return TokenSet(
            access_token="synthetic-procore-access-token",
            refresh_token="synthetic-procore-refresh-token",
            expires_at=now + timedelta(hours=1),
            obtained_at=now,
        )


def test_procore_status_start_and_exchange_are_redacted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_writes: list[str] = []
    monkeypatch.setattr(
        "hb_assistant.construction.analytics.auth_onboarding.AuthOnboardingService._procore_oauth_client",
        staticmethod(lambda: _FakeProcoreClient()),
    )
    monkeypatch.setattr(
        "hb_assistant.procore.token_provider.write_token_cache",
        lambda token_set: cache_writes.append("written") or (tmp_path / "procore_token.json"),
    )
    client = _client(tmp_path)
    headers = {"X-HB-UI-Role": "admin"}

    status = client.get("/auth/procore/status")
    assert status.status_code == 200
    assert status.json()["surface"] == "analytics.auth_onboarding.procore_status"

    start = client.post("/auth/procore/oauth/start", headers=headers)
    assert start.status_code == 200
    assert start.json()["authorization_url"].startswith("https://login-sandbox.procore.com")

    exchange = client.post(
        "/auth/procore/oauth/exchange",
        headers=headers,
        json={"code": "synthetic-code"},
    )
    assert exchange.status_code == 200
    payload = exchange.json()
    assert payload["ok"] is True
    assert payload["access_cached"] is True
    assert payload["refresh_cached"] is True
    assert cache_writes == ["written"]

    serialized = json.dumps({"status": status.json(), "start": start.json(), "exchange": payload})
    for marker in FORBIDDEN:
        assert marker not in serialized
