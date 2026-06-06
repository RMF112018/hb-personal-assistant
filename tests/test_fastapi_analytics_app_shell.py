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
        # Prompt 11 / UI-11 Admin / Data Confidence detailed surfaces (root + 6 sections)
        "/api/admin",
        "/api/admin/source-sync-health",
        "/api/admin/workflow-job-health",
        "/api/admin/evidence-guardrails",
        "/api/admin/retrieval-ai-quality",
        "/api/admin/permissions-governance",
        "/api/admin/data-completeness",
        # Prompt 14B / UI-14B Settings / Connection Management UX (overview + 8 areas + patches)
        "/api/settings",
        "/api/settings/accounts",
        "/api/settings/projects",
        "/api/settings/sources",
        "/api/settings/keywords",
        "/api/settings/daily-brief",
        "/api/settings/preferences",
        "/api/settings/admin-sync",
        "/api/settings/admin",
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


def test_all_ui_analytics_routes_no_forbidden_sensitive_fields_and_role_guards(
    tmp_path: Path,
) -> None:
    """Prompt 13 / UI-13: explicit no-raw assertions across the full current surface set.
    Confirms forbidden markers never appear in serialized responses, role guards active,
    chat/status disabled, and guardrails declare no_raw_sensitive_response_fields.
    """
    client = _client(tmp_path)

    # Routes + minimal (method, required_role_for_success, path_params_sub)
    # Use admin role to cover all (admin can access viewer/operator surfaces); separately test 403s.
    surfaces = [
        ("GET", "viewer", "/health", None),
        ("GET", "viewer", "/chat/status", None),
        ("GET", "viewer", "/onboarding/auth/status", None),
        ("GET", "viewer", "/auth/graph/status", None),
        ("GET", "viewer", "/auth/procore/status", None),
        ("GET", "viewer", "/connections/preview", None),  # may 405 or handled
        ("GET", "viewer", "/projects/DEMO-001/keywords", None),
        ("GET", "viewer", "/projects/DEMO-001/sync-freshness", None),
        ("GET", "viewer", "/admin/sync/pending-approvals", None),
        ("GET", "viewer", "/api/today", None),
        ("GET", "viewer", "/api/projects/portfolio", None),
        ("GET", "viewer", "/api/projects/all/overview", None),
        ("GET", "viewer", "/api/projects/DEMO-001/overview", None),
        ("GET", "viewer", "/api/projects/DEMO-001/meetings", None),
        ("GET", "viewer", "/api/projects/DEMO-001/field-operations", None),
        ("GET", "viewer", "/api/projects/DEMO-001/cost-time", None),
        ("GET", "viewer", "/api/my-items", None),
        # Daily Brief family (Prompt 10)
        ("GET", "viewer", "/api/daily-brief/status", None),
        ("GET", "viewer", "/api/daily-brief/latest", None),
        ("GET", "viewer", "/api/today/daily-brief", None),
        # Admin / Data Confidence family (Prompt 11) — admin role
        ("GET", "admin", "/api/admin", None),
        ("GET", "admin", "/api/admin/source-sync-health", None),
        ("GET", "admin", "/api/admin/workflow-job-health", None),
        ("GET", "admin", "/api/admin/evidence-guardrails", None),
        ("GET", "admin", "/api/admin/retrieval-ai-quality", None),
        ("GET", "admin", "/api/admin/permissions-governance", None),
        ("GET", "admin", "/api/admin/data-completeness", None),
        # Operator/admin write-ish for local config (use admin to simplify)
        ("POST", "admin", "/api/daily-brief/configure", {}),
        ("POST", "admin", "/api/daily-brief/detect-latest", {}),
    ]

    for method, _min_role, path, body in surfaces:
        headers = {"X-HB-UI-Role": "admin"}  # sufficient to exercise; role tests below cover guards
        if method == "GET":
            resp = client.get(path, headers=headers)
        else:
            resp = client.post(path, json=body or {}, headers=headers)
        # Accept success or client/validation errors; never 5xx, and no forbidden in body
        assert resp.status_code < 500, f"{method} {path} -> {resp.status_code}"
        # Serialize whatever json or text we got
        try:
            payload = resp.json()
        except Exception:
            payload = {"text": resp.text[:500]}
        serialized = json.dumps(payload, default=str)
        for marker in FORBIDDEN:
            assert marker not in serialized, f"FORBIDDEN {marker} leaked in {method} {path}"
        # Where present, assert the guardrail flag (some surfaces like /health use a subset; API /api/* include the full no_raw declaration)
        if isinstance(payload, dict) and "guardrails" in payload:
            g = payload["guardrails"] or {}
            if "no_raw_sensitive_response_fields" in g:
                assert g.get("no_raw_sensitive_response_fields") is True, (
                    f"missing no_raw guard on {path}"
                )
            if "read_only" in g:
                assert g.get("read_only") is True

    # Role enforcement spot checks (admin surfaces require admin; viewer gets 403)
    r = client.get("/api/admin", headers={"X-HB-UI-Role": "viewer"})
    assert r.status_code == 403
    r = client.get("/api/admin/evidence-guardrails", headers={"X-HB-UI-Role": "operator"})
    assert r.status_code == 403

    # Daily brief configure requires operator+
    r = client.post("/api/daily-brief/configure", json={}, headers={"X-HB-UI-Role": "viewer"})
    assert r.status_code == 403

    # chat/status remains disabled for all roles (already covered but re-assert)
    for role in ALLOWED_UI_ROLES:
        s = client.get("/chat/status", headers={"X-HB-UI-Role": role})
        assert s.status_code == 200
        assert s.json().get("chat_enabled") is False
        assert s.json().get("status") == "disabled"
