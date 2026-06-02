"""Phase 08A Prompt 08 — Answer Synthesis Agent (A04) against seeded DBs.

Proves: tier-1 source-backed context yields a synthesized advisory answer with source
refs + a passing evaluation; Tier-3 / high-impact context is gated (not synthesized, not
a final conclusion); empty context blocks; the result carries every interactive_query
required_output field; and no raw content leaks.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain.contracts import load_phase_08a_contract
from hb_assistant.construction.second_brain.reasoning import MockClaudeAdapter
from hb_assistant.construction.second_brain.synthesis import (
    build_answer_synthesis_agent_proof,
    synthesize_answer,
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
    return str(tmp_path / "synthesis.sqlite")


def _accepted_relationship(store: ConstructionStore, rel_id: str, review_required: bool) -> None:
    store.upsert_cross_source_relationship(
        relationship_id=rel_id,
        source_family="email",
        source_record_type="message",
        source_record_ref=f"m-{rel_id}",
        target_family="procore",
        target_record_type="rfi",
        target_record_ref=f"rfi-{rel_id}",
        relationship_type="references",
        confidence_class="human_promoted",
        source_reference_json=json.dumps({"project_key": "P1"}),
        project_key="P1",
        promotion_status="promoted",
        promoted_by="human",
        review_required=review_required,
    )


def _seed_tier1(db_path: str) -> None:
    store = ConstructionStore(db_path)
    _accepted_relationship(store, "rel-1", review_required=False)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO long_term_memory_items "
        "(memory_id, memory_type, statement_redacted, project_key, confidence_class, review_status) "
        "VALUES ('mem1','fact','kickoff confirmed','P1','high','accepted')"
    )
    conn.commit()
    conn.close()


def test_tier1_context_synthesizes_advisory_answer(db_path: str) -> None:
    _seed_tier1(db_path)
    result = synthesize_answer(
        question="What changed this week?",
        project_key="P1",
        db_path=db_path,
        adapter=MockClaudeAdapter(),
    )
    assert result.synthesized is True
    assert result.mode == "mock"
    assert result.source_refs
    assert result.advisory_vs_actionable_marking["disposition"] == "advisory"
    assert result.advisory_vs_actionable_marking["actionable_recommendations"] == []
    assert result.confidence_labels["claim_strength"] in {"strong", "qualified"}
    assert result.evaluation_summary["passed"] is True


def test_tier3_high_impact_is_not_a_final_conclusion(db_path: str) -> None:
    store = ConstructionStore(db_path)
    _accepted_relationship(store, "rel-review", review_required=True)  # -> tier 3
    result = synthesize_answer(
        question="Is the contractor entitled to this claim?",
        project_key="P1",
        db_path=db_path,
        adapter=MockClaudeAdapter(),
    )
    assert result.synthesized is False
    assert result.answer_redacted == ""
    assert result.review_tiers["review_status"] == "review_required"
    assert any(w.startswith("synthesis_blocked") for w in result.warnings)
    assert result.evaluation_summary["checklist"]["no_tier_3_treated_as_accepted_fact"] is True


def test_empty_context_blocks(db_path: str) -> None:
    ConstructionStore(db_path)  # migrate only
    result = synthesize_answer(
        question="Anything?", project_key="P1", db_path=db_path, adapter=MockClaudeAdapter()
    )
    assert result.synthesized is False
    assert result.research_packet_summary["degradation_mode"] == "blocked"


def test_result_carries_all_required_output_fields(db_path: str) -> None:
    _seed_tier1(db_path)
    result = synthesize_answer(
        question="q", project_key="P1", db_path=db_path, adapter=MockClaudeAdapter()
    )
    dumped = result.model_dump()
    for field in load_phase_08a_contract("interactive_query_contract")["required_output"]:
        assert field in dumped


def test_no_raw_content(db_path: str) -> None:
    _seed_tier1(db_path)
    result = synthesize_answer(
        question="q", project_key="P1", db_path=db_path, adapter=MockClaudeAdapter()
    )
    blob = result.model_dump_json()
    for forbidden in _FORBIDDEN:
        assert forbidden not in blob


def test_emit_receipt_persists_packet(db_path: str) -> None:
    _seed_tier1(db_path)
    result = synthesize_answer(
        question="q",
        project_key="P1",
        db_path=db_path,
        adapter=MockClaudeAdapter(),
        emit_receipt=True,
    )
    assert result.packet_receipt_id
    assert result.retrieval_receipt_id
    conn = sqlite3.connect(db_path)
    n = conn.execute("SELECT COUNT(*) FROM second_brain_research_packets").fetchone()[0]
    conn.close()
    assert n == 1


def test_build_answer_synthesis_agent_proof_passes() -> None:
    proof = build_answer_synthesis_agent_proof()
    assert proof["proof_passed"] is True
    assert proof["synthesized_query"]["synthesized"] is True
    assert proof["high_impact_query"]["synthesized"] is False
    assert proof["no_raw_content"] is True
