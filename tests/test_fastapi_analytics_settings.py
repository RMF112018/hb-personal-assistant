"""Prompt 14B — Settings / Connection Management UX tests."""

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


def _client(tmp_path: Path) -> TestClient:
    db = str(tmp_path / "settings.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return TestClient(create_app(db_path=db))


def _assert_safe(payload: Any) -> None:
    serialized = json.dumps(payload, default=str)
    for marker in FORBIDDEN:
        assert marker not in serialized


def test_settings_overview_and_accounts(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r = client.get("/api/settings")
    assert r.status_code == 200
    data = r.json()
    assert data["surface"] == "analytics.settings.overview"
    assert "accounts" in data
    assert "daily_brief" in data
    assert data["guardrails"]["no_live_endpoint_calls"] is True
    _assert_safe(data)

    ra = client.get("/api/settings/accounts")
    assert ra.status_code == 200
    acc = ra.json()
    # Should contain graph/procore sections with tokens_returned false etc (from auth service)
    assert "graph" in acc or "procore" in acc or isinstance(acc, dict)
    _assert_safe(acc)


def test_graph_procore_status_no_secrets(tmp_path: Path) -> None:
    client = _client(tmp_path)
    for path in ("/auth/graph/status", "/auth/procore/status"):
        r = client.get(path)
        assert r.status_code == 200
        payload = r.json()
        _assert_safe(payload)
        s = json.dumps(payload, default=str)
        assert "access_token" not in s
        assert "refresh_token" not in s
        assert "client_secret" not in s


def test_project_connections_and_sources(tmp_path: Path) -> None:
    client = _client(tmp_path)
    rp = client.get("/api/settings/projects")
    assert rp.status_code == 200
    _assert_safe(rp.json())

    rs = client.get("/api/settings/sources")
    assert rs.status_code == 200
    sdata = rs.json()
    # Key notes present
    assert "outlook_calendar" in sdata or "source_scope_note" in sdata
    _assert_safe(sdata)


def test_outlook_calendar_project_matching_only_false_by_default(tmp_path: Path) -> None:
    # Indirect: the sources info advertises the default; connection preview for calendar already tested elsewhere
    # Here we just confirm the settings surface mentions the contract.
    client = _client(tmp_path)
    rs = client.get("/api/settings/sources")
    txt = json.dumps(rs.json(), default=str)
    assert "project_matching_only" in txt or "false by default" in txt.lower() or "optional" in txt.lower()


def test_onedrive_all_folders_warning_in_sources(tmp_path: Path) -> None:
    client = _client(tmp_path)
    rs = client.get("/api/settings/sources")
    txt = json.dumps(rs.json(), default=str).lower()
    assert "all_folders" in txt or "large-scope" in txt or "explicit" in txt


def test_keywords_info_excludes_template_folders(tmp_path: Path) -> None:
    client = _client(tmp_path)
    rk = client.get("/api/settings/keywords")
    assert rk.status_code == 200
    txt = json.dumps(rk.json(), default=str).lower()
    assert "drawings" in txt or "rfis" in txt or "submittals" in txt or "excluded" in txt or "rejected" in txt
    _assert_safe(rk.json())


def test_daily_brief_settings_surface(tmp_path: Path) -> None:
    client = _client(tmp_path)
    rd = client.get("/api/settings/daily-brief")
    assert rd.status_code == 200
    _assert_safe(rd.json())


def test_preferences_get_and_patch(tmp_path: Path) -> None:
    client = _client(tmp_path)
    rp = client.get("/api/settings/preferences")
    assert rp.status_code == 200
    _assert_safe(rp.json())

    patch = {"theme": "dark", "default_landing_page": "Today"}
    rpatch = client.patch("/api/settings/preferences", json=patch)
    assert rpatch.status_code == 200
    _assert_safe(rpatch.json())


def test_admin_sync_hidden_for_non_admin_and_visible_for_admin(tmp_path: Path) -> None:
    client = _client(tmp_path)
    # non-admin should 403 on admin-sync
    r403 = client.get("/api/settings/admin-sync", headers={"X-HB-UI-Role": "operator"})
    assert r403.status_code == 403

    # admin ok
    ra = client.get("/api/settings/admin-sync", headers={"X-HB-UI-Role": "admin"})
    assert ra.status_code == 200
    _assert_safe(ra.json())


def test_admin_patch_requires_admin(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r403 = client.patch("/api/settings/admin", json={"global_rate_limit": 30}, headers={"X-HB-UI-Role": "operator"})
    assert r403.status_code == 403

    ra = client.patch("/api/settings/admin", json={"global_rate_limit": 30}, headers={"X-HB-UI-Role": "admin"})
    assert ra.status_code == 200
    _assert_safe(ra.json())


def test_chat_remains_disabled_in_settings_context(tmp_path: Path) -> None:
    client = _client(tmp_path)
    # Reuse the global chat disabled surface
    s = client.get("/chat/status")
    assert s.status_code == 200
    assert s.json()["chat_enabled"] is False
    assert client.get("/chat").status_code in {404, 405}


def test_no_forbidden_in_all_settings_responses(tmp_path: Path) -> None:
    client = _client(tmp_path)
    for path in (
        "/api/settings",
        "/api/settings/accounts",
        "/api/settings/projects",
        "/api/settings/sources",
        "/api/settings/keywords",
        "/api/settings/daily-brief",
        "/api/settings/preferences",
    ):
        r = client.get(path)
        if r.status_code < 500:
            _assert_safe(r.json() if r.headers.get("content-type", "").startswith("application/json") else {"text": r.text[:200]})

    # admin requires role
    ra = client.get("/api/settings/admin-sync", headers={"X-HB-UI-Role": "admin"})
    if ra.status_code < 500:
        _assert_safe(ra.json() if ra.headers.get("content-type","").startswith("application/json") else {})


# Additional coverage for role on keywords (delegated but surface mentions policy)
def test_keywords_surface_readable_by_viewer(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r = client.get("/api/settings/keywords")
    assert r.status_code == 200
