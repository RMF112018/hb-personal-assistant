"""N8C-11 packet builder: answer-role classification, citation manifest coverage, computed answer contract,
budget/truncation, provenance preservation, bounded content, no answer generation, and projection+review+
source-table nonmutation across preview / dry-run / apply."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp import context_pack_builder as CB
from hb_assistant.obsidian_mcp import decision_memory_extractor as EX
from hb_assistant.obsidian_mcp import intelligence_projection_builder as IB
from hb_assistant.obsidian_mcp import research_packet_builder as PB
from hb_assistant.obsidian_mcp import review_builder as RB
from hb_assistant.obsidian_mcp.claim_models import ClaimCandidate
from hb_assistant.obsidian_mcp.claim_repository import ClaimRepository
from hb_assistant.obsidian_mcp.context_pack_models import Budget
from hb_assistant.obsidian_mcp.context_pack_repository import ContextPackRepository
from hb_assistant.obsidian_mcp.decision_memory_repository import DecisionMemoryRepository
from hb_assistant.obsidian_mcp.enrichment_repository import EnrichmentRepository
from hb_assistant.obsidian_mcp.intelligence_projection_models import (
    REVIEW_AWARE_CONTEXT,
    TRUSTED_CONTEXT,
)
from hb_assistant.obsidian_mcp.intelligence_projection_repository import (
    IntelligenceProjectionRepository,
)
from hb_assistant.obsidian_mcp.memory_repository import MemoryRepository
from hb_assistant.obsidian_mcp.research_packet_models import (
    EVIDENCE_HARD_CAP,
    REVIEW_AWARE_ANSWER_CONTEXT,
    TRUSTED_ANSWER_CONTEXT,
    PacketBudget,
)
from hb_assistant.obsidian_mcp.research_packet_repository import ResearchPacketRepository
from hb_assistant.obsidian_mcp.review_repository import ReviewRepository
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.store.migrator import SQLiteMigrator

# Projection + review overlay + source advisory tables a packet must NEVER mutate.
_PROTECTED = (
    "assistant_intelligence_projections", "assistant_intelligence_projection_items",
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
    iprovs = IB.ProjectionProviders(RB.ReviewProviders(pr, cr, er, sr, MemoryRepository(db), dr), rrepo)
    irepo = IntelligenceProjectionRepository(db)

    def project(ptype):
        return IB.build_intelligence_projection(iprovs, irepo, pack_id=pack, projection_type=ptype,
                                                apply=True)["projection_id"]

    providers = PB.PacketProviders(irepo)
    return {"db": db, "pack": pack, "rrepo": rrepo, "irepo": irepo, "iprovs": iprovs,
            "providers": providers, "prepo": ResearchPacketRepository(db), "project": project,
            "rid": project(REVIEW_AWARE_CONTEXT)}


def test_review_aware_packet_includes_and_labels_candidates(seeded) -> None:
    pv = PB.preview_research_packet(seeded["providers"], projection_id=seeded["rid"],
                                    packet_type=REVIEW_AWARE_ANSWER_CONTEXT)
    assert pv["included_count"] >= 1
    included = [i for i in pv["items"] if i["included"]]
    # all undisposed → candidate_context (labelled, never silently promoted to trusted/primary)
    assert all(i["answer_role"] == "candidate_context" for i in included)
    assert all(i["inclusion_state"] == "candidate" for i in included)


def test_every_included_support_item_is_cited(seeded) -> None:
    pv = PB.preview_research_packet(seeded["providers"], projection_id=seeded["rid"],
                                    packet_type=REVIEW_AWARE_ANSWER_CONTEXT)
    cited_items = {c["packet_item_id"] for c in pv["citations"]}
    for it in pv["items"]:
        if it["included"] and it["answer_role"] not in ("open_question", "excluded_context"):
            assert it["packet_item_id"] in cited_items  # citation coverage guaranteed
            assert it["citation_ids_json"]


def test_citations_provenance_linked_and_bounded(seeded) -> None:
    pv = PB.preview_research_packet(seeded["providers"], projection_id=seeded["rid"],
                                    packet_type=REVIEW_AWARE_ANSWER_CONTEXT)
    anchors = ("source_id", "note_rel_path", "claim_id", "receipt_id", "pack_id", "pack_item_id",
               "memory_node_id", "memory_mention_id", "compilation_id", "decision_id", "preference_id",
               "open_loop_id", "review_item_id", "projection_item_id")
    assert pv["citations"]
    ids = [c["citation_id"] for c in pv["citations"]]
    assert len(ids) == len(set(ids))  # anchor entropy → no collisions
    for c in pv["citations"]:
        assert any(c.get(a) for a in anchors)  # provenance-linked
        if c["evidence_excerpt"]:
            assert len(c["evidence_excerpt"]) <= EVIDENCE_HARD_CAP  # bounded, never a full payload


def test_answer_contract_computed_no_answer_prose(seeded) -> None:
    pv = PB.preview_research_packet(seeded["providers"], projection_id=seeded["rid"],
                                    packet_type=REVIEW_AWARE_ANSWER_CONTEXT)
    ac = pv["answer_contract"]
    assert ac["citation_required"] is True
    assert ac["action_policy"] == "no_execution"
    assert ac["review_labels_required"] is True
    assert "unresolved_questions" in ac and "must_not_say" in ac
    # answer_allowed computed from included candidate support (review-aware includes candidates)
    assert ac["answer_allowed"] is True and ac["candidate_claims_allowed"] == "with_caveat"
    # NO generated-answer field anywhere in the packet payload
    blob = json.dumps(pv)
    assert not any(k in blob for k in ("final_answer", "answer_text", "generated_answer",
                                       '"response"'))


def test_trusted_packet_answer_not_allowed_until_accepted(seeded) -> None:
    tv = PB.preview_research_packet(seeded["providers"], projection_id=seeded["rid"],
                                    packet_type=TRUSTED_ANSWER_CONTEXT)
    assert tv["included_count"] == 0
    assert tv["answer_contract"]["answer_allowed"] is False  # computed, not defaulted true
    # accept one → build a trusted projection → trusted packet becomes answerable
    rid = seeded["rrepo"].list_review_items(limit=1)[0]["review_item_id"]
    seeded["rrepo"].record_disposition(review_item_id=rid, disposition_type="accept")
    tproj = seeded["project"](TRUSTED_CONTEXT)
    tv2 = PB.preview_research_packet(seeded["providers"], projection_id=tproj,
                                     packet_type=TRUSTED_ANSWER_CONTEXT)
    assert tv2["counts"]["trusted"] == 1 and tv2["included_count"] == 1
    assert tv2["answer_contract"]["answer_allowed"] is True
    trusted = [i for i in tv2["items"] if i["included"]][0]
    assert trusted["answer_role"] == "primary_support" and trusted["effective_state"] == "accepted"


def test_must_not_say_bounded_and_minimized(seeded) -> None:
    # reject one → it feeds a bounded, content-minimized must_not_say entry (no full content)
    rid = seeded["rrepo"].list_review_items(limit=1)[0]["review_item_id"]
    seeded["rrepo"].record_disposition(review_item_id=rid, disposition_type="reject")
    proj = seeded["project"](REVIEW_AWARE_CONTEXT)
    pv = PB.preview_research_packet(seeded["providers"], projection_id=proj,
                                    packet_type=REVIEW_AWARE_ANSWER_CONTEXT)
    mns = pv["answer_contract"]["must_not_say"]
    assert mns
    allowed_keys = {"target_kind", "target_id", "effective_state", "inclusion_state",
                    "exclusion_reason", "label"}
    for e in mns:
        assert set(e).issubset(allowed_keys)  # ids/labels/reasons only, no full content
        assert e["inclusion_state"] in ("excluded", "not_required", "superseded")


def test_items_preserve_provenance_and_bounded(seeded) -> None:
    pv = PB.preview_research_packet(seeded["providers"], projection_id=seeded["rid"],
                                    packet_type=REVIEW_AWARE_ANSWER_CONTEXT)
    anchors = ("source_id", "note_rel_path", "claim_id", "receipt_id", "pack_id", "pack_item_id",
               "memory_node_id", "memory_mention_id", "compilation_id", "decision_id", "preference_id",
               "open_loop_id")
    for it in pv["items"]:
        assert it["target_id"] and it["projection_item_id"]
        assert any(it.get(a) for a in anchors)
        if it["evidence_excerpt"]:
            assert len(it["evidence_excerpt"]) <= EVIDENCE_HARD_CAP


def test_budget_max_items_truncates(seeded) -> None:
    bud = PacketBudget.for_type(REVIEW_AWARE_ANSWER_CONTEXT)
    bud.max_items = 1
    pv = PB.preview_research_packet(seeded["providers"], projection_id=seeded["rid"],
                                    packet_type=REVIEW_AWARE_ANSWER_CONTEXT, budget=bud)
    assert pv["included_count"] == 1 and pv["truncated"] is True


def test_budget_max_citations_per_item(seeded) -> None:
    bud = PacketBudget.for_type(REVIEW_AWARE_ANSWER_CONTEXT)
    bud.max_citations_per_item = 1
    pv = PB.preview_research_packet(seeded["providers"], projection_id=seeded["rid"],
                                    packet_type=REVIEW_AWARE_ANSWER_CONTEXT, budget=bud)
    by_item: dict[str, int] = {}
    for c in pv["citations"]:
        by_item[c["packet_item_id"]] = by_item.get(c["packet_item_id"], 0) + 1
    assert by_item and all(n <= 1 for n in by_item.values())


def test_implementation_context_open_loops_advisory(seeded) -> None:
    proj = seeded["project"]("implementation_context")
    pv = PB.preview_research_packet(seeded["providers"], projection_id=proj,
                                    packet_type="implementation_research_context")
    open_loops = [i for i in pv["items"] if i["target_kind"] == "open_loop" and i["included"]]
    assert open_loops
    for i in open_loops:
        assert i["answer_role"] == "implementation_note"  # advisory only — never executable
    assert pv["answer_contract"]["open_loops_policy"] == "advisory_only"


def test_preview_dryrun_apply_do_not_mutate_projection_review_source(seeded) -> None:
    before = _snapshot(seeded["db"])
    PB.preview_research_packet(seeded["providers"], projection_id=seeded["rid"],
                               packet_type=REVIEW_AWARE_ANSWER_CONTEXT)
    assert _snapshot(seeded["db"]) == before
    PB.build_research_packet(seeded["providers"], seeded["prepo"], projection_id=seeded["rid"],
                             packet_type=REVIEW_AWARE_ANSWER_CONTEXT, apply=False)
    assert _snapshot(seeded["db"]) == before
    res = PB.build_research_packet(seeded["providers"], seeded["prepo"], projection_id=seeded["rid"],
                                  packet_type=REVIEW_AWARE_ANSWER_CONTEXT, apply=True)
    assert res["applied"] is True and res["created"] is True
    assert _snapshot(seeded["db"]) == before  # only packet tables were written
    assert seeded["prepo"].count() == 1


def test_projection_dispositions_events_unchanged_by_apply(seeded) -> None:
    def snap():
        with sqlite3.connect(seeded["db"]) as c:
            p = c.execute("SELECT * FROM assistant_intelligence_projections ORDER BY 1").fetchall()
            d = c.execute("SELECT * FROM assistant_review_dispositions ORDER BY 1").fetchall()
            e = c.execute("SELECT * FROM assistant_review_events ORDER BY 1").fetchall()
        return (repr(p), repr(d), repr(e))
    before = snap()
    PB.build_research_packet(seeded["providers"], seeded["prepo"], projection_id=seeded["rid"],
                             packet_type=REVIEW_AWARE_ANSWER_CONTEXT, apply=True)
    assert snap() == before


def test_build_apply_idempotent(seeded) -> None:
    PB.build_research_packet(seeded["providers"], seeded["prepo"], projection_id=seeded["rid"],
                             packet_type=REVIEW_AWARE_ANSWER_CONTEXT, apply=True)
    res2 = PB.build_research_packet(seeded["providers"], seeded["prepo"], projection_id=seeded["rid"],
                                   packet_type=REVIEW_AWARE_ANSWER_CONTEXT, apply=True)
    assert res2["reused"] is True and res2["created"] is False


def test_export_bounded_no_answer_prose(seeded) -> None:
    res = PB.build_research_packet(seeded["providers"], seeded["prepo"], projection_id=seeded["rid"],
                                  packet_type=REVIEW_AWARE_ANSWER_CONTEXT, apply=True)
    exp = PB.export_research_packet(seeded["prepo"], packet_id=res["packet_id"])
    assert set(exp) == {"format", "packet", "answer_contract", "items", "citations", "item_count",
                        "citation_count"}
    blob = json.dumps(exp)
    assert not any(k in blob for k in ("final_answer", "answer_text", "generated_answer"))


def test_unknown_projection_raises(seeded) -> None:
    from hb_assistant.obsidian_mcp.research_packet_models import ResearchPacketValidationError
    with pytest.raises(ResearchPacketValidationError):
        PB.preview_research_packet(seeded["providers"], projection_id="nope",
                                   packet_type=REVIEW_AWARE_ANSWER_CONTEXT)
