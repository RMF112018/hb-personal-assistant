"""CPM graph diagnostics foundation tests (Phase 1).

Covers the pure graph builder (`build_graph`) with small hand-built fixtures and one
integration test that imports a minimal XER and persists/reads graph diagnostics.

These tests assert the foundation reports GRAPH DIAGNOSTICS ONLY — no CPM dates, float, or
critical path — and that `cpm_recalculation_status` stays `"not_implemented"`.
"""

from __future__ import annotations

import json
from pathlib import Path

from hb_assistant.construction.analytics.schedule_cpm_graph import (
    ANALYSIS_SCOPE,
    CPM_RECALCULATION_STATUS,
    DIAG_CYCLE,
    DIAG_DUPLICATE_RELATIONSHIP,
    DIAG_MISSING_PREDECESSOR,
    DIAG_MISSING_SUCCESSOR,
    DIAG_OPEN_FINISH,
    DIAG_OPEN_START,
    DIAG_SELF_RELATIONSHIP,
    DIAG_UNSUPPORTED_TYPE,
    build_graph,
)
from hb_assistant.construction.analytics.schedule_cpm_service import ScheduleCpmGraphService
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.schedule_cpm_repository import ScheduleCpmDiagnosticsRepository
from tests.schedule_project_test_helpers import clear_schedule_cpm_runs, seed_procore_ep_project

XER_FIXTURE = Path(__file__).parent / "fixtures" / "schedules" / "xer" / "minimal.xer"


def _act(activity_id: str, **kw: object) -> dict[str, object]:
    return {"activity_id": activity_id, **kw}


def _rel(pred: str, succ: str, rel_type: str = "FS", **kw: object) -> dict[str, object]:
    return {
        "predecessor_activity_id": pred,
        "successor_activity_id": succ,
        "relationship_type": rel_type,
        **kw,
    }


def _types(result, diag_type: str) -> list:
    return [d for d in result.diagnostics if d.diagnostic_type == diag_type]


# --------------------------------------------------------------------------- unit


def test_simple_chain_topological_order() -> None:
    activities = [_act("A"), _act("B"), _act("C")]
    relationships = [_rel("A", "B"), _rel("B", "C")]
    result = build_graph(activities, relationships)

    assert result.node_count == 3
    assert result.edge_count == 2
    assert result.is_acyclic is True
    assert result.topological_order == ["A", "B", "C"]
    assert result.analysis_scope == ANALYSIS_SCOPE
    assert result.cpm_recalculation_status == CPM_RECALCULATION_STATUS == "not_implemented"
    # One open start (A) and one open finish (C).
    assert {d.activity_id for d in _types(result, DIAG_OPEN_START)} == {"A"}
    assert {d.activity_id for d in _types(result, DIAG_OPEN_FINISH)} == {"C"}


def test_parallel_paths_deterministic_order() -> None:
    # A -> B -> D, A -> C -> D (diamond).
    activities = [_act("A"), _act("B"), _act("C"), _act("D")]
    relationships = [_rel("A", "B"), _rel("A", "C"), _rel("B", "D"), _rel("C", "D")]
    result = build_graph(activities, relationships)

    assert result.is_acyclic is True
    order = result.topological_order
    assert order is not None
    # Deterministic tie-break by sorted activity_id: A, then B before C, then D.
    assert order == ["A", "B", "C", "D"]
    assert result.edge_count == 4
    # Single source A is the only open start; single sink D the only open finish.
    assert {d.activity_id for d in _types(result, DIAG_OPEN_START)} == {"A"}
    assert {d.activity_id for d in _types(result, DIAG_OPEN_FINISH)} == {"D"}


def test_open_start_and_open_finish_for_isolated_node() -> None:
    activities = [_act("A"), _act("B"), _act("X")]
    relationships = [_rel("A", "B")]
    result = build_graph(activities, relationships)

    open_starts = {d.activity_id for d in _types(result, DIAG_OPEN_START)}
    open_finishes = {d.activity_id for d in _types(result, DIAG_OPEN_FINISH)}
    # X is isolated: both open start and open finish. A is open start, B open finish.
    assert open_starts == {"A", "X"}
    assert open_finishes == {"B", "X"}


def test_missing_predecessor_activity() -> None:
    activities = [_act("B")]
    relationships = [_rel("A", "B")]  # A not in activities
    result = build_graph(activities, relationships)

    missing = _types(result, DIAG_MISSING_PREDECESSOR)
    assert len(missing) == 1
    assert missing[0].activity_id == "A"
    assert missing[0].severity == "error"
    # Edge dropped from the graph; B is the only node and is both open start/finish.
    assert result.edge_count == 0
    assert result.is_acyclic is True


def test_missing_successor_activity() -> None:
    activities = [_act("A")]
    relationships = [_rel("A", "B")]  # B not in activities
    result = build_graph(activities, relationships)

    missing = _types(result, DIAG_MISSING_SUCCESSOR)
    assert len(missing) == 1
    assert missing[0].activity_id == "B"
    assert result.edge_count == 0


def test_duplicate_relationship() -> None:
    activities = [_act("A"), _act("B")]
    relationships = [_rel("A", "B"), _rel("A", "B")]
    result = build_graph(activities, relationships)

    dups = _types(result, DIAG_DUPLICATE_RELATIONSHIP)
    assert len(dups) == 1
    assert dups[0].severity == "warning"
    # Only one edge is kept.
    assert result.edge_count == 1


