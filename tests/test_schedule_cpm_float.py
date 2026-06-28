"""CPM float foundation tests (Phase 4).

Pure-algorithm unit tests over ``compute_float`` (driven by a real forward+backward pass, or
synthetic CPM rows for the edge cases) plus integration tests that persist float and prove
the forward/backward runs are left unchanged.

Boundaries asserted: float only (``cpm_recalculation_status='forward_backward_float_only'``),
derived solely from Phase 2/3 offsets, no source-field reads/writes, nothing marked
critical, deterministic, negative/fractional float preserved.
"""

from __future__ import annotations

import copy
from datetime import datetime
from pathlib import Path

from hb_assistant.construction.analytics.schedule_cpm_backward_pass import (
    compute_backward_pass,
    resolve_finish_anchor,
)
from hb_assistant.construction.analytics.schedule_cpm_float import (
    BLOCK_MISSING_BACKWARD_PASS,
    FF_MISSING_SUCCESSOR_EARLY,
    FF_NOT_APPLICABLE_TERMINAL,
    FF_UNSUPPORTED_TYPE,
    TF_INCONSISTENT,
    compute_float,
)
from hb_assistant.construction.analytics.schedule_cpm_forward_pass import compute_forward_pass
from hb_assistant.construction.analytics.schedule_cpm_graph import build_graph
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


def _cpm_rows(bp):
    """Adapt backward-pass result objects into the persisted CPM-row dict shape."""
    acts = [
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
    rels = [
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
    return acts, rels


def _float_from(activities, relationships, *, anchor=ANCHOR, finish_offset=None):
    graph = build_graph(activities, relationships)
    fp = compute_forward_pass(
        activities, relationships, graph, anchor=anchor, anchor_source="data_date"
    )
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
        }
        for r in fp.relationships
    ]
    max_ef = max(
        (a["early_finish_offset_days"] for a in fwd_acts if a["early_finish_offset_days"] is not None),
        default=None,
    )
    anchor_input = finish_offset if finish_offset is not None else max_ef
    offset, source, caveat = resolve_finish_anchor(
        source_scheduled_finish=None,
        source_planned_finish=None,
        max_early_finish_offset=anchor_input,
        start_anchor=anchor,
    )
    bp = compute_backward_pass(
        graph, fwd_acts, fwd_rels,
        finish_anchor_offset=offset, finish_anchor_source=source,
        finish_anchor_caveat=caveat, start_anchor=anchor,
    )
    cpm_acts, cpm_rels = _cpm_rows(bp)
    return graph, compute_float(graph, cpm_acts, cpm_rels)


def _tf(result):
    return {a.activity_id: a.computed_total_float for a in result.activities}


def _ff(result):
    return {a.activity_id: a.computed_free_float for a in result.activities}


def _by_id(result):
    return {a.activity_id: a for a in result.activities}


# --------------------------------------------------------------------------- total float


def test_single_activity_total_float() -> None:
    _, result = _float_from([_act("A", duration="5")], [])
    assert result.run_status == "float_only"
    assert result.cpm_recalculation_status == "forward_backward_float_only"
    a = _by_id(result)["A"]
    assert a.computed_total_float == 0.0  # anchor = max EF, zero float
    assert a.computed_total_float_status == "computed"
    assert a.computed_total_float_basis == "late_start_minus_early_start"


def test_fs_chain_total_float_zero() -> None:
    acts = [_act("A"), _act("B"), _act("C")]
    rels = [_rel("A", "B"), _rel("B", "C")]
    _, result = _float_from(acts, rels)
    assert _tf(result) == {"A": 0.0, "B": 0.0, "C": 0.0}


def test_parallel_branches_differing_total_float() -> None:
    acts = [_act("A", duration="5"), _act("B", duration="5"), _act("C", duration="8")]
    rels = [_rel("A", "B"), _rel("A", "C")]
    _, result = _float_from(acts, rels)
    tf = _tf(result)
    assert tf["A"] == 0.0
    assert tf["B"] == 3.0  # shorter branch carries float
    assert tf["C"] == 0.0


def test_negative_total_float_preserved() -> None:
    # Finish anchor (5) earlier than the forward finish (10) → negative float, not clamped.
    acts = [_act("A"), _act("B")]
    rels = [_rel("A", "B")]
    _, result = _float_from(acts, rels, finish_offset=5.0)
    tf = _tf(result)
    assert tf["A"] == -5.0
    assert tf["B"] == -5.0


