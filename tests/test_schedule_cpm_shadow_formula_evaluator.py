"""Hand-calculated shadow CPM formula evaluator tests."""

from __future__ import annotations

from hb_assistant.construction.analytics.schedule_cpm_shadow_formula_evaluator import (
    CpmShadowFormulaEvaluator,
    FORMULA_EXPRESSIONS,
)

_EVAL = CpmShadowFormulaEvaluator()


def _rel(
    pred: str,
    succ: str,
    *,
    rel_type: str = "FS",
    lag: float = 0.0,
    rel_id: str | None = None,
) -> dict:
    return {
        "predecessor_activity_id": pred,
        "successor_activity_id": succ,
        "relationship_type": rel_type,
        "normalized_lag_days": lag,
        "relationship_row_id": rel_id or f"{pred}->{succ}",
    }


def _act(activity_id: str, *, duration: float, milestone: bool = False) -> dict:
    return {
        "activity_id": activity_id,
        "duration_value": 0.0 if milestone else duration,
        "is_milestone": milestone,
    }


def _chain(
    activities: dict[str, dict],
    relationships: list[dict],
    *,
    finish_lf: float | None = None,
) -> tuple[dict, list]:
    topo = list(activities.keys())
    return _EVAL.run_full_shadow_chain(
        topo_order=topo,
        activities=activities,
        relationships=relationships,
        finish_anchor_lf=finish_lf,
    )


def test_forward_fs_no_lag() -> None:
    value, expr = _EVAL.evaluate_forward_candidate(
        rel_type="FS", lag_days=0, pred_es=0, pred_ef=5, succ_duration=3
    )
    assert value == 5.0
    assert expr == FORMULA_EXPRESSIONS["forward_FS"]


def test_forward_ss_with_lag() -> None:
    value, _ = _EVAL.evaluate_forward_candidate(
        rel_type="SS", lag_days=2, pred_es=4, pred_ef=9, succ_duration=5
    )
    assert value == 6.0


def test_forward_ff_with_lag() -> None:
    value, _ = _EVAL.evaluate_forward_candidate(
        rel_type="FF", lag_days=1, pred_es=0, pred_ef=8, succ_duration=4
    )
    assert value == 5.0


def test_forward_sf_with_lag() -> None:
    value, _ = _EVAL.evaluate_forward_candidate(
        rel_type="SF", lag_days=2, pred_es=3, pred_ef=8, succ_duration=5
    )
    assert value == 0.0


def test_milestone_zero_duration_chain() -> None:
    acts, _ = _chain(
        {"M": _act("M", duration=0, milestone=True), "B": _act("B", duration=4)},
        [_rel("M", "B")],
        finish_lf=4.0,
    )
    assert acts["M"].early_start == 0.0
    assert acts["M"].early_finish == 0.0
    assert acts["B"].early_start == 0.0
    assert acts["B"].early_finish == 4.0


def test_parallel_predecessors_select_max() -> None:
    acts, _ = _chain(
        {
            "A": _act("A", duration=5),
            "B": _act("B", duration=3),
            "C": _act("C", duration=2),
        },
        [
            _rel("A", "C", rel_id="r1"),
            _rel("B", "C", rel_id="r2"),
        ],
        finish_lf=7.0,
    )
    assert acts["C"].early_start == 5.0
    assert acts["C"].early_finish == 7.0
    fwd = acts["C"].forward_evaluation
    assert fwd is not None
    assert fwd.selected_candidate_id == "r1"
    assert len(fwd.rejected_candidates) == 1
    assert fwd.rejected_candidates[0]["relationship_id"] == "r2"


def test_tie_break_by_relationship_id() -> None:
    acts, _ = _chain(
        {"A": _act("A", duration=5), "B": _act("B", duration=5), "C": _act("C", duration=1)},
        [
            _rel("A", "C", rel_id="z-last"),
            _rel("B", "C", rel_id="a-first"),
        ],
        finish_lf=6.0,
    )
    assert acts["C"].early_start == 5.0
    fwd = acts["C"].forward_evaluation
    assert fwd is not None
    assert fwd.tie_break_applied is True
    assert fwd.selected_candidate_id == "a-first"


def test_backward_terminal_uses_finish_anchor() -> None:
    acts, _ = _chain({"A": _act("A", duration=10)}, [], finish_lf=25.0)
    assert acts["A"].late_finish == 25.0
    assert acts["A"].late_start == 15.0
    assert acts["A"].total_float == 15.0


def test_total_float_ls_minus_es() -> None:
    assert _EVAL.evaluate_total_float(2, 7, 5, 10) == 5.0


def test_free_float_fs_formula() -> None:
    value, expr = _EVAL.evaluate_free_float_candidate(
        rel_type="FS",
        lag_days=1,
        pred_es=0,
        pred_ef=5,
        succ_es=8,
        succ_ef=10,
    )
    assert value == 2.0
    assert expr == FORMULA_EXPRESSIONS["free_float_FS"]


def test_criticality_thresholds() -> None:
    assert _EVAL.evaluate_criticality(0) == "computed_critical"
    assert _EVAL.evaluate_criticality(5) == "computed_near_critical"
    assert _EVAL.evaluate_criticality(15) == "computed_noncritical"
