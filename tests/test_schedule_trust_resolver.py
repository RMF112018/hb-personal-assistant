"""Schedule trust resolver tests for Project Schedule Hub Phase 2."""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from hb_assistant.construction.analytics.project_schedule_summary_service import (
    ProjectScheduleSummaryService,
)
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.project_schedule_hub_repository import (
    MEMBERSHIP_EXCLUDED,
    ProjectScheduleHubRepository,
)
from tests.schedule_project_test_helpers import seed_procore_ep_project
from tests.test_project_schedule_hub_api import _seed_comparable_versions, _seed_unrelated_future_version


def _fresh_db(tmp_path: Path) -> Path:
    db = tmp_path / "trust.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    return db


def test_unrelated_future_import_does_not_become_current(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_comparable_versions(db)
    _seed_unrelated_future_version(db)

    body = ProjectScheduleSummaryService(db_path=str(db)).build_summary(
        "tropical", as_of=date(2026, 7, 3)
    )

    assert body["current_schedule"]["friendly_label"] == "TWNU19"
    assert body["schedule_trust"]["status"] in {"trusted", "review_required", "unknown"}


def test_excluded_import_is_ignored_by_resolver(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    _seed_comparable_versions(db)
    _seed_unrelated_future_version(db)
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            INSERT INTO project_schedule_series_membership (
              membership_id, project_key, schedule_version_key, import_id,
              membership_status, review_reason
            ) VALUES (
              'psm-excluded', 'tropical', 'tropical|S1|2026-07-01', 'imp-current',
              'excluded', 'operator_excluded'
            )
            """
        )
        conn.commit()

    body = ProjectScheduleSummaryService(db_path=str(db)).build_summary(
        "tropical", as_of=date(2026, 7, 3)
    )

    assert body["current_schedule"]["friendly_label"] == "TWNU18"


def test_series_membership_persists_excluded_status(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    repo = ProjectScheduleHubRepository(db_path=str(db))
    row = repo.upsert_membership(
        project_key="tropical",
        schedule_version_key="tropical|S1|2026-07-01",
        import_id="imp-current",
        membership_status=MEMBERSHIP_EXCLUDED,
        review_reason="test_exclusion",
    )
    assert row["membership_status"] == MEMBERSHIP_EXCLUDED