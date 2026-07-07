"""N8C-20 read-only quality API surface: GET-only, bounded, redacted, advisory findings, no
write/build/evaluate/repair route; /summary declared before /{quality_run_id}; 404 on missing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.obsidian_mcp import feedback_service as fs
from hb_assistant.obsidian_mcp.feedback_repository import FeedbackRepository
from hb_assistant.obsidian_mcp.quality_evaluator import QualityProviders, build_quality
from hb_assistant.obsidian_mcp.quality_repository import QualityRepository
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
    res = build_quality(QualityProviders(feedback_repo=FeedbackRepository(db)), QualityRepository(db),
                        target_kind="feedback", target_id="OL1", apply=True)
    return res["quality_run_id"]


@pytest.fixture()
def client(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS", "1")
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    qid = _seed(db)
    return TestClient(create_app(db_path=db)), qid


def test_routes_ok_and_safe(client) -> None:
    c, qid = client
    for path in ("/api/assistant/quality",
                 "/api/assistant/quality/summary",
                 f"/api/assistant/quality/{qid}",
                 f"/api/assistant/quality/{qid}/findings",
                 f"/api/assistant/quality/{qid}/targets",
                 f"/api/assistant/quality/{qid}/export"):
        r = c.get(path, headers={"X-HB-UI-Role": "viewer"})
        assert r.status_code == 200, path
        body = r.json()
        assert body["guardrails"]["read_only"] is True
        _assert_safe(body)


def test_summary_not_shadowed(client) -> None:
    c, _qid = client
    body = c.get("/api/assistant/quality/summary", headers={"X-HB-UI-Role": "viewer"}).json()
    assert "summary" in body and "total_runs" in body["summary"]


def test_run_pins_advisory_policy(client) -> None:
    c, qid = client
    run = c.get(f"/api/assistant/quality/{qid}", headers={"X-HB-UI-Role": "viewer"}).json()["run"]
    assert run["action_policy"] == "no_execution"
    assert run["execution_policy"] == "evaluate_only"
    assert run["status"] == "evaluated"
    assert run["requires_operator_review"] == 1


def test_findings_are_advisory(client) -> None:
    c, qid = client
    body = c.get(f"/api/assistant/quality/{qid}/findings", headers={"X-HB-UI-Role": "viewer"}).json()
    for f in body["findings"]:
        assert f["execution_policy"] == "evaluate_only"
        assert f["requires_operator_review"] == 1


def test_missing_returns_404(client) -> None:
    c, _qid = client
    assert c.get("/api/assistant/quality/nope").status_code == 404
    assert c.get("/api/assistant/quality/nope/findings").status_code == 404
    assert c.get("/api/assistant/quality/nope/export").status_code == 404


def test_all_roles_allowed(client) -> None:
    c, _qid = client
    for role in ("viewer", "operator", "admin"):
        assert c.get("/api/assistant/quality/summary", headers={"X-HB-UI-Role": role}).status_code == 200


def test_routes_are_get_only(client) -> None:
    c, _qid = client
    surface = {
        "/api/assistant/quality",
        "/api/assistant/quality/summary",
        "/api/assistant/quality/{quality_run_id}",
        "/api/assistant/quality/{quality_run_id}/findings",
        "/api/assistant/quality/{quality_run_id}/targets",
        "/api/assistant/quality/{quality_run_id}/export",
    }
    for route in c.app.routes:
        if getattr(route, "path", None) in surface:
            assert route.methods <= {"GET", "HEAD"}, (route.path, route.methods)


def test_no_write_or_build_route(client) -> None:
    c, qid = client
    assert c.post("/api/assistant/quality").status_code in {401, 404, 405}
    assert c.post(f"/api/assistant/quality/{qid}").status_code in {401, 404, 405}
    assert c.delete("/api/assistant/quality").status_code in {401, 404, 405}
