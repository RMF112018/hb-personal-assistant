"""Phase 4 schedule review workbench, memo export, and driver detail tests."""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from hb_assistant.construction.analytics import create_app
from hb_assistant.construction.analytics.project_schedule_driver_analysis_service import (
    ProjectScheduleDriverAnalysisService,
)
from hb_assistant.construction.analytics.project_schedule_memo_service import ProjectScheduleMemoService
from hb_assistant.construction.analytics.project_schedule_review_service import ProjectScheduleReviewService
from hb_assistant.construction.analytics.project_schedule_summary_service import ProjectScheduleSummaryService
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.project_schedule_hub_repository import REVIEW_WATCHING, ProjectScheduleHubRepository
from tests.schedule_project_test_helpers import seed_procore_ep_project


def _viewer() -> dict[str, str]:
    return {"X-HB-UI-Role": "viewer"}


def _operator() -> dict[str, str]:
    return {"X-HB-UI-Role": "operator"}


def _fresh_db(tmp_path: Path) -> Path:
    db = tmp_path / "phase4.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    return db


def _seed_driver_chain(db: Path) -> None:
    with sqlite3.connect(db) as conn:
        for import_id, version_key, created_at in (
            ("imp-prior", "tropical|S1|2026-06-01", "2026-06-01T10:00:00Z"),
            ("imp-current", "tropical|S1|2026-07-01", "2026-07-01T10:00:00Z"),
        ):
            conn.execute(
                """
                INSERT INTO schedule_file_imports (
                  import_id, project_key, source_type, source_format, import_status,
                  activity_count, relationship_count, cost_loaded_status,
                  schedule_version_key, source_filename_redacted, created_at
                ) VALUES (?, 'tropical', 'xer', 'primavera_xer', 'committed',
                  4, 3, 'not_cost_loaded', ?, ?, ?)
                """,
                (import_id, version_key, f"{import_id}.xer", created_at),
            )
        activities = [
            ("tropical|S1|2026-06-01", "imp-prior", "DRV-A", "Driver Activity", "2026-07-01", "2026-07-10", "WBS-A", "10", 0),
            ("tropical|S1|2026-07-01", "imp-current", "DRV-A", "Driver Activity", "2026-07-11", "2026-07-20", "WBS-A", "10", 0),
            ("tropical|S1|2026-06-01", "imp-prior", "SUCC-B", "Successor B", "2026-07-11", "2026-07-20", "WBS-A", "5", 0),
            ("tropical|S1|2026-07-01", "imp-current", "SUCC-B", "Successor B", "2026-07-21", "2026-07-30", "WBS-A", "5", 0),
            ("tropical|S1|2026-06-01", "imp-prior", "SUCC-C", "Successor C", "2026-07-21", "2026-07-30", "WBS-A", "0", 0),
            ("tropical|S1|2026-07-01", "imp-current", "SUCC-C", "Successor C", "2026-07-31", "2026-08-09", "WBS-A", "0", 0),
            ("tropical|S1|2026-06-01", "imp-prior", "MS-1", "Substantial completion", "2026-08-01", "2026-08-05", "WBS-M", "0", 1),
            ("tropical|S1|2026-07-01", "imp-current", "MS-1", "Substantial completion", "2026-08-06", "2026-08-12", "WBS-M", "0", 1),
        ]
        for row in activities:
            conn.execute(
                """
                INSERT INTO procore_ep_schedule_activities (
                  project_key, schedule_id, schedule_version_key, import_id,
                  source_type, source_format, activity_id, activity_name,
                  start_date, finish_date, wbs_code, duration_remaining, is_milestone
                ) VALUES ('tropical', 'S1', ?, ?, 'xer', 'primavera_xer', ?, ?, ?, ?, ?, ?, ?)
                """,
                row,
            )
        for version_key, import_id in (
            ("tropical|S1|2026-06-01", "imp-prior"),
            ("tropical|S1|2026-07-01", "imp-current"),
        ):
            for pred, succ in (("DRV-A", "SUCC-B"), ("SUCC-B", "SUCC-C"), ("SUCC-C", "MS-1")):
                conn.execute(
                    """
                    INSERT INTO procore_ep_schedule_relationships (
                      project_key, schedule_id, schedule_version_key, import_id,
                      predecessor_activity_id, successor_activity_id, relationship_type
                    ) VALUES ('tropical', 'S1', ?, ?, ?, ?, 'FS')
                    """,
                    (version_key, import_id, pred, succ),
                )
        for import_id, version_key in (
            ("imp-prior", "tropical|S1|2026-06-01"),
            ("imp-current", "tropical|S1|2026-07-01"),
        ):
            conn.execute(
                """
                INSERT OR IGNORE INTO schedule_identities (
                  schedule_identity_key, project_key, identity_status, latest_import_id,
                  latest_schedule_version_key
                ) VALUES ('identity-main', 'tropical', 'active', ?, ?)
                """,
                (import_id, version_key),
            )
            conn.execute(
                """
                INSERT INTO schedule_version_identity_matches (
                  match_id, schedule_identity_key, schedule_version_key, import_id, project_key,
                  source_format, activity_count, relationship_count, wbs_count,
                  match_type, match_status, match_rule, confidence_score, requires_review
                ) VALUES (?, 'identity-main', ?, ?, 'tropical', 'primavera_xer',
                  4, 3, 0, 'seed', 'resolved', 'seed', '1.00', 0)
                """,
                (f"match-{import_id}", version_key, import_id),
            )
        conn.commit()


