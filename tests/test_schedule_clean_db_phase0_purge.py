"""Purge planner tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hb_assistant.construction.schedule_clean_db.purge import run_tropical_purge
from hb_assistant.construction.schedule_clean_db.purge_dependency_map import (
    SUPPLEMENTAL_DELETE_EDGES,
    topological_delete_order,
)
from hb_assistant.store.migrator import SQLiteMigrator
from tests.schedule_project_test_helpers import seed_procore_ep_project
from tests.test_project_schedule_hub_api import _seed_comparable_versions


def _db(tmp_path: Path) -> Path:
    db = tmp_path / "purge.db"
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Wind")
    seed_procore_ep_project(db, project_key="other", display_name="Other Project")
    _seed_comparable_versions(db)
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            INSERT INTO schedule_file_imports (
              import_id, project_key, source_type, source_format, import_status,
              activity_count, relationship_count, cost_loaded_status,
              schedule_version_key, source_filename_redacted, created_at
            ) VALUES ('imp-other', 'other', 'xer', 'primavera_xer', 'committed',
              1, 0, 'not_cost_loaded', 'other|S1|2026-07-01', 'other.xer', '2026-07-01')
            """
        )
        conn.commit()
    return db


def test_supplemental_dependency_map_covers_review_events() -> None:
    assert ("project_schedule_review_events", "project_schedule_review_items") in SUPPLEMENTAL_DELETE_EDGES


def test_topological_order_children_first() -> None:
    tables = {"project_schedule_review_events", "project_schedule_review_items", "schedule_file_imports"}
    order = topological_delete_order(tables, [])
    assert order.index("project_schedule_review_events") < order.index("project_schedule_review_items")


def test_dry_run_does_not_mutate(tmp_path: Path) -> None:
    db = _db(tmp_path)
    before = sqlite3.connect(db).execute("SELECT COUNT(*) FROM schedule_file_imports WHERE project_key='tropical'").fetchone()[0]
    result = run_tropical_purge(str(db), project_key="tropical", dry_run=True, apply=False)
    after = sqlite3.connect(db).execute("SELECT COUNT(*) FROM schedule_file_imports WHERE project_key='tropical'").fetchone()[0]
    assert before == after == 2
    assert result["deleted_counts"] == {}


def test_apply_purges_tropical_not_other(tmp_path: Path) -> None:
    db = _db(tmp_path)
    result = run_tropical_purge(str(db), project_key="tropical", dry_run=False, apply=True)
    with sqlite3.connect(db) as conn:
        tropical = conn.execute(
            "SELECT COUNT(*) FROM schedule_file_imports WHERE project_key='tropical'"
        ).fetchone()[0]
        other = conn.execute(
            "SELECT COUNT(*) FROM schedule_file_imports WHERE project_key='other'"
        ).fetchone()[0]
        catalog = conn.execute(
            "SELECT COUNT(*) FROM procore_ep_projects WHERE project_key='tropical'"
        ).fetchone()[0]
    assert tropical == 0
    assert other == 1
    assert catalog >= 1
    assert result["remaining_tropical_schedule_records"] == 0
    for table, before in result["before_counts"].items():
        assert result["after_counts"].get(table) == 0
        assert before > 0


def test_live_db_path_rejected_by_guard_script(tmp_path: Path) -> None:
    from hb_assistant.config.path_policy import PathPolicy

    live = str(PathPolicy().get_db_path())
    with pytest.raises(ValueError):
        from hb_assistant.construction.schedule_clean_db.guards import assert_clean_copy_path

        assert_clean_copy_path(live, allow_custom_copy_path=True)
