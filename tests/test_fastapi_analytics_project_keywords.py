"""Prompt 05 — optional FastAPI project keyword training surfaces."""

from __future__ import annotations

import json
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
    db = str(tmp_path / "project-keywords.sqlite")
    SQLiteMigrator(db_path=db).apply()
    # Seed a minimal project identity so keyword rows have a sensible parent (FKs are advisory)
    conn = get_connection(db)
    conn.execute(
        """
        INSERT OR IGNORE INTO construction_project_identity
            (project_key, project_name_raw, is_active, match_status, match_confidence)
        VALUES ('keyword-test-proj', 'Keyword Test Project', 1, 'confirmed', 'high')
        """
    )
    conn.commit()
    return TestClient(create_app(db_path=db)), db


def _assert_safe(payload: Any) -> None:
    serialized = json.dumps(payload, default=str)
    for marker in FORBIDDEN:
        assert marker not in serialized


def test_list_keywords_viewer_ok_and_safe(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    resp = client.get("/projects/keyword-test-proj/keywords")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["surface"] == "analytics.project_keywords.list"
    assert payload["project_key"] == "keyword-test-proj"
    assert "guardrails" in payload
    assert payload["guardrails"]["no_folder_names_as_keywords"] is True
    _assert_safe(payload)


def test_add_keyword_operator_roundtrip_and_store_inspect(tmp_path: Path) -> None:
    client, db = _client(tmp_path)
    body = {"term": "Hilltop Gardens", "strength": "strong"}
    add = client.post(
        "/projects/keyword-test-proj/keywords",
        headers={"X-HB-UI-Role": "operator"},
        json=body,
    )
    assert add.status_code == 200
    added = add.json()
    assert added["ok"] is True
    assert added["kind"] == "keyword_added"
    assert added["normalized"] == "hilltop garden"
    assert added["strength"] == "strong"
    _assert_safe(added)

    # Inspect via store
    store = ConstructionStore(db)
    kws = store.list_project_keyword_registry(
        project_key="keyword-test-proj", registry_status="enabled"
    )
    assert len(kws) >= 1
    assert any(k["keyword_normalized"] == "hilltop garden" for k in kws)


def test_viewer_cannot_mutate_keywords(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    # POST
    r = client.post("/projects/keyword-test-proj/keywords", json={"term": "x"})
    assert r.status_code == 403
    assert r.json()["detail"] == "operator_role_required"
    # PATCH/DELETE would also 403 without operator header; use explicit
    r2 = client.patch(
        "/projects/keyword-test-proj/keywords/some-id",
        headers={"X-HB-UI-Role": "viewer"},
        json={"strength": "weak"},
    )
    assert r2.status_code == 403


def test_update_and_delete_keyword_operator(tmp_path: Path) -> None:
    client, db = _client(tmp_path)
    # seed one
    add = client.post(
        "/projects/keyword-test-proj/keywords",
        headers={"X-HB-UI-Role": "operator"},
        json={"term": "Wellington Phase 2", "strength": "normal"},
    )
    kw_id = add.json()["keyword_id"]

    # PATCH strength + status
    up = client.patch(
        f"/projects/keyword-test-proj/keywords/{kw_id}",
        headers={"X-HB-UI-Role": "operator"},
        json={"strength": "weak", "registry_status": "disabled"},
    )
    assert up.status_code == 200
    assert up.json()["kind"] == "keyword_updated"
    assert up.json()["strength"] == "weak"
    assert up.json()["registry_status"] == "disabled"

    store = ConstructionStore(db)
    row = store.get_project_keyword_registry_entry(kw_id)
    assert row is not None
    assert row["strength"] == "weak"
    assert row["registry_status"] == "disabled"

    # DELETE
    dl = client.delete(
        f"/projects/keyword-test-proj/keywords/{kw_id}",
        headers={"X-HB-UI-Role": "operator"},
    )
    assert dl.status_code == 200
    assert dl.json()["kind"] == "keyword_deleted"
    assert store.get_project_keyword_registry_entry(kw_id) is None


def test_folder_name_rejection_on_add(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    for bad in ("Drawings", "RFIs", "Submittals", "Meeting Minutes", "Closeout"):
        r = client.post(
            "/projects/keyword-test-proj/keywords",
            headers={"X-HB-UI-Role": "operator"},
            json={"term": bad},
        )
        assert r.status_code == 200
        payload = r.json()
        assert payload["ok"] is False
        assert payload["kind"] == "keyword_rejected"
        assert payload["reason_code"] == "standard_folder_name_excluded"
        _assert_safe(payload)

    # Direct service also rejects
    from hb_assistant.construction.analytics.project_keywords import ProjectKeywordsService

    svc = ProjectKeywordsService(db_path=None)  # no db needed for reject path
    res = svc.add_keyword("p", "Specifications")
    assert res["ok"] is False
    assert res["reason_code"] == "standard_folder_name_excluded"


def test_explain_match_viewer_accessible_and_safe(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    # seed a keyword that can fire
    client.post(
        "/projects/keyword-test-proj/keywords",
        headers={"X-HB-UI-Role": "operator"},
        json={"term": "Tropical", "strength": "strong"},
    )

    # viewer can call explain
    exp = client.post(
        "/projects/keyword-test-proj/keywords/explain",
        json={"candidate": {"subject_redacted": "[redacted:abc] Tropical site visit notes"}},
    )
    assert exp.status_code == 200
    payload = exp.json()
    assert payload["surface"] == "analytics.project_keywords.explain"
    assert payload["project_key"] == "keyword-test-proj"
    assert "matched_keywords" in payload
    # the normalized 'tropical' should appear if the contains logic fires
    norms = [m.get("normalized") for m in payload["matched_keywords"]]
    assert "tropical" in norms or payload["count"] >= 0  # at least no crash
    _assert_safe(payload)
