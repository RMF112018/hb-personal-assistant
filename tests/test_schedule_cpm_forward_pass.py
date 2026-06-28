"""CPM forward pass foundation tests (Phase 2).

Pure-algorithm unit tests over ``compute_forward_pass`` (hand-built dicts, asserting on the
authoritative day-offsets) plus an integration test that imports a minimal XER and persists
forward-pass results.

Boundaries asserted: forward pass only (``cpm_recalculation_status='forward_pass_only'``),
no source-field reads/writes, deterministic output, and clean blocking on fatal graph
diagnostics or a missing schedule-start anchor.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from hb_assistant.construction.analytics.schedule_cpm_forward_pass import (
    BLOCK_GRAPH_DIAGNOSTIC,
    BLOCK_MISSING_ANCHOR,
    REL_BLOCKED_PRED_NO_FINISH,
    REL_COMPUTED,
    REL_UNSUPPORTED_TYPE,
    RUN_BLOCKED,
    RUN_FORWARD_PASS_ONLY,
    compute_forward_pass,
)
from hb_assistant.construction.analytics.schedule_cpm_graph import build_graph
from hb_assistant.construction.analytics.schedule_cpm_service import ScheduleCpmGraphService
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.schedule_cpm_repository import ScheduleCpmDiagnosticsRepository
from tests.schedule_project_test_helpers import seed_procore_ep_project

XER_FIXTURE = Path(__file__).parent / "fixtures" / "schedules" / "xer" / "minimal.xer"
ANCHOR = datetime(2026, 1, 1)


def _act(activity_id: str, *, duration: str | None = "5", unit: str = "day", **kw: object):
    row: dict[str, object] = {"activity_id": activity_id, "duration_unit": unit, **kw}
    if duration is not None:
        row["duration_original"] = duration
    return row


def _rel(pred: str, succ: str, rel_type: str = "FS", lag: str = "0", **kw: object):
    return {
        "predecessor_activity_id": pred,
        "successor_activity_id": succ,
        "relationship_type": rel_type,
        "lag_value": lag,
        "lag_unit": "day",
        **kw,
    }


def _run(activities, relationships, *, anchor=ANCHOR):
    graph = build_graph(activities, relationships)
    return compute_forward_pass(
        activities, relationships, graph, anchor=anchor, anchor_source="data_date"
    )


def _by_id(result):
    return {a.activity_id: a for a in result.activities}


# --------------------------------------------------------------------------- unit


def test_single_activity_no_predecessors_starts_at_anchor() -> None:
    result = _run([_act("A", duration="5")], [])
    assert result.run_status == RUN_FORWARD_PASS_ONLY
    assert result.cpm_recalculation_status == "forward_pass_only"
    a = _by_id(result)["A"]
    assert a.early_start_offset_days == 0.0
    assert a.early_finish_offset_days == 5.0
    assert a.duration_source == "duration_original"
    assert a.computed_early_start == datetime(2026, 1, 1).isoformat()
    assert a.computed_early_finish == datetime(2026, 1, 6).isoformat()


def test_fs_chain_zero_lag() -> None:
    acts = [_act("A"), _act("B"), _act("C")]
    rels = [_rel("A", "B"), _rel("B", "C")]
    by = _by_id(_run(acts, rels))
    assert (by["A"].early_start_offset_days, by["A"].early_finish_offset_days) == (0.0, 5.0)
    assert (by["B"].early_start_offset_days, by["B"].early_finish_offset_days) == (5.0, 10.0)
    assert (by["C"].early_start_offset_days, by["C"].early_finish_offset_days) == (10.0, 15.0)


def test_fs_chain_positive_lag() -> None:
    acts = [_act("A"), _act("B")]
    rels = [_rel("A", "B", lag="2")]
    by = _by_id(_run(acts, rels))
    assert by["B"].early_start_offset_days == 7.0  # predEF 5 + lag 2
    assert by["B"].early_finish_offset_days == 12.0


def test_fs_chain_negative_lag() -> None:
    acts = [_act("A"), _act("B")]
    rels = [_rel("A", "B", lag="-2")]
    by = _by_id(_run(acts, rels))
    assert by["B"].early_start_offset_days == 3.0  # predEF 5 - 2
    assert by["B"].early_finish_offset_days == 8.0


def test_parallel_predecessors_take_max_candidate() -> None:
    acts = [_act("P1", duration="5"), _act("P2", duration="8"), _act("S", duration="3")]
    rels = [_rel("P1", "S"), _rel("P2", "S")]
    by = _by_id(_run(acts, rels))
    assert by["S"].early_start_offset_days == 8.0  # max(EF P1=5, EF P2=8)
    assert by["S"].early_finish_offset_days == 11.0


def test_ss_relationship() -> None:
    acts = [_act("A", duration="5"), _act("B", duration="3")]
    rels = [_rel("A", "B", "SS", lag="0")]
    by = _by_id(_run(acts, rels))
    assert by["B"].early_start_offset_days == 0.0  # predES 0 + lag 0
    assert by["B"].early_finish_offset_days == 3.0


def test_ff_relationship() -> None:
    acts = [_act("A", duration="5"), _act("B", duration="3")]
    rels = [_rel("A", "B", "FF", lag="0")]
    by = _by_id(_run(acts, rels))
    # succ EF >= predEF(5) + lag(0); ES = 5 - dur(3) = 2
    assert by["B"].early_start_offset_days == 2.0
    assert by["B"].early_finish_offset_days == 5.0


def test_sf_relationship_floors_at_anchor() -> None:
    acts = [_act("A", duration="5"), _act("B", duration="3")]
    rels = [_rel("A", "B", "SF", lag="0")]
    result = _run(acts, rels)
    by = _by_id(result)
    # SF candidate = predES(0) + lag(0) - dur(3) = -3, floored to anchor (0).
    rel = result.relationships[0]
    assert rel.candidate_successor_early_start_offset == -3.0
    assert rel.relationship_calc_status == REL_COMPUTED
    assert by["B"].early_start_offset_days == 0.0
    assert by["B"].early_finish_offset_days == 3.0


def test_milestone_zero_duration() -> None:
    acts = [_act("A", duration="5"), _act("M", duration=None, is_milestone=True)]
    rels = [_rel("A", "M")]
    by = _by_id(_run(acts, rels))
    assert by["M"].duration_value == 0.0
    assert by["M"].duration_source == "milestone"
    assert by["M"].early_start_offset_days == 5.0
    assert by["M"].early_finish_offset_days == 5.0
    assert by["M"].forward_pass_status == "computed"


def test_missing_duration_flags_only_affected_activity() -> None:
    acts = [_act("A", duration=None), _act("B", duration="5")]
    rels = [_rel("A", "B")]
    result = _run(acts, rels)
    by = _by_id(result)
    assert by["A"].forward_pass_status == "missing_duration"
    assert by["A"].early_finish_offset_days is None
    assert result.blocked_activity_count == 1
    assert result.computed_activity_count == 1
    # Successor relationship can't read a finish from a duration-less predecessor.
    rel = result.relationships[0]
    assert rel.relationship_calc_status == REL_BLOCKED_PRED_NO_FINISH
    assert by["B"].early_start_offset_days == 0.0  # no contributing predecessor → anchor


def test_unsupported_relationship_type_recorded_non_fatal() -> None:
    acts = [_act("A"), _act("B")]
    rels = [_rel("A", "B", "ZZ")]
    result = _run(acts, rels)
    assert result.run_status == RUN_FORWARD_PASS_ONLY  # unsupported type does not block run
    rel = result.relationships[0]
    assert rel.relationship_calc_status == REL_UNSUPPORTED_TYPE
    assert rel.candidate_successor_early_start_offset is None


def test_missing_start_anchor_blocks_run() -> None:
    result = _run([_act("A")], [], anchor=None)
    assert result.run_status == RUN_BLOCKED
    assert result.block_reason == BLOCK_MISSING_ANCHOR
    assert result.activities == []


def test_cycle_blocks_forward_pass() -> None:
    acts = [_act("A"), _act("B"), _act("C")]
    rels = [_rel("A", "B"), _rel("B", "C"), _rel("C", "A")]
    result = _run(acts, rels)
    assert result.run_status == RUN_BLOCKED
    assert result.block_reason == BLOCK_GRAPH_DIAGNOSTIC
    assert result.activities == []


def test_missing_predecessor_reference_blocks_forward_pass() -> None:
    acts = [_act("B")]
    rels = [_rel("A", "B")]  # A not present
    result = _run(acts, rels)
    assert result.run_status == RUN_BLOCKED
    assert result.block_reason == BLOCK_GRAPH_DIAGNOSTIC


def test_deterministic_across_repeated_runs() -> None:
    acts = [_act("C"), _act("A"), _act("B")]
    rels = [_rel("B", "C"), _rel("A", "B")]
    first = _run(acts, rels)
    second = _run(list(reversed(acts)), list(reversed(rels)))
    assert [(a.activity_id, a.early_start_offset_days, a.early_finish_offset_days) for a in first.activities] == [
        (a.activity_id, a.early_start_offset_days, a.early_finish_offset_days) for a in second.activities
    ]


# --------------------------------------------------------------------- integration


def test_import_minimal_xer_and_persist_forward_pass(tmp_path: Path) -> None:
    db = tmp_path / "fp.db"
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

    cpm = ScheduleCpmGraphService(db_path=str(db))
    summary = cpm.run_forward_pass(svk)

    # minimal.xer: A1000 (40h=5d) -> A1010 (80h=10d), FS lag 0.
    assert summary["run_status"] == "forward_pass_only"
    assert summary["cpm_recalculation_status"] == "forward_pass_only"
    assert summary["calculation_type"] == "forward_pass"
    assert summary["schedule_start_anchor"] is not None
    assert summary["computed_activity_count"] == 2
    by = {a["activity_id"]: a for a in summary["activities"]}
    assert by["A1000"]["early_start_offset_days"] == 0.0
    assert by["A1000"]["early_finish_offset_days"] == 5.0
    assert by["A1010"]["early_start_offset_days"] == 5.0
    assert by["A1010"]["early_finish_offset_days"] == 15.0

    repo = ScheduleCpmDiagnosticsRepository(db_path=str(db))
    run = repo.get_run(summary["cpm_run_id"])
    assert run["calculation_type"] == "forward_pass"
    assert run["cpm_recalculation_status"] == "forward_pass_only"

    activity_rows = repo.list_activity_results(summary["cpm_run_id"])
    assert len(activity_rows) == 2
    a1000 = next(r for r in activity_rows if r["activity_id"] == "A1000")
    assert a1000["early_finish_offset_days"] == 5.0
    assert a1000["duration_source"] == "duration_original"
    assert a1000["computed_early_start"] is not None

    rel_rows = repo.list_relationship_results(summary["cpm_run_id"])
    assert len(rel_rows) == 1
    assert rel_rows[0]["relationship_calc_status"] == "computed"
    assert rel_rows[0]["candidate_successor_early_start_offset"] == 5.0
    assert rel_rows[0]["normalized_lag_days"] == 0.0


def test_forward_pass_rerun_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "fp.db"
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

    cpm = ScheduleCpmGraphService(db_path=str(db))
    first = cpm.run_forward_pass(svk)
    second = cpm.run_forward_pass(svk)
    assert first["cpm_run_id"] == second["cpm_run_id"]

    repo = ScheduleCpmDiagnosticsRepository(db_path=str(db))
    assert len(repo.list_activity_results(first["cpm_run_id"])) == 2
    assert len(repo.list_relationship_results(first["cpm_run_id"])) == 1


def test_forward_pass_run_distinct_from_graph_run(tmp_path: Path) -> None:
    db = tmp_path / "fp.db"
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

    cpm = ScheduleCpmGraphService(db_path=str(db))
    graph_summary = cpm.run_graph_diagnostics(svk)
    fp_summary = cpm.run_forward_pass(svk)
    # Distinct run ids; the graph-only run is preserved untouched.
    assert graph_summary["cpm_run_id"] != fp_summary["cpm_run_id"]
    repo = ScheduleCpmDiagnosticsRepository(db_path=str(db))
    graph_run = repo.get_run(graph_summary["cpm_run_id"])
    assert graph_run["cpm_recalculation_status"] == "not_implemented"
    assert json.loads(graph_run["topological_order_json"]) == ["A1000", "A1010"]