def test_review_workbench_syncs_and_carries_forward_status(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    repo = ProjectScheduleHubRepository(db_path=str(db))
    review = ProjectScheduleReviewService(db_path=str(db))
    driver = ProjectScheduleDriverAnalysisService(db_path=str(db))
    analysis = driver.build_hub_analysis(
        project_key="tropical",
        current_key="tropical|S1|2026-07-01",
        previous_key="tropical|S1|2026-06-01",
        baseline_key=None,
        diff_id=None,
        milestones={"items": [{"activity_id": "MS-1", "activity_name": "Substantial completion", "movement_days": 7}]},
    )
    first = review.sync_and_list(
        project_key="tropical",
        schedule_version_key="tropical|S1|2026-07-01",
        driver_analysis=analysis,
        milestones={"items": [{"activity_id": "MS-1", "activity_name": "Substantial completion", "movement_days": 7}]},
        remaining_health={"float_pressure": {"negative_float_count": 0, "preview": []}},
        cpm_summary={"critical_path": {"items": []}},
        change_impact={"direct_remaining_changes": {"items": []}},
        remaining_activities=[],
    )
    assert first["summary"]["total_count"] >= 2
    driver_item = next(i for i in first["items"] if i["stable_item_key"] == "driver:DRV-A")
    review.update_item(
        review_item_id=str(driver_item["review_item_id"]),
        review_status=REVIEW_WATCHING,
        pm_notes="watching driver",
        reviewed_by_operator="operator",
    )

    second = review.sync_and_list(
        project_key="tropical",
        schedule_version_key="tropical|S1|2026-07-01",
        driver_analysis=analysis,
        milestones={"items": [{"activity_id": "MS-1", "activity_name": "Substantial completion", "movement_days": 7}]},
        remaining_health={"float_pressure": {"negative_float_count": 0, "preview": []}},
        cpm_summary={"critical_path": {"items": []}},
        change_impact={"direct_remaining_changes": {"items": []}},
        remaining_activities=[],
    )
    carried = next(i for i in second["items"] if i["stable_item_key"] == "driver:DRV-A")
    assert carried["review_status"] == REVIEW_WATCHING
    assert carried["pm_notes"] == "watching driver"
    assert repo.get_review_item(review_item_id=str(carried["review_item_id"])) is not None


def test_driver_detail_returns_side_by_side_path(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    service = ProjectScheduleDriverAnalysisService(db_path=str(db))
    detail = service.build_driver_detail(
        project_key="tropical",
        activity_id="DRV-A",
        current_key="tropical|S1|2026-07-01",
        previous_key="tropical|S1|2026-06-01",
        diff_id=None,
        milestones={"items": [{"activity_id": "MS-1", "activity_name": "Substantial completion", "movement_days": 7}]},
    )
    assert detail["available"] is True
    assert detail["activity"]["finish_delta_days"] == 10
    assert len(detail["downstream_impacts"]) >= 1
    assert "sequence cue" in detail["sequence_cue"].lower()


def test_hub_summary_includes_workbench_and_dual_driver_bases(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    repo = ProjectScheduleHubRepository(db_path=str(db))
    repo.set_baseline_selection(
        project_key="tropical",
        current_schedule_version_key="tropical|S1|2026-07-01",
        selected_baseline_schedule_version_key="tropical|S1|2026-06-01",
        selected_by_operator="operator",
    )
    body = ProjectScheduleSummaryService(db_path=str(db)).build_summary("tropical", as_of=date(2026, 7, 3))
    drivers = body["change_driver_analysis"]
    assert drivers["available"] is True
    assert drivers["prior_update"]["available"] is True
    assert drivers["baseline"]["available"] is True
    assert body["review_workbench"]["available"] is True
    assert body["review_workbench"]["summary"]["total_count"] >= 1


def test_memo_export_markdown_and_html(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    summary = ProjectScheduleSummaryService(db_path=str(db)).build_summary("tropical", as_of=date(2026, 7, 3))
    memo = ProjectScheduleMemoService()
    md = memo.build_export(summary, export_format="markdown")
    html = memo.build_export(summary, export_format="html")
    assert "Schedule Review Memo" in md["body"]
    assert "sequence cues" in md["body"].lower()
    assert "<h1>" in html["body"]
    assert "causation" in html["body"].lower()


def test_review_items_api_and_export(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    monkeypatch.setenv("HB_ASSISTANT_DB_PATH", str(db))
    app = create_app(db_path=str(db))
    from fastapi.testclient import TestClient

    client = TestClient(app)
    summary = client.get("/api/projects/tropical/schedule", headers=_viewer())
    assert summary.status_code == 200
    assert summary.json().get("review_workbench", {}).get("available") is True

    preview = client.get("/api/projects/tropical/schedule/review-items", headers=_viewer())
    assert preview.status_code == 200
    assert preview.json()["available"] is True

    sync = client.post(
        "/api/projects/tropical/schedule/review-items?as_of=2026-07-03",
        headers=_operator(),
    )
    assert sync.status_code == 200
    items = client.get(
        "/api/projects/tropical/schedule/review-items?as_of=2026-07-03",
        headers=_viewer(),
    )
    assert items.status_code == 200
    payload = items.json()
    assert payload["count"] >= 1

    export = client.get("/api/projects/tropical/schedule/export?format=markdown", headers=_viewer())
    assert export.status_code == 200
    assert "Schedule Review Memo" in export.text

    detail = client.get(
        "/api/projects/tropical/schedule/drivers/DRV-A/detail?as_of=2026-07-03",
        headers=_viewer(),
    )
    assert detail.status_code == 200
    assert detail.json()["available"] is True

    persisted = [item for item in payload["items"] if item.get("review_item_id")]
    assert persisted
    first_item = persisted[0]
    patch = client.patch(
        f"/api/projects/tropical/schedule/review-items/{first_item['review_item_id']}",
        headers=_operator(),
        json={"review_status": "reviewed", "pm_notes": "checked"},
    )
    assert patch.status_code == 200
    assert patch.json()["item"]["review_status"] == "reviewed"