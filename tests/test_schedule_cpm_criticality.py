"""CPM criticality foundation tests (Phase 6).

Pure-algorithm unit tests over ``compute_criticality`` (synthetic float + longest-path rows)
plus integration tests that persist classification and prove prior runs are unchanged.

Boundaries asserted: criticality classification only
(``cpm_recalculation_status='criticality_classification_only'``), from application-computed
total float; longest-path membership is context (never overrides); no is_critical, no source
reads; threshold validation; deterministic.
"""

from __future__ import annotations

import copy
from pathlib import Path

from hb_assistant.construction.analytics.schedule_cpm_criticality import (
    BLOCK_GRAPH_DIAGNOSTIC,
    BLOCK_INVALID_THRESHOLDS,
    BLOCK_MISSING_FLOAT_RUN,
    CAVEAT_LP_MEMBER_NOT_CRITICAL,
    CAVEAT_NEGATIVE_FLOAT,
    CAVEAT_ZERO_FLOAT_NOT_ON_LP,
    FLOAT_ROW_WHITELIST,
    compute_criticality,
)
from hb_assistant.construction.analytics.schedule_cpm_graph import build_graph
from hb_assistant.construction.analytics.schedule_cpm_service import ScheduleCpmGraphService
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.schedule_cpm_repository import ScheduleCpmDiagnosticsRepository
from tests.schedule_project_test_helpers import seed_procore_ep_project

XER_FIXTURE = Path(__file__).parent / "fixtures" / "schedules" / "xer" / "minimal.xer"


def _graph(ids, rels=()):
    acts = [{"activity_id": i} for i in ids]
    rs = [
        {"predecessor_activity_id": p, "successor_activity_id": s, "relationship_type": "FS"}
        for p, s in rels
    ]
    return build_graph(acts, rs)


def _fa(aid, tf, *, ff=None, topo=0, name=None):
    return {
        "activity_id": aid, "computed_total_float": tf, "computed_free_float": ff,
        "topological_index": topo, "activity_name": name,
    }


def _lp(aid, seq):
    return {"activity_id": aid, "path_sequence": seq}


def _by_id(result):
    return {a.activity_id: a for a in result.activities}


# --------------------------------------------------------------------------- classification


def test_zero_float_is_critical() -> None:
    result = compute_criticality(_graph(["A"]), [_fa("A", 0.0)], [])
    a = _by_id(result)["A"]
    assert a.computed_criticality_class == "computed_critical"
    assert a.computed_critical_flag is True
    assert a.computed_near_critical_flag is False
    assert a.computed_criticality_status == "computed"


def test_negative_float_is_critical_with_caveat() -> None:
    result = compute_criticality(_graph(["A"]), [_fa("A", -5.0)], [])
    a = _by_id(result)["A"]
    assert a.computed_criticality_class == "computed_critical"
    assert CAVEAT_NEGATIVE_FLOAT in a.notes


def test_within_tolerance_is_critical() -> None:
    result = compute_criticality(_graph(["A"]), [_fa("A", 0.0000005)], [])
    assert _by_id(result)["A"].computed_criticality_class == "computed_critical"


def test_above_critical_within_near_is_near_critical() -> None:
    result = compute_criticality(_graph(["A"]), [_fa("A", 5.0)], [])
    a = _by_id(result)["A"]
    assert a.computed_criticality_class == "computed_near_critical"
    assert a.computed_near_critical_flag is True
    assert a.computed_critical_flag is False


def test_above_near_is_noncritical() -> None:
    result = compute_criticality(_graph(["A"]), [_fa("A", 20.0)], [])
    assert _by_id(result)["A"].computed_criticality_class == "computed_noncritical"


def test_missing_total_float_unclassified() -> None:
    result = compute_criticality(_graph(["A"]), [_fa("A", None)], [])
    a = _by_id(result)["A"]
    assert a.computed_criticality_class == "unclassified"
    assert a.computed_criticality_status == "missing_computed_total_float"
    assert result.unclassified_activity_count == 1


def test_boundary_at_near_threshold_is_near_critical() -> None:
    result = compute_criticality(_graph(["A"]), [_fa("A", 10.0)], [])
    a = _by_id(result)["A"]
    assert a.computed_criticality_class == "computed_near_critical"
    assert "boundary" in a.notes


def test_configurable_thresholds_change_classification() -> None:
    # tf=5 is near-critical by default (near=10) but noncritical when near=3.
    default = compute_criticality(_graph(["A"]), [_fa("A", 5.0)], [])
    tight = compute_criticality(
        _graph(["A"]), [_fa("A", 5.0)], [],
        critical_threshold_days=0.0, near_critical_threshold_days=3.0,
    )
    assert _by_id(default)["A"].computed_criticality_class == "computed_near_critical"
    assert _by_id(tight)["A"].computed_criticality_class == "computed_noncritical"


