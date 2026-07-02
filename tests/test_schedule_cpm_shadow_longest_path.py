"""Shadow longest-path tests: hand-calculated fixtures primary, parity secondary."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from hb_assistant.construction.analytics.schedule_cpm_backward_pass import (
    compute_backward_pass,
    resolve_finish_anchor,
)
from hb_assistant.construction.analytics.schedule_cpm_float import compute_float
from hb_assistant.construction.analytics.schedule_cpm_forward_pass import compute_forward_pass
from hb_assistant.construction.analytics.schedule_cpm_graph import build_graph
from hb_assistant.construction.analytics.schedule_cpm_longest_path import compute_longest_path
from hb_assistant.construction.analytics.schedule_cpm_shadow_formula_evaluator import (
    CpmShadowFormulaEvaluator,
    PATH_DURATION_DEFINITION,
)

ANCHOR = datetime(2026, 1, 1)
_EVAL = CpmShadowFormulaEvaluator()


def _act(activity_id: str, *, duration: str | None = "5", unit: str = "day", **kw: Any):
    row: dict[str, object] = {"activity_id": activity_id, "duration_unit": unit, **kw}
    if duration is not None:
        row["duration_original"] = duration
    return row


def _rel(pred: str, succ: str, rel_type: str = "FS", lag: str = "0", **kw: Any):
    return {
        "predecessor_activity_id": pred,
        "successor_activity_id": succ,
        "relationship_type": rel_type,
        "lag_value": lag,
        "lag_unit": "day",
        **kw,
    }


def _float_rows(activities, relationships, *, anchor=ANCHOR):
    graph = build_graph(activities, relationships)
    fp = compute_forward_pass(activities, relationships, graph, anchor=anchor, anchor_source="data_date")
    fwd_acts = [
        {
            "activity_id": a.activity_id,
            "activity_name": a.activity_name,
            "topological_index": a.topological_index,
            "duration_value": a.duration_value,
            "early_start_offset_days": a.early_start_offset_days,
            "early_finish_offset_days": a.early_finish_offset_days,
        }
        for a in fp.activities
    ]
    fwd_rels = [
        {
            "predecessor_activity_id": r.predecessor_activity_id,
            "successor_activity_id": r.successor_activity_id,
            "relationship_type": r.relationship_type,
            "normalized_lag_days": r.normalized_lag_days,
            "relationship_row_id": r.relationship_row_id,
            "relationship_ref": r.relationship_ref,
            "candidate_successor_early_start_offset": r.candidate_successor_early_start_offset,
        }
        for r in fp.relationships
    ]
    max_ef = max(
        (a["early_finish_offset_days"] for a in fwd_acts if a["early_finish_offset_days"] is not None),
        default=None,
    )
    offset, source, caveat = resolve_finish_anchor(
        source_scheduled_finish=None,
        source_planned_finish=None,
        max_early_finish_offset=max_ef,
        start_anchor=anchor,
    )
    bp = compute_backward_pass(
        graph,
        fwd_acts,
        fwd_rels,
        finish_anchor_offset=offset,
        finish_anchor_source=source,
        finish_anchor_caveat=caveat,
        start_anchor=anchor,
    )
    cpm_acts = [
        {
            "activity_id": a.activity_id,
            "topological_index": a.topological_index,
            "early_start_offset_days": a.early_start_offset_days,
            "early_finish_offset_days": a.early_finish_offset_days,
            "late_start_offset_days": a.late_start_offset_days,
            "late_finish_offset_days": a.late_finish_offset_days,
            "duration_value": a.duration_value,
        }
        for a in bp.activities
    ]
    cpm_rels = [
        {
            "predecessor_activity_id": r.predecessor_activity_id,
            "successor_activity_id": r.successor_activity_id,
            "relationship_type": r.relationship_type,
            "normalized_lag_days": r.normalized_lag_days,
            "relationship_row_id": r.relationship_row_id,
            "relationship_ref": r.relationship_ref,
        }
        for r in bp.relationships
    ]
    flt = compute_float(graph, cpm_acts, cpm_rels)
    bp_by = {a.activity_id: a for a in bp.activities}
    fp_by = {a.activity_id: a for a in fp.activities}
    flp_by = {a.activity_id: a for a in flt.activities}
    float_acts = []
    for aid in graph.topological_order:
        b = bp_by[aid]
        f = fp_by[aid]
        fa = flp_by[aid]
        float_acts.append(
            {
                "activity_id": aid,
                "topological_index": f.topological_index,
                "early_start_offset_days": b.early_start_offset_days,
                "early_finish_offset_days": b.early_finish_offset_days,
                "duration_value": b.duration_value,
                "computed_total_float": fa.computed_total_float,
            }
        )
    float_rels = [
        {
            "predecessor_activity_id": r.predecessor_activity_id,
            "successor_activity_id": r.successor_activity_id,
            "relationship_type": r.relationship_type,
            "normalized_lag_days": r.normalized_lag_days,
            "candidate_successor_early_start_offset": r.candidate_successor_early_start_offset,
            "relationship_ref": r.relationship_ref,
            "relationship_row_id": r.relationship_row_id,
        }
        for r in fp.relationships
    ]
    return graph, float_acts, float_rels


def _shadow(activities, relationships):
    graph, float_acts, float_rels = _float_rows(activities, relationships)
    return _EVAL.evaluate_longest_path(
        graph_result=graph,
        float_activities=float_acts,
        float_relationships=float_rels,
    )


def _assert_fixture(result, expected: dict[str, Any]) -> None:
    assert result.summary is not None
    assert result.summary.end_activity_id == expected["expected_terminal_activity_id"]
    assert result.activity_ids == expected["expected_activity_ids"]
    rel_ids = [
        a.relationship_from_previous.relationship_ref
        for a in result.activities
        if a.relationship_from_previous is not None
    ]
    assert rel_ids == expected["expected_relationship_ids"]
    assert result.summary.path_duration == expected["expected_path_duration"]
    assert result.summary.path_finish_offset_days == expected["expected_path_finish_offset"]
    assert result.summary.path_duration_basis == PATH_DURATION_DEFINITION


def test_linear_abc_hand_calculated() -> None:
    result = _shadow([_act("A"), _act("B"), _act("C")], [_rel("A", "B"), _rel("B", "C")])
    _assert_fixture(
        result,
        {
            "expected_terminal_activity_id": "C",
            "expected_activity_ids": ["A", "B", "C"],
            "expected_relationship_ids": ["A->B (FS)", "B->C (FS)"],
            "expected_path_duration": 15.0,
            "expected_path_finish_offset": 15.0,
        },
    )


def test_parallel_branches_hand_calculated() -> None:
    result = _shadow(
        [_act("A", duration="5"), _act("B", duration="5"), _act("C", duration="8")],
        [_rel("A", "B"), _rel("A", "C")],
    )
    _assert_fixture(
        result,
        {
            "expected_terminal_activity_id": "C",
            "expected_activity_ids": ["A", "C"],
            "expected_relationship_ids": ["A->C (FS)"],
            "expected_path_duration": 13.0,
            "expected_path_finish_offset": 13.0,
        },
    )


def test_equal_duration_tie_break_hand_calculated() -> None:
    result = _shadow(
        [_act("A"), _act("B"), _act("C")],
        [_rel("A", "B"), _rel("A", "C")],
    )
    _assert_fixture(
        result,
        {
            "expected_terminal_activity_id": "B",
            "expected_activity_ids": ["A", "B"],
            "expected_relationship_ids": ["A->B (FS)"],
            "expected_path_duration": 10.0,
            "expected_path_finish_offset": 10.0,
        },
    )


def test_zero_duration_milestone_hand_calculated() -> None:
    result = _shadow(
        [_act("A"), _act("M", duration="0"), _act("B")],
        [_rel("A", "M"), _rel("M", "B")],
    )
    assert "M" in result.activity_ids
    assert result.summary is not None
    assert result.summary.path_duration == result.summary.path_finish_offset_days


def test_lag_driven_controlling_predecessor_hand_calculated() -> None:
    result = _shadow(
        [_act("A", duration="5"), _act("X", duration="4"), _act("B", duration="5")],
        [_rel("A", "B"), _rel("X", "B", lag="2")],
    )
    _assert_fixture(
        result,
        {
            "expected_terminal_activity_id": "B",
            "expected_activity_ids": ["X", "B"],
            "expected_relationship_ids": ["X->B (FS)"],
            "expected_path_duration": 11.0,
            "expected_path_finish_offset": 11.0,
        },
    )


def test_ss_relationship_hand_calculated() -> None:
    result = _shadow(
        [_act("A", duration="5"), _act("B", duration="10")],
        [_rel("A", "B", "SS")],
    )
    _assert_fixture(
        result,
        {
            "expected_terminal_activity_id": "B",
            "expected_activity_ids": ["A", "B"],
            "expected_relationship_ids": ["A->B (SS)"],
            "expected_path_duration": 10.0,
            "expected_path_finish_offset": 10.0,
        },
    )


def test_empty_graph_not_computable() -> None:
    graph = build_graph([], [])
    result = _EVAL.evaluate_longest_path(graph_result=graph, float_activities=[], float_relationships=[])
    assert result.block_reason == "empty_graph"


def test_shadow_matches_production_parity_secondary() -> None:
    activities = [_act("A"), _act("B"), _act("C")]
    relationships = [_rel("A", "B"), _rel("B", "C")]
    graph, float_acts, float_rels = _float_rows(activities, relationships)
    shadow = _EVAL.evaluate_longest_path(
        graph_result=graph, float_activities=float_acts, float_relationships=float_rels
    )
    production = compute_longest_path(graph, float_acts, float_rels)
    assert shadow.activity_ids == [a.activity_id for a in production.activities]
    assert shadow.summary is not None and production.summary is not None
    assert shadow.summary.path_duration == production.summary.path_duration
