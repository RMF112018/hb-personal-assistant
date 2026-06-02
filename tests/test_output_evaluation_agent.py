"""Phase 08A Prompt 12 — Output Evaluation Agent (A05) persistence."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain.reasoning import MockClaudeAdapter
from hb_assistant.construction.second_brain.research import build_research_packet_from_envelope
from hb_assistant.construction.second_brain.retrieval import (
    ALLOWLISTED_SOURCE_FAMILIES,
    RetrievalBroker,
)
from hb_assistant.construction.second_brain.synthesis import (
    build_evaluation_preview,
    build_output_evaluation_agent_proof,
    read_latest_evaluation_runs,
    write_evaluation_run,
)
from hb_assistant.construction.store import ConstructionStore


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "eval.sqlite")


def _seed(db_path: str) -> None:
    store = ConstructionStore(db_path)
    store.upsert_cross_source_relationship(
        relationship_id="rel-1",
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


def _evaluate(db_path: str):
    envelope = RetrievalBroker(db_path=db_path).retrieve(
        project_key="P1", families=ALLOWLISTED_SOURCE_FAMILIES, emit_receipt=False
    )
    packet, assessment, _r, _p = build_research_packet_from_envelope(
        envelope,
        packet_type="daily_brief",
        requested=ALLOWLISTED_SOURCE_FAMILIES,
        project_key="P1",
        db_path=db_path,
        emit_receipt=False,
    )
    ctx = envelope.to_context_envelope(
        question="daily brief", research_packet_ok=packet.degradation_mode != "blocked"
    )
    result = MockClaudeAdapter().synthesize(ctx)
    evaluation = build_evaluation_preview(
        adapter_result=result, packet=packet, assessment=assessment, envelope=ctx
    )
    return evaluation, result, packet


def test_evaluation_run_persisted_with_guards_zero(db_path: str) -> None:
    _seed(db_path)
    evaluation, result, packet = _evaluate(db_path)
    run_id = write_evaluation_run(
        evaluation=evaluation,
        target_kind="daily_brief",
        target_id=packet.packet_id,
        research_packet_id=packet.packet_id,
        confidence_class=result.confidence,
        review_tier_reason_code=result.review_reason_code,
        degradation_mode=result.degradation_mode,
        db_path=db_path,
    )
    assert run_id

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = dict(conn.execute("SELECT * FROM second_brain_evaluation_runs").fetchone())
    conn.close()

    assert row["mode"] == "dry_run"
    assert row["target_kind"] == "daily_brief"
    assert row["review_status"] == "pending_review"  # the row's own review state
    assert row["checklist_total"] == 10
    assert row["passed"] == 1
    guards = [c for c in row if c.endswith("_persisted")] + ["external_writeback_performed"]
    for col in guards:
        assert row[col] == 0, f"guard {col} must be 0"


def test_empty_db_evaluation_fails(db_path: str) -> None:
    ConstructionStore(db_path)  # migrate only
    evaluation, _result, _packet = _evaluate(db_path)
    assert evaluation.passed is False
    assert evaluation.checklist["source_references_present"] is False


def test_read_latest_evaluation_runs(db_path: str) -> None:
    _seed(db_path)
    evaluation, result, packet = _evaluate(db_path)
    run_id = write_evaluation_run(
        evaluation=evaluation,
        target_kind="daily_brief",
        target_id=packet.packet_id,
        confidence_class=result.confidence,
        review_tier_reason_code=result.review_reason_code,
        degradation_mode=result.degradation_mode,
        db_path=db_path,
    )
    rows = read_latest_evaluation_runs(db_path=db_path, target_kind="daily_brief")
    assert rows and rows[0]["evaluation_run_id"] == run_id


def test_output_evaluation_agent_proof_passes() -> None:
    proof = build_output_evaluation_agent_proof()
    assert proof["proof_passed"] is True
    assert proof["passed_case"]["passed"] is True
    assert proof["failed_case"]["passed"] is False
    assert proof["guard_columns_zero"] is True
    assert proof["no_raw_content"] is True
