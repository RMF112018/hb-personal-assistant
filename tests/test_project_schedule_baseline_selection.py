"""Baseline selection tests for Project Schedule Hub Phase 2."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from hb_assistant.construction.analytics.project_schedule_summary_service import (
    ProjectScheduleSummaryService,
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
    assert baseline["status"] == "ready"
    assert baseline["comparison"]["comparison_basis"] == "resolved_finish_date"
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