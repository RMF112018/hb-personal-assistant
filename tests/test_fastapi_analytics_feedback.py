"""N8C-18 read-only feedback API surface: GET-only, bounded, redacted, advisory recommendations, no
write/disposition route; /summary and /recommendations declared before /{feedback_id}; 404 on missing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.obsidian_mcp import feedback_service as fs
from hb_assistant.obsidian_mcp.feedback_repository import FeedbackRepository
from hb_assistant.store.migrator import SQLiteMigrator

FORBIDDEN = ("access_token", "refresh_token", "client_secret", "Bearer ", "eyJ",
             "BEGIN PRIVATE KEY", "/Users/", "claim_text", "evidence_excerpt", "email_body")


def _assert_safe(payload: object) -> None:
    blob = json.dumps(payload)
    for needle in FORBIDDEN:
        assert needle not in blob, f"forbidden token leaked: {needle}"


def _seed(db: str) -> str:
    repo = FeedbackRepository(db)
    out = fs.capture_feedback(
        repo, feedback_type="wrong_source",
        targets=[{"target_kind": "citation", "target_id": "C1", "source_ref": "sr-1"}],
        note="check this", created_by="test", apply=True)
    return out["feedback"]["feedback_id"]


@pytest.fixture()
def client(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS", "1")
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    fid = _seed(db)
    return TestClient(create_app(db_path=db)), fid


def test_routes_ok_and_safe(client) -> None:
    c, fid = client
    for path in ("/api/assistant/feedback",
                 "/api/assistant/feedback/summary",
                 "/api/assistant/feedback/recommendations",
                 f"/api/assistant/feedback/{fid}",
                 f"/api/assistant/feedback/{fid}/targets",
                 f"/api/assistant/feedback/{fid}/export"):
        r = c.get(path, headers={"X-HB-UI-Role": "viewer"})
        assert r.status_code == 200, path
        body = r.json()
        assert body["guardrails"]["read_only"] is True
        _assert_safe(body)


def test_summary_and_recommendations_not_shadowed(client) -> None:
    c, _fid = client
    summary = c.get("/api/assistant/feedback/summary", headers={"X-HB-UI-Role": "viewer"}).json()
    assert "summary" in summary and "total_feedback" in summary["summary"]
    recs = c.get("/api/assistant/feedback/recommendations", headers={"X-HB-UI-Role": "viewer"}).json()
    assert "recommendations" in recs


def test_recommendations_are_advisory(client) -> None:
    c, _fid = client
    body = c.get("/api/assistant/feedback/recommendations", headers={"X-HB-UI-Role": "viewer"}).json()
    assert body["count"] >= 1
    for r in body["recommendations"]:
        assert r["review_policy"] == "advisory_review_loop"
        assert r["requires_operator_review"] == 1


def test_record_pins_no_execution_policy(client) -> None:
    c, fid = client
    body = c.get(f"/api/assistant/feedback/{fid}", headers={"X-HB-UI-Role": "viewer"}).json()
    rec = body["feedback"]
    assert rec["action_policy"] == "no_execution"
    assert rec["execution_policy"] == "feedback_only"


def test_missing_returns_404(client) -> None:
    c, _fid = client
    assert c.get("/api/assistant/feedback/nope").status_code == 404
    assert c.get("/api/assistant/feedback/nope/targets").status_code == 404
    assert c.get("/api/assistant/feedback/nope/export").status_code == 404


def test_all_roles_allowed(client) -> None:
    c, _fid = client
    for role in ("viewer", "operator", "admin"):
        assert c.get("/api/assistant/feedback/summary",
                     headers={"X-HB-UI-Role": role}).status_code == 200


def test_routes_are_get_only(client) -> None:
    c, _fid = client
    surface = {
        "/api/assistant/feedback",
        "/api/assistant/feedback/summary",
        "/api/assistant/feedback/recommendations",
        "/api/assistant/feedback/{feedback_id}",
        "/api/assistant/feedback/{feedback_id}/targets",
        "/api/assistant/feedback/{feedback_id}/export",
    }
    for route in c.app.routes:
        if getattr(route, "path", None) in surface:
            assert route.methods <= {"GET", "HEAD"}, (route.path, route.methods)


def test_no_write_or_disposition_route(client) -> None:
    c, fid = client
    assert c.post("/api/assistant/feedback").status_code in {401, 404, 405}
    assert c.post(f"/api/assistant/feedback/{fid}").status_code in {401, 404, 405}
    assert c.delete("/api/assistant/feedback").status_code in {401, 404, 405}
