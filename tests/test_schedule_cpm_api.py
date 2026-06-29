"""Read-only computed-CPM API endpoint tests (Phase 8)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from hb_assistant.construction.analytics.api import create_app
from hb_assistant.construction.analytics.schedule_cpm_service import ScheduleCpmGraphService
from hb_assistant.store.migrator import SQLiteMigrator
from tests.schedule_project_test_helpers import seed_procore_ep_project

XER = Path(__file__).parent / "fixtures" / "schedules" / "xer" / "minimal.xer"


def _op() -> dict[str, str]:
    return {"X-HB-UI-Role": "operator"}


def _viewer() -> dict[str, str]:
    return {"X-HB-UI-Role": "viewer"}


def _client(tmp_path: Path) -> tuple[TestClient, str]:
    db = tmp_path / "cpm_api.db"
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
    return client, commit.json()["schedule_version_key"], str(db)


def _run_chain(db: str, svk: str) -> None:
    cpm = ScheduleCpmGraphService(db_path=db)
    cpm.run_graph_diagnostics(svk)
    cpm.run_forward_pass(svk)
    cpm.run_backward_pass(svk)
    cpm.run_float_calculation(svk)
    cpm.run_longest_path(svk)
    cpm.run_criticality_classification(svk)


# --------------------------------------------------------------------------- summary


def test_cpm_summary_available_after_import_commit(tmp_path: Path) -> None:
    client, svk, _ = _client(tmp_path)
    resp = client.get(f"/api/schedules/versions/{svk}/cpm/summary", headers=_viewer())
    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is True
    assert body["runs"]["forward_pass"]["available"] is True
    assert body["runs"]["criticality"]["available"] is True


def test_cpm_summary_full_chain(tmp_path: Path) -> None:
    client, svk, db = _client(tmp_path)
    _run_chain(db, svk)
    body = client.get(f"/api/schedules/versions/{svk}/cpm/summary", headers=_viewer()).json()
    assert body["available"] is True
    runs = body["runs"]
    for kind in ("graph_diagnostics", "forward_pass", "backward_pass", "float", "longest_path", "criticality"):
        assert runs[kind]["available"] is True
    dcma = body["dcma_critical_path"]
    assert dcma["available"] is True
    assert dcma["measurable"] is True
    assert dcma["basis"] == "application_computed_cpm"
    assert dcma["source_critical_flags_used"] is False
    assert set(dcma["dependency_run_ids"]) == {
        "forward", "backward", "float", "longest_path", "criticality"
    }


# --------------------------------------------------------------------------- activities


def test_cpm_activities_uses_criticality_run_and_excludes_source_fields(tmp_path: Path) -> None:
    client, svk, db = _client(tmp_path)
    _run_chain(db, svk)
    body = client.get(f"/api/schedules/versions/{svk}/cpm/activities", headers=_viewer()).json()
    assert body["available"] is True
    assert body["source_run"]["calculation_type"] == "criticality"
    assert body["total_count"] == 2
    a = body["activities"][0]
    assert "computed_total_float" in a and "computed_criticality_class" in a
    # No source-export fields leak into the computed activity view.
    for forbidden in ("is_critical", "source_critical_flag", "source_driving_path_flag", "total_float", "free_float"):
        assert forbidden not in a


def test_cpm_activities_prefers_criticality_after_import_commit(tmp_path: Path) -> None:
    client, svk, _ = _client(tmp_path)
    body = client.get(f"/api/schedules/versions/{svk}/cpm/activities", headers=_viewer()).json()
    assert body["available"] is True
    assert body["source_run"]["calculation_type"] == "criticality"


def test_cpm_activities_available_after_import_commit(tmp_path: Path) -> None:
    client, svk, _ = _client(tmp_path)
    body = client.get(f"/api/schedules/versions/{svk}/cpm/activities", headers=_viewer()).json()
    assert body["available"] is True
    assert body["total_count"] == 2


# --------------------------------------------------------------------------- longest path


def test_cpm_longest_path(tmp_path: Path) -> None:
    client, svk, db = _client(tmp_path)
    _run_chain(db, svk)
    body = client.get(f"/api/schedules/versions/{svk}/cpm/longest-path", headers=_viewer()).json()
    assert body["available"] is True
    assert body["path"]["path_type"] == "longest_path"
    assert [a["activity_id"] for a in body["activities"]] == ["A1000", "A1010"]


def test_cpm_longest_path_available_after_import_commit(tmp_path: Path) -> None:
    client, svk, _ = _client(tmp_path)
    resp = client.get(f"/api/schedules/versions/{svk}/cpm/longest-path", headers=_viewer())
    assert resp.status_code == 200
    assert resp.json()["available"] is True


# --------------------------------------------------------------------------- diagnostics


def test_cpm_diagnostics_by_calculation_type(tmp_path: Path) -> None:
    client, svk, db = _client(tmp_path)
    _run_chain(db, svk)
    body = client.get(f"/api/schedules/versions/{svk}/cpm/diagnostics", headers=_viewer()).json()
    assert "diagnostics" in body
    if body["diagnostics"]:
        assert "calculation_type" in body["diagnostics"][0]
        assert "severity" in body["diagnostics"][0]


# --------------------------------------------------------------------------- guarantees


def test_cpm_endpoints_are_read_only(tmp_path: Path) -> None:
    client, svk, db = _client(tmp_path)
    _run_chain(db, svk)
    from hb_assistant.store.schedule_cpm_repository import ScheduleCpmDiagnosticsRepository

    repo = ScheduleCpmDiagnosticsRepository(db_path=db)
    runs_before = repo.list_runs(svk)
    client.get(f"/api/schedules/versions/{svk}/cpm/summary", headers=_viewer())
    client.get(f"/api/schedules/versions/{svk}/cpm/activities", headers=_viewer())
    client.get(f"/api/schedules/versions/{svk}/cpm/longest-path", headers=_viewer())
    client.get(f"/api/schedules/versions/{svk}/cpm/diagnostics", headers=_viewer())
    assert repo.list_runs(svk) == runs_before  # no runs created/mutated by reads


def test_cpm_summary_measurable_after_import_commit(tmp_path: Path) -> None:
    client, svk, _ = _client(tmp_path)
    body = client.get(f"/api/schedules/versions/{svk}/cpm/summary", headers=_viewer()).json()
    assert body["dcma_critical_path"]["measurable"] is True
