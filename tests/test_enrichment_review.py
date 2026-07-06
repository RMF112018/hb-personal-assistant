"""N8C-6 enrichment-review derived read model: derivation, tiering, claims stay candidate."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp import enrichment_review as rv
from hb_assistant.obsidian_mcp.claim_models import ClaimCandidate
from hb_assistant.obsidian_mcp.claim_repository import ClaimRepository
from hb_assistant.obsidian_mcp.enrichment_repository import EnrichmentRepository
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
from hb_assistant.store.migrator import SQLiteMigrator


def _complete(er: EnrichmentRepository, *, job_type: str, source_id: str, result: dict) -> None:
    j = er.queue_job(job_type=job_type, source_id=source_id)
    er.claim_next_job("w", 300)
    er.mark_running(j["job_id"], "w")
    er.complete_job(j["job_id"], "w", status="completed", result_json=json.dumps(result),
                    applied_status="stored_only", receipt_metadata={"output_digest": f"d-{source_id}"})


@pytest.fixture()
def repos(tmp_path: Path):
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return EnrichmentRepository(db), ClaimRepository(db), SourceIndexRepository(db)


def test_review_item_from_source_summary_receipt(repos) -> None:
    er, cr, sr = repos
    _complete(er, job_type="source_summary", source_id="s1",
              result={"summary": "bounded summary", "confidence": 0.8})
    env = rv.list_enrichment_review_items(er, cr, sr, limit=10)
    kinds = {i["review_item_type"] for i in env["review_items"]}
    assert rv.ITEM_SOURCE_SUMMARY in kinds
    it = next(i for i in env["review_items"] if i["review_item_type"] == rv.ITEM_SOURCE_SUMMARY)
    assert it["summary"] == "bounded summary"
    assert it["result_digest"] == "d-s1"
    assert it["review_state"] == "unreviewed"


def test_review_item_from_backlink_receipt(repos) -> None:
    er, cr, sr = repos
    _complete(er, job_type="backlink_suggestions", source_id="s2",
              result={"suggestions": [{"target": "Note A", "reason": "shares topic",
                                       "confidence": 0.6}], "count": 1})
    env = rv.list_enrichment_review_items(er, cr, sr, limit=10, job_type="backlink_suggestions")
    assert env["count"] == 1
    it = env["review_items"][0]
    assert it["review_item_type"] == rv.ITEM_BACKLINK_SUGGESTION
    assert it["evidence_excerpt"] == "Note A"


def test_review_items_from_claim_extraction_receipt_stay_candidate(repos) -> None:
    er, cr, sr = repos
    cr.ingest_candidates(
        [ClaimCandidate(claim_type="fact", claim_text="Deck is 40ft", evidence_excerpt="deck 40ft",
                        confidence=0.7)],
        source_id="s3", note_rel_path="Cards/s3.md", extractor_version="rule_based-v1",
    )
    _complete(er, job_type="claim_extraction", source_id="s3",
              result={"claims": [{"claim_type": "fact", "claim_text": "Deck is 40ft",
                                  "confidence": 0.7}], "count": 1})
    env = rv.list_enrichment_review_items(er, cr, sr, limit=10, job_type="claim_extraction")
    claim_items = [i for i in env["review_items"] if i["review_item_type"] == rv.ITEM_CLAIM_CANDIDATE]
    assert claim_items, "claim_extraction receipt should derive claim_candidate review items"
    assert claim_items[0]["claim_id"]
    # The underlying claim is untouched: still candidate / unreviewed.
    claims = cr.list_claims(status="candidate")
    assert claims and all(c["status"] == "candidate" and c["review_state"] == "unreviewed"
                          for c in claims)


def test_tier_classification_rules() -> None:
    assert rv.classify_review_tier(item_type="source_summary", confidence=0.9,
                                   source_state="current", resolution="unique") == rv.TIER_SAFE_SUMMARY
    assert rv.classify_review_tier(item_type="claim_candidate", confidence=0.1,
                                   source_state="current", resolution="unique") == rv.TIER_LOW_CONFIDENCE
    assert rv.classify_review_tier(item_type="source_summary", confidence=0.9,
                                   source_state="current", resolution="ambiguous") \
        == rv.TIER_NEEDS_OPERATOR_REVIEW
    assert rv.classify_review_tier(item_type="source_summary", confidence=0.9,
                                   source_state="stale", resolution="unique") == rv.TIER_SOURCE_STALE
    assert rv.classify_review_tier(item_type="backlink_suggestion", confidence=0.9,
                                   source_state="current", resolution="unique") == rv.TIER_LINK_CANDIDATE


def test_review_tier_filter_and_get_by_id(repos) -> None:
    er, cr, sr = repos
    _complete(er, job_type="source_summary", source_id="s1", result={"summary": "x", "confidence": 0.8})
    env = rv.list_enrichment_review_items(er, cr, sr, limit=10)
    rid = env["review_items"][0]["review_item_id"]
    got = rv.get_enrichment_review_item(er, cr, sr, rid)
    assert got is not None and got["review_item_id"] == rid
    assert rv.get_enrichment_review_item(er, cr, sr, "does-not-exist") is None
