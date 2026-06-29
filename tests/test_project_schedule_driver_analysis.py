"""Phase 3 schedule driver analysis tests."""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from hb_assistant.construction.analytics.project_schedule_driver_analysis_service import (
    ProjectScheduleDriverAnalysisService,
)
from hb_assistant.store.migrator import SQLiteMigrator
from tests.schedule_project_test_helpers import seed_procore_ep_project


def _fresh_db(tmp_path: Path) -> Path:
    db = tmp_path / "driver.db"
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
        conn.commit()


def test_driver_analysis_ranks_chain_driver(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    service = ProjectScheduleDriverAnalysisService(db_path=str(db))
    analysis = service.build_analysis(
        project_key="tropical",
        current_key="tropical|S1|2026-07-01",
        previous_key="tropical|S1|2026-06-01",
        diff_id=None,
        milestones={
            "items": [
                {
                    "activity_id": "MS-1",
                    "activity_name": "Substantial completion",
                    "movement_days": 7,
                }
            ]
        },
    )
    assert analysis["available"] is True
    assert analysis["advisory_posture"] == "sequence_cues_not_causation"
    drivers = analysis["top_drivers"]
    assert drivers
    top = drivers[0]
    assert top["activity_id"] == "DRV-A"
    assert top["downstream_moved_later_count"] >= 2
    assert top["milestone_touch_count"] >= 1
    assert "sequence cue" in top["sequence_cue"].lower()


def test_driver_narrative_uses_advisory_language(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    service = ProjectScheduleDriverAnalysisService(db_path=str(db))
    analysis = service.build_analysis(
        project_key="tropical",
        current_key="tropical|S1|2026-07-01",
        previous_key="tropical|S1|2026-06-01",
        diff_id=None,
        milestones={"items": [{"activity_id": "MS-1", "activity_name": "Substantial completion", "movement_days": 7}]},
    )
    narrative = service.build_narrative(analysis)
    text = narrative["primary_driver_narrative"].lower()
    assert "appears connected" in text
    assert "review this sequence first" in text
    assert "causation" not in text


def test_impacted_successors_drilldown_requires_driver_id(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    service = ProjectScheduleDriverAnalysisService(db_path=str(db))
    try:
        service.list_drilldown(
            project_key="tropical",
            drilldown_type="impacted_successors",
            current_key="tropical|S1|2026-07-01",
            previous_key="tropical|S1|2026-06-01",
            diff_id=None,
            driver_activity_id=None,
        )
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert str(exc) == "driver_activity_id_required"


def test_impacted_successors_drilldown_returns_chain(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_driver_chain(db)
    service = ProjectScheduleDriverAnalysisService(db_path=str(db))
    page = service.list_drilldown(
        project_key="tropical",
        drilldown_type="impacted_successors",
        current_key="tropical|S1|2026-07-01",
        previous_key="tropical|S1|2026-06-01",
        diff_id=None,
        driver_activity_id="DRV-A",
        limit=10,
        offset=0,
    )
    assert page["count"] >= 2
    ids = {item["activity_id"] for item in page["items"]}
    assert "SUCC-B" in ids or "SUCC-C" in ids