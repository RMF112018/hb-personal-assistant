"""CPM longest path foundation tests (Phase 5).

Pure-algorithm unit tests over ``compute_longest_path`` (driven by a real forward+backward+
float pipeline, or synthetic float-run rows for degraded edge cases) plus integration tests
that persist the path and prove prior runs are unchanged.

Boundaries asserted: longest path only (``cpm_recalculation_status='longest_path_only'``),
NOT a critical-path declaration (no is_critical, no critical marking), conservative
degradation on unsupported/unreconstructable backtrace, deterministic, no source-field reads.
"""

from __future__ import annotations

import copy
from datetime import datetime
from pathlib import Path

from hb_assistant.construction.analytics.schedule_cpm_backward_pass import (
    compute_backward_pass,
    resolve_finish_anchor,
)
from hb_assistant.construction.analytics.schedule_cpm_float import compute_float
from hb_assistant.construction.analytics.schedule_cpm_forward_pass import compute_forward_pass
from hb_assistant.construction.analytics.schedule_cpm_graph import build_graph
from hb_assistant.construction.analytics.schedule_cpm_longest_path import (
    BLOCK_GRAPH_DIAGNOSTIC,
    BLOCK_MISSING_FLOAT_RUN,
    PATH_DEGRADED_PARTIAL,
    PATH_UNSUPPORTED_TYPE,
    RUN_LONGEST_PATH_ONLY,
    compute_longest_path,
)
from hb_assistant.construction.analytics.schedule_cpm_service import ScheduleCpmGraphService
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.schedule_cpm_repository import ScheduleCpmDiagnosticsRepository
from tests.schedule_project_test_helpers import seed_procore_ep_project

XER_FIXTURE = Path(__file__).parent / "fixtures" / "schedules" / "xer" / "minimal.xer"
ANCHOR = datetime(2026, 1, 1)


def _act(activity_id: str, *, duration: str | None = "5", unit: str = "day", **kw):
    row: dict[str, object] = {"activity_id": activity_id, "duration_unit": unit, **kw}
    if duration is not None:
        row["duration_original"] = duration
    return row


def _rel(pred: str, succ: str, rel_type: str = "FS", lag: str = "0", **kw):
    return {
        "predecessor_activity_id": pred,
        "successor_activity_id": succ,
        "relationship_type": rel_type,
        "lag_value": lag,
        "lag_unit": "day",
        **kw,
    }


