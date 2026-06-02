"""Phase 08A Prompt 07 — Research Packet Agent (A02) against a seeded DB.

Proves: the packet carries the contract required_fields; source coverage, tier
distribution, stale/conflict counts, accepted-memory refs, and open questions are
computed; the receipt persists with guard columns 0; no raw content; and empty context
blocks (degrade, not overstate).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain.contracts import load_phase_08a_contract
from hb_assistant.construction.second_brain.research import (
    build_research_packet,
    build_research_packet_agent_proof,
)
from hb_assistant.construction.store import ConstructionStore

_FORBIDDEN = (
    "raw_body",
    "raw_document_text",
    "raw_calendar_payload",
    "raw_prompt",
    "raw_response",
    "signed_url",
    "download_url",
    "secret",
)


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "research.sqlite")


def _seed(db_path: str) -> ConstructionStore:
    store = ConstructionStore(db_path)
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
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO long_term_memory_items "
        "(memory_id, memory_type, statement_redacted, project_key, confidence_class, review_status) "
        "VALUES ('mem1','fact','kickoff confirmed','P1','high','accepted')"
    )
    conn.execute(
        "INSERT INTO project_risk_digest_items "
        "(risk_digest_id, project_key, risk_indicator_type, risk_source_class, summary_redacted, "
        " confidence_class, review_required, created_utc) "
        "VALUES ('rd1','P1','schedule_slip','review_required','schedule slip','low',1,"
        "'2026-06-01T00:00:00Z')"
    )
    conn.commit()
    conn.close()
    return store


def test_packet_carries_contract_required_fields(db_path: str) -> None:
    _seed(db_path)
    packet, _assessment, _rid, _pid = build_research_packet(
        packet_type="interactive_query", project_key="P1", db_path=db_path, emit_receipt=False
    )
    dumped = packet.model_dump()
    for field in load_phase_08a_contract("research_packet_contract")["required_fields"]:
        assert field in dumped


def test_assessment_computed(db_path: str) -> None:
    _seed(db_path)
    packet, assessment, _rid, _pid = build_research_packet(
        packet_type="interactive_query", project_key="P1", db_path=db_path, emit_receipt=False
    )
    assert packet.source_ref_count >= 3
    assert "cross_source_relationships" in assessment.families_present
    assert assessment.families_missing  # not all 7 backed families present
    assert assessment.review_tier_distribution
    # The review_required risk row is tier 3 (visible, not concluded).
    assert packet.review_required_count >= 1
    assert any(
        r["source_family"] == "accepted_long_term_memory" for r in assessment.accepted_memory_refs
    )
    assert assessment.open_questions


def test_receipt_persisted_with_guards_zero(db_path: str) -> None:
    _seed(db_path)
    build_research_packet(
        packet_type="daily_brief", project_key="P1", db_path=db_path, emit_receipt=True
    )
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM second_brain_research_packets").fetchall()
    assert len(rows) == 1
    row = dict(rows[0])
    assert row["mode"] == "dry_run"
    assert row["review_status"] == "pending_review"
    assert row["source_ref_count"] >= 3
    guards = [c for c in row if c.endswith("_persisted")] + [
        "arbitrary_sql_allowed",
        "external_writeback_performed",
    ]
    for col in guards:
        assert row[col] == 0, f"guard {col} must be 0"
    conn.close()


def test_no_raw_content(db_path: str) -> None:
    _seed(db_path)
    packet, assessment, _rid, _pid = build_research_packet(
        packet_type="interactive_query", project_key="P1", db_path=db_path, emit_receipt=False
    )
    blob = packet.model_dump_json() + assessment.model_dump_json()
    for forbidden in _FORBIDDEN:
        assert forbidden not in blob


def test_empty_context_blocks_not_overstates(db_path: str) -> None:
    ConstructionStore(db_path)  # migrate only, no seed
    packet, _assessment, _rid, _pid = build_research_packet(
        packet_type="interactive_query", project_key="P1", db_path=db_path, emit_receipt=False
    )
    assert packet.degradation_mode == "blocked"
    assert packet.context_quality_class == "insufficient"
    assert packet.status == "blocked"
    assert packet.source_ref_count == 0


def test_v25_rows_unchanged_after_packet(db_path: str) -> None:
    store = _seed(db_path)
    before = store.list_cross_source_relationships(project_key="P1")
    build_research_packet(
        packet_type="interactive_query", project_key="P1", db_path=db_path, emit_receipt=False
    )
    after = store.list_cross_source_relationships(project_key="P1")
    assert before == after


def test_build_research_packet_agent_proof_passes() -> None:
    proof = build_research_packet_agent_proof()
    assert proof["proof_passed"] is True
    assert proof["guard_columns_zero"] is True
    assert proof["no_raw_content"] is True
    assert proof["empty_db_packet"]["degradation_mode"] == "blocked"