def test_longest_path_member_flag_recorded() -> None:
    result = compute_criticality(_graph(["A"]), [_fa("A", 0.0)], [_lp("A", 1)])
    a = _by_id(result)["A"]
    assert a.longest_path_member_flag is True
    assert a.longest_path_sequence == 1
    assert result.longest_path_member_count == 1


def test_membership_does_not_override_classification() -> None:
    # Noncritical activity that happens to be a longest-path member stays noncritical.
    result = compute_criticality(_graph(["A"]), [_fa("A", 20.0)], [_lp("A", 1)])
    a = _by_id(result)["A"]
    assert a.computed_criticality_class == "computed_noncritical"
    assert a.computed_critical_flag is False
    assert a.longest_path_member_flag is True
    assert CAVEAT_LP_MEMBER_NOT_CRITICAL in a.notes


def test_critical_but_not_member_records_caveat() -> None:
    result = compute_criticality(_graph(["A"]), [_fa("A", 0.0)], [])  # no membership
    assert CAVEAT_ZERO_FLOAT_NOT_ON_LP in _by_id(result)["A"].notes


def test_deterministic_across_repeated_runs() -> None:
    graph = _graph(["A", "B", "C"], [("A", "B"), ("B", "C")])
    fa = [_fa("A", 0.0, topo=0), _fa("B", 5.0, topo=1), _fa("C", 20.0, topo=2)]
    first = compute_criticality(graph, fa, [_lp("A", 1)])
    second = compute_criticality(graph, list(fa), [_lp("A", 1)])
    assert [(a.activity_id, a.computed_criticality_class) for a in first.activities] == [
        (a.activity_id, a.computed_criticality_class) for a in second.activities
    ]


def test_does_not_mutate_inputs() -> None:
    fa = [_fa("A", 0.0)]
    lp = [_lp("A", 1)]
    before_fa = copy.deepcopy(fa)
    before_lp = copy.deepcopy(lp)
    compute_criticality(_graph(["A"]), fa, lp)
    assert fa == before_fa and lp == before_lp


def test_sets_no_is_critical_and_reads_no_source_fields() -> None:
    result = compute_criticality(_graph(["A"]), [_fa("A", 0.0)], [])
    assert not hasattr(_by_id(result)["A"], "is_critical")
    # The whitelist of fields copied from the float run excludes all source-export fields.
    for forbidden in (
        "is_critical", "source_critical_flag", "source_driving_path_flag",
        "total_float", "free_float", "early_start", "late_start",
    ):
        assert forbidden not in FLOAT_ROW_WHITELIST


def test_missing_float_blocks() -> None:
    result = compute_criticality(_graph(["A"]), [], [])
    assert result.run_status == "blocked"
    assert result.block_reason == BLOCK_MISSING_FLOAT_RUN


def test_fatal_graph_blocks() -> None:
    graph = _graph(["A", "B", "C"], [("A", "B"), ("B", "C"), ("C", "A")])
    result = compute_criticality(graph, [_fa("A", 0.0)], [])
    assert result.run_status == "blocked"
    assert result.block_reason == BLOCK_GRAPH_DIAGNOSTIC


def test_invalid_thresholds_block() -> None:
    # critical > near
    r1 = compute_criticality(
        _graph(["A"]), [_fa("A", 0.0)], [],
        critical_threshold_days=10.0, near_critical_threshold_days=0.0,
    )
    assert r1.block_reason == BLOCK_INVALID_THRESHOLDS
    # non-finite threshold
    r2 = compute_criticality(
        _graph(["A"]), [_fa("A", 0.0)], [],
        near_critical_threshold_days=float("inf"),
    )
    assert r2.block_reason == BLOCK_INVALID_THRESHOLDS
    # negative tolerance
    r3 = compute_criticality(_graph(["A"]), [_fa("A", 0.0)], [], tolerance=-1.0)
    assert r3.block_reason == BLOCK_INVALID_THRESHOLDS


# --------------------------------------------------------------------- integration


def _import_minimal(tmp_path: Path):
    db = tmp_path / "cr.db"
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


def _full_chain(cpm, svk):
    cpm.run_forward_pass(svk)
    cpm.run_backward_pass(svk)
    cpm.run_float_calculation(svk)
    cpm.run_longest_path(svk)


