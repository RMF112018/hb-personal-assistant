"""Phase 10 V51 — usefulness-gate ranking contradiction tests.

Verifies the gate fails a would-be success when the advisory ranking layer overclaims (model-scored
item missing source refs, enriched-without-receipt, fallback-but-claims-success, coverage < 1.0),
and that a None ``ranking_context`` leaves the gate behaviour unchanged.
"""

from __future__ import annotations

from pathlib import Path

from hb_assistant.construction.second_brain.local_ai.daily_brief_assembly import (
    ranking_stage_context,
    run_candidate_ranking_and_assembly,
)
from hb_assistant.construction.second_brain.local_ai.usefulness_gate import evaluate_usefulness_gate
from tests._phase_10_ranking_seed import BRIEF_DATE, NOW, accept_task, seed_ranking_store


def _gate(db: str, ranking_context):
    from hb_assistant.construction.store import ConstructionStore

    return evaluate_usefulness_gate(
        store=ConstructionStore(db_path=db),
        brief_date=BRIEF_DATE,
        synthesis_present=True,
        synthesis_degraded=False,
        ranking_context=ranking_context,
    )


def test_clean_ranking_context_has_no_contradictions(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    result = run_candidate_ranking_and_assembly(
        store=seed_ranking_store(db), brief_date=BRIEF_DATE, now_utc=NOW, use_model=False
    )
    ctx = ranking_stage_context(result)
    assert ctx["contradictions"] == []


def test_coverage_below_one_is_flagged(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    store = seed_ranking_store(db)
    accept_task(store, "noref", refs=False, project_key="PRJ-Z")
    result = run_candidate_ranking_and_assembly(
        store=store, brief_date=BRIEF_DATE, now_utc=NOW, use_model=False
    )
    ctx = ranking_stage_context(result)
    assert "ranking_source_ref_coverage_below_100" in ctx["contradictions"]
    gate = _gate(db, ctx)
    assert "ranking_source_ref_coverage_below_100" in gate.failed_reasons


def test_model_enriched_without_receipt_is_flagged() -> None:
    # Hand-built result claiming enrichment with no receipt metadata and a model-scored item.
    fake = {
        "ranking": {
            "model_status": "model_enriched",
            "deterministic_fallback_used": False,
            "source_ref_coverage": 1.0,
            "guard_clean": True,
            "ranked": [
                {
                    "candidate_id": "x",
                    "subject_type": "accepted_task",
                    "source_ref_count": 1,
                    "lifecycle_state": "accepted",
                    "model_advisory_score": 90.0,
                },
            ],
        },
        "receipt": {"output_hash": None, "would_write_receipt": None, "model_receipt_id": None},
    }
    ctx = ranking_stage_context(fake)
    assert "model_enriched_without_receipt" in ctx["contradictions"]


def test_model_scored_item_missing_source_refs_is_flagged() -> None:
    fake = {
        "ranking": {
            "model_status": "model_enriched",
            "deterministic_fallback_used": False,
            "source_ref_coverage": 1.0,
            "guard_clean": True,
            "ranked": [
                {
                    "candidate_id": "x",
                    "subject_type": "accepted_task",
                    "source_ref_count": 0,
                    "lifecycle_state": "accepted",
                    "model_advisory_score": 90.0,
                },
            ],
        },
        "receipt": {"output_hash": "abc"},
    }
    ctx = ranking_stage_context(fake)
    assert "model_ranked_item_missing_source_refs" in ctx["contradictions"]


def test_none_ranking_context_unaffected(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    seed_ranking_store(db)
    gate = _gate(db, None)
    # No ranking metrics are added when ranking_context is None.
    assert "ranking_contradictions" not in gate.metrics
