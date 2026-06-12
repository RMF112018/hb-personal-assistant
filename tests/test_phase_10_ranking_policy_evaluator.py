"""Phase 10 V52 — ranking-policy evaluator tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from hb_assistant.construction.second_brain.local_ai.daily_brief_effectiveness_packets import (
    build_effectiveness_packets,
)
from hb_assistant.construction.second_brain.local_ai.ranking_policy_evaluator import (
    EVAL_MODES,
    evaluate_ranking_policy,
)
from tests._phase_10_effectiveness_seed import (
    EVAL_NOW,
    WINDOW_END,
    WINDOW_START,
    seed_effectiveness_store,
)


def _packet(tmp_path: Path):
    store = seed_effectiveness_store(str(tmp_path / "t.sqlite"))
    return build_effectiveness_packets(
        store, window_start=WINDOW_START, window_end=WINDOW_END, now_utc=EVAL_NOW
    )


def test_deterministic_only_evaluates_without_model_telemetry(tmp_path: Path) -> None:
    pkt = _packet(tmp_path)
    # The seed runs --no-client (deterministic): there are no model receipts.
    assert not pkt["receipts"]
    ev = evaluate_ranking_policy(pkt, eval_mode="deterministic-replay")
    assert ev["metrics"]["rank_outcome_score"] is not None
    assert ev["metrics"]["model_degradation_rate"] == 1.0  # deterministic fallback dominated
    assert ev["observational_only"] is True


def test_all_modes_supported(tmp_path: Path) -> None:
    pkt = _packet(tmp_path)
    for mode in EVAL_MODES:
        ev = evaluate_ranking_policy(pkt, eval_mode=mode)
        assert ev["eval_mode"] == mode
        assert len(ev["eval_items"]) == 5
    with pytest.raises(ValueError):
        evaluate_ranking_policy(pkt, eval_mode="bogus")


def test_metrics_carry_sample_size_caveat(tmp_path: Path) -> None:
    pkt = _packet(tmp_path)
    ev = evaluate_ranking_policy(pkt, eval_mode="observed")
    # 5 outcomes == MIN_OUTCOME_SAMPLE → sufficient; the confidence note is honest either way.
    assert ev["sample_sufficient"] is True
    assert "observational" in ev["confidence_note"]


def test_deterministic_vs_model_delta_present(tmp_path: Path) -> None:
    pkt = _packet(tmp_path)
    ev = evaluate_ranking_policy(pkt, eval_mode="ablation")
    delta = ev["metrics"]["deterministic_vs_model_delta"]
    assert delta["causal"] is False
    assert "deterministic_baseline_rank_outcome" in ev["metrics"]
    assert "model_assisted_rank_outcome" in ev["metrics"]


def test_eval_items_are_raw_free_and_normalized(tmp_path: Path) -> None:
    pkt = _packet(tmp_path)
    ev = evaluate_ranking_policy(pkt, eval_mode="observed")
    for item in ev["eval_items"]:
        assert item["candidate_family"]  # normalized, never empty
        assert item["source_family"]
        assert item["project_key"]
        assert item["eval_notes_json"].startswith("{")


def test_same_candidate_two_runs_preserved(tmp_path: Path) -> None:
    import sqlite3

    from hb_assistant.construction.second_brain.local_ai import (
        run_daily_brief_effectiveness_evaluation,
    )
    from tests._phase_10_effectiveness_seed import seed_two_brief_runs

    db = str(tmp_path / "t.sqlite")
    store = seed_two_brief_runs(db)
    pkt = build_effectiveness_packets(
        store, window_start=WINDOW_START, window_end=WINDOW_END, now_utc=EVAL_NOW
    )
    ev = evaluate_ranking_policy(pkt, eval_mode="observed")
    shared = [
        e
        for e in ev["eval_items"]
        if e["daily_brief_action_candidate_id"] == "task_candidate:c_shared"
    ]
    # The same candidate surfaced in two ranking runs → two distinct eval-item facts.
    assert len(shared) == 2
    assert len({e["ranking_run_id"] for e in shared}) == 2
    # Apply preserves both rows under the composite PK.
    res = run_daily_brief_effectiveness_evaluation(
        store, window_start=WINDOW_START, window_end=WINDOW_END, now_utc=EVAL_NOW,
        eval_mode="observed", dry_run=False, max_persist=500,
    )
    assert res["applied"] is True
    conn = sqlite3.connect(db)
    n = conn.execute(
        "SELECT COUNT(*) FROM ranking_policy_eval_items WHERE daily_brief_action_candidate_id = ?",
        ("task_candidate:c_shared",),
    ).fetchone()[0]
    assert n == 2
