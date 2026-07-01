#!/usr/bin/env python3
"""Seed fixture DB for Phase 18 portfolio dashboard browser evidence."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "subrepos/construction-financial-review/src"))
sys.path.insert(0, str(ROOT))

from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.project_schedule_hub_repository import ProjectScheduleHubRepository
from tests.schedule_project_test_helpers import seed_procore_ep_project
from tests.test_project_schedule_portfolio_review import _seed_current_schedule
from tests.test_project_schedule_review_workbench import _seed_driver_chain

FIXTURE_DB = Path(__file__).resolve().parent / "fixture-phase18-portfolio.db"


def main() -> int:
    if FIXTURE_DB.exists():
        FIXTURE_DB.unlink()
    SQLiteMigrator(db_path=str(FIXTURE_DB)).apply()
    seed_procore_ep_project(FIXTURE_DB, project_key="tropical", display_name="Tropical Wind")
    seed_procore_ep_project(FIXTURE_DB, project_key="palm", display_name="Palm Shores", project_id="9002")
    seed_procore_ep_project(FIXTURE_DB, project_key="reef", display_name="Reef Tower", project_id="9003")
    _seed_driver_chain(FIXTURE_DB)
    _seed_current_schedule(FIXTURE_DB, project_key="reef", version_suffix="2026-01-01", import_id="imp-reef-stale")
    repo = ProjectScheduleHubRepository(db_path=str(FIXTURE_DB))
    repo.upsert_review_item(
        project_key="tropical",
        schedule_version_key="tropical|S1|2026-07-01",
        stable_item_key="driver:DRV-A",
        item_type="driver",
        item_title="Driver Activity",
        priority=90,
        evidence={"materializable": True},
        source_activity_id="DRV-A",
    )
    print(FIXTURE_DB)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
