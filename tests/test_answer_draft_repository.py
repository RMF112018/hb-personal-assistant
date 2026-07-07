"""N8C-14 — answer-draft repository: deterministic ids, idempotent upsert (no duplicate), lineage-scoped
supersede, stale-on-drift, and the hard boundary that a draft upsert writes ONLY the five draft tables
(never a packet / projection / review / source record)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from hb_assistant.obsidian_mcp import answer_draft_builder as B
from hb_assistant.obsidian_mcp.answer_draft_builder import DraftProviders
from hb_assistant.obsidian_mcp.answer_draft_repository import AnswerDraftRepository
from hb_assistant.obsidian_mcp.research_packet_repository import ResearchPacketRepository
from hb_assistant.store.migrator import SQLiteMigrator

_SID = "a" * 32


def _seed_packet(db: str, *, packet_id: str = "PKT1", trusted: bool = True) -> None:
    pr = ResearchPacketRepository(db)
    contract = {"answer_allowed": True, "citation_required": True, "review_labels_required": True,
                "trusted_claims_allowed": True, "candidate_claims_allowed": "with_caveat",
                "must_not_say": [], "unresolved_questions": []}
    acj = json.dumps(contract, sort_keys=True, separators=(",", ":"))
    acd = "d" * 24
    pr.upsert_packet(
        {"packet_id": packet_id, "packet_type": "review_aware_answer_context", "answer_contract_json": acj,
         "status": "built", "created_by": "t", "projection_id": "P", "answer_contract_digest": acd,
         "trusted_count": 1, "candidate_count": 0, "excluded_count": 0, "citation_count": 1,
         "open_question_count": 0, "item_count": 1, "truncated": 0, "budget_json": "{}", "scope_json": "{}"},
        [{"packet_item_id": "IT", "packet_id": packet_id, "target_kind": "claim", "target_id": "C",
          "effective_state": "accepted", "inclusion_state": "trusted", "answer_role": "primary_support",
          "title": "T", "summary": "S", "evidence_excerpt": "E", "source_id": _SID, "claim_id": "C",
          "confidence": 0.9, "included": 1}],
        [{"citation_id": "CT", "packet_id": packet_id, "packet_item_id": "IT", "citation_order": 0,
          "citation_type": "claim", "target_kind": "claim", "target_id": "C", "claim_id": "C",
          "source_id": _SID}],
        {"packet_receipt_id": "R", "packet_id": packet_id, "builder_version": "v", "input_digest": "i",
         "output_digest": "o", "answer_contract_digest": acd})


def _providers(db: str) -> DraftProviders:
    return DraftProviders(packet_repo=ResearchPacketRepository(db), source_repo=None)


def _mk(db: Path) -> str:
    return str(db)


def test_deterministic_ids_and_idempotent_reuse(tmp_path: Path) -> None:
    db = _mk(tmp_path / "t.db")
    SQLiteMigrator(db_path=db).apply()
    _seed_packet(db)
    repo = AnswerDraftRepository(db)
    r1 = B.build_answer_draft(_providers(db), repo, packet_id="PKT1",
                              draft_type="review_aware_answer_draft", apply=True)
    assert r1["created"] is True
    # same inputs → same draft_id, reused (no duplicate row, no new supersede).
    r2 = B.build_answer_draft(_providers(db), repo, packet_id="PKT1",
                              draft_type="review_aware_answer_draft", apply=True)
    assert r2["draft_id"] == r1["draft_id"] and r2["reused"] is True
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT COUNT(*) FROM assistant_answer_drafts").fetchone()[0] == 1
    # section + citation + receipt ids are deterministic 24-hex.
    exp = B.export_answer_draft(repo, draft_id=r1["draft_id"])
    assert len(exp["sections"][0]["draft_section_id"]) == 24
    assert len(exp["citations"][0]["draft_citation_id"]) == 24


def test_changed_packet_supersedes_prior_draft(tmp_path: Path) -> None:
    db = _mk(tmp_path / "t.db")
    SQLiteMigrator(db_path=db).apply()
    _seed_packet(db)
    repo = AnswerDraftRepository(db)
    r1 = B.build_answer_draft(_providers(db), repo, packet_id="PKT1",
                              draft_type="review_aware_answer_draft", apply=True)
    # A different objective changes the draft_id (same lineage: type+packet+policy) → supersede.
    r2 = B.build_answer_draft(_providers(db), repo, packet_id="PKT1", objective="new-objective",
                              draft_type="review_aware_answer_draft", apply=True)
    assert r2["draft_id"] != r1["draft_id"]
    assert r1["draft_id"] in r2["superseded"]
    with sqlite3.connect(db) as c:
        prior = c.execute("SELECT status FROM assistant_answer_drafts WHERE draft_id=?",
                          (r1["draft_id"],)).fetchone()[0]
    assert prior == "superseded"


def test_stale_on_input_drift(tmp_path: Path) -> None:
    db = _mk(tmp_path / "t.db")
    SQLiteMigrator(db_path=db).apply()
    _seed_packet(db)
    repo = AnswerDraftRepository(db)
    r1 = B.build_answer_draft(_providers(db), repo, packet_id="PKT1",
                              draft_type="review_aware_answer_draft", apply=True)
    res = repo.mark_answer_draft_stale_if_needed(r1["draft_id"], current_input_digest="changed")
    assert res["found"] is True and res["stale"] is True
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT status FROM assistant_answer_drafts WHERE draft_id=?",
                        (r1["draft_id"],)).fetchone()[0] == "stale"


def test_upsert_writes_only_draft_tables(tmp_path: Path) -> None:
    db = _mk(tmp_path / "t.db")
    SQLiteMigrator(db_path=db).apply()
    _seed_packet(db)
    repo = AnswerDraftRepository(db)

    def _digests() -> dict[str, str]:
        with sqlite3.connect(db) as c:
            out = {}
            for t in ("assistant_research_packets", "assistant_research_packet_items",
                      "assistant_research_packet_citations", "source_intelligence_sources"):
                rows = c.execute(f"SELECT * FROM {t} ORDER BY 1").fetchall()  # noqa: S608 (fixed table names)
                out[t] = json.dumps(rows, default=str, sort_keys=True)
            return out

    before = _digests()
    B.build_answer_draft(_providers(db), repo, packet_id="PKT1",
                         draft_type="review_aware_answer_draft", apply=True)
    after = _digests()
    assert before == after, "draft upsert must not mutate packet/source upstream tables"
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT COUNT(*) FROM assistant_answer_draft_events").fetchone()[0] >= 2
