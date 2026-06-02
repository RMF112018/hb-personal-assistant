"""Phase 08A Prompt 10 — Memory Curator Agent (A07) against a temp DB.

Proves: candidates carry origin + source refs + review tier; sensitive/high-impact ->
Tier 3; promotion to accepted memory happens only via explicit review (no silent
acceptance); accepted memory persists source refs + quality signals with guard columns 0;
no raw content.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain.memory import (
    build_long_term_memory_proof,
    build_memory_curator_agent_proof,
    propose_memory_candidate,
    review_memory_candidate,
)
from hb_assistant.construction.store import ConstructionStore

_REFS = [{"source_family": "cross_source_relationships", "source_ref": "rel-1"}]


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    db = str(tmp_path / "memory.sqlite")
    ConstructionStore(db)  # migrate to V26
    return db


def test_candidate_requires_origin_and_source_refs_and_tier(db_path: str) -> None:
    c = propose_memory_candidate(
        statement_redacted="P1 kickoff confirmed",
        proposed_memory_type="fact",
        origin_id="qr-1",
        source_refs=_REFS,
        confidence_class="high",
        project_key="P1",
        db_path=db_path,
        emit=True,
    )
    assert c.origin_id == "qr-1"
    assert c.source_refs
    assert c.review_tier == 1
    assert c.status == "proposed"


def test_sensitive_candidate_routes_tier_3(db_path: str) -> None:
    c = propose_memory_candidate(
        statement_redacted="alleged entitlement claim",
        proposed_memory_type="claim",
        origin_id="qr-2",
        source_refs=_REFS,
        confidence_class="high",
        sensitivity_category="financial",
        db_path=db_path,
        emit=True,
    )
    assert c.review_tier == 3
    assert c.review_required is True
    assert c.review_tier_reason_code == "T3_SENSITIVE_HIGH_IMPACT"


def test_propose_does_not_create_memory_item_no_silent_acceptance(db_path: str) -> None:
    propose_memory_candidate(
        statement_redacted="x", proposed_memory_type="fact", origin_id="o", source_refs=_REFS,
        confidence_class="high", db_path=db_path, emit=True,
    )
    conn = sqlite3.connect(db_path)
    n = conn.execute("SELECT COUNT(*) FROM long_term_memory_items").fetchone()[0]
    conn.close()
    assert n == 0  # nothing accepted without an explicit review


def test_review_accept_promotes_to_memory_with_signals(db_path: str) -> None:
    c = propose_memory_candidate(
        statement_redacted="P1 baseline accepted", proposed_memory_type="fact", origin_id="brief-1",
        source_refs=_REFS, confidence_class="high", project_key="P1", db_path=db_path, emit=True,
    )
    review, item, signals = review_memory_candidate(
        candidate=c, decision="accepted", db_path=db_path, emit=True
    )
    assert review.decision == "accepted"
    assert item is not None and item.review_status == "accepted"
    assert {s.signal_type for s in signals} == {"origin", "quality"}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    mem = dict(conn.execute("SELECT * FROM long_term_memory_items").fetchone())
    refs = conn.execute("SELECT * FROM long_term_memory_source_refs").fetchall()
    sigs = conn.execute("SELECT * FROM long_term_memory_quality_signals").fetchall()
    cand = dict(conn.execute("SELECT * FROM memory_update_candidates").fetchone())
    guards = [c2 for c2 in mem if c2.endswith("_persisted")]
    for col in guards:
        assert mem[col] == 0
    conn.close()
    assert mem["origin_id"] == "brief-1"
    assert len(refs) == 1
    assert len(sigs) == 2
    assert cand["status"] == "accepted"


def test_review_reject_does_not_create_memory(db_path: str) -> None:
    c = propose_memory_candidate(
        statement_redacted="x", proposed_memory_type="fact", origin_id="o", source_refs=_REFS,
        confidence_class="medium", db_path=db_path, emit=True,
    )
    _review, item, _signals = review_memory_candidate(
        candidate=c, decision="rejected", db_path=db_path, emit=True
    )
    assert item is None
    conn = sqlite3.connect(db_path)
    n = conn.execute("SELECT COUNT(*) FROM long_term_memory_items").fetchone()[0]
    conn.close()
    assert n == 0


def test_proofs_pass() -> None:
    assert build_memory_curator_agent_proof()["proof_passed"] is True
    assert build_long_term_memory_proof()["proof_passed"] is True
