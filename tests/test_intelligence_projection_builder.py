"""N8C-10 projection builder: effective-state classification, policy, budget/truncation, provenance
preservation, bounded content, and review+source-table nonmutation across preview / dry-run / apply."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

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
from hb_assistant.obsidian_mcp.intelligence_projection_models import (
    EVIDENCE_HARD_CAP,
    REVIEW_AWARE_CONTEXT,
    TRUSTED_CONTEXT,
    ProjectionBudget,
)
from hb_assistant.obsidian_mcp.intelligence_projection_repository import (
    IntelligenceProjectionRepository,
)
from hb_assistant.obsidian_mcp.memory_repository import MemoryRepository
from hb_assistant.obsidian_mcp.review_repository import ReviewRepository
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.store.migrator import SQLiteMigrator

# Review overlay + source advisory tables that a projection must NEVER mutate.
_PROTECTED = (
    "assistant_review_items", "assistant_review_dispositions", "assistant_review_events",
    "assistant_claims", "assistant_context_pack_items", "assistant_decision_records",
    "assistant_preference_records", "assistant_open_loop_records", "assistant_memory_nodes",
    "assistant_enrichment_receipts",
)


def _snapshot(db: str) -> dict[str, str]:
    out: dict[str, str] = {}
    with sqlite3.connect(db) as c:
        for t in _PROTECTED:
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
    pack = CB.build_context_pack(CB.PackRequest(pack_type="enrichment_review", budget=Budget(max_items=20)),
                                 CB.Providers(er, cr, sr), pr, apply=True)["pack_id"]
    EX.apply_decision_memory(EX.DecisionMemoryProviders(cr, pr, er, sr, MemoryRepository(db)),
                             dr, pack_id=pack, apply=True)
    rrepo = ReviewRepository(db)
    RB.build_review_queue(RB.ReviewProviders(pr, cr, er, sr, MemoryRepository(db), dr), rrepo,
                          pack_id=pack, apply=True)
    providers = IB.ProjectionProviders(RB.ReviewProviders(pr, cr, er, sr, MemoryRepository(db), dr), rrepo)
    return {"db": db, "pack": pack, "providers": providers,
            "irepo": IntelligenceProjectionRepository(db), "rrepo": rrepo}


def test_review_aware_includes_and_labels_candidates(seeded) -> None:
    pv = IB.preview_intelligence_projection(seeded["providers"], pack_id=seeded["pack"],
                                            projection_type=REVIEW_AWARE_CONTEXT)
    assert len(pv["items"]) >= 1
    # all undisposed → candidate, included + labeled candidate
    assert all(i["inclusion_state"] == "candidate" for i in pv["items"])
    assert all(i["included"] == 1 for i in pv["items"])


def test_trusted_excludes_candidates_until_accepted(seeded) -> None:
    tv = IB.preview_intelligence_projection(seeded["providers"], pack_id=seeded["pack"],
                                            projection_type=TRUSTED_CONTEXT)
    assert tv["included_count"] == 0  # nothing accepted yet
    rid = seeded["rrepo"].list_review_items(limit=1)[0]["review_item_id"]
    seeded["rrepo"].record_disposition(review_item_id=rid, disposition_type="accept")
    tv2 = IB.preview_intelligence_projection(seeded["providers"], pack_id=seeded["pack"],
                                             projection_type=TRUSTED_CONTEXT)
    assert tv2["counts"]["trusted"] == 1 and tv2["included_count"] == 1
    trusted = [i for i in tv2["items"] if i["included"]][0]
    assert trusted["inclusion_state"] == "trusted" and trusted["effective_state"] == "accepted"
    assert trusted["review_item_id"] == rid  # review linkage preserved


def test_items_preserve_provenance_and_bounded(seeded) -> None:
    pv = IB.preview_intelligence_projection(seeded["providers"], pack_id=seeded["pack"],
                                            projection_type=REVIEW_AWARE_CONTEXT)
    anchors = ("source_id", "note_rel_path", "claim_id", "receipt_id", "pack_id", "pack_item_id",
               "memory_node_id", "memory_mention_id", "compilation_id", "decision_id", "preference_id",
               "open_loop_id")
    for it in pv["items"]:
        assert it["target_id"]
        assert any(it.get(a) for a in anchors)
        if it["evidence_excerpt"]:
            assert len(it["evidence_excerpt"]) <= EVIDENCE_HARD_CAP  # bounded, never a full payload


def test_budget_max_items_truncates(seeded) -> None:
    bud = ProjectionBudget.for_type(REVIEW_AWARE_CONTEXT)
    bud.max_items = 1
    pv = IB.preview_intelligence_projection(seeded["providers"], pack_id=seeded["pack"],
                                            projection_type=REVIEW_AWARE_CONTEXT, budget=bud)
    assert pv["included_count"] == 1 and pv["truncated"] is True
    dropped = [i for i in pv["items"] if not i["included"]]
    assert dropped and all(i["exclusion_reason"] for i in dropped)


def test_budget_max_chars_truncates(seeded) -> None:
    bud = ProjectionBudget.for_type(REVIEW_AWARE_CONTEXT)
    bud.max_chars = 1  # nothing fits
    pv = IB.preview_intelligence_projection(seeded["providers"], pack_id=seeded["pack"],
                                            projection_type=REVIEW_AWARE_CONTEXT, budget=bud)
    assert pv["included_count"] == 0 and pv["truncated"] is True
    assert all(i["exclusion_reason"] == "budget_max_chars" for i in pv["items"] if not i["included"])


def test_budget_max_trusted_and_candidates(seeded) -> None:
    # accept everything → all trusted; cap max_trusted to 1
    for it in seeded["rrepo"].list_review_items(limit=200):
        seeded["rrepo"].record_disposition(review_item_id=it["review_item_id"], disposition_type="accept")
    bud = ProjectionBudget.for_type(TRUSTED_CONTEXT)
    bud.max_trusted = 1
    pv = IB.preview_intelligence_projection(seeded["providers"], pack_id=seeded["pack"],
                                            projection_type=TRUSTED_CONTEXT, budget=bud)
    included = [i for i in pv["items"] if i["included"]]
    assert len(included) == 1
    assert any(i["exclusion_reason"] == "budget_max_trusted" for i in pv["items"] if not i["included"])


def test_excluded_items_minimized(seeded) -> None:
    # reject one → excluded item keeps ids/state/digest but drops content
    rid = seeded["rrepo"].list_review_items(limit=1)[0]["review_item_id"]
    seeded["rrepo"].record_disposition(review_item_id=rid, disposition_type="reject")
    pv = IB.preview_intelligence_projection(seeded["providers"], pack_id=seeded["pack"],
                                            projection_type=REVIEW_AWARE_CONTEXT)
    excluded = [i for i in pv["items"] if i["inclusion_state"] == "excluded"]
    assert excluded
    for i in excluded:
        assert i["included"] == 0 and i["target_id"] and i["effective_state"] == "rejected"
        assert i["exclusion_reason"] == "rejected"
        assert i["summary"] is None and i["evidence_excerpt"] is None  # no unnecessary content


def test_implementation_context_open_loops_advisory(seeded) -> None:
    pv = IB.preview_intelligence_projection(seeded["providers"], pack_id=seeded["pack"],
                                            projection_type="implementation_context")
    open_loops = [i for i in pv["items"] if i["target_kind"] == "open_loop"]
    assert open_loops  # the seeded commitment yields an open loop
    for i in open_loops:
        meta = json.loads(i["metadata_json"]) if i["metadata_json"] else {}
        assert meta.get("advisory") is True  # advisory only — never executable instructions


def test_preview_and_dryrun_and_apply_do_not_mutate_review_or_source(seeded) -> None:
    before = _snapshot(seeded["db"])
    # preview
    IB.preview_intelligence_projection(seeded["providers"], pack_id=seeded["pack"],
                                       projection_type=REVIEW_AWARE_CONTEXT)
    assert _snapshot(seeded["db"]) == before
    # dry-run build
    IB.build_intelligence_projection(seeded["providers"], seeded["irepo"], pack_id=seeded["pack"],
                                     projection_type=REVIEW_AWARE_CONTEXT, apply=False)
    assert _snapshot(seeded["db"]) == before
    # apply build — writes only projection tables; review + source snapshots unchanged
    res = IB.build_intelligence_projection(seeded["providers"], seeded["irepo"], pack_id=seeded["pack"],
                                           projection_type=REVIEW_AWARE_CONTEXT, apply=True)
    assert res["applied"] is True and res["created"] is True
    assert _snapshot(seeded["db"]) == before
    assert seeded["irepo"].count() == 1  # projection persisted


def test_dispositions_and_events_unchanged_by_apply(seeded) -> None:
    # explicit before/after over the two ledger tables specifically
    def disp_events():
        with sqlite3.connect(seeded["db"]) as c:
            d = c.execute("SELECT * FROM assistant_review_dispositions ORDER BY 1").fetchall()
            e = c.execute("SELECT * FROM assistant_review_events ORDER BY 1").fetchall()
        return (repr(d), repr(e))
    before = disp_events()
    IB.build_intelligence_projection(seeded["providers"], seeded["irepo"], pack_id=seeded["pack"],
                                     projection_type=TRUSTED_CONTEXT, apply=True)
    assert disp_events() == before


def test_build_apply_idempotent(seeded) -> None:
    IB.build_intelligence_projection(seeded["providers"], seeded["irepo"], pack_id=seeded["pack"],
                                     projection_type=REVIEW_AWARE_CONTEXT, apply=True)
    res2 = IB.build_intelligence_projection(seeded["providers"], seeded["irepo"], pack_id=seeded["pack"],
                                            projection_type=REVIEW_AWARE_CONTEXT, apply=True)
    assert res2["reused"] is True and res2["created"] is False
