"""N8C-8 read-only decision-memory API surface: GET-only, bounded, redacted, no write route."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.obsidian_mcp import context_pack_builder as CB
from hb_assistant.obsidian_mcp import decision_memory_extractor as EX
from hb_assistant.obsidian_mcp.claim_models import ClaimCandidate
from hb_assistant.obsidian_mcp.claim_repository import ClaimRepository
from hb_assistant.obsidian_mcp.context_pack_models import Budget
from hb_assistant.obsidian_mcp.context_pack_repository import ContextPackRepository
from hb_assistant.obsidian_mcp.decision_memory_repository import DecisionMemoryRepository
from hb_assistant.obsidian_mcp.enrichment_repository import EnrichmentRepository
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.store.migrator import SQLiteMigrator

FORBIDDEN = ("access_token", "refresh_token", "client_secret", "Bearer ", "eyJ",
             "BEGIN PRIVATE KEY", "result_json", "/Users/")


def _assert_safe(payload: object) -> None:
    blob = json.dumps(payload)
    for needle in FORBIDDEN:
        assert needle not in blob, f"forbidden token leaked: {needle}"


@pytest.fixture()
def client(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS", "1")
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    er, cr, sr = EnrichmentRepository(db), ClaimRepository(db), SourceIndexRepository(db)
    pr, dr = ContextPackRepository(db), DecisionMemoryRepository(db)
    cr.ingest_candidates(
        [ClaimCandidate(claim_type="decision_candidate", claim_text="We decided to keep MCP read-only",
                        evidence_excerpt="ev", confidence=0.8, normalized_subject="mcp",
                        normalized_object="keep read-only"),
         ClaimCandidate(claim_type="preference", claim_text="prefer no ai trailer",
                        evidence_excerpt="ev", confidence=0.7, normalized_subject="commits",
                        normalized_object="no ai trailer"),
         ClaimCandidate(claim_type="commitment", claim_text="I will send the schedule",
                        evidence_excerpt="ev", confidence=0.7, normalized_subject="sched",
                        normalized_object="send schedule")],
        source_id="s1", note_rel_path="Cards/s1.md", extractor_version="rule_based-v1")
    j = er.queue_job(job_type="claim_extraction", source_id="s1")
    er.claim_next_job("w", 300)
    er.mark_running(j["job_id"], "w")
    er.complete_job(j["job_id"], "w", status="completed",
                    result_json=json.dumps({"claims": [], "count": 0}),
                    applied_status="stored_only", receipt_metadata={"output_digest": "d1"})
    from hb_assistant.obsidian_mcp.memory_repository import MemoryRepository
    pack = CB.build_context_pack(CB.PackRequest(pack_type="enrichment_review", budget=Budget(max_items=20)),
                                 CB.Providers(er, cr, sr), pr, apply=True)["pack_id"]
    prov = EX.DecisionMemoryProviders(cr, pr, er, sr, MemoryRepository(db))
    EX.apply_decision_memory(prov, dr, pack_id=pack, apply=True)
    did = dr.list_decisions()[0]["decision_id"]
    pid = dr.list_preferences()[0]["preference_id"]
    oid = dr.list_open_loops()[0]["open_loop_id"]
    return TestClient(create_app(db_path=db)), did, pid, oid


def test_routes_ok_and_safe(client) -> None:
    c, did, pid, oid = client
    for path in ("/api/assistant/decisions", f"/api/assistant/decisions/{did}",
                 "/api/assistant/preferences", f"/api/assistant/preferences/{pid}",
                 "/api/assistant/open-loops", f"/api/assistant/open-loops/{oid}"):
        r = c.get(path, headers={"X-HB-UI-Role": "viewer"})
        assert r.status_code == 200, path
        body = r.json()
        assert body["guardrails"]["read_only"] is True
        _assert_safe(body)


def test_list_shapes_have_counts(client) -> None:
    c, _did, _pid, _oid = client
    assert "count" in c.get("/api/assistant/decisions").json()
    assert "count" in c.get("/api/assistant/preferences").json()
    assert "count" in c.get("/api/assistant/open-loops").json()


def test_missing_returns_404(client) -> None:
    c, _did, _pid, _oid = client
    assert c.get("/api/assistant/decisions/nope").status_code == 404
    assert c.get("/api/assistant/preferences/nope").status_code == 404
    assert c.get("/api/assistant/open-loops/nope").status_code == 404


def test_all_roles_allowed(client) -> None:
    c, _did, _pid, _oid = client
    for role in ("viewer", "operator", "admin"):
        assert c.get("/api/assistant/decisions",
                     headers={"X-HB-UI-Role": role}).status_code == 200


def test_routes_are_get_only(client) -> None:
    c, _did, _pid, _oid = client
    surface = {"/api/assistant/decisions", "/api/assistant/decisions/{decision_id}",
               "/api/assistant/preferences", "/api/assistant/preferences/{preference_id}",
               "/api/assistant/open-loops", "/api/assistant/open-loops/{open_loop_id}"}
    for route in c.app.routes:
        if getattr(route, "path", None) in surface:
            assert route.methods <= {"GET", "HEAD"}, (route.path, route.methods)


def test_no_write_route_on_surface(client) -> None:
    c, _did, _pid, _oid = client
    assert c.post("/api/assistant/decisions").status_code in {401, 404, 405}
    assert c.delete("/api/assistant/open-loops").status_code in {401, 404, 405}


def test_bounded_limit_is_clamped(client) -> None:
    c, _did, _pid, _oid = client
    r = c.get("/api/assistant/decisions?limit=100000", headers={"X-HB-UI-Role": "viewer"})
    assert r.status_code == 200
    assert len(r.json()["decisions"]) <= 200
