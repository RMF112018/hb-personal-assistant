"""N8C-7 memory compiler: discovery, provenance, tiers, idempotency, no-writeback."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp import context_pack_builder as CB
from hb_assistant.obsidian_mcp import memory_compiler as MC
from hb_assistant.obsidian_mcp import memory_models as mm
from hb_assistant.obsidian_mcp.claim_models import ClaimCandidate
from hb_assistant.obsidian_mcp.claim_repository import ClaimRepository
from hb_assistant.obsidian_mcp.context_pack_models import Budget
from hb_assistant.obsidian_mcp.context_pack_repository import ContextPackRepository
from hb_assistant.obsidian_mcp.enrichment_repository import EnrichmentRepository
from hb_assistant.obsidian_mcp.memory_repository import MemoryRepository
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.store.migrator import SQLiteMigrator

_WATCHED_LIKE = ("assistant_memory%", "assistant_claim%", "assistant_enrichment%",
                 "assistant_context_pack%", "source_intelligence%")


def _complete(er: EnrichmentRepository, *, job_type: str, source_id: str, result: dict) -> None:
    j = er.queue_job(job_type=job_type, source_id=source_id)
    er.claim_next_job("w", 300)
    er.mark_running(j["job_id"], "w")
    er.complete_job(j["job_id"], "w", status="completed", result_json=json.dumps(result),
                    applied_status="stored_only", receipt_metadata={"output_digest": f"d-{job_type}"})


def _row_counts(db: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    with sqlite3.connect(db) as c:
        names: list[str] = []
        for pat in _WATCHED_LIKE:
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
    pr, mr = ContextPackRepository(db), MemoryRepository(db)
    # A candidate claim with normalized subject/object, plus enrichment receipts so the
    # enrichment_review pack has claim / summary / backlink items.
    cr.ingest_candidates(
        [ClaimCandidate(claim_type="fact", claim_text="Tropical uses Procore",
                        evidence_excerpt="...Procore...", confidence=0.8,
                        normalized_subject="Tropical Waters", normalized_object="Procore")],
        source_id="s1", note_rel_path="Cards/s1.md", extractor_version="rule_based-v1")
    _complete(er, job_type="claim_extraction", source_id="s1", result={"claims": [], "count": 0})
    _complete(er, job_type="source_summary", source_id="s1",
              result={"summary": "Summary of the project", "confidence": 0.8})
    _complete(er, job_type="backlink_suggestions", source_id="s1",
              result={"suggestions": [{"target": "Marina Plan", "reason": "topic", "confidence": 0.6}],
                      "count": 1})
    res = CB.build_context_pack(CB.PackRequest(pack_type="enrichment_review", budget=Budget(max_items=30)),
                                CB.Providers(er, cr, sr), pr, apply=True)
    prov = MC.MemoryProviders(cr, pr, er, sr)
    return {"db": db, "prov": prov, "mr": mr, "cr": cr, "er": er, "pack_id": res["pack_id"]}


def test_discovery_from_claim_subject_and_object(env) -> None:
    prev = MC.preview_memory_compilation(env["prov"], pack_id=env["pack_id"])
    names = {n["canonical_name"] for n in prev["nodes"]}
    assert "Tropical Waters" in names and "Procore" in names  # normalized_subject/object


def test_discovery_from_summary_and_backlink(env) -> None:
    prev = MC.preview_memory_compilation(env["prov"], pack_id=env["pack_id"])
    mtypes = {m["mention_type"] for m in prev["mentions"]}
    assert "enrichment_summary" in mtypes   # context-pack summary item
    assert "backlink_target" in mtypes      # backlink suggestion item
    assert "claim_subject" in mtypes        # claim


def test_every_node_has_mention_and_provenance(env) -> None:
    prev = MC.preview_memory_compilation(env["prov"], pack_id=env["pack_id"])
    node_ids = {n["node_id"] for n in prev["nodes"]}
    mentioned = {m["node_id"] for m in prev["mentions"]}
    assert node_ids <= mentioned  # every node is backed by >=1 mention
    for m in prev["mentions"]:
        assert any(m.get(k) for k in ("source_id", "note_rel_path", "claim_id", "receipt_id",
                                      "pack_id", "pack_item_id"))


def test_compilation_is_bounded(env) -> None:
    prev = MC.preview_memory_compilation(env["prov"], pack_id=env["pack_id"])
    for comp in prev["compilations"]:
        assert len(comp["summary"] or "") <= mm.SUMMARY_HARD_CAP
        assert len(json.loads(comp["key_points_json"])) <= mm.KEY_POINTS_MAX


def test_tier_rules() -> None:
    # deterministic source-backed claim mention, clean source -> trusted
    assert MC.mention_tier(mention_type="claim_subject", source_state="current", resolution="unique",
                           confidence=0.8, is_fallback=False) == mm.TIER_TRUSTED_SOURCE_BACKED
    # stale source -> stale_source
    assert MC.mention_tier(mention_type="claim_subject", source_state="stale", resolution="unique",
                           confidence=0.8, is_fallback=False) == mm.TIER_STALE_SOURCE
    # ambiguous -> ambiguous_source
    assert MC.mention_tier(mention_type="claim_subject", source_state="current",
                           resolution="ambiguous", confidence=0.8,
                           is_fallback=False) == mm.TIER_AMBIGUOUS_SOURCE
    # low confidence -> low_confidence
    assert MC.mention_tier(mention_type="claim_subject", source_state="current", resolution="unique",
                           confidence=0.1, is_fallback=False) == mm.TIER_LOW_CONFIDENCE
    # Qwen-derived summary -> needs_operator_review
    assert MC.mention_tier(mention_type="enrichment_summary", source_state="current",
                           resolution="unique", confidence=0.9,
                           is_fallback=False) == mm.TIER_NEEDS_OPERATOR_REVIEW
    # raw claim_text fallback -> needs_operator_review
    assert MC.mention_tier(mention_type="claim_subject", source_state="current", resolution="unique",
                           confidence=0.8, is_fallback=True) == mm.TIER_NEEDS_OPERATOR_REVIEW
    # backlink -> low_confidence
    assert MC.mention_tier(mention_type="backlink_target", source_state="current",
                           resolution="unique", confidence=0.6,
                           is_fallback=False) == mm.TIER_LOW_CONFIDENCE


def test_fallback_claim_text_is_needs_review(tmp_path: Path) -> None:
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    er, cr, sr = EnrichmentRepository(db), ClaimRepository(db), SourceIndexRepository(db)
    pr = ContextPackRepository(db)
    # A claim with NO normalized subject/object -> claim_text fallback.
    cr.ingest_candidates(
        [ClaimCandidate(claim_type="fact", claim_text="Some unstructured fact here",
                        evidence_excerpt="ev", confidence=0.8)],
        source_id="s9", note_rel_path="Cards/s9.md", extractor_version="rule_based-v1")
    _complete(er, job_type="claim_extraction", source_id="s9", result={"claims": [], "count": 0})
    res = CB.build_context_pack(CB.PackRequest(pack_type="enrichment_review"),
                                CB.Providers(er, cr, sr), pr, apply=True)
    prev = MC.preview_memory_compilation(MC.MemoryProviders(cr, pr, er, sr), pack_id=res["pack_id"])
    fallback = [m for m in prev["mentions"] if (m["mention_text"] or "").startswith("Some unstructured")]
    # Raw claim_text fallback: concept node, capped confidence, never trusted (a cautious tier).
    assert fallback
    assert fallback[0]["confidence"] <= 0.39
    assert fallback[0]["review_tier"] != mm.TIER_TRUSTED_SOURCE_BACKED


def test_apply_is_idempotent_no_duplicates(env) -> None:
    a = MC.apply_memory_compilation(env["prov"], env["mr"], pack_id=env["pack_id"], apply=True)
    n1, m1 = env["mr"].count_nodes(), a["new_mentions"]
    b = MC.apply_memory_compilation(env["prov"], env["mr"], pack_id=env["pack_id"], apply=True)
    assert env["mr"].count_nodes() == n1              # no duplicate nodes
    assert b["new_mentions"] == 0                     # no duplicate mentions
    assert b["new_compilations"] == 0                 # same input -> reused compilations
    assert m1 > 0


def test_changed_input_creates_new_compilation_and_supersedes(env) -> None:
    MC.apply_memory_compilation(env["prov"], env["mr"], pack_id=env["pack_id"], apply=True)
    node = next(n for n in env["mr"].list_nodes() if n["canonical_name"] == "Tropical Waters")
    nid = node["node_id"]
    before = env["mr"].list_compilations(nid)
    assert len(before) == 1 and before[0]["status"] == "built"
    # Add a second claim with the same normalized_subject from another source -> node input changes.
    env["cr"].ingest_candidates(
        [ClaimCandidate(claim_type="fact", claim_text="more", evidence_excerpt="ev2", confidence=0.7,
                        normalized_subject="Tropical Waters", normalized_object="Schedule")],
        source_id="s2", note_rel_path="Cards/s2.md", extractor_version="rule_based-v1")
    _complete(env["er"], job_type="claim_extraction", source_id="s2", result={"claims": [], "count": 0})
    res = CB.build_context_pack(CB.PackRequest(pack_type="enrichment_review", budget=Budget(max_items=30)),
                                CB.Providers(env["er"], env["cr"], SourceIndexRepository(env["db"])),
                                ContextPackRepository(env["db"]), apply=True)
    MC.apply_memory_compilation(env["prov"], env["mr"], pack_id=res["pack_id"], apply=True)
    after = env["mr"].list_compilations(nid)
    assert len(after) == 2
    assert sorted(c["status"] for c in after) == ["built", "superseded"]


def test_node_id_stable_when_identity_unchanged(env) -> None:
    a = MC.apply_memory_compilation(env["prov"], env["mr"], pack_id=env["pack_id"], apply=True)
    ids_1 = {n["node_id"] for n in env["mr"].list_nodes()}
    MC.apply_memory_compilation(env["prov"], env["mr"], pack_id=env["pack_id"], apply=True)
    ids_2 = {n["node_id"] for n in env["mr"].list_nodes()}
    assert ids_1 == ids_2 and a["nodes"] > 0


def test_preview_and_dry_run_are_read_only(env) -> None:
    before = _row_counts(env["db"])
    MC.preview_memory_compilation(env["prov"], pack_id=env["pack_id"])
    MC.apply_memory_compilation(env["prov"], env["mr"], pack_id=env["pack_id"], apply=False)
    assert _row_counts(env["db"]) == before  # nothing written


def test_apply_writes_only_memory_tables(env) -> None:
    before = _row_counts(env["db"])
    MC.apply_memory_compilation(env["prov"], env["mr"], pack_id=env["pack_id"], apply=True)
    after = _row_counts(env["db"])
    for name, count in before.items():
        if name.startswith("assistant_memory"):
            assert after[name] >= count
        else:
            assert after[name] == count  # claims/enrichment/context-pack/source untouched


def test_claims_stay_candidate_unreviewed(env) -> None:
    MC.apply_memory_compilation(env["prov"], env["mr"], pack_id=env["pack_id"], apply=True)
    claims = env["cr"].list_claims()
    assert claims and all(c["status"] == "candidate" and c["review_state"] == "unreviewed"
                          for c in claims)


def test_export_is_bounded_json(env) -> None:
    MC.apply_memory_compilation(env["prov"], env["mr"], pack_id=env["pack_id"], apply=True)
    node = env["mr"].list_nodes()[0]
    nid = node["node_id"]
    exp = MC.export_memory_node(node, env["mr"].list_mentions(nid), env["mr"].list_compilations(nid))
    blob = json.dumps(exp)
    assert exp["format"] == "json"
    assert "result_json" not in blob
