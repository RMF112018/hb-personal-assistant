"""N8C-8 extractor: classification, provenance, idempotency, compilation-derived, no-writeback."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp import context_pack_builder as CB
from hb_assistant.obsidian_mcp import decision_memory_extractor as EX
from hb_assistant.obsidian_mcp import decision_memory_models as M
from hb_assistant.obsidian_mcp import memory_models as MM
from hb_assistant.obsidian_mcp.claim_models import ClaimCandidate
from hb_assistant.obsidian_mcp.claim_repository import ClaimRepository
from hb_assistant.obsidian_mcp.context_pack_models import Budget
from hb_assistant.obsidian_mcp.context_pack_repository import ContextPackRepository
from hb_assistant.obsidian_mcp.decision_memory_repository import DecisionMemoryRepository
from hb_assistant.obsidian_mcp.enrichment_repository import EnrichmentRepository
from hb_assistant.obsidian_mcp.memory_repository import MemoryRepository
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.store.migrator import SQLiteMigrator

_WATCHED = ("assistant_decision%", "assistant_preference%", "assistant_open_loop%", "assistant_claim%",
            "assistant_enrichment%", "assistant_context_pack%", "assistant_memory%",
            "source_intelligence%")

_CLAIMS = [
    ("decision_candidate", "We decided to keep MCP read-only", "mcp", "keep read-only", 0.8),
    ("preference", "Bobby prefers no AI trailer in commits", "commits", "no ai trailer", 0.75),
    ("commitment", "I will send the revised schedule", "schedule", "send revised schedule", 0.7),
    ("task_candidate", "Need to verify V102 migration idempotency", "v102", "verify idempotency", 0.6),
    ("risk", "Risk: source digest drift before ingestion", "ingestion", "digest drift", 0.65),
    ("task_candidate", "Should context packs persist?", "packs", "persist", 0.5),  # question-shaped
    ("fact", "The sky is blue", "sky", "blue", 0.9),  # unsupported → rejected
]


def _row_counts(db: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    with sqlite3.connect(db) as c:
        names: list[str] = []
        for pat in _WATCHED:
            names += [r[0] for r in c.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE ?", (pat,))]
        for n in names:
            counts[n] = c.execute(f"SELECT COUNT(*) FROM {n}").fetchone()[0]  # noqa: S608
    return counts


@pytest.fixture()
def env(tmp_path: Path):
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    er, cr, sr = EnrichmentRepository(db), ClaimRepository(db), SourceIndexRepository(db)
    pr, mr, dr = ContextPackRepository(db), MemoryRepository(db), DecisionMemoryRepository(db)
    cr.ingest_candidates(
        [ClaimCandidate(claim_type=ct, claim_text=txt, evidence_excerpt="ev", confidence=conf,
                        normalized_subject=subj, normalized_object=obj)
         for (ct, txt, subj, obj, conf) in _CLAIMS],
        source_id="s1", note_rel_path="Cards/s1.md", extractor_version="rule_based-v1")
    j = er.queue_job(job_type="claim_extraction", source_id="s1")
    er.claim_next_job("w", 300)
    er.mark_running(j["job_id"], "w")
    er.complete_job(j["job_id"], "w", status="completed",
                    result_json=json.dumps({"claims": [], "count": 0}),
                    applied_status="stored_only", receipt_metadata={"output_digest": "d1"})
    # A memory node + mention (source s1) + built compilation with populated advisory arrays.
    nid = MM.compute_node_id("project", MM.normalize_memory_name("Tropical"), None)
    mr.upsert_node({"node_id": nid, "node_type": "project", "canonical_name": "Tropical",
                    "normalized_name": MM.normalize_memory_name("Tropical"), "domain": None,
                    "aliases": [], "review_tier": "trusted_source_backed", "confidence": 0.8,
                    "input_digest": "x", "created_by": "t"})
    mr.upsert_mention(MM.MemoryMention(mention_type="claim_subject", source_id="s1", claim_id="c1",
                                       evidence_excerpt="ev").to_row(nid))
    cid = MM.compute_compilation_id(nid, "node_summary", "idig")
    mr.persist_compilation({"compilation_id": cid, "node_id": nid, "compile_type": "node_summary",
                            "summary": "s", "input_digest": "idig",
                            "review_tier": "trusted_source_backed", "mention_count": 1,
                            "preferences_json": json.dumps(["prefer weekly cadence"]),
                            "risks_json": json.dumps(["budget overrun risk"]),
                            "open_questions_json": json.dumps(["who owns closeout?"])})
    pack = CB.build_context_pack(CB.PackRequest(pack_type="enrichment_review", budget=Budget(max_items=50)),
                                 CB.Providers(er, cr, sr), pr, apply=True)["pack_id"]
    prov = EX.DecisionMemoryProviders(cr, pr, er, sr, mr)
    return {"db": db, "prov": prov, "dr": dr, "cr": cr, "pack_id": pack, "node_id": nid}


def test_decision_extracted_from_decision_candidate_claim(env) -> None:
    prev = EX.preview_decision_memory(env["prov"], pack_id=env["pack_id"])
    assert [d["decision_type"] for d in prev["decisions"]] == ["decision_candidate"]


def test_preference_extracted_from_preference_claim(env) -> None:
    prev = EX.preview_decision_memory(env["prov"], pack_id=env["pack_id"])
    claim_prefs = [p for p in prev["preferences"] if p["preference_type"] == "user_preference"]
    assert claim_prefs and claim_prefs[0]["normalized_preference"] == "no ai trailer"


def test_commitment_task_risk_question_become_open_loops(env) -> None:
    prev = EX.preview_decision_memory(env["prov"], pack_id=env["pack_id"])
    types = sorted(o["open_loop_type"] for o in prev["open_loops"])
    # commitment + task_candidate + risk_followup(claim) + question(claim) + risk_followup(comp) +
    # question(comp).
    assert "commitment" in types
    assert "task_candidate" in types
    assert "risk_followup" in types
    assert "question" in types


def test_context_pack_items_produce_candidates(env) -> None:
    # Every claim-derived record traces to a pack item (path 1).
    prev = EX.preview_decision_memory(env["prov"], pack_id=env["pack_id"])
    claim_derived = [r for kind in ("decisions", "preferences", "open_loops") for r in prev[kind]
                     if r.get("pack_item_id")]
    assert claim_derived


def test_compilation_produces_weak_candidates(env) -> None:
    prev = EX.preview_decision_memory(env["prov"], pack_id=env["pack_id"])
    derived = [r for kind in ("preferences", "open_loops") for r in prev[kind]
               if r.get("metadata_json") and "compilation_derived" in r["metadata_json"]]
    assert derived
    for r in derived:  # weak: low confidence + needs_review + compilation_id provenance
        assert r["confidence"] <= M.COMPILATION_CONFIDENCE_CAP
        assert r["review_state"] == "needs_review"
        assert r["compilation_id"]


def test_question_is_conservative(env) -> None:
    prev = EX.preview_decision_memory(env["prov"], pack_id=env["pack_id"])
    questions = [o for o in prev["open_loops"] if o["open_loop_type"] == "question"]
    assert questions
    for q in questions:
        assert q["confidence"] <= M.QUESTION_CONFIDENCE_CAP
        assert q["review_state"] == "needs_review"


def test_unsupported_claim_rejected(env) -> None:
    prev = EX.preview_decision_memory(env["prov"], pack_id=env["pack_id"])
    texts = [r["decision_text"] for r in prev["decisions"]]
    texts += [r.get("open_loop_text") for r in prev["open_loops"]]
    texts += [r.get("preference_text") for r in prev["preferences"]]
    assert "The sky is blue" not in texts  # plain fact, not a decision/pref/open-loop/question


def test_every_record_has_provenance_and_bounded_evidence(env) -> None:
    prev = EX.preview_decision_memory(env["prov"], pack_id=env["pack_id"])
    for kind in ("decisions", "preferences", "open_loops"):
        for r in prev[kind]:
            assert any(r.get(a) for a in ("source_id", "note_rel_path", "claim_id", "memory_node_id",
                                          "compilation_id", "pack_id", "pack_item_id", "receipt_id"))
            assert len(r.get("evidence_excerpt") or "") <= M.EVIDENCE_HARD_CAP


def test_default_status_is_candidate_unreviewed(env) -> None:
    prev = EX.preview_decision_memory(env["prov"], pack_id=env["pack_id"])
    for kind in ("decisions", "preferences", "open_loops"):
        for r in prev[kind]:
            assert r["status"] == "candidate"
            assert r["review_state"] in ("unreviewed", "needs_review")


def test_preview_and_dry_run_are_read_only(env) -> None:
    before = _row_counts(env["db"])
    EX.preview_decision_memory(env["prov"], pack_id=env["pack_id"])
    EX.apply_decision_memory(env["prov"], env["dr"], pack_id=env["pack_id"], apply=False)
    assert _row_counts(env["db"]) == before


def test_apply_writes_only_n8c8_tables(env) -> None:
    before = _row_counts(env["db"])
    EX.apply_decision_memory(env["prov"], env["dr"], pack_id=env["pack_id"], apply=True)
    after = _row_counts(env["db"])
    owned = ("assistant_decision", "assistant_preference", "assistant_open_loop")
    for name, count in before.items():
        if name.startswith(owned):
            assert after[name] >= count
        else:
            assert after[name] == count  # claims/enrichment/context-pack/memory/source untouched


def test_apply_is_idempotent(env) -> None:
    a = EX.apply_decision_memory(env["prov"], env["dr"], pack_id=env["pack_id"], apply=True)
    total = env["dr"].count("decision") + env["dr"].count("preference") + env["dr"].count("open_loop")
    b = EX.apply_decision_memory(env["prov"], env["dr"], pack_id=env["pack_id"], apply=True)
    assert b["created"] == {"decisions": 0, "preferences": 0, "open_loops": 0}
    assert b["superseded"] == 0
    total2 = env["dr"].count("decision") + env["dr"].count("preference") + env["dr"].count("open_loop")
    assert total == total2 and sum(a["created"].values()) > 0


def test_claims_stay_candidate_unreviewed(env) -> None:
    EX.apply_decision_memory(env["prov"], env["dr"], pack_id=env["pack_id"], apply=True)
    claims = env["cr"].list_claims()
    assert claims and all(c["status"] == "candidate" and c["review_state"] == "unreviewed"
                          for c in claims)


def test_memory_node_status_unchanged(env) -> None:
    before = env["prov"].memory_repo.get_node(env["node_id"])["status"]
    EX.apply_decision_memory(env["prov"], env["dr"], pack_id=env["pack_id"], apply=True)
    after = env["prov"].memory_repo.get_node(env["node_id"])["status"]
    assert before == after == "active"  # extractor never mutates memory nodes


def test_export_is_bounded_json_no_raw(env) -> None:
    EX.apply_decision_memory(env["prov"], env["dr"], pack_id=env["pack_id"], apply=True)
    exp = EX.export_decision_memory(env["dr"], kind="open-loops")
    blob = json.dumps(exp)
    assert exp["format"] == "json"
    assert "result_json" not in blob
    assert "/Users/" not in blob
