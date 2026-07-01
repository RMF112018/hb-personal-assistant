"""Phase 16 workbench quality preview cue tests."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from hb_assistant.construction.analytics.project_schedule_review_cue_service import (
    ProjectScheduleReviewCueService,
)
from hb_assistant.store.migrator import SQLiteMigrator
from tests.schedule_project_test_helpers import seed_procore_ep_project
from tests.test_project_schedule_quality_controls import _seed_completed_quality
from tests.test_project_schedule_review_workbench import _seed_driver_chain


def test_quality_metric_preview_cues_are_project_level(tmp_path: Path) -> None:
    db = tmp_path / "wb-quality.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    _seed_driver_chain(db)
    svk = "tropical|S1|2026-07-01"
    _seed_completed_quality(str(db), schedule_version_key=svk)
    cues = ProjectScheduleReviewCueService(db_path=str(db)).collect_review_cues(
        project_key="tropical",
        schedule_version_key=svk,
        as_of_date=date(2026, 7, 3),
        comparison_basis="prior_update",
        include_activity_metric_cues=True,
    )
    preview = [c for c in cues if str(c.get("source_metric_key")) == "schedule_quality_metrics"]
    assert preview, "expected project-level quality preview cues"
    assert all(not c.get("source_activity_id") for c in preview)
    stable = {c.get("stable_item_key") for c in preview}
    assert len(stable) == len(preview)


def test_quality_preview_cue_copy_is_pm_safe(tmp_path: Path) -> None:
    db = tmp_path / "wb-quality-qa.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    _seed_driver_chain(db)
    svk = "tropical|S1|2026-07-01"
    _seed_completed_quality(str(db), schedule_version_key=svk)
    cues = ProjectScheduleReviewCueService(db_path=str(db)).collect_review_cues(
        project_key="tropical",
        schedule_version_key=svk,
        as_of_date=date(2026, 7, 3),
        comparison_basis="prior_update",
        include_activity_metric_cues=True,
    )
    blob = json.dumps(
        [
            {
                "item_title": c.get("item_title"),
                "cue_summary": c.get("cue_summary"),
                "stable_item_key": c.get("stable_item_key"),
            }
            for c in cues
        ]
    ).lower()
    assert "schedule_version_key" not in blob
    assert "compensable" not in blob