def test_fractional_total_float_preserved() -> None:
    # Hour durations (8h/day) → fractional offsets; the shorter branch carries 0.5d float.
    acts = [
        _act("A", duration="8", unit="hour"),
        _act("B", duration="8", unit="hour"),
        _act("C", duration="12", unit="hour"),
    ]
    rels = [_rel("A", "B"), _rel("A", "C")]
    _, result = _float_from(acts, rels)
    assert _by_id(result)["B"].computed_total_float == 0.5


def test_inconsistent_start_finish_float_records_caveat() -> None:
    graph = build_graph([_act("A")], [])
    # Synthetic mismatch: start-based TF = 2, finish-based TF = 3.
    rows = [
        {
            "activity_id": "A",
            "topological_index": 0,
            "early_start_offset_days": 0.0,
            "early_finish_offset_days": 5.0,
            "late_start_offset_days": 2.0,
            "late_finish_offset_days": 8.0,
            "duration_value": 5.0,
        }
    ]
    result = compute_float(graph, rows, [])
    a = _by_id(result)["A"]
    assert a.computed_total_float_status == TF_INCONSISTENT
    assert a.computed_total_float == 2.0  # conservative: start-based
    assert a.total_float_notes["finish_based_total_float"] == 3.0


def test_missing_early_late_values_marks_total_float() -> None:
    graph = build_graph([_act("A")], [])
    rows = [{"activity_id": "A", "topological_index": 0}]  # no offsets
    result = compute_float(graph, rows, [])
    a = _by_id(result)["A"]
    assert a.computed_total_float is None
    assert a.computed_total_float_status == "missing_early_late_values"


def test_missing_cpm_results_block() -> None:
    graph = build_graph([_act("A")], [])
    result = compute_float(graph, [], [])
    assert result.run_status == "blocked"
    assert result.block_reason == BLOCK_MISSING_BACKWARD_PASS


# --------------------------------------------------------------------------- free float


def test_terminal_activity_free_float_is_null() -> None:
    _, result = _float_from([_act("A")], [])
    a = _by_id(result)["A"]
    assert a.computed_free_float is None
    assert a.computed_free_float_status == FF_NOT_APPLICABLE_TERMINAL


def test_fs_free_float() -> None:
    # A and X both feed B; B starts at X.EF=5, so A (finishing at 2) has 3 days free float.
    acts = [_act("A", duration="2"), _act("X", duration="5"), _act("B", duration="1")]
    rels = [_rel("A", "B"), _rel("X", "B")]
    _, result = _float_from(acts, rels)
    assert _ff(result)["A"] == 3.0   # B.ES(5) - A.EF(2) - 0
    assert _ff(result)["X"] == 0.0   # B.ES(5) - X.EF(5) - 0


def test_ss_free_float_candidate() -> None:
    _, result = _float_from(
        [_act("A", duration="5"), _act("B", duration="3")], [_rel("A", "B", "SS")]
    )
    rel = next(r for r in result.relationships if r.successor_activity_id == "B")
    assert rel.relationship_type == "SS"
    assert rel.free_float_candidate == 0.0  # B.ES(0) - A.ES(0) - 0


def test_ff_free_float_candidate() -> None:
    _, result = _float_from(
        [_act("A", duration="5"), _act("B", duration="3")], [_rel("A", "B", "FF")]
    )
    rel = next(r for r in result.relationships if r.successor_activity_id == "B")
    assert rel.free_float_candidate == 0.0  # B.EF(5) - A.EF(5) - 0


def test_sf_free_float_candidate() -> None:
    _, result = _float_from(
        [_act("A", duration="5"), _act("B", duration="3")], [_rel("A", "B", "SF")]
    )
    rel = next(r for r in result.relationships if r.successor_activity_id == "B")
    assert rel.free_float_candidate == 3.0  # B.EF(3) - A.ES(0) - 0
    assert _by_id(result)["A"].computed_free_float == 3.0


def test_multiple_successors_use_min_candidate() -> None:
    acts = [_act("A", duration="2"), _act("B", duration="1"), _act("C", duration="1")]
    rels = [_rel("A", "B"), _rel("A", "C")]
    _, result = _float_from(acts, rels)
    a = _by_id(result)["A"]
    # B.ES and C.ES both = A.EF = 2 → candidates both 0 → min 0, controlling sorted (B).
    assert a.computed_free_float == 0.0
    assert a.controlling_free_float_successor_activity_id == "B"


