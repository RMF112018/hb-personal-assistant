"""N8C-9 review builder: source-backed pack-scoped discovery, anchored + bounded items, idempotency,
family scoping, and source-table nonmutation across build --apply."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp import context_pack_builder as CB
from hb_assistant.obsidian_mcp import decision_memory_extractor as EX
from hb_assistant.obsidian_mcp import review_builder as RB
from hb_assistant.obsidian_mcp.claim_models import ClaimCandidate
from hb_assistant.obsidian_mcp.claim_repository import ClaimRepository
from hb_assistant.obsidian_mcp.context_pack_models import Budget
from hb_assistant.obsidian_mcp.context_pack_repository import ContextPackRepository
from hb_assistant.obsidian_mcp.decision_memory_repository import DecisionMemoryRepository
from hb_assistant.obsidian_mcp.enrichment_repository import EnrichmentRepository
from hb_assistant.obsidian_mcp.memory_repository import MemoryRepository
from hb_assistant.obsidian_mcp.review_models import EVIDENCE_HARD_CAP
from hb_assistant.obsidian_mcp.review_repository import ReviewRepository
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.store.migrator import SQLiteMigrator

_SOURCE_TABLES = (
    "assistant_claims", "assistant_context_pack_items", "assistant_context_packs",
    "assistant_decision_records", "assistant_preference_records", "assistant_open_loop_records",
    "assistant_enrichment_receipts", "assistant_memory_nodes",
)


def _snapshot(db: str) -> dict[str, str]:
    out: dict[str, str] = {}
    with sqlite3.connect(db) as c:
        for t in _SOURCE_TABLES:
            rows = c.execute(f"SELECT * FROM {t} ORDER BY 1").fetchall()  # noqa: S608 (fixed names)
            out[t] = hashlib.sha256(repr(rows).encode()).hexdigest()
    return out


@pytest.fixture()
def seeded(tmp_path: Path):
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    er, cr, sr = EnrichmentRepository(db), ClaimRepository(db), SourceIndexRepository(db)
    pr, dr = ContextPackRepository(db), DecisionMemoryRepository(db)
    cr.ingest_candidates(
        [ClaimCandidate(claim_type="decision_candidate", claim_text="Keep MCP read-only",
                        evidence_excerpt="ev", confidence=0.8, normalized_subject="mcp",
                        normalized_object="keep read-only"),
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
    pack = CB.build_context_pack(
        CB.PackRequest(pack_type="enrichment_review", budget=Budget(max_items=20)),
        CB.Providers(er, cr, sr), pr, apply=True)["pack_id"]
    EX.apply_decision_memory(EX.DecisionMemoryProviders(cr, pr, er, sr, MemoryRepository(db)),
                             dr, pack_id=pack, apply=True)
    providers = RB.ReviewProviders(pr, cr, er, sr, MemoryRepository(db), dr)
    return {"db": db, "pack": pack, "providers": providers, "repo": ReviewRepository(db)}


def test_preview_is_read_only(seeded) -> None:
    snap = _snapshot(seeded["db"])
    res = RB.preview_review_queue(seeded["providers"], pack_id=seeded["pack"])
    assert res["count"] >= 1
    # no review rows written, no source rows changed
    assert seeded["repo"].count() == 0
    assert _snapshot(seeded["db"]) == snap


def test_build_apply_produces_anchored_bounded_items(seeded) -> None:
    res = RB.build_review_queue(seeded["providers"], seeded["repo"], pack_id=seeded["pack"], apply=True)
    assert res["applied"] is True and res["created"] >= 1
    items = seeded["repo"].list_review_items(limit=200)
    assert items
    anchors = ("source_id", "note_rel_path", "claim_id", "receipt_id", "pack_id", "pack_item_id",
               "memory_node_id", "memory_mention_id", "compilation_id", "decision_id",
               "preference_id", "open_loop_id")
    for it in items:
        assert it["target_id"]  # every item names its target
        assert any(it.get(a) for a in anchors)  # every item is provenance-anchored
        if it["evidence_excerpt"]:
            assert len(it["evidence_excerpt"]) <= EVIDENCE_HARD_CAP


def test_families_discovered(seeded) -> None:
    res = RB.preview_review_queue(seeded["providers"], pack_id=seeded["pack"])
    types = set(res["by_review_type"])
    # the seed yields at least claim/context-pack review and decision/open-loop review
    assert "claim_review" in types or "context_pack_review" in types
    assert "decision_review" in types or "open_loop_review" in types


def test_kind_scoping_narrows(seeded) -> None:
    only_decisions = RB.preview_review_queue(seeded["providers"], pack_id=seeded["pack"],
                                             kinds=(RB.KIND_DECISIONS,))
    assert set(only_decisions["by_review_type"]) <= {"decision_review"}


def test_build_apply_idempotent_and_nonmutating(seeded) -> None:
    RB.build_review_queue(seeded["providers"], seeded["repo"], pack_id=seeded["pack"], apply=True)
    snap = _snapshot(seeded["db"])
    n1 = seeded["repo"].count()
    # second build creates no new items and mutates no source table
    res2 = RB.build_review_queue(seeded["providers"], seeded["repo"], pack_id=seeded["pack"], apply=True)
    assert res2["created"] == 0
    assert seeded["repo"].count() == n1
    assert _snapshot(seeded["db"]) == snap


def test_claims_and_decisions_remain_candidate(seeded) -> None:
    RB.build_review_queue(seeded["providers"], seeded["repo"], pack_id=seeded["pack"], apply=True)
    with sqlite3.connect(seeded["db"]) as c:
        # every claim stays candidate/unreviewed — building a review item never accepts the source
        bad_claims = c.execute(
            "SELECT COUNT(*) FROM assistant_claims "
            "WHERE status!='candidate' OR review_state!='unreviewed'").fetchone()[0]
        bad_dec = c.execute(
            "SELECT COUNT(*) FROM assistant_decision_records "
            "WHERE status!='candidate' OR review_state!='unreviewed'").fetchone()[0]
    assert bad_claims == 0
    assert bad_dec == 0