def test_self_relationship() -> None:
    activities = [_act("A"), _act("B")]
    relationships = [_rel("A", "A"), _rel("A", "B")]
    result = build_graph(activities, relationships)

    selfs = _types(result, DIAG_SELF_RELATIONSHIP)
    assert len(selfs) == 1
    assert selfs[0].activity_id == "A"
    assert selfs[0].severity == "error"
    # Self-loop excluded; only A->B counts.
    assert result.edge_count == 1


def test_cycle_detection() -> None:
    activities = [_act("A"), _act("B"), _act("C")]
    relationships = [_rel("A", "B"), _rel("B", "C"), _rel("C", "A")]
    result = build_graph(activities, relationships)

    assert result.is_acyclic is False
    assert result.topological_order is None
    cycles = _types(result, DIAG_CYCLE)
    assert len(cycles) == 1
    assert sorted(cycles[0].evidence["cyclic_activity_ids"]) == ["A", "B", "C"]


def test_unsupported_relationship_type() -> None:
    activities = [_act("A"), _act("B"), _act("C")]
    # "ZZ" is unsupported; None is also unsupported. Both still form dependency edges.
    relationships = [_rel("A", "B", "ZZ"), _rel("B", "C", None)]
    result = build_graph(activities, relationships)

    unsupported = _types(result, DIAG_UNSUPPORTED_TYPE)
    assert len(unsupported) == 2
    assert all(d.severity == "warning" for d in unsupported)
    # Unsupported-typed edges are still honored for topology.
    assert result.edge_count == 2
    assert result.topological_order == ["A", "B", "C"]


def test_build_is_deterministic_regardless_of_input_order() -> None:
    activities = [_act("C"), _act("A"), _act("B")]
    forward = [_rel("A", "B"), _rel("B", "C")]
    reversed_input = [_rel("B", "C"), _rel("A", "B")]
    first = build_graph(activities, forward)
    second = build_graph(list(reversed(activities)), reversed_input)
    assert first.topological_order == second.topological_order == ["A", "B", "C"]


# --------------------------------------------------------------------- integration


def test_import_minimal_xer_and_persist_graph_diagnostics(tmp_path: Path) -> None:
    db = tmp_path / "cpm.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(
        db,
        project_key="tropical",
        display_name="Tropical Wind",
        project_number="TWNU18",
    )

    from hb_assistant.construction.analytics.schedule_import_service import (
        ScheduleImportService,
    )

    svc = ScheduleImportService(db_path=str(db))
    preview = svc.preview_bytes(
        filename=XER_FIXTURE.name,
        data=XER_FIXTURE.read_bytes(),
        project_key="tropical",
    )
    commit = svc.commit(
        import_id=preview["import_id"],
        project_key="tropical",
        confirm=True,
    )
    svk = commit["schedule_version_key"]

    cpm = ScheduleCpmGraphService(db_path=str(db))
    summary = cpm.run_graph_diagnostics(svk)

    # minimal.xer = 2 activities (A1000 -> A1010 FS).
    assert summary["node_count"] == 2
    assert summary["edge_count"] == 1
    assert summary["is_acyclic"] is True
    assert summary["topological_order"] == ["A1000", "A1010"]
    assert summary["cpm_recalculation_status"] == "not_implemented"
    assert summary["analysis_scope"] == "graph_diagnostics_only"

    # Persisted and readable via the repository.
    repo = ScheduleCpmDiagnosticsRepository(db_path=str(db))
    runs = repo.list_runs(svk)
    run = next(row for row in runs if row["cpm_run_id"] == summary["cpm_run_id"])
    assert run["cpm_run_id"] == summary["cpm_run_id"]
    assert run["is_acyclic"] == 1
    assert json.loads(run["topological_order_json"]) == ["A1000", "A1010"]
    assert run["cpm_recalculation_status"] == "not_implemented"

    diagnostics = repo.list_diagnostics(run["cpm_run_id"])
    assert len(diagnostics) == run["diagnostic_count"]
    diag_types = {d["diagnostic_type"] for d in diagnostics}
    # A1000 has no predecessor (open start); A1010 has no successor (open finish).
    assert DIAG_OPEN_START in diag_types
    assert DIAG_OPEN_FINISH in diag_types


def test_rerun_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "cpm.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(
        db,
        project_key="tropical",
        display_name="Tropical Wind",
        project_number="TWNU18",
    )
    from hb_assistant.construction.analytics.schedule_import_service import (
        ScheduleImportService,
    )

    svc = ScheduleImportService(db_path=str(db))
    preview = svc.preview_bytes(
        filename=XER_FIXTURE.name,
        data=XER_FIXTURE.read_bytes(),
        project_key="tropical",
    )
    commit = svc.commit(
        import_id=preview["import_id"], project_key="tropical", confirm=True
    )
    svk = commit["schedule_version_key"]
    clear_schedule_cpm_runs(db, svk)

    cpm = ScheduleCpmGraphService(db_path=str(db))
    first = cpm.run_graph_diagnostics(svk)
    second = cpm.run_graph_diagnostics(svk)

    assert first["cpm_run_id"] == second["cpm_run_id"]
    repo = ScheduleCpmDiagnosticsRepository(db_path=str(db))
    # Rerun replaced rather than accumulated.
    assert len(repo.list_runs(svk)) == 1
    assert len(repo.list_diagnostics(first["cpm_run_id"])) == first["diagnostic_count"]
