"""V69 schedule import FK drift repair."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator
from hb_assistant.store.schedule_import_fk_repair import reconcile_schedule_import_fk_drift
from hb_assistant.store.schedule_schema_verify import verify_schedule_import_fk_targets


def _simulate_live_fk_drift(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='schedule_file_imports'"
    ).fetchone()
    assert row and row[0]
    create_sql = str(row[0]).replace("schedule_file_imports", "schedule_file_imports_v66", 1)
    conn.execute("ALTER TABLE schedule_file_imports RENAME TO schedule_file_imports_v66")
    conn.execute(create_sql.replace("schedule_file_imports_v66", "schedule_file_imports", 1))
    conn.commit()


def test_v69_repair_restores_canonical_import_fk(tmp_path: Path) -> None:
    assert LATEST_SCHEMA_VERSION >= 70
    db = tmp_path / "fk.db"
    SQLiteMigrator(db_path=str(db)).apply()

    conn = sqlite3.connect(db)
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        assert verify_schedule_import_fk_targets(conn) == []
        _simulate_live_fk_drift(conn)
        assert verify_schedule_import_fk_targets(conn)

        conn.execute(
            """
            INSERT INTO schedule_file_imports (
              import_id, project_key, source_type, source_format, import_status,
              activity_count, relationship_count, wbs_count, calendar_count,
              code_count, udf_count, cost_loaded_status
            ) VALUES (
              'imp-test', 'tropical', 'xer', 'primavera_xer', 'committed',
              1, 0, 0, 0, 0, 0, 'not_cost_loaded'
            )
            """
        )
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO procore_ep_schedule_activities (
                  project_key, schedule_id, schedule_version_key, import_id,
                  source_type, source_format, activity_id
                ) VALUES (
                  'tropical', 'TWNU18', 'tropical|TWNU18|2026-01-01', 'imp-test',
                  'xer', 'primavera_xer', 'A1000'
                )
                """
            )
            conn.commit()

        report = reconcile_schedule_import_fk_drift(conn)
        assert report["issues_after"] == []
        assert "procore_ep_schedule_activities" in report["rebuilt_tables"]

        conn.execute(
            """
            INSERT INTO procore_ep_schedule_activities (
              project_key, schedule_id, schedule_version_key, import_id,
              source_type, source_format, activity_id
            ) VALUES (
              'tropical', 'TWNU18', 'tropical|TWNU18|2026-01-01', 'imp-test',
              'xer', 'primavera_xer', 'A1000'
            )
            """
        )
        conn.commit()
        count = conn.execute(
            "SELECT COUNT(*) FROM procore_ep_schedule_activities WHERE import_id='imp-test'"
        ).fetchone()[0]
        assert int(count) == 1
    finally:
        conn.close()

    migrator = SQLiteMigrator(db_path=str(db))
    assert migrator.current_version() == LATEST_SCHEMA_VERSION
