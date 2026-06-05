"""Phase 09 Prompt 32 — agent performance and feedback.

Proves the five required paths: (1) normal — per-agent repeated corrections / review burden / weak
coverage are aggregated and an advisory policy recommendation is emitted, with no determination;
(2) missing-policy — fail-closed; (3) stale-schema — fail-closed on a pre-V38 store; (4) unsafe-source —
the assessor emits only counts/bands/recommendation codes (never raw feedback reason), and a correction on
an unmapped target_kind counts to no agent (no crash); (5) no-raw / no-writeback — read-only default
persists nothing and the persisted per-(agent, metric) rows are metadata-only + guard-clean. Plus the
proof. The surface makes no determination; recommendations are advisory.
"""

from __future__ import annotations

import json
import re
import sqlite3
import tempfile
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain import agent_performance_feedback as apf
from hb_assistant.construction.second_brain.agent_performance_feedback import (
    AgentPerformanceFeedbackError,
    _seed_proof_db,
    assess_agent_performance,
    build_agent_performance_feedback,
    build_agent_performance_feedback_proof,
)
from hb_assistant.store.migrator import SQLiteMigrator

_SECRET_OR_URL = re.compile(
    r"BEGIN [A-Z ]*PRIVATE KEY|Bearer [A-Za-z0-9._-]{20,}|https?://|[?&](sig|token)="
)

_TABLE = "second_brain_agent_performance_feedback_runs"

_SEED = {
    "high_corrections_count": 3,
    "high_tier3_share": 0.50,
    "correction_feedback_classes": ["correct", "reject"],
    "target_kind_to_agent": {
        "retrieval": "retrieval_source_broker_agent",
        "memory": "memory_curator_agent",
    },
    "coverage_owner_agent": "retrieval_source_broker_agent",
}


def _rows(db: str) -> int:
    conn = sqlite3.connect(db)
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {_TABLE}").fetchone()[0])
    finally:
        conn.close()


def _seeded_db(td: str) -> str:
    db = str(Path(td) / "apf.sqlite")
    SQLiteMigrator(db_path=db).apply()
    _seed_proof_db(db)
    return db


def test_normal_aggregates_per_agent_signals() -> None:
    receipts = [
        {"agent_id": "retrieval_source_broker_agent", "review_tier": 3, "status": "succeeded"},
        {"agent_id": "retrieval_source_broker_agent", "review_tier": 3, "status": "succeeded"},
        {"agent_id": "retrieval_source_broker_agent", "review_tier": 1, "status": "succeeded"},
    ]
    feedback = [
        {"target_kind": "retrieval", "feedback_class": "correct"},
        {"target_kind": "retrieval", "feedback_class": "reject"},
        {"target_kind": "retrieval", "feedback_class": "accept"},  # not a correction
        {"target_kind": "unmapped_kind", "feedback_class": "correct"},  # unattributable -> no agent
    ]
    coverage = {"empty_families": ["f1"], "deferred_families": ["f2", "f3"]}
    a = assess_agent_performance(
        receipts,
        feedback,
        coverage,
        agents=["retrieval_source_broker_agent", "memory_curator_agent"],
        seed=_SEED,
    )
    broker = next(x for x in a["per_agent"] if x["agent_name"] == "retrieval_source_broker_agent")
    assert broker["repeated_corrections"] == 2
    assert broker["review_burden_run_count"] == 3
    assert broker["review_burden_tier3_count"] == 2
    assert broker["weak_coverage_count"] == 3  # 1 empty + 2 deferred
    assert broker["policy_recommendation"] in (
        "recommend_confidence_tuning",
        "recommend_source_expansion",
        "recommend_review_tier_increase",
    )
    # other agents have zero burden + a no_action recommendation
    mem = next(x for x in a["per_agent"] if x["agent_name"] == "memory_curator_agent")
    assert mem["review_burden_run_count"] == 0 and mem["weak_coverage_count"] == 0


def test_missing_policy_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom() -> dict:
        raise AgentPerformanceFeedbackError("contract unavailable")

    monkeypatch.setattr(apf, "load_agent_performance_feedback_contract", _boom)
    with tempfile.TemporaryDirectory() as td:
        db = _seeded_db(td)
        with pytest.raises(AgentPerformanceFeedbackError):
            build_agent_performance_feedback(db)
        assert _rows(db) == 0


def test_stale_schema_fail_closed() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "empty.db"
        sqlite3.connect(str(db)).close()
        with pytest.raises(AgentPerformanceFeedbackError):
            build_agent_performance_feedback(str(db))


def test_unsafe_source_unmapped_kind_and_hashed() -> None:
    # An unmapped target_kind correction counts to no agent (no crash); no raw reason emitted.
    a = assess_agent_performance(
        [],
        [{"target_kind": "totally_unknown", "feedback_class": "correct"}],
        {"empty_families": [], "deferred_families": []},
        agents=["retrieval_source_broker_agent"],
        seed=_SEED,
    )
    assert a["per_agent"][0]["repeated_corrections"] == 0
    assert "reason" not in json.dumps(a, default=str).replace("policy_recommendation", "")


def test_no_raw_no_writeback_and_run_guard_clean() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _seeded_db(td)
        before = _rows(db)
        result = build_agent_performance_feedback(db)
        assert _rows(db) == before  # read-only default persists nothing
        assert result["read_only"] is True
        assert result["makes_determination"] is False
        blob = json.dumps(result, default=str)
        assert "reason_redacted" not in blob
        assert not _SECRET_OR_URL.search(blob)

        result2 = build_agent_performance_feedback(db, emit_receipt=True)
        assert result2["receipt_emitted"] is True
        conn = sqlite3.connect(db)
        try:
            n = conn.execute(f"SELECT COUNT(*) FROM {_TABLE}").fetchone()[0]
            cols = [str(r[1]) for r in conn.execute(f"PRAGMA table_info({_TABLE})")]
            guard_cols = [
                g
                for g in cols
                if g.endswith(("_persisted", "_performed")) or g.endswith("_bypassed_policy")
            ]
            gsum = conn.execute(
                f"SELECT COALESCE(SUM({'+'.join(guard_cols)}), 0) FROM {_TABLE}"
            ).fetchone()[0]
            assert gsum == 0
        finally:
            conn.close()
        assert n >= 1  # per-(agent, metric) rows persisted


def test_proof_passes_and_is_clean() -> None:
    proof = build_agent_performance_feedback_proof(write_evidence=False)
    assert proof["proof_passed"] is True
    assert proof["corrections_attributed"] is True
    assert proof["review_burden_computed"] is True
    assert proof["weak_coverage_computed"] is True
    assert proof["recommendation_emitted"] is True
    assert proof["makes_determination"] is False
    assert proof["rows_persisted_guard_clean"] is True
    assert proof["read_only_default_no_persist"] is True
    assert proof["no_raw_emitted"] is True
    assert not _SECRET_OR_URL.search(json.dumps(proof, default=str))


def test_proof_writes_guard_clean_artifacts(tmp_path: Path) -> None:
    proof = build_agent_performance_feedback_proof(evidence_dir=str(tmp_path), write_evidence=True)
    pj = tmp_path / "agent-performance-feedback-proof.json"
    pm = tmp_path / "agent-performance-feedback-proof.md"
    assert pj.exists() and pm.exists()
    assert proof["proof_passed"] is True
    assert not _SECRET_OR_URL.search(pj.read_text())
    assert not _SECRET_OR_URL.search(pm.read_text())
