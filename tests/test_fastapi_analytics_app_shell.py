"""Prompt 02 — optional FastAPI analytics app shell tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import ALLOWED_UI_ROLES, create_app
from hb_assistant.store.migrator import SQLiteMigrator

FORBIDDEN = (
    "BEGIN PRIVATE KEY",
    "access_token",
    "client_secret",
    "raw_body",
    "raw_prompt",
    "raw_response",
    "signed_url",
    "download_url",
)


def _client(tmp_path: Path) -> TestClient:
    db = str(tmp_path / "api.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return TestClient(create_app(db_path=db))


def test_health_is_metadata_only_and_chat_disabled(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["surface"] == "analytics.fastapi_shell"
    assert payload["chat_enabled"] is False
    assert payload["guardrails"]["read_only"] is True
    assert payload["guardrails"]["active_chat_routes"] is False
    assert payload["role"]["role"] == "viewer"

    serialized = json.dumps(payload, default=str)
    for marker in FORBIDDEN:
        assert marker not in serialized


def test_openapi_exposes_only_shell_routes(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = set(response.json()["paths"])
    assert paths == {
        "/health",
        "/chat/status",
        "/onboarding/auth/status",
        "/auth/graph/status",
        "/auth/graph/device-login/start",
        "/auth/graph/device-login/complete",
        "/auth/procore/status",
        "/auth/procore/oauth/start",
        "/auth/procore/oauth/exchange",
        "/connections/preview",
        "/connections/save",
        "/admin/connections/{connection_id}/approve-first-sync",
        "/admin/projects/{project_key}/sync-schedule",
        "/projects/{project_key}/keywords",
        "/projects/{project_key}/keywords/{keyword_id}",
        "/projects/{project_key}/keywords/explain",
        "/projects/{project_key}/refresh-request",
        "/projects/{project_key}/sync-freshness",
        "/admin/sync/pending-approvals",
        "/api/today",
        "/api/projects/portfolio",
        "/api/projects/all/overview",
        "/api/projects/{project_key}/overview",
        "/api/projects/{project_key}/meetings",
        "/api/projects/{project_key}/field-operations",
        "/api/projects/{project_key}/cost-time",
        "/api/my-items",
        # Prompt 10 / UI-10 Daily Brief external workflow surfaces
        "/api/daily-brief/status",
        "/api/daily-brief/latest",
        "/api/daily-brief/configure",
        "/api/daily-brief/generate-setup-instructions",
        "/api/daily-brief/validate-output-folder",
        "/api/daily-brief/detect-latest",
        "/api/today/daily-brief",
    }
    assert response.json()["info"]["title"] == "HB Personal Assistant Analytics UI Shell"


def test_valid_roles_can_access_health_and_chat_status(tmp_path: Path) -> None:
    client = _client(tmp_path)

    for role in ALLOWED_UI_ROLES:
        headers = {"X-HB-UI-Role": role}
        assert client.get("/health", headers=headers).status_code == 200
        status_response = client.get("/chat/status", headers=headers)
        assert status_response.status_code == 200
        assert status_response.json()["chat_enabled"] is False
        assert status_response.json()["status"] == "disabled"


def test_invalid_role_is_forbidden(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/health", headers={"X-HB-UI-Role": "writer"})
    assert response.status_code == 403
    assert response.json()["detail"] == "invalid_ui_role"


def test_active_chat_routes_are_inaccessible(tmp_path: Path) -> None:
    client = _client(tmp_path)

    assert client.get("/chat").status_code in {404, 405}
    for path in ("/chat", "/chat/send", "/chat/completions"):
        response = client.post(path, json={"message": "hello"})
        assert response.status_code in {404, 405}
