"""N8C-6 context-pack builder: budget/truncation, provenance, ordering, no-writeback, stale."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp import context_pack_builder as B
from hb_assistant.obsidian_mcp.claim_models import ClaimCandidate
from hb_assistant.obsidian_mcp.claim_repository import ClaimRepository
from hb_assistant.obsidian_mcp.context_pack_models import Budget
from hb_assistant.obsidian_mcp.context_pack_repository import ContextPackRepository
from hb_assistant.obsidian_mcp.enrichment_repository import EnrichmentRepository
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.store.migrator import SQLiteMigrator

# Tables that must never change under a preview / dry-run (read-only proof, clarification #5).
_WATCHED_LIKE = ("assistant_context_pack%", "assistant_claim%", "assistant_enrichment%",
                 "source_intelligence%")


def _seed_summary(er: EnrichmentRepository, source_id: str, summary: str) -> None:
    j = er.queue_job(job_type="source_summary", source_id=source_id)
    er.claim_next_job("w", 300)
    er.mark_running(j["job_id"], "w")
    er.complete_job(j["job_id"], "w", status="completed",
                    result_json=json.dumps({"summary": summary, "confidence": 0.8}),
                    applied_status="stored_only", receipt_metadata={"output_digest": f"d-{source_id}"})


def _seed_claim_extraction(er: EnrichmentRepository, source_id: str) -> None:
    j = er.queue_job(job_type="claim_extraction", source_id=source_id)
    er.claim_next_job("w", 300)
    er.mark_running(j["job_id"], "w")
    er.complete_job(j["job_id"], "w", status="completed",
                    result_json=json.dumps({"claims": [], "count": 0}),
                    applied_status="candidate_claims_ingested",
                    receipt_metadata={"output_digest": f"c-{source_id}"})


def _row_counts(db: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    with sqlite3.connect(db) as c:
        names: list[str] = []
        for pat in _WATCHED_LIKE:
            names += [r[0] for r in c.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE ?", (pat,))]
        for n in names:
            counts[n] = c.execute(f"SELECT COUNT(*) FROM {n}").fetchone()[0]  # noqa: S608 (table from sqlite_master)
    return counts


@pytest.fixture()
def env(tmp_path: Path):
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    er, cr, sr = EnrichmentRepository(db), ClaimRepository(db), SourceIndexRepository(db)
    pr = ContextPackRepository(db)
    return {"db": db, "prov": B.Providers(er, cr, sr), "pr": pr, "er": er, "cr": cr, "sr": sr}


def test_budget_max_items_and_truncated(env) -> None:
    for i in range(4):
        _seed_summary(env["er"], f"s{i}", "S" * 50)
    req = B.PackRequest(pack_type="enrichment_review", budget=Budget(max_items=2))
    out = B.preview_context_pack(req, env["prov"])
    included = [i for i in out["items"] if i["included"]]
    excluded = [i for i in out["items"] if not i["included"]]
    assert len(included) == 2
    assert out["pack"]["truncated"] is True
    assert all(e["exclusion_reason"] == "budget_max_items" for e in excluded)


def test_per_item_and_total_char_caps(env) -> None:
    _seed_summary(env["er"], "s0", "Z" * 5000)
    req = B.PackRequest(pack_type="enrichment_review",
                        budget=Budget(max_items=10, max_chars=300, max_chars_per_item=100))
    out = B.preview_context_pack(req, env["prov"])
    inc = [i for i in out["items"] if i["included"]]
    assert all(len(i["content_excerpt"] or "") <= 100 for i in inc)
    assert out["receipt"]["total_chars"] <= 300


def test_items_retain_provenance(env) -> None:
    env["cr"].ingest_candidates(
        [ClaimCandidate(claim_type="fact", claim_text="x", evidence_excerpt="ev", confidence=0.7)],
        source_id="s0", note_rel_path="Cards/s0.md", extractor_version="rule_based-v1")
    _seed_summary(env["er"], "s0", "sum")
    _seed_claim_extraction(env["er"], "s0")  # claim review items derive from a claim_extraction receipt
    out = B.preview_context_pack(B.PackRequest(pack_type="enrichment_review"), env["prov"])
    claim_item = next(i for i in out["items"] if i["item_type"] == "claim_candidate")
    assert claim_item["claim_id"] and claim_item["source_id"] == "s0"
    summ_item = next(i for i in out["items"] if i["item_type"] == "source_summary")
    assert summ_item["receipt_id"] and summ_item["result_digest"] == "d-s0"


def test_deterministic_ordering_and_output_digest(env) -> None:
    for i in range(3):
        _seed_summary(env["er"], f"s{i}", "S")
    req = B.PackRequest(pack_type="enrichment_review")
    a = B.preview_context_pack(req, env["prov"])
    b = B.preview_context_pack(req, env["prov"])
    assert [i["item_order"] for i in a["items"]] == [i["item_order"] for i in b["items"]]
    assert a["pack"]["output_digest"] == b["pack"]["output_digest"]
    assert a["pack"]["pack_id"] == b["pack"]["pack_id"]  # idempotent id


def test_items_never_store_full_result_json(env) -> None:
    _seed_summary(env["er"], "s0", "sum body")
    out = B.preview_context_pack(B.PackRequest(pack_type="enrichment_review"), env["prov"])
    for it in out["items"]:
        assert "result_json" not in it  # only receipt_id + result_digest link out
        assert set(it.keys()) & {"result_digest", "receipt_id"}


def test_preview_and_dry_run_are_read_only(env) -> None:
    _seed_summary(env["er"], "s0", "sum")
    before = _row_counts(env["db"])
    B.preview_context_pack(B.PackRequest(pack_type="enrichment_review"), env["prov"])
    B.build_context_pack(B.PackRequest(pack_type="enrichment_review"), env["prov"], env["pr"],
                         apply=False)
    after = _row_counts(env["db"])
    assert before == after  # no context-pack / claim / enrichment / source_intelligence row changed


def test_apply_persists_only_context_pack_tables(env) -> None:
    _seed_summary(env["er"], "s0", "sum")
    before = _row_counts(env["db"])
    res = B.build_context_pack(B.PackRequest(pack_type="enrichment_review"), env["prov"], env["pr"],
                               apply=True)
    after = _row_counts(env["db"])
    assert res["applied"] is True
    # claims / enrichment / source_intelligence unchanged; only context-pack tables grew.
    for name, count in before.items():
        if name.startswith("assistant_context_pack"):
            assert after[name] >= count
        else:
            assert after[name] == count


def test_apply_is_idempotent_reuse(env) -> None:
    _seed_summary(env["er"], "s0", "sum")
    req = B.PackRequest(pack_type="enrichment_review")
    r1 = B.build_context_pack(req, env["prov"], env["pr"], apply=True)
    r2 = B.build_context_pack(req, env["prov"], env["pr"], apply=True)
    assert r2.get("reused") is True
    assert r1["pack_id"] == r2["pack_id"]
    assert env["pr"].count_packs() == 1


def test_stale_detection_explicit_only(env) -> None:
    _seed_summary(env["er"], "s0", "sum")
    req = B.PackRequest(pack_type="enrichment_review")
    res = B.build_context_pack(req, env["prov"], env["pr"], apply=True)
    # No drift yet -> not stale.
    chk0 = B.mark_context_pack_stale_if_needed(res["pack_id"], req, env["prov"], env["pr"])
    assert chk0["stale"] is False
    # A new receipt drifts the input digest -> explicit check marks stale.
    _seed_summary(env["er"], "s1", "another")
    chk1 = B.mark_context_pack_stale_if_needed(res["pack_id"], req, env["prov"], env["pr"])
    assert chk1["stale"] is True
    assert env["pr"].get_pack(res["pack_id"])["status"] == "stale"


def test_export_is_bounded_json(env) -> None:
    _seed_summary(env["er"], "s0", "sum")
    res = B.build_context_pack(B.PackRequest(pack_type="enrichment_review"), env["prov"], env["pr"],
                               apply=True)
    pack = env["pr"].get_pack(res["pack_id"])
    exp = B.export_context_pack(pack, env["pr"].list_items(res["pack_id"]))
    assert exp["format"] == "json"
    blob = json.dumps(exp)
    assert "result_json" not in blob
