"""N8C-4 — claim repository: provenance, bounds, status/review enforcement, idempotency, events.

Read/write only to the V100 claim tables; no source/import table is mutated.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp.claim_models import (
    EVIDENCE_MAX_CHARS,
    ClaimCandidate,
    ClaimValidationError,
    compute_claim_id,
)
from hb_assistant.obsidian_mcp.claim_repository import ClaimRepository
from hb_assistant.store.migrator import SQLiteMigrator


@pytest.fixture()
def repo(tmp_path: Path) -> ClaimRepository:
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return ClaimRepository(db)


def _cand(t: str = "risk", text: str = "risk: switchgear may slip", **kw) -> ClaimCandidate:
    return ClaimCandidate(claim_type=t, claim_text=text, evidence_excerpt=kw.pop("ev", text), **kw)


def test_tables_exist_and_empty(repo: ClaimRepository) -> None:
    assert repo.count_claims() == 0  # ships empty; nothing auto-populates


def test_unsupported_batch_rejected(repo: ClaimRepository) -> None:
    with pytest.raises(ClaimValidationError):
        repo.ingest_candidates([_cand()])  # no source_id and no note_rel_path


def test_ingest_with_source_provenance(repo: ClaimRepository) -> None:
    res = repo.ingest_candidates([_cand()], source_id="s1", note_rel_path="Source Notes/a.md",
                                 card_id="c1", source_kind="external_file", source_root_key="proj",
                                 source_rel_path="docs/a.txt", extractor_version="rule_based-v1")
    assert res["ingested"] == 1
    claims = repo.get_claims_for_source("s1")
    assert len(claims) == 1
    row = claims[0]
    assert row["source_id"] == "s1" and row["note_rel_path"] == "Source Notes/a.md"
    assert row["card_id"] == "c1" and row["source_root_key"] == "proj"
    assert row["evidence_excerpt"] and row["status"] == "candidate"
    assert row["review_state"] == "unreviewed" and row["extractor_version"] == "rule_based-v1"
    assert row["claim_id"] == compute_claim_id("s1", "Source Notes/a.md", "risk",
                                               "risk: switchgear may slip")


def test_note_only_provenance_ok(repo: ClaimRepository) -> None:
    res = repo.ingest_candidates([_cand()], note_rel_path="Notes/x.md")  # note anchor alone is enough
    assert res["ingested"] == 1
    assert len(repo.get_claims_for_note("Notes/x.md")) == 1


def test_bad_candidate_collected_not_written(repo: ClaimRepository) -> None:
    res = repo.ingest_candidates(
        [_cand(t="not_a_type"), ClaimCandidate("fact", "", ""), _cand()],
        source_id="s1")
    assert res["ingested"] == 1
    reasons = {r["reason"].split(":")[0] for r in res["rejected"]}
    assert reasons == {"invalid_claim_type", "empty_claim_text"}


def test_confidence_is_clamped(repo: ClaimRepository) -> None:
    repo.ingest_candidates([_cand(confidence=1.9), _cand(t="fact", text="x", confidence=-3.0)],
                           source_id="s2")
    for row in repo.get_claims_for_source("s2"):
        assert 0.0 <= row["confidence"] <= 1.0


def test_db_check_blocks_out_of_range_confidence(repo: ClaimRepository) -> None:
    # Backstop: a direct write bypassing the repo clamp still cannot store a bad probability.
    with sqlite3.connect(repo.db_path) as c, pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO assistant_claims (claim_id, claim_type, claim_text, evidence_excerpt,"
                  " source_id, confidence) VALUES ('z','fact','t','e','s',2.0)")


def test_invalid_status_and_review_rejected(repo: ClaimRepository) -> None:
    with pytest.raises(ClaimValidationError):
        repo.ingest_candidates([_cand()], source_id="s1", status="bogus")
    with pytest.raises(ClaimValidationError):
        repo.ingest_candidates([_cand()], source_id="s1", review_state="bogus")


def test_evidence_is_bounded(repo: ClaimRepository) -> None:
    big = "risk " + ("x" * (EVIDENCE_MAX_CHARS * 3))
    repo.ingest_candidates([_cand(ev=big)], source_id="s3")
    row = repo.get_claims_for_source("s3")[0]
    assert len(row["evidence_excerpt"]) <= EVIDENCE_MAX_CHARS


def test_reingest_is_idempotent_and_logs_events(repo: ClaimRepository) -> None:
    r1 = repo.ingest_candidates([_cand()], source_id="s1")
    r2 = repo.ingest_candidates([_cand()], source_id="s1")
    assert r1["ingested"] == 1 and r2["ingested"] == 0 and r2["updated"] == 1
    assert repo.count_claims() == 1
    claim_id = repo.get_claims_for_source("s1")[0]["claim_id"]
    events = [e["event_type"] for e in repo.list_events(claim_id)]
    assert events[0] == "created" and "updated" in events


def test_set_status_and_mark_stale(repo: ClaimRepository) -> None:
    repo.ingest_candidates([_cand()], source_id="s1")
    claim_id = repo.get_claims_for_source("s1")[0]["claim_id"]
    assert repo.set_status(claim_id, "accepted", review_state="operator_accepted") is True
    assert repo.get_claim(claim_id)["status"] == "accepted"
    assert repo.get_claim(claim_id)["review_state"] == "operator_accepted"
    assert repo.mark_stale(claim_id, reason="source_digest_drift") is True
    assert repo.get_claim(claim_id)["status"] == "stale"
    evts = [e["event_type"] for e in repo.list_events(claim_id)]
    assert "accepted" in evts and "marked_stale" in evts


def test_list_filters_and_bounded(repo: ClaimRepository) -> None:
    repo.ingest_candidates([_cand(), _cand(t="date", text="due March 4, 2027")], source_id="s1")
    assert len(repo.list_claims(claim_type="risk")) == 1
    assert len(repo.list_claims(status="candidate")) == 2
    assert repo.list_claims(limit=10_000) is not None  # clamped internally, no error