def test_full_chain_then_criticality_persists(tmp_path: Path) -> None:
    db, svk = _import_minimal(tmp_path)
    cpm = ScheduleCpmGraphService(db_path=str(db))
    cpm.run_graph_diagnostics(svk)
    _full_chain(cpm, svk)
    summary = cpm.run_criticality_classification(svk)

    assert summary["run_status"] == "criticality_classification_only"
    assert summary["cpm_recalculation_status"] == "criticality_classification_only"
    assert summary["calculation_type"] == "criticality"
    assert summary["source_run_id"] is not None
    # minimal.xer: both activities have negative total float (-98) -> both computed_critical
    # and both are longest-path members.
    assert summary["computed_critical_activity_count"] == 2
    assert summary["longest_path_member_count"] == 2
    by = {a["activity_id"]: a for a in summary["activities"]}
    assert by["A1000"]["computed_criticality_class"] == "computed_critical"
    assert by["A1000"]["longest_path_member_flag"] is True

    repo = ScheduleCpmDiagnosticsRepository(db_path=str(db))
    run = repo.get_run(summary["cpm_run_id"])
    assert run["calculation_type"] == "criticality"
    assert run["critical_float_threshold_days"] == 0.0
    rows = repo.list_activity_results(summary["cpm_run_id"])
    a1000 = next(r for r in rows if r["activity_id"] == "A1000")
    assert a1000["computed_critical_flag"] == 1
    assert a1000["computed_criticality_class"] == "computed_critical"
    # whitelist copy carried early/late/float context
    assert a1000["early_finish_offset_days"] == 5.0
    assert a1000["computed_total_float"] is not None


def test_custom_thresholds_persist(tmp_path: Path) -> None:
    db, svk = _import_minimal(tmp_path)
    cpm = ScheduleCpmGraphService(db_path=str(db))
    _full_chain(cpm, svk)
    summary = cpm.run_criticality_classification(
        svk, critical_threshold_days=2.0, near_critical_threshold_days=20.0
    )
    assert summary["critical_float_threshold_days"] == 2.0
    assert summary["near_critical_float_threshold_days"] == 20.0
    repo = ScheduleCpmDiagnosticsRepository(db_path=str(db))
    rows = repo.list_activity_results(summary["cpm_run_id"])
    assert all(r["critical_float_threshold_days"] == 2.0 for r in rows)


def test_criticality_blocks_without_float(tmp_path: Path) -> None:
    db, svk = _import_minimal(tmp_path)
    cpm = ScheduleCpmGraphService(db_path=str(db))
    summary = cpm.run_criticality_classification(svk)  # nothing run
    assert summary["run_status"] == "blocked"
    assert summary["block_reason"] == "blocked_by_missing_float_run"


def test_criticality_blocks_without_longest_path(tmp_path: Path) -> None:
    db, svk = _import_minimal(tmp_path)
    cpm = ScheduleCpmGraphService(db_path=str(db))
    cpm.run_forward_pass(svk)
    cpm.run_backward_pass(svk)
    cpm.run_float_calculation(svk)  # float but no longest path
    summary = cpm.run_criticality_classification(svk)
    assert summary["run_status"] == "blocked"
    assert summary["block_reason"] == "blocked_by_missing_longest_path_run"


def test_prior_runs_unchanged_after_criticality(tmp_path: Path) -> None:
    db, svk = _import_minimal(tmp_path)
    cpm = ScheduleCpmGraphService(db_path=str(db))
    fwd = cpm.run_forward_pass(svk)
    bwd = cpm.run_backward_pass(svk)
    flt = cpm.run_float_calculation(svk)
    lp = cpm.run_longest_path(svk)
    repo = ScheduleCpmDiagnosticsRepository(db_path=str(db))
    before = {r: repo.list_activity_results(r) for r in (fwd["cpm_run_id"], bwd["cpm_run_id"], flt["cpm_run_id"])}
    lp_paths_before = repo.list_paths(lp["cpm_run_id"])
    cr = cpm.run_criticality_classification(svk)
    assert cr["cpm_run_id"] not in before
    for r, rows in before.items():
        assert repo.list_activity_results(r) == rows
    assert repo.list_paths(lp["cpm_run_id"]) == lp_paths_before


def test_criticality_rerun_idempotent(tmp_path: Path) -> None:
    db, svk = _import_minimal(tmp_path)
    cpm = ScheduleCpmGraphService(db_path=str(db))
    _full_chain(cpm, svk)
    first = cpm.run_criticality_classification(svk)
    second = cpm.run_criticality_classification(svk)
    assert first["cpm_run_id"] == second["cpm_run_id"]
    repo = ScheduleCpmDiagnosticsRepository(db_path=str(db))
    assert len(repo.list_activity_results(first["cpm_run_id"])) == 2
