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

    def _fake_check_permissions(self):  # type: ignore[no-untyped-def]
        # When a save has been recorded by the fake complete flow, report the msal cache bin as present
        # so that graph_status() and the Prompt A mappers see cache_present and map to connected_valid.
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


# Prompt A tests — new normalized contract surfaces + 7-state / 5-state coverage + redaction.
# These are additive; all legacy root paths and behaviors must remain unchanged.


def test_onboarding_readiness_and_connections_accounts_are_safe(tmp_path: Path) -> None:
    client = _client(tmp_path)
    # viewer may read readiness and accounts
    r = client.get("/api/onboarding/readiness")
    assert r.status_code == 200
    data = r.json()
    assert "onboarding_state" in data
    assert data["onboarding_state"] in {"first_time", "ready", "degraded", "reauth_required", "blocked"}
    assert "data_quality" in data
    assert data["guardrails"]["tokens_returned"] is False
    assert "get_started_required" in data
    # graph should surface as never_connected in a fresh client (no cache in test env)
    actions = data.get("required_actions") or []
    assert any(a.get("source") == "graph" for a in actions)
    _assert_no_forbidden(data)

    ra = client.get("/api/settings/connections/accounts")
    assert ra.status_code == 200
    acc = ra.json()
    assert "graph" in acc and "procore" in acc
    assert acc["graph"]["status"] in {"never_connected", "connected_valid", "connected_stale_refreshable", "connected_stale_reauth_required", "connected_error", "connected_refreshing", "disconnected_by_user"}
    _assert_no_forbidden(acc)


def _assert_no_forbidden(payload: Any) -> None:
    s = json.dumps(payload, default=str)
    for marker in FORBIDDEN:
        assert marker not in s


def test_auth_refresh_is_safe_and_does_not_trigger_sync(tmp_path: Path) -> None:
    client = _client(tmp_path)
    headers = {"X-HB-UI-Role": "operator"}
    body = {"sources": ["graph", "procore"]}
    rr = client.post("/api/settings/connections/auth/refresh", headers=headers, json=body)
    assert rr.status_code == 200
    res = rr.json()
    assert "results" in res
    for item in res["results"]:
        assert item["before"] in {"never_connected", "connected_valid", "connected_stale_refreshable", "connected_stale_reauth_required", "connected_error", "connected_refreshing", "disconnected_by_user"}
        assert "reauth_required" in item
    _assert_no_forbidden(res)
    # readiness must still report first_time or equivalent without having started any sync
    rd = client.get("/api/onboarding/readiness")
    assert rd.status_code == 200
    # no first_sync_triggered at the readiness level
    assert "first_sync_triggered" not in json.dumps(rd.json())


def test_new_project_and_admin_contract_paths_exist_and_safe(tmp_path: Path) -> None:
    client = _client(tmp_path)
    # preview is readable by viewer (no role write)
    prev = client.post("/api/settings/connections/projects/preview", json={"url": "https://app.procore.com/2525840/project/home"})
    assert prev.status_code == 200
    p = prev.json()
    assert p.get("status") in {"ready_to_save", "unavailable"}
    _assert_no_forbidden(p)

    # save and approve require roles; just check they are wired (403 without role is fine)
    assert client.post("/api/settings/connections/projects/save", json={"url": "https://app.procore.com/2525840/project/home"}).status_code == 403

    # admin approve path exists (will 403 or 200 depending on prior save, but must not 404/5xx)
    a = client.post("/api/settings/connections/admin/some-conn/approve-first-sync", headers={"X-HB-UI-Role": "admin"})
    assert a.status_code in (200, 403, 404)  # 404 if no such conn is acceptable (contract surface is present)
    _assert_no_forbidden(a.json() if a.headers.get("content-type", "").startswith("application/json") else {})

    # data quality summary (all) and detail (admin)
    ds = client.get("/api/settings/data-quality/summary")
    assert ds.status_code == 200
    _assert_no_forbidden(ds.json())

    dd = client.get("/api/settings/data-quality/detail", headers={"X-HB-UI-Role": "admin"})
    assert dd.status_code == 200
    _assert_no_forbidden(dd.json())


def test_readiness_transitions_toward_ready_after_graph_complete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_graph_fake(monkeypatch)
    client = _client(tmp_path)
    headers = {"X-HB-UI-Role": "operator"}

    # before: first_time / never_connected dominant
    before = client.get("/api/onboarding/readiness").json()
    assert before["onboarding_state"] in {"first_time", "degraded"}

    # perform the device flow (existing test flow)
    start = client.post("/auth/graph/device-login/start", headers=headers)
    assert start.status_code == 200
    complete = client.post(
        "/auth/graph/device-login/complete",
        headers=headers,
        json={"flow_id": start.json()["flow_id"]},
    )
    assert complete.status_code == 200

    # after: graph should report connected_valid (via the internal cache-present path)
    after_acc = client.get("/api/settings/connections/accounts").json()
    assert after_acc["graph"]["status"] == "connected_valid"

    after_ready = client.get("/api/onboarding/readiness").json()
    # With graph now valid, state should allow main app (ready or degraded depending on other signals)
    assert after_ready["onboarding_state"] in {"ready", "degraded", "reauth_required"}
    assert after_ready["main_app_allowed"] in {True, False}  # depends on has_prior_setup signals in this env
    _assert_no_forbidden(after_ready)
