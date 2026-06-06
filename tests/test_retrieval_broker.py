"""Phase 08A Synthesized Prompt 04 — Retrieval Broker (A03) against a seeded DB.

Proves: items carry source_ref + confidence + review_tier + warnings; no raw source
access; Tier 3 visible but review_required (not concluded); excluded families
denied; retrieval receipt persisted with all guard columns 0; V25 rows unchanged.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain.retrieval import RetrievalBroker
from hb_assistant.construction.store import ConstructionStore


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "retrieval.sqlite")


def _seed(db_path: str) -> ConstructionStore:
    store = ConstructionStore(db_path)  # runs migrator to V26
    # A promoted (human) relationship → authoritative/accepted, tier 1.
    store.upsert_cross_source_relationship(
        relationship_id="rel-accepted",
        source_family="email",
        source_record_type="message",
        source_record_ref="m1",
        target_family="procore",
        target_record_type="rfi",
        target_record_ref="rfi1",
        relationship_type="references",
        confidence_class="human_promoted",
        source_reference_json=json.dumps({"project_key": "P1"}),
        project_key="P1",
        promotion_status="promoted",
        promoted_by="human",
        review_required=False,
    )
    # A review-required relationship → tier 3 (visible, not concluded).
    store.upsert_cross_source_relationship(
        relationship_id="rel-sensitive",
        source_family="email",
        source_record_type="message",
        source_record_ref="m2",
        target_family="financial",
        target_record_type="invoice",
        target_record_ref="inv1",
        relationship_type="references",
        confidence_class="weak_heuristic",
        source_reference_json=json.dumps({"project_key": "P1"}),
        project_key="P1",
        promotion_status="promoted",
        promoted_by="human",
        review_required=True,
    )
    # An accepted long-term memory item.
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO long_term_memory_items "
        "(memory_id, memory_type, statement_redacted, project_key, confidence_class, review_status) "
        "VALUES ('mem1','fact','project P1 kickoff confirmed','P1','high','accepted')"
    )
    conn.commit()
    conn.close()
    return store


def test_retrieve_returns_source_linked_items(db_path: str) -> None:
    _seed(db_path)
    env = RetrievalBroker(db_path=db_path).retrieve(project_key="P1")
    assert env.items, "expected retrieved items"
    for it in env.items:
        assert it.source_ref
        assert it.confidence_class
        assert it.review_tier in (1, 2, 3)
        assert it.allowed_for_model_context is True
    families = {it.source_family for it in env.items}
    assert "cross_source_relationships" in families
    assert "accepted_long_term_memory" in families


def test_tier3_visible_but_review_required(db_path: str) -> None:
    _seed(db_path)
    env = RetrievalBroker(db_path=db_path).retrieve(project_key="P1")
    sensitive = [it for it in env.items if it.source_ref == "rel-sensitive"]
    assert sensitive, "tier-3 sensitive relationship must be retrievable"
    it = sensitive[0]
    assert it.review_tier == 3
    assert it.review_required is True
    assert it.review_status == "review_required"
    assert it.relationship_state is not None  # derived read-only label present


def test_no_raw_source_access(db_path: str) -> None:
    _seed(db_path)
    env = RetrievalBroker(db_path=db_path).retrieve(project_key="P1")
    blob = env.model_dump_json()
    for forbidden in (
        "raw_body",
        "raw_document_text",
        "raw_calendar_payload",
        "raw_prompt",
        "raw_response",
        "signed_url",
        "download_url",
    ):
        assert forbidden not in blob


def test_excluded_family_denied(db_path: str) -> None:
    _seed(db_path)
    env = RetrievalBroker(db_path=db_path).retrieve(
        project_key="P1", families=("cross_source_relationships", "raw_email_body")
    )
    assert any("denied_excluded_family:raw_email_body" in w for w in env.coverage_warnings)
    assert all(it.source_family != "raw_email_body" for it in env.items)


def test_receipt_persisted_with_guards_zero(db_path: str) -> None:
    _seed(db_path)
    RetrievalBroker(db_path=db_path).retrieve(project_key="P1")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    receipts = conn.execute("SELECT * FROM retrieval_query_receipts").fetchall()
    assert len(receipts) == 1
    row = dict(receipts[0])
    assert row["mode"] == "dry_run"
    assert row["source_ref_count"] >= 1
    guards = [c for c in row if c.endswith("_persisted")] + [
        "arbitrary_sql_allowed",
        "external_writeback_performed",
    ]
    for col in guards:
        assert row[col] == 0, f"guard {col} must be 0"
    refs = conn.execute("SELECT * FROM retrieval_context_refs").fetchall()
    assert len(refs) == row["source_ref_count"]
    conn.close()


def test_v25_rows_unchanged_after_retrieve(db_path: str) -> None:
    store = _seed(db_path)
    before = store.list_cross_source_relationships(project_key="P1")
    RetrievalBroker(db_path=db_path).retrieve(project_key="P1")
    after = store.list_cross_source_relationships(project_key="P1")
    assert before == after  # broker derives state read-only; never rewrites V25


def test_empty_db_degrades_gracefully(db_path: str) -> None:
    ConstructionStore(db_path)  # migrate only, no seed
    env = RetrievalBroker(db_path=db_path).retrieve(project_key="P1")
    assert env.items == []
    assert env.degradation_mode == "blocked"
    # All allowlisted families are now reader-backed (Phase 09 coverage expansion); an empty DB
    # degrades to empty results rather than no_read_model coverage warnings.
    assert not any(w.startswith("no_read_model:") for w in env.coverage_warnings)
