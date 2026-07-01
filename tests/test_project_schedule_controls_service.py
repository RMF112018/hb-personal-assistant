"""Phase 6 schedule controls analytics tests."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.construction.analytics.project_schedule_controls_service import (
    ProjectScheduleControlsService,
)
from hb_assistant.construction.analytics.project_schedule_narrative_qa import validate_controls_text
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.schedule_cpm_import_observability_repository import (
    ScheduleCpmImportObservabilityRepository,
)
from tests.schedule_project_test_helpers import seed_procore_ep_project
from tests.test_project_schedule_review_workbench import _seed_driver_chain, _viewer


def _fresh_db(tmp_path: Path) -> Path:
    db = tmp_path / "controls-phase6.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    return db


def _seed_cpm_obs(db: Path, *, schedule_version_key: str, import_id: str, status: str = "success") -> None:
    ScheduleCpmImportObservabilityRepository(db_path=str(db)).upsert(
        import_id=import_id,
        schedule_version_key=schedule_version_key,
        package_id="pkg-controls",
        trigger_source="import_commit",
        canonical_input_activity_count=8,
        canonical_input_relationship_count=6,
        graph_node_count=8,
        graph_edge_count=6,
        status=status,
        started_at="2026-07-01T10:00:00Z",
        finished_at="2026-07-01T10:00:05Z",
        duration_ms=5000,
        warning_count=1 if status == "success" else 0,
        error_count=1 if status == "failed" else 0,
        failure_code="cpm_failed" if status == "failed" else None,
        cpm_run_id="cpm-run-controls",
    )


def test_controls_unavailable_when_no_schedule(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    payload = ProjectScheduleControlsService(db_path=str(db)).build_controls("tropical")
    assert payload["available"] is False
    assert payload["reason"] == "no_schedule"


def test_controls_respects_as_of_historical_context(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    svc = ProjectScheduleControlsService(db_path=str(db))
    latest = svc.build_controls("tropical", as_of=date(2026, 7, 3), include_technical=True)
    historical = svc.build_controls("tropical", as_of=date(2026, 6, 15), include_technical=True)
    assert latest["available"] is True
    assert historical["available"] is True
    assert latest["schedule_version_key"] != historical["schedule_version_key"]


def test_controls_prior_update_basis_includes_top_controls(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    _seed_cpm_obs(db, schedule_version_key="tropical|S1|2026-07-01", import_id="imp-current")
    payload = ProjectScheduleControlsService(db_path=str(db)).build_controls(
        "tropical",
        as_of=date(2026, 7, 3),
        comparison_basis="prior_update",
    )
    assert payload["available"] is True
    assert payload["comparison_basis"] == "prior_update"
    assert payload["advisory_posture"] == "sequence_cues_not_causation"
    assert len(payload["top_controls"]) >= 1
    assert payload["sections"]["movement"]["available"] is True


def test_controls_baseline_unavailable_returns_reason(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    payload = ProjectScheduleControlsService(db_path=str(db)).build_controls(
        "tropical",
        as_of=date(2026, 7, 3),
        comparison_basis="baseline",
    )
    assert payload["available"] is False
    assert "baseline" in str(payload["reason"])


def test_controls_includes_cpm_observability_when_present(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    _seed_cpm_obs(db, schedule_version_key="tropical|S1|2026-07-01", import_id="imp-current")
    payload = ProjectScheduleControlsService(db_path=str(db)).build_controls(
        "tropical",
        as_of=date(2026, 7, 3),
    )
    cpm = payload["sections"]["cpm_observability"]
    assert cpm["available"] is True
    assert "CPM recompute" in cpm["headline"]
    assert payload["provenance"]["cpm_run_id"] == "cpm-run-controls"
    assert payload["provenance"]["canonical_input_activity_count"] == 8


def test_controls_top_controls_sorted_deterministically(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    svc = ProjectScheduleControlsService(db_path=str(db))
    first = svc.build_controls("tropical", as_of=date(2026, 7, 3))
    second = svc.build_controls("tropical", as_of=date(2026, 7, 3))
    assert [row["control_id"] for row in first["top_controls"]] == [
        row["control_id"] for row in second["top_controls"]
    ]


def test_controls_language_qa_passes_for_fixture_payload(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    payload = ProjectScheduleControlsService(db_path=str(db)).build_controls(
        "tropical",
        as_of=date(2026, 7, 3),
    )
    qa = payload["controls_language_qa"]
    assert qa["passed"] is True
    assert validate_controls_text(payload)["passed"] is True


def test_controls_language_qa_fails_on_forbidden_terms() -> None:
    payload = {
        "summary": {"headline": "Owner-caused delay confirmed.", "supporting_points": []},
        "top_controls": [],
        "sections": {},
    }
    qa = validate_controls_text(payload)
    assert qa["passed"] is False
    assert any(v["code"] == "forbidden_term" for v in qa["violations"])


def test_controls_links_include_review_and_driver_paths(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    payload = ProjectScheduleControlsService(db_path=str(db)).build_controls(
        "tropical",
        as_of=date(2026, 7, 3),
    )
    control = payload["top_controls"][0]
    assert control["links"]["schedule_hub"] == "/projects/tropical/schedule"
    if control["links"].get("driver_detail"):
        assert "basis=prior_update" in control["links"]["driver_detail"]
        assert "as_of=2026-07-03" in control["links"]["driver_detail"]


def test_controls_api_route_forwards_as_of_and_basis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    app = create_app(db_path=str(db))
    client = TestClient(app)
    calls: list[dict[str, object]] = []
    original = ProjectScheduleControlsService.build_controls

    def _spy(self, project_key: str, *, as_of=None, comparison_basis="prior_update", include_technical=False):
        calls.append({"project_key": project_key, "as_of": as_of, "comparison_basis": comparison_basis})
        return original(self, project_key, as_of=as_of, comparison_basis=comparison_basis)

    monkeypatch.setattr(ProjectScheduleControlsService, "build_controls", _spy)
    response = client.get(
        "/api/projects/tropical/schedule/controls?as_of=2026-07-03&comparison_basis=prior_update",
        headers=_viewer(),
    )
    assert response.status_code == 200
    assert calls == [
        {
            "project_key": "tropical",
            "as_of": date(2026, 7, 3),
            "comparison_basis": "prior_update",
        }
    ]


def test_build_schedule_hub_context_public_wrapper(tmp_path: Path) -> None:
    from hb_assistant.construction.analytics.project_schedule_summary_service import (
        ProjectScheduleSummaryService,
    )

    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    summary = ProjectScheduleSummaryService(db_path=str(db))
    context = summary.build_schedule_hub_context("tropical", as_of=date(2026, 7, 3))
    assert context is not None
    assert context["schedule_version_key"] == "tropical|S1|2026-07-01"
    assert context.get("schedule_data_date")
