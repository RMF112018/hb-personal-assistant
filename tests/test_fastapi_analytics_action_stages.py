"""N8C-19 read-only action-stage API surface: GET-only, bounded, redacted, non-executing items, no
write/build/execute route; /summary declared before /{stage_id}; 404 on missing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.obsidian_mcp import action_stage_builder as B
from hb_assistant.obsidian_mcp import feedback_service as fs
from hb_assistant.obsidian_mcp.action_stage_repository import ActionStageRepository
from hb_assistant.obsidian_mcp.feedback_repository import FeedbackRepository
from hb_assistant.obsidian_mcp.workflow_router import WorkflowRouter
from hb_assistant.store.migrator import SQLiteMigrator

FORBIDDEN = ("access_token", "refresh_token", "client_secret", "Bearer ", "eyJ",
             "BEGIN PRIVATE KEY", "/Users/", "claim_text", "evidence_excerpt", "email_body")


def _assert_safe(payload: object) -> None:
    blob = json.dumps(payload)
    for needle in FORBIDDEN:
        assert needle not in blob, f"forbidden token leaked: {needle}"


def _seed(db: str) -> str:
    fs.capture_feedback(FeedbackRepository(db), feedback_type="needs_review",
                        targets=[{"target_kind": "open_loop", "target_id": "OL1", "open_loop_id": "OL1"}],
                        apply=True)
    prov = B.ActionStageProviders(router=WorkflowRouter(db), feedback_repo=FeedbackRepository(db))
    out = B.build_action_stage(prov, ActionStageRepository(db),
                               request_inputs={"workflow_type": "open_loop_triage"}, apply=True)
    return out["stage_id"]


@pytest.fixture()
def client(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS", "1")
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    sid = _seed(db)
    return TestClient(create_app(db_path=db)), sid


def test_routes_ok_and_safe(client) -> None:
    c, sid = client
    for path in ("/api/assistant/action-stages",
                 "/api/assistant/action-stages/summary",
                 f"/api/assistant/action-stages/{sid}",
                 f"/api/assistant/action-stages/{sid}/items",
                 f"/api/assistant/action-stages/{sid}/citations",
                 f"/api/assistant/action-stages/{sid}/export"):
        r = c.get(path, headers={"X-HB-UI-Role": "viewer"})
        assert r.status_code == 200, path
        body = r.json()
        assert body["guardrails"]["read_only"] is True
        _assert_safe(body)


def test_summary_not_shadowed(client) -> None:
    c, _sid = client
    body = c.get("/api/assistant/action-stages/summary", headers={"X-HB-UI-Role": "viewer"}).json()
    assert "summary" in body and "total_stages" in body["summary"]


def test_items_are_non_executing(client) -> None:
    c, sid = client
    body = c.get(f"/api/assistant/action-stages/{sid}/items", headers={"X-HB-UI-Role": "viewer"}).json()
    for it in body["items"]:
        assert it["execution_status"] == "not_executed"
        assert it["external_system"] == "none"
        assert it["external_ref"] is None
        assert it["requires_operator_review"] == 1


def test_stage_pins_no_execution_policy(client) -> None:
    c, sid = client
    stage = c.get(f"/api/assistant/action-stages/{sid}", headers={"X-HB-UI-Role": "viewer"}).json()["stage"]
    assert stage["action_policy"] == "no_execution"
    assert stage["execution_policy"] == "staged_only"


def test_missing_returns_404(client) -> None:
    c, _sid = client
    assert c.get("/api/assistant/action-stages/nope").status_code == 404
    assert c.get("/api/assistant/action-stages/nope/items").status_code == 404
    assert c.get("/api/assistant/action-stages/nope/export").status_code == 404


def test_all_roles_allowed(client) -> None:
    c, _sid = client
    for role in ("viewer", "operator", "admin"):
        assert c.get("/api/assistant/action-stages/summary",
                     headers={"X-HB-UI-Role": role}).status_code == 200


def test_routes_are_get_only(client) -> None:
    c, _sid = client
    surface = {
        "/api/assistant/action-stages",
        "/api/assistant/action-stages/summary",
        "/api/assistant/action-stages/{stage_id}",
        "/api/assistant/action-stages/{stage_id}/items",
        "/api/assistant/action-stages/{stage_id}/citations",
        "/api/assistant/action-stages/{stage_id}/export",
    }
    for route in c.app.routes:
        if getattr(route, "path", None) in surface:
            assert route.methods <= {"GET", "HEAD"}, (route.path, route.methods)


def test_no_write_or_build_route(client) -> None:
    c, sid = client
    assert c.post("/api/assistant/action-stages").status_code in {401, 404, 405}
    assert c.post(f"/api/assistant/action-stages/{sid}").status_code in {401, 404, 405}
    assert c.delete("/api/assistant/action-stages").status_code in {401, 404, 405}