def test_unsupported_relationship_type_marks_only_free_float() -> None:
    # Synthetic rows: A has valid early/late (so total float computes) but an unsupported
    # outgoing relationship, isolating the free-float marking.
    graph = build_graph([_act("A"), _act("B")], [_rel("A", "B", "ZZ")])
    rows = [
        {"activity_id": "A", "topological_index": 0, "early_start_offset_days": 0.0,
         "early_finish_offset_days": 5.0, "late_start_offset_days": 0.0,
         "late_finish_offset_days": 5.0, "duration_value": 5.0},
        {"activity_id": "B", "topological_index": 1, "early_start_offset_days": 5.0,
         "early_finish_offset_days": 8.0, "late_start_offset_days": 5.0,
         "late_finish_offset_days": 8.0, "duration_value": 3.0},
    ]
    rels = [{"predecessor_activity_id": "A", "successor_activity_id": "B",
             "relationship_type": "ZZ", "normalized_lag_days": 0.0,
             "relationship_row_id": 1, "relationship_ref": "A->B (ZZ)"}]
    result = compute_float(graph, rows, rels)
    a = _by_id(result)["A"]
    assert a.computed_free_float is None
    assert a.computed_free_float_status == FF_UNSUPPORTED_TYPE
    # Total float is computed independently of the unsupported relationship.
    assert a.computed_total_float == 0.0
    assert a.computed_total_float_status == "computed"


def test_missing_successor_early_values_marks_free_float() -> None:
    graph = build_graph([_act("A"), _act("B")], [_rel("A", "B")])
    rows = [
        {
            "activity_id": "A", "topological_index": 0,
            "early_start_offset_days": 0.0, "early_finish_offset_days": 5.0,
            "late_start_offset_days": 0.0, "late_finish_offset_days": 5.0,
            "duration_value": 5.0,
        },
        {
            "activity_id": "B", "topological_index": 1,
            "early_start_offset_days": None, "early_finish_offset_days": None,
            "late_start_offset_days": 5.0, "late_finish_offset_days": 8.0,
            "duration_value": 3.0,
        },
    ]
    rels = [{"predecessor_activity_id": "A", "successor_activity_id": "B",
             "relationship_type": "FS", "normalized_lag_days": 0.0,
             "relationship_row_id": 1, "relationship_ref": "A->B (FS)"}]
    result = compute_float(graph, rows, rels)
    a = _by_id(result)["A"]
    assert a.computed_free_float is None
    assert a.computed_free_float_status == FF_MISSING_SUCCESSOR_EARLY


# --------------------------------------------------------------------------- invariants


def test_deterministic_across_repeated_runs() -> None:
    acts = [_act("C"), _act("A"), _act("B")]
    rels = [_rel("B", "C"), _rel("A", "B")]
    _, first = _float_from(acts, rels)
    _, second = _float_from(list(reversed(acts)), list(reversed(rels)))
    assert _tf(first) == _tf(second)
    assert _ff(first) == _ff(second)


def test_compute_float_does_not_mutate_inputs() -> None:
    graph = build_graph([_act("A"), _act("B")], [_rel("A", "B")])
    rows = [
        {"activity_id": "A", "topological_index": 0, "early_start_offset_days": 0.0,
         "early_finish_offset_days": 5.0, "late_start_offset_days": 0.0,
         "late_finish_offset_days": 5.0, "duration_value": 5.0},
        {"activity_id": "B", "topological_index": 1, "early_start_offset_days": 5.0,
         "early_finish_offset_days": 8.0, "late_start_offset_days": 5.0,
         "late_finish_offset_days": 8.0, "duration_value": 3.0},
    ]
    rels = [{"predecessor_activity_id": "A", "successor_activity_id": "B",
             "relationship_type": "FS", "normalized_lag_days": 0.0,
             "relationship_row_id": 1, "relationship_ref": "A->B (FS)"}]
    before = copy.deepcopy(rows)
    compute_float(graph, rows, rels)
    assert rows == before  # early/late inputs are never mutated


def test_float_result_sets_no_critical_marking() -> None:
    _, result = _float_from([_act("A"), _act("B")], [_rel("A", "B")])
    for a in result.activities:
        assert not hasattr(a, "is_critical")
        # zero total float is NOT criticality in this phase
        assert "critical" not in a.computed_total_float_status


