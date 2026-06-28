"""DCMA critical-path integration eligibility tests (Phase 7).

Pure-algorithm unit tests over ``evaluate_dcma_critical_path_eligibility`` with synthetic
CPM run / longest-path / criticality rows.

Boundaries asserted: measurable only when every dependency + path integrity + criticality
consistency holds; conservative not-measurable with explicit reasons otherwise; source
critical/driving-path flags are never inputs; longest-path membership context only.
"""

from __future__ import annotations

from hb_assistant.construction.analytics.schedule_cpm_dcma_integration import (
    CAVEAT_CRITICAL_OUTSIDE_PATH,
    DCMA_BASIS_APP_CPM,
    REASON_DURATION_INCONSISTENT,
    REASON_FINISH_OFFSET_MISMATCH,
    REASON_GRAPH_FATAL,
    REASON_MEMBER_MISSING_TOTAL_FLOAT,
    REASON_MEMBER_UNCLASSIFIED,
    REASON_MISSING_BACKWARD,
    REASON_MISSING_CRITICALITY,
    REASON_MISSING_FLOAT,
    REASON_MISSING_FORWARD,
    REASON_MISSING_LONGEST_PATH,
    REASON_MISSING_PATH_ACTIVITIES,
    REASON_MISSING_RELATIONSHIP,
    REASON_NO_LONGEST_PATH_ROW,
    REASON_NOT_COMPUTED_CRITICAL,
    REASON_SEQUENCE_NOT_CONTIGUOUS,
    evaluate_dcma_critical_path_eligibility,
)

_RUNS = {
    "forward": {"cpm_run_id": "f", "cpm_recalculation_status": "forward_pass_only"},
    "backward": {"cpm_run_id": "b", "cpm_recalculation_status": "backward_pass_only"},
    "float": {"cpm_run_id": "fl", "cpm_recalculation_status": "forward_backward_float_only"},
    "longest_path": {"cpm_run_id": "lp", "cpm_recalculation_status": "longest_path_only"},
    "criticality": {"cpm_run_id": "cr", "cpm_recalculation_status": "criticality_classification_only"},
}


def _path_rows(**over):
    base = {
        "path_id": "p1", "path_type": "longest_path", "path_rank": 1,
        "path_status": "computed", "path_finish_offset_days": 10.0, "path_duration": 10.0,
    }
    base.update(over)
    return [base]


def _path_acts(rel_b="A->B (FS)", seq_b=2):
    return [
        {"path_id": "p1", "path_sequence": 1, "activity_id": "A",
         "early_start_offset_days": 0.0, "early_finish_offset_days": 5.0,
         "relationship_from_previous_ref": None},
        {"path_id": "p1", "path_sequence": seq_b, "activity_id": "B",
         "early_start_offset_days": 5.0, "early_finish_offset_days": 10.0,
         "relationship_from_previous_ref": rel_b},
    ]


def _crit(a_cls="computed_critical", b_cls="computed_critical", b_tf=0.0, extra=None):
    rows = [
        {"activity_id": "A", "computed_total_float": 0.0, "computed_criticality_class": a_cls},
        {"activity_id": "B", "computed_total_float": b_tf, "computed_criticality_class": b_cls},
    ]
    if extra:
        rows.extend(extra)
    return rows


def _eval(**over):
    kw = {
        "graph_has_fatal": False,
        "forward_run": _RUNS["forward"], "backward_run": _RUNS["backward"],
        "float_run": _RUNS["float"], "longest_path_run": _RUNS["longest_path"],
        "criticality_run": _RUNS["criticality"],
        "path_rows": _path_rows(), "path_activity_rows": _path_acts(),
        "criticality_activity_rows": _crit(),
    }
    kw.update(over)
    return evaluate_dcma_critical_path_eligibility(**kw)


# --------------------------------------------------------------------------- measurable


def test_full_chain_all_critical_is_measurable() -> None:
    r = _eval()
    assert r.measurable is True
    assert r.basis == DCMA_BASIS_APP_CPM
    assert r.reason_codes == []
    assert r.dependency_run_ids == {
        "forward": "f", "backward": "b", "float": "fl", "longest_path": "lp", "criticality": "cr",
    }
    assert r.longest_path_critical_activity_count == 2
    assert r.evidence["source_critical_flags_used"] is False


def test_computed_critical_outside_longest_path_is_caveat_not_failure() -> None:
    extra = [{"activity_id": "C", "computed_total_float": 0.0,
              "computed_criticality_class": "computed_critical"}]
    r = _eval(criticality_activity_rows=_crit(extra=extra))
    assert r.measurable is True
    assert CAVEAT_CRITICAL_OUTSIDE_PATH in r.caveats
    assert r.computed_critical_activity_count == 3


