"""N8C-15 read-only workflow API surface: GET-only catalog + route, bounded, redacted, no write/build/
execute route, no workflow-run persistence."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.store.migrator import SQLiteMigrator

FORBIDDEN = ("access_token", "refresh_token", "client_secret", "Bearer ", "eyJ",
             "BEGIN PRIVATE KEY", "result_json", "/Users/", "final_answer", "answer_text",
             "generated_answer", "operator_approved_answer", "authoritative_answer", "metadata_json")


def _assert_safe(payload: object) -> None:
    blob = json.dumps(payload)
    for needle in FORBIDDEN:
        assert needle not in blob, f"forbidden token leaked: {needle}"


@pytest.fixture()
def client(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS", "1")
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO assistant_answer_drafts (draft_id, draft_type, status, citation_count) "
                  "VALUES (?,?,?,?)", ("D1", "review_aware_answer_draft", "built", 0))
    return TestClient(create_app(db_path=db))


def test_catalog_route_ok_and_safe(client) -> None:
    r = client.get("/api/assistant/workflows/catalog", headers={"X-HB-UI-Role": "viewer"})
    assert r.status_code == 200
    body = r.json()
    assert body["guardrails"]["read_only"] is True
    assert len(body["catalog"]["workflow_types"]) == 11
    _assert_safe(body)


def test_route_endpoint_routes_and_carries_policies(client) -> None:
    r = client.get("/api/assistant/workflows/route",
                   params={"workflow_type": "draft_review", "draft_id": "D1"},
                   headers={"X-HB-UI-Role": "viewer"})
    assert r.status_code == 200
    env = r.json()["workflow"]
    assert env["status"] == "routed"
    assert env["action_policy"] == "no_execution" and env["execution_policy"] == "route_only"
    assert "draft_has_no_citations" in env["warnings"]
    _assert_safe(r.json())


def test_route_source_lookup_no_db_dependency(client) -> None:
    r = client.get("/api/assistant/workflows/route",
                   params={"workflow_type": "source_file_lookup", "query": "invoice pdf"},
                   headers={"X-HB-UI-Role": "viewer"})
    env = r.json()["workflow"]
    assert env["routing_decision"]["primary_target"] == "source_connector"


def test_routes_are_get_only(client) -> None:
    # No POST/PUT/PATCH/DELETE workflow route exists — a POST must not be accepted (405/404).
    for method in ("post", "put", "patch", "delete"):
        resp = getattr(client, method)("/api/assistant/workflows/route",
                                       headers={"X-HB-UI-Role": "viewer"})
        assert resp.status_code in (404, 405), f"{method} unexpectedly accepted"


def test_catalog_before_param_route(client) -> None:
    # /catalog is a literal path and must resolve to the catalog handler, not a param route.
    body = client.get("/api/assistant/workflows/catalog", headers={"X-HB-UI-Role": "viewer"}).json()
    assert "catalog" in body and "workflows" in body["catalog"]
