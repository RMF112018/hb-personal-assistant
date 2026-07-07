"""N8C-14 read-only answer-draft API surface: GET-only, bounded, citation-safe, redacted, no
write/build/answer route; /summary declared before /{draft_id}; 404 on missing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.obsidian_mcp import answer_draft_builder as B
from hb_assistant.obsidian_mcp.answer_draft_builder import DraftProviders
from hb_assistant.obsidian_mcp.answer_draft_repository import AnswerDraftRepository
from hb_assistant.obsidian_mcp.research_packet_repository import ResearchPacketRepository
from hb_assistant.store.migrator import SQLiteMigrator

FORBIDDEN = ("access_token", "refresh_token", "client_secret", "Bearer ", "eyJ",
             "BEGIN PRIVATE KEY", "result_json", "/Users/", "final_answer", "answer_text",
             "generated_answer", "operator_approved_answer", "authoritative_answer")


def _assert_safe(payload: object) -> None:
    blob = json.dumps(payload)
    for needle in FORBIDDEN:
        assert needle not in blob, f"forbidden token leaked: {needle}"


def _seed_draft(db: str) -> str:
    pr = ResearchPacketRepository(db)
    contract = {"answer_allowed": True, "citation_required": True, "review_labels_required": True,
                "trusted_claims_allowed": True, "candidate_claims_allowed": "with_caveat",
                "action_policy": "no_execution", "must_not_say": [], "unresolved_questions": []}
    acj = json.dumps(contract, sort_keys=True, separators=(",", ":"))
    acd = "d" * 24
    pr.upsert_packet(
        {"packet_id": "PKT", "packet_type": "review_aware_answer_context", "answer_contract_json": acj,
         "status": "built", "created_by": "t", "projection_id": "P", "answer_contract_digest": acd,
         "trusted_count": 1, "citation_count": 1, "item_count": 1, "budget_json": "{}", "scope_json": "{}"},
        [{"packet_item_id": "IT", "packet_id": "PKT", "target_kind": "claim", "target_id": "C",
          "effective_state": "accepted", "inclusion_state": "trusted", "answer_role": "primary_support",
          "title": "T", "summary": "S", "evidence_excerpt": "E", "claim_id": "C", "confidence": 0.9,
          "included": 1}],
        [{"citation_id": "CT", "packet_id": "PKT", "packet_item_id": "IT", "citation_order": 0,
          "citation_type": "claim", "target_kind": "claim", "target_id": "C", "claim_id": "C"}],
        {"packet_receipt_id": "R", "packet_id": "PKT", "builder_version": "v", "input_digest": "i",
         "output_digest": "o", "answer_contract_digest": acd})
    res = B.build_answer_draft(DraftProviders(packet_repo=pr, source_repo=None), AnswerDraftRepository(db),
                               packet_id="PKT", draft_type="review_aware_answer_draft", apply=True)
    return res["draft_id"]


@pytest.fixture()
def client(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS", "1")
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    did = _seed_draft(db)
    return TestClient(create_app(db_path=db)), did


def test_routes_ok_and_safe(client) -> None:
    c, did = client
    for path in ("/api/assistant/answer-drafts",
                 f"/api/assistant/answer-drafts/{did}",
                 f"/api/assistant/answer-drafts/{did}/sections",
                 f"/api/assistant/answer-drafts/{did}/citations",
                 f"/api/assistant/answer-drafts/{did}/export",
                 "/api/assistant/answer-drafts/summary"):
        r = c.get(path, headers={"X-HB-UI-Role": "viewer"})
        assert r.status_code == 200, path
        body = r.json()
        assert body["guardrails"]["read_only"] is True
        _assert_safe(body)


def test_summary_not_shadowed_by_draft_id(client) -> None:
    # /summary is a literal path declared before /{draft_id}; it must resolve to the summary handler.
    c, _did = client
    body = c.get("/api/assistant/answer-drafts/summary", headers={"X-HB-UI-Role": "viewer"}).json()
    assert "summary" in body and "total_drafts" in body["summary"]


def test_sections_carry_review_labels_no_finality(client) -> None:
    c, did = client
    body = c.get(f"/api/assistant/answer-drafts/{did}/sections",
                 headers={"X-HB-UI-Role": "viewer"}).json()
    assert body["count"] >= 1
    for s in body["sections"]:
        assert "review_label" in s
        assert not ({"final_answer", "answer_text", "generated_answer"} & set(s.keys()))


def test_missing_returns_404(client) -> None:
    c, _did = client
    assert c.get("/api/assistant/answer-drafts/nope").status_code == 404
    assert c.get("/api/assistant/answer-drafts/nope/sections").status_code == 404
    assert c.get("/api/assistant/answer-drafts/nope/citations").status_code == 404
    assert c.get("/api/assistant/answer-drafts/nope/export").status_code == 404


def test_all_roles_allowed(client) -> None:
    c, _did = client
    for role in ("viewer", "operator", "admin"):
        assert c.get("/api/assistant/answer-drafts/summary",
                     headers={"X-HB-UI-Role": role}).status_code == 200


def test_routes_are_get_only(client) -> None:
    c, _did = client
    surface = {
        "/api/assistant/answer-drafts",
        "/api/assistant/answer-drafts/{draft_id}",
        "/api/assistant/answer-drafts/{draft_id}/sections",
        "/api/assistant/answer-drafts/{draft_id}/citations",
        "/api/assistant/answer-drafts/{draft_id}/export",
        "/api/assistant/answer-drafts/summary",
    }
    for route in c.app.routes:
        if getattr(route, "path", None) in surface:
            assert route.methods <= {"GET", "HEAD"}, (route.path, route.methods)


def test_no_write_or_build_route(client) -> None:
    c, did = client
    assert c.post("/api/assistant/answer-drafts").status_code in {401, 404, 405}
    assert c.post(f"/api/assistant/answer-drafts/{did}/sections").status_code in {401, 404, 405}
    assert c.delete("/api/assistant/answer-drafts").status_code in {401, 404, 405}


def test_bounded_limit_is_clamped(client) -> None:
    c, did = client
    r = c.get(f"/api/assistant/answer-drafts/{did}/citations?limit=100000",
              headers={"X-HB-UI-Role": "viewer"})
    assert r.status_code == 200
    assert len(r.json()["citations"]) <= 200
