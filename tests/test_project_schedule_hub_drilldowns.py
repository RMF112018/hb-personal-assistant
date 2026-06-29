"""Drilldown endpoint tests for Project Schedule Hub Phase 2."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from hb_assistant.construction.analytics.project_schedule_summary_service import (
    ProjectScheduleSummaryService,
)
from hb_assistant.store.migrator import SQLiteMigrator
from tests.schedule_project_test_helpers import seed_procore_ep_project
from tests.test_project_schedule_hub_api import _seed_comparable_versions, _seed_xer_change_impact_comparison


def _fresh_db(tmp_path: Path) -> Path:
    db = tmp_path / "drilldown.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    return db


def test_drilldown_count_reconciles_with_summary(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_xer_change_impact_comparison(db)
    service = ProjectScheduleSummaryService(db_path=str(db))
    summary = service.build_summary("tropical", as_of=date(2026, 7, 3))
    expected = summary["change_impact"]["direct_remaining_changes"]["summary"]["finish_moved_later_count"]
    drilldown = service.build_drilldown(
        "tropical",
        drilldown_type="remaining_later",
        limit=100,
        offset=0,
        as_of=date(2026, 7, 3),
    )
    assert drilldown["count"] == expected
    assert drilldown["count"] >= 2


def test_driver_drilldown_lists_candidates(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_comparable_versions(db)
    service = ProjectScheduleSummaryService(db_path=str(db))
    page = service.build_driver_drilldown(
        "tropical",
        drilldown_type="drivers",
        limit=10,
        offset=0,
        as_of=date(2026, 7, 3),
    )
    assert page.get("available") is True
    assert page["drilldown_type"] == "drivers"


def test_drilldown_pagination_and_limit(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_comparable_versions(db)
    service = ProjectScheduleSummaryService(db_path=str(db))
    page = service.build_drilldown("tropical", drilldown_type="finish_changed", limit=1, offset=0)
    assert page["limit"] == 1
    assert len(page["items"]) <= 1