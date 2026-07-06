"""N8C-6 read-only API surface: enrichment-review + context-packs. GET-only, bounded, redacted."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.obsidian_mcp import context_pack_builder as B
from hb_assistant.obsidian_mcp.context_pack_models import Budget
from hb_assistant.obsidian_mcp.context_pack_repository import ContextPackRepository
from hb_assistant.obsidian_mcp.enrichment_repository import EnrichmentRepository
from hb_assistant.obsidian_mcp.claim_repository import ClaimRepository
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
    er = EnrichmentRepository(db)
    j = er.queue_job(job_type="source_summary", source_id="s1")
    er.claim_next_job("w", 300)
    er.mark_running(j["job_id"], "w")
    er.complete_job(j["job_id"], "w", status="completed",
                    result_json=json.dumps({"summary": "hi", "confidence": 0.8}),
                    applied_status="stored_only", receipt_metadata={"output_digest": "d1"})
    prov = B.Providers(er, ClaimRepository(db), SourceIndexRepository(db))
    pr = ContextPackRepository(db)
    res = B.build_context_pack(B.PackRequest(pack_type="enrichment_review", budget=Budget(max_items=5)),
                               prov, pr, apply=True)
    return TestClient(create_app(db_path=db)), res["pack_id"]


def test_review_and_pack_routes_ok_and_safe(client) -> None:
    c, pid = client
    for path in ("/api/assistant/enrichment/review",
                 "/api/assistant/context-packs",
                 f"/api/assistant/context-packs/{pid}",
                 f"/api/assistant/context-packs/{pid}/items",
                 f"/api/assistant/context-packs/{pid}/export"):
        r = c.get(path, headers={"X-HB-UI-Role": "viewer"})
        assert r.status_code == 200, path
        body = r.json()
        assert body["guardrails"]["read_only"] is True
        _assert_safe(body)


def test_list_shapes_have_counts(client) -> None:
    c, _pid = client
    assert "count" in c.get("/api/assistant/enrichment/review").json()
    assert "count" in c.get("/api/assistant/context-packs").json()


def test_missing_returns_404(client) -> None:
    c, _pid = client
    assert c.get("/api/assistant/context-packs/nope").status_code == 404
    assert c.get("/api/assistant/enrichment/review/nope").status_code == 404


def test_all_roles_allowed(client) -> None:
    c, _pid = client
    for role in ("viewer", "operator", "admin"):
        assert c.get("/api/assistant/context-packs", headers={"X-HB-UI-Role": role}).status_code == 200


def test_routes_are_get_only(client) -> None:
    c, _pid = client
    surface = {"/api/assistant/enrichment/review", "/api/assistant/context-packs",
               "/api/assistant/context-packs/{pack_id}",
               "/api/assistant/context-packs/{pack_id}/items",
               "/api/assistant/context-packs/{pack_id}/export"}
    for route in c.app.routes:
        if getattr(route, "path", None) in surface:
            assert route.methods <= {"GET", "HEAD"}, (route.path, route.methods)


def test_no_write_route_on_surface(client) -> None:
    c, _pid = client
    assert c.post("/api/assistant/context-packs").status_code in {401, 404, 405}
    assert c.delete("/api/assistant/context-packs").status_code in {401, 404, 405}
