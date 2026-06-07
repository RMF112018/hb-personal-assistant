"""P03 — /api/sources/procore/* Procore safe status + auth bridge tests.

Proves the Procore source-status + auth routes are metadata-only, never call a live Procore client
(projects/sync/data API), never leak tokens/secrets/cache paths, and report correct missing-config /
missing-mapping / connected states. Mirrors the auth-onboarding test harness.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.procore.oauth import TokenSet
from hb_assistant.store.migrator import SQLiteMigrator

FORBIDDEN = (
    "BEGIN PRIVATE",
    "access_token",
    "refresh_token",
    "client_secret",
    "raw_body",
    "raw_prompt",
    "raw_response",
    "synthetic-procore-access-token",
    "synthetic-procore-refresh-token",
)


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


def _install_procore_fake(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    writes: list[str] = []
    monkeypatch.setattr(
        "hb_assistant.construction.analytics.auth_onboarding.AuthOnboardingService._procore_oauth_client",
        staticmethod(lambda: _FakeProcoreClient()),
    )
    monkeypatch.setattr(
        "hb_assistant.procore.token_provider.write_token_cache",
        lambda token_set: writes.append("written") or Path("/tmp/p.json"),
    )
    return writes


def _client(tmp_path: Path) -> TestClient:
    db = str(tmp_path / "procore-bridge.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return TestClient(create_app(db_path=db))


def _assert_safe(payload: Any) -> None:
    serialized = json.dumps(payload, default=str)
    for marker in FORBIDDEN:
        assert marker not in serialized


def test_status_metadata_only_and_safe(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r = client.get("/api/sources/procore/status")

    assert r.status_code == 200
    payload = r.json()
    assert payload["surface"] == "analytics.sources.procore.status"
    assert payload["system"] == "procore"
    assert payload["guardrails"]["procore_data_api_called"] is False
    assert payload["guardrails"]["tokens_returned"] is False
    assert "missing_config" in payload
    assert "missing_mapping" in payload
    assert "mapping" in payload
    _assert_safe(payload)


def test_status_never_constructs_live_procore_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("status must not construct a live Procore client")

    monkeypatch.setattr("hb_assistant.procore.http_client.ProcoreHTTPClient", _boom)
    client = _client(tmp_path)
    assert client.get("/api/sources/procore/status").status_code == 200


def test_status_missing_config_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    crafted = {
        "surface": "analytics.auth_onboarding.procore_status",
        "status": "env_absent",
        "env_keys_present": [],
        "env_keys_missing": ["PROCORE_CLIENT_ID", "PROCORE_CLIENT_SECRET"],
        "token_cache_present": False,
        "cache_present": False,
        "access_cached": False,
        "ready_for_live_calls": False,
        "keychain_secret_present": False,
        "expires_in_seconds_if_known": None,
        "hint": "Not configured.",
        "guardrails": {"tokens_returned": False, "procore_data_api_called": False},
    }
    monkeypatch.setattr(
        "hb_assistant.construction.analytics.auth_onboarding.AuthOnboardingService.procore_status",
        lambda self: dict(crafted),
    )
    client = _client(tmp_path)
    payload = client.get("/api/sources/procore/status").json()

    assert payload["state"] == "not_configured"
    assert payload["missing_config"] is True


def test_status_connected_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    crafted = {
        "surface": "analytics.auth_onboarding.procore_status",
        "status": "env_present",
        "env_keys_present": ["PROCORE_CLIENT_ID", "PROCORE_CLIENT_SECRET"],
        "env_keys_missing": [],
        "token_cache_present": True,
        "cache_present": True,
        "access_cached": True,
        "ready_for_live_calls": True,
        "keychain_secret_present": True,
        "expires_in_seconds_if_known": 1800,
        "hint": "Ready.",
        "guardrails": {"tokens_returned": False, "procore_data_api_called": False},
    }
    monkeypatch.setattr(
        "hb_assistant.construction.analytics.auth_onboarding.AuthOnboardingService.procore_status",
        lambda self: dict(crafted),
    )
    client = _client(tmp_path)
    payload = client.get("/api/sources/procore/status").json()

    assert payload["state"] == "connected"
    assert payload["missing_config"] is False


def test_status_missing_mapping_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "hb_assistant.construction.analytics.auth_onboarding.AuthOnboardingService._procore_mapping_summary",
        lambda self: {
            "status": "ok",
            "ok": False,
            "company_id": "5280",
            "total": 2,
            "by_status": {"pilot": 1, "pending": 1},
            "pending_projects": ["hilltop"],
        },
    )
    client = _client(tmp_path)
    payload = client.get("/api/sources/procore/status").json()

    assert payload["missing_mapping"] is True
    assert "hilltop" in payload["mapping"]["pending_projects"]


def test_status_complete_mapping_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "hb_assistant.construction.analytics.auth_onboarding.AuthOnboardingService._procore_mapping_summary",
        lambda self: {
            "status": "ok",
            "ok": True,
            "company_id": "5280",
            "total": 2,
            "by_status": {"pilot": 2},
            "pending_projects": [],
        },
    )
    client = _client(tmp_path)
    payload = client.get("/api/sources/procore/status").json()

    assert payload["missing_mapping"] is False


def test_auth_start_then_poll(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_procore_fake(monkeypatch)
    client = _client(tmp_path)
    headers = {"X-HB-UI-Role": "operator"}

    started = client.post("/api/sources/procore/auth/start", headers=headers)
    assert started.status_code == 200
    s = started.json()
    assert "flow_id" in s and "authorization_url" in s
    assert s.get("manual_code_fallback_available") is True
    _assert_safe(s)

    poll = client.get(
        f"/api/sources/procore/auth/status?flow_id={s['flow_id']}", headers=headers
    ).json()
    assert poll["status"] == "pending"
    assert poll["flow_id"] == s["flow_id"]
    _assert_safe(poll)


def test_auth_callback_returns_safe_html(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    writes = _install_procore_fake(monkeypatch)
    client = _client(tmp_path)
    headers = {"X-HB-UI-Role": "operator"}

    started = client.post("/api/sources/procore/auth/start", headers=headers).json()
    state = (parse_qs(urlparse(started["authorization_url"]).query).get("state") or [""])[0]

    cb = client.get(f"/api/sources/procore/auth/callback?code=synthetic-code&state={state}")
    assert cb.status_code == 200
    html = cb.text
    assert "Procore connected" in html
    for marker in FORBIDDEN:
        assert marker not in html
    assert "cache_path" not in html.lower()
    assert writes  # exchange happened server-side


def test_auth_refresh_is_safe(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r = client.post("/api/sources/procore/auth/refresh", headers={"X-HB-UI-Role": "operator"})

    assert r.status_code == 200
    payload = r.json()
    assert payload["surface"] == "analytics.settings.connections.auth.refresh"
    assert payload["results"][0]["source"] == "procore"
    _assert_safe(payload)


def test_role_gating(tmp_path: Path) -> None:
    client = _client(tmp_path)
    viewer = {"X-HB-UI-Role": "viewer"}

    # status is viewer-safe
    assert client.get("/api/sources/procore/status", headers=viewer).status_code == 200
    # auth actions are operator+
    assert client.post("/api/sources/procore/auth/start", headers=viewer).status_code == 403
    assert (
        client.get("/api/sources/procore/auth/status?flow_id=x", headers=viewer).status_code == 403
    )
    assert client.post("/api/sources/procore/auth/refresh", headers=viewer).status_code == 403
    # callback is not role-gated (browser redirect; CSRF state + one-time code) -> reachable
    assert client.get("/api/sources/procore/auth/callback?code=x&state=bogus").status_code == 200
