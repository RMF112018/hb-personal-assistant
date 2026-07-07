"""N8C-10 read-only intelligence API surface: GET-only, bounded, redacted, no write/build route."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.obsidian_mcp import context_pack_builder as CB
from hb_assistant.obsidian_mcp import decision_memory_extractor as EX
from hb_assistant.obsidian_mcp import intelligence_projection_builder as IB
from hb_assistant.obsidian_mcp import review_builder as RB
from hb_assistant.obsidian_mcp.claim_models import ClaimCandidate
from hb_assistant.obsidian_mcp.claim_repository import ClaimRepository
from hb_assistant.obsidian_mcp.context_pack_models import Budget
from hb_assistant.obsidian_mcp.context_pack_repository import ContextPackRepository
from hb_assistant.obsidian_mcp.decision_memory_repository import DecisionMemoryRepository
from hb_assistant.obsidian_mcp.enrichment_repository import EnrichmentRepository
from hb_assistant.obsidian_mcp.intelligence_projection_models import REVIEW_AWARE_CONTEXT
from hb_assistant.obsidian_mcp.intelligence_projection_repository import (
    IntelligenceProjectionRepository,
)
from hb_assistant.obsidian_mcp.memory_repository import MemoryRepository
from hb_assistant.obsidian_mcp.review_repository import ReviewRepository
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
        [ClaimCandidate(claim_type="decision_candidate", claim_text="Keep MCP read-only",
                        evidence_excerpt="ev", confidence=0.8, normalized_subject="mcp",
                        normalized_object="keep read-only")],
        source_id="s1", note_rel_path="Cards/s1.md", extractor_version="rule_based-v1")
    j = er.queue_job(job_type="claim_extraction", source_id="s1")
    er.claim_next_job("w", 300)
    er.mark_running(j["job_id"], "w")
    er.complete_job(j["job_id"], "w", status="completed",
                    result_json=json.dumps({"claims": [], "count": 0}),
                    applied_status="stored_only", receipt_metadata={"output_digest": "d1"})
    pack = CB.build_context_pack(CB.PackRequest(pack_type="enrichment_review", budget=Budget(max_items=20)),
                                 CB.Providers(er, cr, sr), pr, apply=True)["pack_id"]
    EX.apply_decision_memory(EX.DecisionMemoryProviders(cr, pr, er, sr, MemoryRepository(db)),
                             dr, pack_id=pack, apply=True)
    rrepo = ReviewRepository(db)
    RB.build_review_queue(RB.ReviewProviders(pr, cr, er, sr, MemoryRepository(db), dr), rrepo,
                          pack_id=pack, apply=True)
    res = IB.build_intelligence_projection(
        IB.ProjectionProviders(RB.ReviewProviders(pr, cr, er, sr, MemoryRepository(db), dr), rrepo),
        IntelligenceProjectionRepository(db), pack_id=pack, projection_type=REVIEW_AWARE_CONTEXT,
        apply=True)
    return TestClient(create_app(db_path=db)), res["projection_id"]


def test_routes_ok_and_safe(client) -> None:
    c, pid = client
    for path in ("/api/assistant/intelligence/projections",
                 f"/api/assistant/intelligence/projections/{pid}",
                 f"/api/assistant/intelligence/projections/{pid}/items",
                 f"/api/assistant/intelligence/projections/{pid}/export",
                 "/api/assistant/intelligence/summary"):
        r = c.get(path, headers={"X-HB-UI-Role": "viewer"})
        assert r.status_code == 200, path
        body = r.json()
        assert body["guardrails"]["read_only"] is True
        _assert_safe(body)


def test_missing_returns_404(client) -> None:
    c, _pid = client
    assert c.get("/api/assistant/intelligence/projections/nope").status_code == 404
    assert c.get("/api/assistant/intelligence/projections/nope/items").status_code == 404
    assert c.get("/api/assistant/intelligence/projections/nope/export").status_code == 404


def test_all_roles_allowed(client) -> None:
    c, _pid = client
    for role in ("viewer", "operator", "admin"):
        assert c.get("/api/assistant/intelligence/summary",
                     headers={"X-HB-UI-Role": role}).status_code == 200


def test_routes_are_get_only(client) -> None:
    c, _pid = client
    surface = {
        "/api/assistant/intelligence/projections",
        "/api/assistant/intelligence/projections/{projection_id}",
        "/api/assistant/intelligence/projections/{projection_id}/items",
        "/api/assistant/intelligence/projections/{projection_id}/export",
        "/api/assistant/intelligence/summary",
    }
    for route in c.app.routes:
        if getattr(route, "path", None) in surface:
            assert route.methods <= {"GET", "HEAD"}, (route.path, route.methods)


def test_no_write_or_build_route(client) -> None:
    c, pid = client
    assert c.post("/api/assistant/intelligence/projections").status_code in {401, 404, 405}
    assert c.post(f"/api/assistant/intelligence/projections/{pid}/items").status_code in {401, 404, 405}
    assert c.delete("/api/assistant/intelligence/projections").status_code in {401, 404, 405}


def test_bounded_limit_is_clamped(client) -> None:
    c, pid = client
    r = c.get(f"/api/assistant/intelligence/projections/{pid}/items?limit=100000",
              headers={"X-HB-UI-Role": "viewer"})
    assert r.status_code == 200
    assert len(r.json()["items"]) <= 200