# --------------------------------------------------------------------- integration


def _import_minimal(tmp_path: Path):
    db = tmp_path / "fl.db"
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


def test_import_full_chain_then_float_persists(tmp_path: Path) -> None:
    db, svk = _import_minimal(tmp_path)
    cpm = ScheduleCpmGraphService(db_path=str(db))
    cpm.run_graph_diagnostics(svk)
    cpm.run_forward_pass(svk)
    cpm.run_backward_pass(svk)
    summary = cpm.run_float_calculation(svk)

    assert summary["run_status"] == "float_only"
    assert summary["cpm_recalculation_status"] == "forward_backward_float_only"
    assert summary["calculation_type"] == "float"
    assert summary["total_float_computed_count"] == 2
    assert summary["source_run_id"] is not None
    by = {a["activity_id"]: a for a in summary["activities"]}
    assert by["A1000"]["computed_total_float_status"] == "computed"
    assert by["A1010"]["computed_total_float_status"] == "computed"
    # Single chain → both share the same total float; terminal A1010 has NULL free float.
    assert by["A1000"]["computed_total_float"] == by["A1010"]["computed_total_float"]
    assert by["A1010"]["computed_free_float"] is None
    assert by["A1000"]["computed_free_float"] == 0.0  # A1010.ES - A1000.EF - 0

    repo = ScheduleCpmDiagnosticsRepository(db_path=str(db))
    run = repo.get_run(summary["cpm_run_id"])
    assert run["calculation_type"] == "float"
    assert run["cpm_recalculation_status"] == "forward_backward_float_only"
    rows = repo.list_activity_results(summary["cpm_run_id"])
    a1000 = next(r for r in rows if r["activity_id"] == "A1000")
    # Float run rows carry early+late (copied) AND float (computed).
    assert a1000["early_finish_offset_days"] == 5.0
    assert a1000["late_finish_offset_days"] is not None
    assert a1000["computed_total_float"] is not None


def test_float_blocks_without_forward(tmp_path: Path) -> None:
    db, svk = _import_minimal(tmp_path)
    cpm = ScheduleCpmGraphService(db_path=str(db))
    summary = cpm.run_float_calculation(svk)  # nothing run first
    assert summary["run_status"] == "blocked"
    assert summary["block_reason"] == "blocked_by_missing_forward_pass"


def test_float_blocks_without_backward(tmp_path: Path) -> None:
    db, svk = _import_minimal(tmp_path)
    cpm = ScheduleCpmGraphService(db_path=str(db))
    cpm.run_forward_pass(svk)  # forward only, no backward
    summary = cpm.run_float_calculation(svk)
    assert summary["run_status"] == "blocked"
    assert summary["block_reason"] == "blocked_by_missing_backward_pass"


def test_forward_and_backward_unchanged_after_float(tmp_path: Path) -> None:
    db, svk = _import_minimal(tmp_path)
    cpm = ScheduleCpmGraphService(db_path=str(db))
    fwd = cpm.run_forward_pass(svk)
    bwd = cpm.run_backward_pass(svk)
    repo = ScheduleCpmDiagnosticsRepository(db_path=str(db))
    fwd_before = repo.list_activity_results(fwd["cpm_run_id"])
    bwd_before = repo.list_activity_results(bwd["cpm_run_id"])
    flt = cpm.run_float_calculation(svk)
    assert flt["cpm_run_id"] not in {fwd["cpm_run_id"], bwd["cpm_run_id"]}
    assert repo.list_activity_results(fwd["cpm_run_id"]) == fwd_before
    assert repo.list_activity_results(bwd["cpm_run_id"]) == bwd_before
    # Forward/backward rows never got float values written.
    assert all(r["computed_total_float"] is None for r in repo.list_activity_results(fwd["cpm_run_id"]))


def test_float_rerun_is_idempotent(tmp_path: Path) -> None:
    db, svk = _import_minimal(tmp_path)
    cpm = ScheduleCpmGraphService(db_path=str(db))
    cpm.run_forward_pass(svk)
    cpm.run_backward_pass(svk)
    first = cpm.run_float_calculation(svk)
    second = cpm.run_float_calculation(svk)
    assert first["cpm_run_id"] == second["cpm_run_id"]
    repo = ScheduleCpmDiagnosticsRepository(db_path=str(db))
    assert len(repo.list_activity_results(first["cpm_run_id"])) == 2
