"""Baseline selection tests for Project Schedule Hub Phase 2."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient

from hb_assistant.construction.analytics.api import create_app
from hb_assistant.construction.analytics.project_schedule_summary_service import (
    ProjectScheduleSummaryService,
)
from hb_assistant.construction.analytics.project_schedule_trend_aggregation_service import (
    ProjectScheduleTrendAggregationService,
)
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.project_schedule_hub_repository import ProjectScheduleHubRepository
from tests.schedule_project_test_helpers import seed_procore_ep_project
from tests.test_project_schedule_hub_api import _seed_comparable_versions


def _fresh_db(tmp_path: Path) -> Path:
    db = tmp_path / "baseline.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    return db


def _viewer() -> dict[str, str]:
    return {"X-HB-UI-Role": "viewer"}


def _operator() -> dict[str, str]:
    return {"X-HB-UI-Role": "operator"}


def _add_duration_facts(db: Path) -> None:
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            UPDATE procore_ep_schedule_activities
            SET duration_remaining='5'
            WHERE schedule_version_key='tropical|S1|2026-07-01'
              AND activity_id IN ('A200', 'A300')
            """
        )
        conn.execute(
            """
            UPDATE procore_ep_schedule_activities
            SET duration_remaining='8'
            WHERE schedule_version_key='tropical|S1|2026-06-01'
              AND activity_id='A200'
            """
        )
        conn.commit()


