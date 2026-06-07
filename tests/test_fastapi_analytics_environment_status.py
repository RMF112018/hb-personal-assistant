"""P01 — /api/environment and /api/sources/status contract tests.

Asserts the two new status routes are browser-safe and offline:
- return 200 for all roles;
- never leak tokens/secrets/cache paths;
- never construct a live Graph/Procore data client;
- report live-read flags OFF by default (Dev live refresh disabled by default).
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
    "BEGIN PRIVATE KEY",
    "access_token",
    "refresh_token",
    "client_secret",
    "raw_body",
    "raw_document_text",
    "raw_calendar_payload",
    "raw_prompt",
    "raw_response",
    "signed_url",
    "download_url",
)

_FAKE_COMBINED: dict[str, Any] = {
    "surface": "analytics.auth_onboarding.status",
    "graph": {
        "token_type": "none",
        "classification": "absent",
        "account": None,
        "expires_in_seconds_if_known": None,
    },
    "procore": {
        "status": "absent",
        "cache_present": False,
        "ready_for_live_calls": False,
        "expires_in_seconds_if_known": None,
    },
    "ready": {"graph_delegated": False, "procore_oauth": False},
    "guardrails": {"tokens_returned": False, "secrets_returned": False},
}


@pytest.fixture(autouse=True)
def _hermetic_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make auth status deterministic and offline (do not read the machine's real cache)."""
    monkeypatch.setattr(
        "hb_assistant.construction.analytics.auth_onboarding.AuthOnboardingService.build_combined_status",
        lambda self: dict(_FAKE_COMBINED),
    )


def _client(tmp_path: Path) -> TestClient:
    db = str(tmp_path / "envstatus.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return TestClient(create_app(db_path=db))


def _assert_safe(payload: Any) -> None:
    serialized = json.dumps(payload, default=str)
    for marker in FORBIDDEN:
        assert marker not in serialized


def test_environment_returns_200_and_is_safe(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = client.get("/api/environment")

    assert response.status_code == 200
    payload = response.json()
    assert payload["surface"] == "analytics.environment"
    assert payload["environment"] in {"dev", "production"}
    assert "source_refresh_mode" in payload
    g = payload["guardrails"]
    assert g["read_only"] is True
    assert g["no_live_endpoint_calls"] is True
    _assert_safe(payload)


def test_environment_live_flags_off_by_default(tmp_path: Path) -> None:
    client = _client(tmp_path)
    payload = client.get("/api/environment").json()

    live = payload["live_reads"]
    assert live["enable_live_reads"] is False
    assert live["enable_procore_live_reads"] is False
    assert live["enable_graph_live_reads"] is False
    # Dev live refresh disabled by default (and prod defaults off too).
    assert payload["live_refresh"]["enabled"] is False


def test_environment_all_roles_accessible(tmp_path: Path) -> None:
    client = _client(tmp_path)
    for role in ("viewer", "operator", "admin"):
        r = client.get("/api/environment", headers={"X-HB-UI-Role": role})
        assert r.status_code == 200


def test_sources_status_returns_200_with_summaries(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = client.get("/api/sources/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["surface"] == "analytics.sources.status"
    assert "graph" in payload
    assert "procore" in payload
    assert "scheduler" in payload
    assert payload["graph"]["system"] == "microsoft_365_graph"
    assert payload["procore"]["system"] == "procore"
    assert payload["guardrails"]["no_live_endpoint_calls"] is True
    _assert_safe(payload)


def test_dev_mode_reports_local_mock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dev_root = tmp_path / "HB Personal Assistant (Dev)"
    monkeypatch.setattr(
        "hb_assistant.config.path_policy.PathPolicy.get_app_support",
        lambda self: dev_root,
    )
    client = _client(tmp_path)

    env_payload = client.get("/api/environment").json()
    assert env_payload["environment"] == "dev"
    assert env_payload["source_refresh_mode"] == "mock_data"
    assert env_payload["live_refresh"]["enabled"] is False
    assert env_payload["live_refresh"]["reason"] == "dev_local_mock_only"

    src_payload = client.get("/api/sources/status").json()
    assert src_payload["environment"] == "dev"
    assert src_payload["source_refresh_mode"] == "mock_data"


def test_status_never_constructs_live_data_clients(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("live data client must not be constructed by status endpoints")

    monkeypatch.setattr("hb_assistant.graph.http_client.GraphHttpClient", _boom)
    monkeypatch.setattr("hb_assistant.procore.http_client.ProcoreHTTPClient", _boom)

    client = _client(tmp_path)
    assert client.get("/api/environment").status_code == 200
    assert client.get("/api/sources/status").status_code == 200
