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

PURGE_TRACKED_TABLES = (
    "schedule_version_diffs",
    "schedule_version_diff_facts",
    "schedule_version_diff_detail_facts",
    "schedule_version_diff_impact_rollups",
    "schedule_baseline_projects",
    "schedule_baseline_activity_codes",
    "schedule_baseline_udfs",
    "schedule_baseline_wbs",
    "schedule_baseline_activities",
    "schedule_baseline_relationships",
)


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


def _table_counts(db: Path, tables: tuple[str, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    with sqlite3.connect(db) as conn:
        for table in tables:
            try:
                counts[table] = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            except sqlite3.Error:
                counts[table] = -1
    return counts


def _seed_diff_and_baseline_orphans(db: Path) -> None:
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            INSERT INTO schedule_version_diffs (
              project_key, from_schedule_version_key, to_schedule_version_key,
              diff_type, created_at
            ) VALUES ('tropical', 'tropical|S1|2026-06-01', 'tropical|S2|2026-06-02', 'manual', '2026-07-01')
            """
        )
        diff_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        conn.execute(
            """
            INSERT INTO schedule_version_diff_detail_facts (
              detail_id, diff_id, project_key, from_schedule_version_key, to_schedule_version_key,
              identity_safe, comparison_type, change_domain, change_type
            ) VALUES ('det-1', ?, 'tropical', 'tropical|S1|2026-06-01', 'tropical|S2|2026-06-02',
              1, 'manual', 'activity', 'changed')
            """,
            (diff_id,),
        )
        import_row = conn.execute(
            "SELECT import_id, schedule_version_key FROM schedule_file_imports WHERE project_key='tropical' LIMIT 1"
        ).fetchone()
        assert import_row is not None
        import_id, svk = import_row
        conn.execute(
            """
            INSERT INTO schedule_baseline_projects (
              baseline_project_key, package_id, import_id, current_schedule_version_key,
              baseline_project_id, baseline_project_name, created_at
            ) VALUES ('bp-tropical-1', 'pkg-test', ?, ?, '815', 'TWNU07', '2026-07-01')
            """,
            (import_id, svk),
        )
        conn.execute(
            """
            INSERT INTO schedule_baseline_activity_codes (
              baseline_project_key, activity_id, code_type, code_value
            ) VALUES ('bp-tropical-1', 'ac-1', 'Resp', 'GC')
            """
        )
        conn.execute(
            """
            INSERT INTO schedule_baseline_activity_crosswalk (
              crosswalk_id, current_schedule_version_key, baseline_project_key,
              match_method, match_confidence, review_required, review_status
            ) VALUES ('xw-1', ?, 'bp-tropical-1', 'exact', 'high', 0, 'not_reviewed')
            """,
            (svk,),
        )
        conn.execute(
            """
            INSERT INTO schedule_baseline_health_facts (
              fact_id, current_schedule_version_key, baseline_project_key,
              metric_key, status
            ) VALUES ('hf-1', ?, 'bp-tropical-1', 'activity_count', 'ok')
            """,
            (svk,),
        )
        conn.commit()


def test_apply_purge_clears_diff_and_baseline_orphans_with_fk_on(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _seed_diff_and_baseline_orphans(db)
    before = _table_counts(db, PURGE_TRACKED_TABLES)
    assert before["schedule_version_diff_detail_facts"] >= 1
    assert before["schedule_baseline_activity_codes"] >= 1

    result = run_tropical_purge(str(db), project_key="tropical", dry_run=False, apply=True)
    after = _table_counts(db, PURGE_TRACKED_TABLES)

    with sqlite3.connect(db) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        fk_rows = conn.execute("PRAGMA foreign_key_check").fetchall()

    assert fk_rows == []
    assert result["remaining_tropical_schedule_records"] == 0
    for table in PURGE_TRACKED_TABLES:
        if before.get(table, 0) > 0:
            assert after.get(table) == 0, table