def _pipeline(activities, relationships, *, anchor=ANCHOR):
    """Run forward→backward→float and assemble float-run-shaped rows for the longest path."""
    graph = build_graph(activities, relationships)
    fp = compute_forward_pass(activities, relationships, graph, anchor=anchor, anchor_source="data_date")
    fwd_acts = [
        {
            "activity_id": a.activity_id, "activity_name": a.activity_name,
            "topological_index": a.topological_index, "duration_value": a.duration_value,
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
        }
        for r in fp.relationships
    ]
    max_ef = max(
        (a["early_finish_offset_days"] for a in fwd_acts if a["early_finish_offset_days"] is not None),
        default=None,
    )
    offset, source, caveat = resolve_finish_anchor(
        source_scheduled_finish=None, source_planned_finish=None,
        max_early_finish_offset=max_ef, start_anchor=anchor,
    )
    bp = compute_backward_pass(
        graph, fwd_acts, fwd_rels,
        finish_anchor_offset=offset, finish_anchor_source=source,
        finish_anchor_caveat=caveat, start_anchor=anchor,
    )
    cpm_acts = [
        {
            "activity_id": a.activity_id, "topological_index": a.topological_index,
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
    flp = compute_float(graph, cpm_acts, cpm_rels)

    bp_by = {a.activity_id: a for a in bp.activities}
    fp_by = {a.activity_id: a for a in fp.activities}
    flp_by = {a.activity_id: a for a in flp.activities}
    float_activities = []
    for aid in graph.topological_order:
        b = bp_by[aid]
        f = fp_by[aid]
        fa = flp_by[aid]
        float_activities.append({
            "activity_id": aid, "activity_name": f.activity_name,
            "topological_index": f.topological_index,
            "early_start_offset_days": b.early_start_offset_days,
            "early_finish_offset_days": b.early_finish_offset_days,
            "late_start_offset_days": b.late_start_offset_days,
            "late_finish_offset_days": b.late_finish_offset_days,
            "computed_total_float": fa.computed_total_float,
            "computed_free_float": fa.computed_free_float,
            "duration_value": b.duration_value,
            "computed_early_start": f.computed_early_start,
            "computed_early_finish": f.computed_early_finish,
            "computed_late_start": b.computed_late_start,
            "computed_late_finish": b.computed_late_finish,
        })
    float_relationships = [
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
    return graph, compute_longest_path(graph, float_activities, float_relationships)


def _ids(result):
    return [a.activity_id for a in result.activities]


# --------------------------------------------------------------------------- unit


def test_single_activity_path() -> None:
    _, result = _pipeline([_act("A")], [])
    assert result.run_status == RUN_LONGEST_PATH_ONLY
    assert result.cpm_recalculation_status == "longest_path_only"
    assert _ids(result) == ["A"]
    assert result.summary.start_activity_id == result.summary.end_activity_id == "A"
    assert result.summary.relationship_count == 0


def test_fs_chain_path() -> None:
    _, result = _pipeline([_act("A"), _act("B"), _act("C")], [_rel("A", "B"), _rel("B", "C")])
    assert _ids(result) == ["A", "B", "C"]
    assert result.summary.path_status == "computed"
    assert result.summary.relationship_count == 2
    # path duration == finish - start of the selected activities
    assert result.summary.path_duration == (
        result.summary.path_finish_offset_days - result.summary.path_start_offset_days
    )


def test_parallel_branches_choose_max_finish() -> None:
    _, result = _pipeline(
        [_act("A", duration="5"), _act("B", duration="5"), _act("C", duration="8")],
        [_rel("A", "B"), _rel("A", "C")],
    )
    assert _ids(result) == ["A", "C"]  # C branch finishes latest
    assert result.summary.end_activity_id == "C"


def test_tie_on_finish_uses_deterministic_tiebreak() -> None:
    # B and C both finish at 10; tie -> larger ES (both 5) -> lower topo index -> B.
    _, result = _pipeline(
        [_act("A"), _act("B"), _act("C")], [_rel("A", "B"), _rel("A", "C")]
    )
    assert result.summary.end_activity_id == "B"
    assert "endpoint_tie_break" in result.summary.notes


def test_positive_lag_changes_controlling_predecessor() -> None:
    # B is driven by X (FS lag 2 -> 6) over A (FS lag 0 -> 5); controlling pred is X.
    _, result = _pipeline(
        [_act("A", duration="5"), _act("X", duration="4"), _act("B", duration="5")],
        [_rel("A", "B"), _rel("X", "B", lag="2")],
    )
    assert _ids(result) == ["X", "B"]


def test_negative_lag_excludes_predecessor() -> None:
    # X's negative lag makes its candidate (2) not control B.ES (5); A controls.
    _, result = _pipeline(
        [_act("A", duration="5"), _act("X", duration="5"), _act("B", duration="5")],
        [_rel("A", "B"), _rel("X", "B", lag="-3")],
    )
    assert _ids(result) == ["A", "B"]


def test_ss_backtrace() -> None:
    _, result = _pipeline(
        [_act("A", duration="5"), _act("B", duration="10")], [_rel("A", "B", "SS")]
    )
    assert _ids(result) == ["A", "B"]  # B finishes latest; SS controls B.ES


def test_ff_backtrace() -> None:
    _, result = _pipeline(
        [_act("A", duration="12"), _act("B", duration="3")], [_rel("A", "B", "FF")]
    )
    assert _ids(result) == ["A", "B"]  # FF candidate (9) controls B.ES


def test_sf_backtrace() -> None:
    _, result = _pipeline(
        [_act("A", duration="5"), _act("B", duration="3")], [_rel("A", "B", "SF", lag="5")]
    )
    assert _ids(result) == ["A", "B"]  # SF candidate (2) controls B.ES


def test_unsupported_relationship_type_degrades() -> None:
    # Synthetic: end E has ES=5 (not anchor) but its only incoming rel is unsupported type.
    graph = build_graph([_act("A"), _act("E")], [_rel("A", "E", "ZZ")])
    fa = [
        {"activity_id": "A", "topological_index": 0, "early_start_offset_days": 0.0,
         "early_finish_offset_days": 5.0, "late_start_offset_days": 0.0,
         "late_finish_offset_days": 5.0, "duration_value": 5.0},
        {"activity_id": "E", "topological_index": 1, "early_start_offset_days": 5.0,
         "early_finish_offset_days": 8.0, "late_start_offset_days": 5.0,
         "late_finish_offset_days": 8.0, "duration_value": 3.0},
    ]
    fr = [{"predecessor_activity_id": "A", "successor_activity_id": "E",
           "relationship_type": "ZZ", "normalized_lag_days": 0.0,
           "candidate_successor_early_start_offset": None,
           "relationship_ref": "A->E (ZZ)", "relationship_row_id": 1}]
    result = compute_longest_path(graph, fa, fr)
    assert result.summary.path_status == PATH_UNSUPPORTED_TYPE
    assert _ids(result) == ["E"]  # partial path, stopped conservatively


def test_missing_candidate_relationship_degrades() -> None:
    # Supported FS but its candidate (3) doesn't match E.ES (5) -> degraded, stop.
    graph = build_graph([_act("A"), _act("E")], [_rel("A", "E")])
    fa = [
        {"activity_id": "A", "topological_index": 0, "early_start_offset_days": 0.0,
         "early_finish_offset_days": 3.0, "late_start_offset_days": 0.0,
         "late_finish_offset_days": 3.0, "duration_value": 3.0},
        {"activity_id": "E", "topological_index": 1, "early_start_offset_days": 5.0,
         "early_finish_offset_days": 8.0, "late_start_offset_days": 5.0,
         "late_finish_offset_days": 8.0, "duration_value": 3.0},
    ]
    fr = [{"predecessor_activity_id": "A", "successor_activity_id": "E",
           "relationship_type": "FS", "normalized_lag_days": 0.0,
           "candidate_successor_early_start_offset": 3.0,
           "relationship_ref": "A->E (FS)", "relationship_row_id": 1}]
    result = compute_longest_path(graph, fa, fr)
    assert result.summary.path_status == PATH_DEGRADED_PARTIAL


def test_missing_float_blocks() -> None:
    graph = build_graph([_act("A")], [])
    result = compute_longest_path(graph, [], [])
    assert result.run_status == "blocked"
    assert result.block_reason == BLOCK_MISSING_FLOAT_RUN


def test_cycle_blocks() -> None:
    graph = build_graph(
        [_act("A"), _act("B"), _act("C")],
        [_rel("A", "B"), _rel("B", "C"), _rel("C", "A")],
    )
    fa = [{"activity_id": a, "topological_index": 0, "early_start_offset_days": 0.0,
           "early_finish_offset_days": 5.0, "late_start_offset_days": 0.0,
           "late_finish_offset_days": 5.0, "duration_value": 5.0} for a in ("A", "B", "C")]
    result = compute_longest_path(graph, fa, [])
    assert result.run_status == "blocked"
    assert result.block_reason == BLOCK_GRAPH_DIAGNOSTIC


def test_deterministic_across_repeated_runs() -> None:
    acts = [_act("C"), _act("A"), _act("B")]
    rels = [_rel("B", "C"), _rel("A", "B")]
    _, first = _pipeline(acts, rels)
    _, second = _pipeline(list(reversed(acts)), list(reversed(rels)))
    assert _ids(first) == _ids(second) == ["A", "B", "C"]


def test_compute_does_not_mutate_inputs() -> None:
    graph = build_graph([_act("A"), _act("B")], [_rel("A", "B")])
    fa = [
        {"activity_id": "A", "topological_index": 0, "early_start_offset_days": 0.0,
         "early_finish_offset_days": 5.0, "late_start_offset_days": 0.0,
         "late_finish_offset_days": 5.0, "duration_value": 5.0},
        {"activity_id": "B", "topological_index": 1, "early_start_offset_days": 5.0,
         "early_finish_offset_days": 8.0, "late_start_offset_days": 5.0,
         "late_finish_offset_days": 8.0, "duration_value": 3.0},
    ]
    fr = [{"predecessor_activity_id": "A", "successor_activity_id": "B",
           "relationship_type": "FS", "normalized_lag_days": 0.0,
           "candidate_successor_early_start_offset": 5.0,
           "relationship_ref": "A->B (FS)", "relationship_row_id": 1}]
    before_a = copy.deepcopy(fa)
    before_r = copy.deepcopy(fr)
    compute_longest_path(graph, fa, fr)
    assert fa == before_a and fr == before_r


def test_sets_no_critical_marking() -> None:
    _, result = _pipeline([_act("A"), _act("B")], [_rel("A", "B")])
    for a in result.activities:
        assert not hasattr(a, "is_critical")
        assert "critical" not in a.selection_basis
    assert "critical" not in result.summary.path_status


# --------------------------------------------------------------------- integration


def _import_minimal(tmp_path: Path):
    db = tmp_path / "lp.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(
        db, project_key="tropical", display_name="Tropical Wind", project_number="TWNU18"
    )
    from hb_assistant.construction.analytics.schedule_import_service import (
        ScheduleImportService,
    )

    svc = ScheduleImportService(db_path=str(db))
    preview = svc.preview_bytes(
        filename=XER_FIXTURE.name, data=XER_FIXTURE.read_bytes(), project_key="tropical"
    )
    commit = svc.commit(import_id=preview["import_id"], project_key="tropical", confirm=True)
    return db, commit["schedule_version_key"]


def test_full_chain_then_longest_path_persists(tmp_path: Path) -> None:
    db, svk = _import_minimal(tmp_path)
    cpm = ScheduleCpmGraphService(db_path=str(db))
    cpm.run_graph_diagnostics(svk)
    cpm.run_forward_pass(svk)
    cpm.run_backward_pass(svk)
    cpm.run_float_calculation(svk)
    summary = cpm.run_longest_path(svk)

    assert summary["run_status"] == "longest_path_only"
    assert summary["cpm_recalculation_status"] == "longest_path_only"
    assert summary["calculation_type"] == "longest_path"
    assert summary["source_run_id"] is not None
    assert [a["activity_id"] for a in summary["activities"]] == ["A1000", "A1010"]
    assert summary["path"]["end_activity_id"] == "A1010"
    assert summary["path"]["activity_count"] == 2

    repo = ScheduleCpmDiagnosticsRepository(db_path=str(db))
    run = repo.get_run(summary["cpm_run_id"])
    assert run["calculation_type"] == "longest_path"
    assert run["longest_path_end_activity_id"] == "A1010"
    paths = repo.list_paths(summary["cpm_run_id"])
    assert len(paths) == 1
    assert paths[0]["path_type"] == "longest_path"
    pacts = repo.list_path_activities(paths[0]["path_id"])
    assert [p["activity_id"] for p in pacts] == ["A1000", "A1010"]
    assert pacts[0]["path_sequence"] == 1
    assert pacts[1]["relationship_from_previous_ref"] is not None


def test_longest_path_blocks_without_float(tmp_path: Path) -> None:
    db, svk = _import_minimal(tmp_path)
    cpm = ScheduleCpmGraphService(db_path=str(db))
    cpm.run_forward_pass(svk)  # no float run
    summary = cpm.run_longest_path(svk)
    assert summary["run_status"] == "blocked"
    assert summary["block_reason"] == "blocked_by_missing_float_run"


def test_longest_path_blocks_without_forward(tmp_path: Path) -> None:
    db, svk = _import_minimal(tmp_path)
    cpm = ScheduleCpmGraphService(db_path=str(db))
    summary = cpm.run_longest_path(svk)  # nothing run
    assert summary["run_status"] == "blocked"
    assert summary["block_reason"] == "blocked_by_missing_forward_pass"


def test_prior_runs_unchanged_after_longest_path(tmp_path: Path) -> None:
    db, svk = _import_minimal(tmp_path)
    cpm = ScheduleCpmGraphService(db_path=str(db))
    fwd = cpm.run_forward_pass(svk)
    bwd = cpm.run_backward_pass(svk)
    flt = cpm.run_float_calculation(svk)
    repo = ScheduleCpmDiagnosticsRepository(db_path=str(db))
    before = {
        r: repo.list_activity_results(r)
        for r in (fwd["cpm_run_id"], bwd["cpm_run_id"], flt["cpm_run_id"])
    }
    lp = cpm.run_longest_path(svk)
    assert lp["cpm_run_id"] not in before
    for r, rows in before.items():
        assert repo.list_activity_results(r) == rows


def test_longest_path_rerun_idempotent(tmp_path: Path) -> None:
    db, svk = _import_minimal(tmp_path)
    cpm = ScheduleCpmGraphService(db_path=str(db))
    cpm.run_forward_pass(svk)
    cpm.run_backward_pass(svk)
    cpm.run_float_calculation(svk)
    first = cpm.run_longest_path(svk)
    second = cpm.run_longest_path(svk)
    assert first["cpm_run_id"] == second["cpm_run_id"]
    repo = ScheduleCpmDiagnosticsRepository(db_path=str(db))
    assert len(repo.list_paths(first["cpm_run_id"])) == 1