# --------------------------------------------------------------------- missing dependency


def test_missing_forward_blocks() -> None:
    r = _eval(forward_run=None)
    assert r.measurable is False
    assert REASON_MISSING_FORWARD in r.reason_codes


def test_missing_backward_blocks() -> None:
    assert REASON_MISSING_BACKWARD in _eval(backward_run=None).reason_codes


def test_missing_float_blocks() -> None:
    assert REASON_MISSING_FLOAT in _eval(float_run=None).reason_codes


def test_missing_longest_path_blocks() -> None:
    assert REASON_MISSING_LONGEST_PATH in _eval(longest_path_run=None).reason_codes


def test_missing_criticality_blocks() -> None:
    assert REASON_MISSING_CRITICALITY in _eval(criticality_run=None).reason_codes


def test_unsuccessful_status_blocks() -> None:
    bad = {"cpm_run_id": "f", "cpm_recalculation_status": "blocked"}
    assert REASON_MISSING_FORWARD in _eval(forward_run=bad).reason_codes


def test_graph_fatal_blocks() -> None:
    assert REASON_GRAPH_FATAL in _eval(graph_has_fatal=True).reason_codes


# --------------------------------------------------------------------- path integrity


def test_no_longest_path_row_blocks() -> None:
    assert REASON_NO_LONGEST_PATH_ROW in _eval(path_rows=[]).reason_codes


def test_missing_path_activities_blocks() -> None:
    assert REASON_MISSING_PATH_ACTIVITIES in _eval(path_activity_rows=[]).reason_codes


def test_non_contiguous_sequence_blocks() -> None:
    assert REASON_SEQUENCE_NOT_CONTIGUOUS in _eval(path_activity_rows=_path_acts(seq_b=3)).reason_codes


def test_missing_relationship_blocks() -> None:
    assert REASON_MISSING_RELATIONSHIP in _eval(path_activity_rows=_path_acts(rel_b=None)).reason_codes


def test_finish_offset_mismatch_blocks() -> None:
    assert REASON_FINISH_OFFSET_MISMATCH in _eval(path_rows=_path_rows(path_finish_offset_days=99.0)).reason_codes


def test_duration_inconsistent_blocks() -> None:
    assert REASON_DURATION_INCONSISTENT in _eval(path_rows=_path_rows(path_duration=99.0)).reason_codes


# --------------------------------------------------------------------- criticality consistency


def test_member_missing_total_float_blocks() -> None:
    r = _eval(criticality_activity_rows=_crit(b_tf=None))
    assert r.measurable is False
    assert REASON_MEMBER_MISSING_TOTAL_FLOAT in r.reason_codes


def test_member_unclassified_blocks() -> None:
    r = _eval(criticality_activity_rows=_crit(b_cls="unclassified"))
    assert REASON_MEMBER_UNCLASSIFIED in r.reason_codes


def test_member_noncritical_blocks_with_not_computed_critical() -> None:
    r = _eval(criticality_activity_rows=_crit(b_cls="computed_noncritical"))
    assert r.measurable is False
    assert REASON_NOT_COMPUTED_CRITICAL in r.reason_codes


def test_near_critical_member_blocks_conservatively() -> None:
    r = _eval(criticality_activity_rows=_crit(b_cls="computed_near_critical"))
    assert r.measurable is False
    assert REASON_NOT_COMPUTED_CRITICAL in r.reason_codes


def test_source_flags_are_ignored() -> None:
    # A row that is computed_noncritical but carries source is_critical / driving-path flags
    # must still block (source flags are NOT inputs).
    rows = _crit(b_cls="computed_noncritical")
    rows[1]["is_critical"] = 1
    rows[1]["source_driving_path_flag"] = 1
    rows[1]["source_critical_flag"] = 1
    r = _eval(criticality_activity_rows=rows)
    assert r.measurable is False
    assert REASON_NOT_COMPUTED_CRITICAL in r.reason_codes


def test_evidence_payload_shape() -> None:
    r = _eval()
    ev = r.evidence
    assert ev["basis"] == DCMA_BASIS_APP_CPM
    assert set(ev["dependency_run_ids"]) == {
        "forward", "backward", "float", "longest_path", "criticality"
    }
    assert ev["reason_codes"] == []
    assert ev["source_export_evidence"] == "separate"
    assert ev["path_id"] == "p1"
