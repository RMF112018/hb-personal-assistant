"""CPM backward pass foundation tests (Phase 3).

Pure-algorithm unit tests over ``compute_backward_pass`` / ``resolve_finish_anchor`` (driven
by a real forward pass, asserting on the authoritative day-offsets) plus integration tests
that persist late dates and prove the forward-pass run is left unchanged.

Boundaries asserted: backward pass only (``cpm_recalculation_status='backward_pass_only'``),
no source-field writes, deterministic output, clean blocking on fatal graph diagnostics /
missing forward pass / missing finish anchor.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from hb_assistant.construction.analytics.schedule_cpm_backward_pass import (
    ANCHOR_SOURCE_MAX_EARLY_FINISH,
    ANCHOR_SOURCE_SCHEDULED_FINISH,
    BLOCK_GRAPH_DIAGNOSTIC,
    BLOCK_MISSING_FINISH_ANCHOR,
    BLOCK_MISSING_FORWARD_PASS,
    CAVEAT_FINISH_BEFORE_FORWARD,
    RUN_BACKWARD_PASS_ONLY,
    RUN_BLOCKED,
    compute_backward_pass,
    resolve_finish_anchor,
)
from hb_assistant.construction.analytics.schedule_cpm_forward_pass import compute_forward_pass
from hb_assistant.construction.analytics.schedule_cpm_graph import build_graph
from hb_assistant.construction.analytics.schedule_cpm_service import ScheduleCpmGraphService
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.schedule_cpm_repository import ScheduleCpmDiagnosticsRepository
from tests.schedule_project_test_helpers import clear_schedule_cpm_runs, seed_procore_ep_project

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


def _forward_inputs(fp):
    acts = [
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
    rels = [
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
    return acts, rels


def _backward(activities, relationships, *, anchor=ANCHOR):
    graph = build_graph(activities, relationships)
    fp = compute_forward_pass(
        activities, relationships, graph, anchor=anchor, anchor_source="data_date"
    )
    fwd_acts, fwd_rels = _forward_inputs(fp)
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
    return compute_backward_pass(
        graph,
        fwd_acts,
        fwd_rels,
        finish_anchor_offset=offset,
        finish_anchor_source=source,
        finish_anchor_caveat=caveat,
        start_anchor=anchor,
    )


def _by_id(result):
    return {a.activity_id: a for a in result.activities}


def _ls_lf(result):
    return {
        a.activity_id: (a.late_start_offset_days, a.late_finish_offset_days)
        for a in result.activities
    }


# --------------------------------------------------------------------------- unit


def test_single_activity_no_successors_is_terminal() -> None:
    result = _backward([_act("A", duration="5")], [])
    assert result.run_status == RUN_BACKWARD_PASS_ONLY
    assert result.cpm_recalculation_status == "backward_pass_only"
    a = _by_id(result)["A"]
    assert a.terminal_activity_flag is True
    assert a.late_finish_offset_days == 5.0  # anchor = max EF = 5
    assert a.late_start_offset_days == 0.0


def test_fs_chain_zero_lag_zero_float() -> None:
    acts = [_act("A"), _act("B"), _act("C")]
    rels = [_rel("A", "B"), _rel("B", "C")]
    result = _backward(acts, rels)
    # anchor = max EF = 15; LS==ES, LF==EF (zero float).
    assert _ls_lf(result) == {"A": (0.0, 5.0), "B": (5.0, 10.0), "C": (10.0, 15.0)}
    assert _by_id(result)["C"].terminal_activity_flag is True


def test_fs_chain_positive_lag() -> None:
    result = _backward([_act("A"), _act("B")], [_rel("A", "B", lag="2")])
    ls_lf = _ls_lf(result)
    assert ls_lf["B"] == (7.0, 12.0)  # terminal, anchor = 12
    assert ls_lf["A"] == (0.0, 5.0)   # cand_LF = B.LS - lag = 7 - 2 = 5


def test_fs_chain_negative_lag() -> None:
    result = _backward([_act("A"), _act("B")], [_rel("A", "B", lag="-2")])
    ls_lf = _ls_lf(result)
    assert ls_lf["B"] == (3.0, 8.0)   # anchor = 8
    assert ls_lf["A"] == (0.0, 5.0)   # cand_LF = B.LS - (-2) = 3 + 2 = 5


def test_parallel_successors_take_min_controlling_candidate() -> None:
    acts = [_act("A", duration="5"), _act("B", duration="5"), _act("C", duration="8")]
    rels = [_rel("A", "B"), _rel("A", "C")]
    result = _backward(acts, rels)
    a = _by_id(result)["A"]
    # B.LS=8, C.LS=5 → controlling is C (min). A.LF=5, A.LS=0.
    assert a.late_finish_offset_days == 5.0
    assert a.late_start_offset_days == 0.0
    assert a.controlling_successor_activity_id == "C"


def test_ss_relationship() -> None:
    result = _backward([_act("A", duration="5"), _act("B", duration="3")], [_rel("A", "B", "SS")])
    ls_lf = _ls_lf(result)
    assert ls_lf["B"] == (2.0, 5.0)   # terminal, anchor = max EF = 5
    assert ls_lf["A"] == (2.0, 7.0)   # cand_LS = B.LS - lag = 2; cand_LF = 2 + dur(5) = 7


def test_ff_relationship() -> None:
    result = _backward([_act("A", duration="5"), _act("B", duration="3")], [_rel("A", "B", "FF")])
    ls_lf = _ls_lf(result)
    assert ls_lf["B"] == (2.0, 5.0)
    assert ls_lf["A"] == (0.0, 5.0)   # cand_LF = B.LF - lag = 5


def test_sf_relationship() -> None:
    result = _backward([_act("A", duration="5"), _act("B", duration="3")], [_rel("A", "B", "SF")])
    ls_lf = _ls_lf(result)
    assert ls_lf["B"] == (2.0, 5.0)
    assert ls_lf["A"] == (5.0, 10.0)  # cand_LS = B.LF - lag = 5; cand_LF = 5 + dur(5) = 10


def test_milestone_zero_duration_terminal() -> None:
    acts = [_act("A", duration="5"), _act("M", duration=None, is_milestone=True)]
    result = _backward(acts, [_rel("A", "M")])
    m = _by_id(result)["M"]
    assert m.duration_value == 0.0
    assert m.terminal_activity_flag is True
    assert m.late_finish_offset_days == 5.0
    assert m.late_start_offset_days == 5.0  # LF - 0


def test_multiple_terminals_share_finish_anchor() -> None:
    acts = [_act("A"), _act("B"), _act("C")]
    rels = [_rel("A", "B"), _rel("A", "C")]
    result = _backward(acts, rels)
    by = _by_id(result)
    assert by["B"].terminal_activity_flag is True
    assert by["C"].terminal_activity_flag is True
    assert by["B"].late_finish_offset_days == by["C"].late_finish_offset_days == 10.0


def test_resolve_finish_anchor_from_source_scheduled_finish() -> None:
    offset, source, caveat = resolve_finish_anchor(
        source_scheduled_finish=datetime(2026, 1, 11),
        source_planned_finish=None,
        max_early_finish_offset=5.0,
        start_anchor=datetime(2026, 1, 1),
    )
    assert offset == 10.0
    assert source == ANCHOR_SOURCE_SCHEDULED_FINISH
    assert caveat is None


def test_resolve_finish_anchor_fallback_to_max_early_finish() -> None:
    offset, source, caveat = resolve_finish_anchor(
        source_scheduled_finish=None,
        source_planned_finish=None,
        max_early_finish_offset=5.0,
        start_anchor=datetime(2026, 1, 1),
    )
    assert offset == 5.0
    assert source == ANCHOR_SOURCE_MAX_EARLY_FINISH
    assert caveat is None


def test_resolve_finish_anchor_before_forward_finish_records_caveat() -> None:
    offset, source, caveat = resolve_finish_anchor(
        source_scheduled_finish=datetime(2026, 1, 4),
        source_planned_finish=None,
        max_early_finish_offset=5.0,
        start_anchor=datetime(2026, 1, 1),
    )
    assert offset == 3.0
    assert caveat == CAVEAT_FINISH_BEFORE_FORWARD


def test_missing_forward_pass_blocks() -> None:
    graph = build_graph([_act("A")], [])
    result = compute_backward_pass(
        graph, [], [],
        finish_anchor_offset=None, finish_anchor_source=None,
        finish_anchor_caveat=None, start_anchor=None,
    )
    assert result.run_status == RUN_BLOCKED
    assert result.block_reason == BLOCK_MISSING_FORWARD_PASS


def test_missing_finish_anchor_blocks() -> None:
    graph = build_graph([_act("A")], [])
    fwd = [{"activity_id": "A", "duration_value": 5.0, "early_start_offset_days": 0.0, "early_finish_offset_days": 5.0}]
    result = compute_backward_pass(
        graph, fwd, [],
        finish_anchor_offset=None, finish_anchor_source=None,
        finish_anchor_caveat=None, start_anchor=ANCHOR,
    )
    assert result.run_status == RUN_BLOCKED
    assert result.block_reason == BLOCK_MISSING_FINISH_ANCHOR


def test_cycle_blocks_backward_pass() -> None:
    acts = [_act("A"), _act("B"), _act("C")]
    rels = [_rel("A", "B"), _rel("B", "C"), _rel("C", "A")]
    graph = build_graph(acts, rels)
    fwd = [{"activity_id": a, "duration_value": 5.0, "early_start_offset_days": 0.0, "early_finish_offset_days": 5.0} for a in ("A", "B", "C")]
    result = compute_backward_pass(
        graph, fwd, [],
        finish_anchor_offset=5.0, finish_anchor_source="x",
        finish_anchor_caveat=None, start_anchor=ANCHOR,
    )
    assert result.run_status == RUN_BLOCKED
    assert result.block_reason == BLOCK_GRAPH_DIAGNOSTIC


def test_missing_predecessor_reference_blocks_backward_pass() -> None:
    graph = build_graph([_act("B")], [_rel("A", "B")])  # A missing
    fwd = [{"activity_id": "B", "duration_value": 5.0, "early_start_offset_days": 0.0, "early_finish_offset_days": 5.0}]
    result = compute_backward_pass(
        graph, fwd, [],
        finish_anchor_offset=5.0, finish_anchor_source="x",
        finish_anchor_caveat=None, start_anchor=ANCHOR,
    )
    assert result.run_status == RUN_BLOCKED
    assert result.block_reason == BLOCK_GRAPH_DIAGNOSTIC


def test_deterministic_across_repeated_runs() -> None:
    acts = [_act("C"), _act("A"), _act("B")]
    rels = [_rel("B", "C"), _rel("A", "B")]
    first = _ls_lf(_backward(acts, rels))
    second = _ls_lf(_backward(list(reversed(acts)), list(reversed(rels))))
    assert first == second


# --------------------------------------------------------------------- integration


def _import_minimal(tmp_path: Path):
    db = tmp_path / "bp.db"
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
    svk = commit["schedule_version_key"]
    clear_schedule_cpm_runs(db, svk)
    return db, svk


def test_import_run_forward_then_backward_persists_late_dates(tmp_path: Path) -> None:
    db, svk = _import_minimal(tmp_path)
    cpm = ScheduleCpmGraphService(db_path=str(db))
    cpm.run_forward_pass(svk)
    summary = cpm.run_backward_pass(svk)

    assert summary["run_status"] == "backward_pass_only"
    assert summary["cpm_recalculation_status"] == "backward_pass_only"
    assert summary["calculation_type"] == "backward_pass"
    assert summary["schedule_finish_anchor"] is not None
    by = {a["activity_id"]: a for a in summary["activities"]}
    # A1000 (5d) -> A1010 (10d). Terminal A1010 LF == finish anchor; LS == LF - duration.
    a1010 = by["A1010"]
    assert a1010["terminal_activity_flag"] is True
    anchor_offset = summary["finish_anchor_offset"]
    assert a1010["late_finish_offset_days"] == anchor_offset
    assert a1010["late_start_offset_days"] == anchor_offset - 10.0

    repo = ScheduleCpmDiagnosticsRepository(db_path=str(db))
    run = repo.get_run(summary["cpm_run_id"])
    assert run["calculation_type"] == "backward_pass"
    assert run["cpm_recalculation_status"] == "backward_pass_only"
    assert run["schedule_finish_anchor"] is not None
    rows = repo.list_activity_results(summary["cpm_run_id"])
    a1000 = next(r for r in rows if r["activity_id"] == "A1000")
    # Backward run rows carry BOTH early (copied) and late (computed) values.
    assert a1000["early_finish_offset_days"] == 5.0
    assert a1000["late_finish_offset_days"] is not None
    rel_rows = repo.list_relationship_results(summary["cpm_run_id"])
    assert len(rel_rows) == 1
    assert rel_rows[0]["backward_relationship_calc_status"] == "computed"
    assert rel_rows[0]["candidate_predecessor_late_finish"] is not None


def test_backward_pass_blocks_when_no_forward_pass(tmp_path: Path) -> None:
    db, svk = _import_minimal(tmp_path)
    cpm = ScheduleCpmGraphService(db_path=str(db))
    summary = cpm.run_backward_pass(svk)  # no forward pass run first
    assert summary["run_status"] == "blocked"
    assert summary["block_reason"] == BLOCK_MISSING_FORWARD_PASS
    repo = ScheduleCpmDiagnosticsRepository(db_path=str(db))
    assert repo.list_activity_results(summary["cpm_run_id"]) == []


def test_forward_pass_results_unchanged_after_backward_pass(tmp_path: Path) -> None:
    db, svk = _import_minimal(tmp_path)
    cpm = ScheduleCpmGraphService(db_path=str(db))
    fwd = cpm.run_forward_pass(svk)
    repo = ScheduleCpmDiagnosticsRepository(db_path=str(db))
    before = repo.list_activity_results(fwd["cpm_run_id"])
    bwd = cpm.run_backward_pass(svk)
    after = repo.list_activity_results(fwd["cpm_run_id"])
    # Distinct runs; the forward run's rows are byte-for-byte unchanged.
    assert fwd["cpm_run_id"] != bwd["cpm_run_id"]
    assert before == after
    # Forward run rows still have NULL late columns (backward never wrote to them).
    assert all(r["late_finish_offset_days"] is None for r in after)


def test_backward_rerun_is_idempotent(tmp_path: Path) -> None:
    db, svk = _import_minimal(tmp_path)
    cpm = ScheduleCpmGraphService(db_path=str(db))
    cpm.run_forward_pass(svk)
    first = cpm.run_backward_pass(svk)
    second = cpm.run_backward_pass(svk)
    assert first["cpm_run_id"] == second["cpm_run_id"]
    repo = ScheduleCpmDiagnosticsRepository(db_path=str(db))
    assert len(repo.list_activity_results(first["cpm_run_id"])) == 2