def test_baseline_selection_appears_in_hub_summary(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_comparable_versions(db)
    repo = ProjectScheduleHubRepository(db_path=str(db))
    repo.set_baseline_selection(
        project_key="tropical",
        current_schedule_version_key="tropical|S1|2026-07-01",
        selected_baseline_schedule_version_key="tropical|S1|2026-06-01",
        selected_by_operator="operator",
        selection_note="Compare against TWNU18 baseline",
    )

    body = ProjectScheduleSummaryService(db_path=str(db)).build_summary(
        "tropical", as_of=date(2026, 7, 3)
    )

    baseline = body["baseline_summary"]
    assert baseline["selected_baseline_available"] is True
    assert baseline["status"] == "recompute_required"
    assert baseline["recompute_required"] is True
    assert baseline["readiness"]["blockers"] == ["duration_basis_unavailable", "current_duration_unavailable", "baseline_duration_unavailable"]
    assert baseline["comparison"] == {}
    assert body["previous_update"]["available"] is True
    assert body["change_impact"]["available"] is True


def test_no_baseline_selection_prompts_selection(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_comparable_versions(db)

    body = ProjectScheduleSummaryService(db_path=str(db)).build_summary(
        "tropical", as_of=date(2026, 7, 3)
    )

    assert body["baseline_summary"]["status"] == "no_selection"
    assert body["readiness"]["baseline_unavailable"]["required"] is True


def test_selected_baseline_routes_read_persist_and_supersede(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_comparable_versions(db)
    client = TestClient(create_app(db_path=str(db)))

    read = client.get("/api/projects/tropical/schedule/baseline", headers=_viewer())
    assert read.status_code == 200
    assert read.json()["status"] == "no_selection"

    viewer_put = client.put(
        "/api/projects/tropical/schedule/baseline",
        headers=_viewer(),
        json={
            "current_schedule_version_key": "tropical|S1|2026-07-01",
            "selected_baseline_schedule_version_key": "tropical|S1|2026-06-01",
        },
    )
    assert viewer_put.status_code == 403
    assert viewer_put.json() == {"detail": "operator_role_required"}

    first = client.put(
        "/api/projects/tropical/schedule/baseline",
        headers=_operator(),
        json={
            "current_schedule_version_key": "tropical|S1|2026-07-01",
            "selected_baseline_schedule_version_key": "tropical|S1|2026-06-01",
            "selection_note": "Owner-approved comparison baseline",
        },
    )
    assert first.status_code == 200
    body = first.json()
    assert body["selected_baseline_version_key"] == "tropical|S1|2026-06-01"
    assert body["status"] == "recompute_required"
    assert body["prior_update_comparison"] == {"basis": "prior_update", "separate": True}

    _add_duration_facts(db)
    second = client.put(
        "/api/projects/tropical/schedule/baseline",
        headers=_operator(),
        json={
            "current_schedule_version_key": "tropical|S1|2026-07-01",
            "selected_baseline_schedule_version_key": "tropical|S1|2026-06-01",
            "selection_note": "Refresh after duration facts",
        },
    )
    assert second.status_code == 200
    assert second.json()["status"] == "ready"

    with sqlite3.connect(db) as conn:
        statuses = [
            row[0]
            for row in conn.execute(
                """
                SELECT selection_status FROM project_schedule_baseline_selections
                WHERE project_key='tropical'
                ORDER BY created_at
                """
            ).fetchall()
        ]
    assert statuses == ["superseded", "active"]


def test_selected_baseline_route_validation_errors(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_comparable_versions(db)
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            INSERT INTO schedule_file_imports (
              import_id, project_key, source_type, source_format, import_status,
              activity_count, relationship_count, cost_loaded_status,
              schedule_version_key, source_filename_redacted, created_at
            ) VALUES ('imp-other', 'other', 'xer', 'primavera_xer', 'committed',
              0, 0, 'not_cost_loaded', 'other|S9|2026-06-01', 'OTHER.xer', '2026-06-01')
            """
        )
        conn.execute(
            """
            INSERT INTO schedule_file_imports (
              import_id, project_key, source_type, source_format, import_status,
              activity_count, relationship_count, cost_loaded_status,
              schedule_version_key, source_filename_redacted, created_at
            ) VALUES ('imp-future', 'tropical', 'xer', 'primavera_xer', 'committed',
              0, 0, 'not_cost_loaded', 'tropical|S1|2026-08-01', 'FUTURE.xer', '2026-08-01')
            """
        )
        conn.execute(
            """
            INSERT INTO schedule_file_imports (
              import_id, project_key, source_type, source_format, import_status,
              activity_count, relationship_count, cost_loaded_status,
              schedule_version_key, source_filename_redacted, created_at
            ) VALUES ('imp-other-identity', 'tropical', 'xer', 'primavera_xer', 'committed',
              0, 0, 'not_cost_loaded', 'tropical|S2|2026-06-15', 'OTHERID.xer', '2026-06-15')
            """
        )
        conn.execute(
            """
            INSERT INTO schedule_version_identity_matches (
              match_id, schedule_identity_key, schedule_version_key, import_id, project_key,
              source_format, activity_count, relationship_count, wbs_count,
              match_type, match_status, match_rule, confidence_score, requires_review
            ) VALUES ('match-other-identity', 'identity-other', 'tropical|S2|2026-06-15',
              'imp-other-identity', 'tropical', 'primavera_xer',
              0, 0, 0, 'seed', 'resolved', 'seed', '1.00', 0)
            """
        )
        conn.commit()

    client = TestClient(create_app(db_path=str(db)))
    cases = [
        ({}, "baseline_selection_required"),
        (
            {
                "current_schedule_version_key": "tropical|S1|2026-07-01",
                "selected_baseline_schedule_version_key": "tropical|S1|2026-07-01",
            },
            "baseline_must_differ_from_current",
        ),
        (
            {
                "current_schedule_version_key": "missing",
                "selected_baseline_schedule_version_key": "tropical|S1|2026-06-01",
            },
            "invalid_current_schedule_version",
        ),
        (
            {
                "current_schedule_version_key": "tropical|S1|2026-07-01",
                "selected_baseline_schedule_version_key": "missing",
            },
            "invalid_selected_baseline_version",
        ),
        (
            {
                "current_schedule_version_key": "tropical|S1|2026-07-01",
                "selected_baseline_schedule_version_key": "other|S9|2026-06-01",
            },
            "baseline_project_mismatch",
        ),
        (
            {
                "current_schedule_version_key": "tropical|S1|2026-07-01",
                "selected_baseline_schedule_version_key": "tropical|S1|2026-08-01",
            },
            "baseline_must_not_be_future_of_current",
        ),
        (
            {
                "current_schedule_version_key": "tropical|S1|2026-07-01",
                "selected_baseline_schedule_version_key": "tropical|S2|2026-06-15",
            },
            "baseline_identity_mismatch",
        ),
    ]
    for payload, code in cases:
        response = client.put("/api/projects/tropical/schedule/baseline", headers=_operator(), json=payload)
        assert response.status_code == 400
        assert response.json() == {"detail": code}


def test_schedule_compression_ratio_readiness_states(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_comparable_versions(db)
    service = ProjectScheduleTrendAggregationService(db_path=str(db))

    try:
        service.build_trend("tropical", "schedule_compression_ratio", as_of=date(2026, 7, 3))
    except ValueError as exc:
        assert str(exc) == "metric_not_trend_ready"
    else:  # pragma: no cover
        raise AssertionError("schedule_compression_ratio should require selected baseline")

    repo = ProjectScheduleHubRepository(db_path=str(db))
    repo.set_baseline_selection(
        project_key="tropical",
        current_schedule_version_key="tropical|S1|2026-07-01",
        selected_baseline_schedule_version_key="tropical|S1|2026-06-01",
        selected_by_operator="operator",
    )
    blocked = service.build_trend("tropical", "schedule_compression_ratio", as_of=date(2026, 7, 3))
    assert blocked["available"] is False
    assert blocked["recompute_required"] is True
    assert blocked["reason"] == "selected_baseline_recompute_required"

    _add_duration_facts(db)
    ready = service.build_trend("tropical", "schedule_compression_ratio", as_of=date(2026, 7, 3))
    assert ready["available"] is True
    assert ready["recompute_required"] is False
    assert ready["points"][0]["matched_activity_count"] == 2
    assert ready["readiness"]["usable_duration_activity_count"] == 1
    assert ready["points"][0]["comparison_basis"] == "selected_baseline"
    assert ready["points"][0]["compression_ratio"] == 60.0
