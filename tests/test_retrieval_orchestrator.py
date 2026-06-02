"""Phase 08A Prompt 07 — Retrieval Orchestrator (A01) gating.

Proves: a research packet is built for daily-brief + complex-query paths; those paths
require a packet; insufficient context blocks synthesis (degrade, not overstate); and
the synthetic proof passes.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain.research import (
    RetrievalOrchestrator,
    build_retrieval_orchestrator_proof,
)
from hb_assistant.construction.store import ConstructionStore


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "orchestrator.sqlite")


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
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO long_term_memory_items "
        "(memory_id, memory_type, statement_redacted, project_key, confidence_class, review_status) "
        "VALUES ('mem1','fact','kickoff confirmed','P1','high','accepted')"
    )
    conn.commit()
    conn.close()


def test_packet_built_for_daily_brief_and_complex_query(db_path: str) -> None:
    _seed(db_path)
    orch = RetrievalOrchestrator(db_path=db_path)
    for packet_type in ("daily_brief", "interactive_query"):
        result = orch.orchestrate(packet_type=packet_type, project_key="P1", emit_receipt=False)
        assert result.packet.packet_id
        assert result.request_requires_packet is True
        assert result.packet.source_ref_count >= 1


def test_insufficient_context_blocks_synthesis(db_path: str) -> None:
    ConstructionStore(db_path)  # migrate only, no seed
    result = RetrievalOrchestrator(db_path=db_path).orchestrate(
        packet_type="interactive_query", project_key="P1", emit_receipt=False
    )
    assert result.packet.degradation_mode == "blocked"
    assert result.research_packet_ok is False
    assert result.synthesis_allowed is False
    assert any(w.startswith("synthesis_blocked") for w in result.warnings)


def test_emit_receipt_persists_packet(db_path: str) -> None:
    _seed(db_path)
    result = RetrievalOrchestrator(db_path=db_path).orchestrate(
        packet_type="interactive_query", project_key="P1", emit_receipt=True
    )
    assert result.packet_receipt_id
    assert result.retrieval_receipt_id
    conn = sqlite3.connect(db_path)
    n = conn.execute("SELECT COUNT(*) FROM second_brain_research_packets").fetchone()[0]
    conn.close()
    assert n == 1


def test_build_retrieval_orchestrator_proof_passes() -> None:
    proof = build_retrieval_orchestrator_proof()
    assert proof["proof_passed"] is True
    assert proof["complex_paths_require_packet"] is True
    assert proof["insufficient_context_degrades_not_overstates"] is True
