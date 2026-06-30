"""Schedule Health computed-CPM aggregation tests (Phase 9A.1).

Covers the additive, read-only ``computed_cpm_health`` envelope on /health-data: full chain,
no runs, partial chain, read-only guarantee, scope guard, and provenance labels.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from hb_assistant.construction.analytics.api import create_app
from hb_assistant.construction.analytics.schedule_cpm_service import ScheduleCpmGraphService
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.schedule_cpm_repository import ScheduleCpmDiagnosticsRepository
from tests.schedule_project_test_helpers import clear_schedule_cpm_runs, seed_procore_ep_project

XER = Path(__file__).parent / "fixtures" / "schedules" / "xer" / "minimal.xer"


def _op() -> dict[str, str]:
    return {"X-HB-UI-Role": "operator"}


def _viewer() -> dict[str, str]:
    return {"X-HB-UI-Role": "viewer"}


def _client(tmp_path: Path) -> tuple[TestClient, str, str]:
    db = tmp_path / "health_cpm.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    client = TestClient(create_app(db_path=str(db)))
    preview = client.post(
        "/api/schedules/import-preview",
        headers=_op(),
        files={"file": ("minimal.xer", XER.read_bytes(), "application/xml")},
        data={"project_key": "tropical"},
    )
    import_id = preview.json()["import_id"]
    commit = client.post(
        "/api/schedules/import-commit",
        headers=_op(),
        json={"import_id": import_id, "project_key": "tropical", "confirm": True},
    )
    svk = commit.json()["schedule_version_key"]
    clear_schedule_cpm_runs(db, svk)
    return client, svk, str(db)


def _run_chain(db: str, svk: str) -> None:
    cpm = ScheduleCpmGraphService(db_path=db)
    cpm.run_graph_diagnostics(svk)
    cpm.run_forward_pass(svk)
    cpm.run_backward_pass(svk)
    cpm.run_float_calculation(svk)
    cpm.run_longest_path(svk)
    cpm.run_criticality_classification(svk)


def _health(client: TestClient, svk: str) -> dict:
    resp = client.get(f"/api/schedules/versions/{svk}/health-data", headers=_viewer())
    assert resp.status_code == 200
    return resp.json()


# --------------------------------------------------------------------------- full chain


def test_health_data_includes_computed_cpm_health_full_chain(tmp_path: Path) -> None:
    client, svk, db = _client(tmp_path)
    _run_chain(db, svk)
    health = _health(client, svk)

    assert "computed_cpm_health" in health  # additive key present
    cpm = health["computed_cpm_health"]
    assert cpm["available"] is True
    assert cpm["evidence_class"] == "application_computed_cpm"
    assert cpm["source_export_evidence"] == "separate"

    for kind in (
        "graph_diagnostics",
        "forward_pass",
        "backward_pass",
        "float",
        "longest_path",
        "criticality",
    ):
        assert cpm["run_chain"][kind]["available"] is True
    assert cpm["missing_dependency_reasons"] == []

    # Counts equal the pre-aggregated criticality run row (no separate hydration).
    repo = ScheduleCpmDiagnosticsRepository(db_path=db)
    crit = repo.get_criticality_run(svk)
    assert crit is not None
    counts = cpm["counts"]
    assert counts["computed_activity_count"] == 2
    assert counts["computed_critical_activity_count"] == crit["computed_critical_activity_count"]
    assert (
        counts["computed_near_critical_activity_count"]
        == crit["computed_near_critical_activity_count"]
    )
    assert counts["longest_path_member_count"] == crit["longest_path_member_count"]

    # Float buckets came from the single GROUP BY aggregate (classified == activity count).
    assert counts["classified_total_float_count"] == 2
    assert counts["high_total_float_threshold_days"] == 44.0
    for bucket in (
        "negative_total_float_count",
        "zero_total_float_count",
        "high_total_float_count",
    ):
        assert isinstance(counts[bucket], int) and counts[bucket] >= 0

    lp = cpm["longest_path_summary"]
    assert lp["available"] is True
    assert lp["path_id"]

    dcma = cpm["dcma_critical_path_metric"]
    assert dcma["available"] is True
    assert dcma["measurable"] is True
    assert dcma["basis"] == "application_computed_cpm"
    assert dcma["source_critical_flags_used"] is False

    assert cpm["diagnostics_summary"]["available"] is True
    assert cpm["links"]["computed_cpm"].startswith("/schedules/cpm?version=")


def test_computed_cpm_health_carries_caveats_when_present(tmp_path: Path) -> None:
    client, svk, db = _client(tmp_path)
    _run_chain(db, svk)
    dcma = _health(client, svk)["computed_cpm_health"]["dcma_critical_path_metric"]
    # Caveats are passed through verbatim from the read-only DCMA evaluator (never hidden).
    assert isinstance(dcma["caveats"], list)
    assert isinstance(dcma["reason_codes"], list)


# --------------------------------------------------------------------------- no runs


def test_health_data_computed_cpm_unavailable_without_runs(tmp_path: Path) -> None:
    client, svk, _ = _client(tmp_path)
    health = _health(client, svk)  # imported, but no CPM chain run

    # Source-export health still loads.
    assert health.get("schedule_version_key") == svk
    assert "capabilities" in health

    cpm = health["computed_cpm_health"]
    assert cpm["available"] is False
    assert cpm["reason"] == "no_computed_cpm"
    assert cpm["evidence_class"] == "application_computed_cpm"
    assert "forward_pass" in cpm["missing_dependency_reasons"]
    assert cpm["run_chain"]["criticality"]["available"] is False


# --------------------------------------------------------------------------- partial chain


def test_health_data_partial_chain_reports_missing_dependencies(tmp_path: Path) -> None:
    client, svk, db = _client(tmp_path)
    ScheduleCpmGraphService(db_path=db).run_forward_pass(svk)  # only forward pass
    cpm = _health(client, svk)["computed_cpm_health"]

    assert cpm["available"] is True  # at least one run present
    assert cpm["run_chain"]["forward_pass"]["available"] is True
    for missing in ("backward_pass", "float", "longest_path", "criticality"):
        assert missing in cpm["missing_dependency_reasons"]
        assert cpm["run_chain"][missing]["available"] is False
    # No float run yet -> float buckets stay null rather than fabricated zeros.
    assert cpm["counts"]["classified_total_float_count"] is None


# --------------------------------------------------------------------------- guarantees


def test_health_data_aggregation_is_read_only(tmp_path: Path) -> None:
    client, svk, db = _client(tmp_path)
    _run_chain(db, svk)
    repo = ScheduleCpmDiagnosticsRepository(db_path=db)
    runs_before = repo.list_runs(svk)
    _health(client, svk)
    _health(client, svk)
    assert repo.list_runs(svk) == runs_before  # reads never create/mutate runs


def test_health_data_project_scope_mismatch_is_blocked(tmp_path: Path) -> None:
    # The version/project scope guard runs before any aggregation; a mismatched project_key on
    # this read route is rejected (404) rather than leaking another project's health.
    client, svk, _ = _client(tmp_path)
    resp = client.get(
        f"/api/schedules/versions/{svk}/health-data",
        params={"project_key": "not-this-project"},
        headers=_viewer(),
    )
    assert resp.status_code == 404
