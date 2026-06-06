"""Prompt 06 — sync governance surfaces (admin approval/schedule, user refresh, freshness)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.store.connection import get_connection
from hb_assistant.store.migrator import SQLiteMigrator

FORBIDDEN = (
    "access_token",
    "refresh_token",
    "client_secret",
    "raw_body",
    "raw_prompt",
    "raw_response",
    "downloadUrl",
    "token=",
    "sig=",
    "BEGIN PRIVATE",
)


def _client(tmp_path: Path) -> tuple[TestClient, str]:
    db = str(tmp_path / "sync-governance.sqlite")
    SQLiteMigrator(db_path=db).apply()
    conn = get_connection(db)
    # Seed a project and a source + sync state so freshness/request have data
    conn.execute(
        """
        INSERT OR IGNORE INTO construction_project_identity
            (project_key, project_name_raw, is_active, match_status, match_confidence)
        VALUES ('gov-test-proj', 'Governance Test', 1, 'confirmed', 'high')
        """
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO construction_source_locations
            (source_id, source_system, source_scope, source_name, project_key, enabled, read_only, created_utc, updated_utc)
        VALUES ('gov-src-1', 'sharepoint', 'sharepoint_project_drive_folder', 'Gov Docs', 'gov-test-proj', 1, 1, ?, ?)
        """,
        (datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat()),
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO construction_source_sync_state
            (source_id, last_successful_sync_utc, last_attempted_sync_utc, sync_status)
        VALUES ('gov-src-1', ?, ?, 'approved_first_sync_not_started')
        """,
        (datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    return TestClient(create_app(db_path=db)), db


def _assert_safe(payload: Any) -> None:
    serialized = json.dumps(payload, default=str)
    for marker in FORBIDDEN:
        assert marker not in serialized


def test_user_refresh_request_operator_marks_state(tmp_path: Path) -> None:
    client, db = _client(tmp_path)
    r = client.post(
        "/projects/gov-test-proj/refresh-request",
        headers={"X-HB-UI-Role": "operator"},
        json={},
    )
    assert r.status_code == 200
    payload = r.json()
    assert payload["ok"] is True
    assert payload["kind"] == "user_refresh_requested"
    assert payload["project_key"] == "gov-test-proj"
    _assert_safe(payload)

    # Verify via store
    store = ConstructionStore(db)
    st = store.get_source_sync_state("gov-src-1")
    assert st is not None
    assert st["sync_status"] == "user_refresh_requested"


def test_viewer_cannot_request_refresh(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    r = client.post("/projects/gov-test-proj/refresh-request", json={})
    assert r.status_code == 403
    assert r.json()["detail"] == "operator_role_required"


def test_project_sync_freshness_viewer_ok_and_shape(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    r = client.get("/projects/gov-test-proj/sync-freshness")
    assert r.status_code == 200
    payload = r.json()
    assert payload["surface"] == "analytics.sync_governance.project_freshness"
    assert payload["project_key"] == "gov-test-proj"
    assert "overall_freshness" in payload
    assert "sources" in payload
    assert payload["guardrails"]["freshness_computed_from_local_sync_state"] is True
    _assert_safe(payload)
    # At least the seeded source appears
    assert any(s["source_id"] == "gov-src-1" for s in payload["sources"])


def test_admin_pending_approvals_sees_markers(tmp_path: Path) -> None:
    client, db = _client(tmp_path)
    # Set one to pending for visibility
    store = ConstructionStore(db)
    store.upsert_source_sync_state(source_id="gov-src-1", sync_status="pending_admin_approval")

    r = client.get("/admin/sync/pending-approvals", headers={"X-HB-UI-Role": "admin"})
    assert r.status_code == 200
    payload = r.json()
    assert payload["surface"] == "analytics.sync_governance.pending_approvals"
    assert payload["count"] >= 1
    assert any("pending" in (i.get("sync_status") or "") for i in payload["items"])
    _assert_safe(payload)


def test_admin_only_for_pending_list(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    r = client.get("/admin/sync/pending-approvals", headers={"X-HB-UI-Role": "operator"})
    assert r.status_code == 403
    assert r.json()["detail"] == "admin_role_required"
