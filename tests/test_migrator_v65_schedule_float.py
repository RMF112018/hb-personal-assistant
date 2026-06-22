"""V65 derived finish-float schema migration."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator
from hb_assistant.store.schedule_float_tables import METRIC_STATUS_CHECK_VALUES


def test_v65_columns_present(tmp_path: Path) -> None:
    db = tmp_path / "v65.db"
    assert LATEST_SCHEMA_VERSION == 66
    SQLiteMigrator(db_path=str(db)).apply()
    conn = sqlite3.connect(db)
    import_cols = {r[1] for r in conn.execute("PRAGMA table_info(schedule_file_imports)")}
    activity_cols = {
        r[1] for r in conn.execute("PRAGMA table_info(procore_ep_schedule_activities)")
    }
    conn.close()
    assert "compute_total_float_type" in import_cols
    assert "derived_total_float_days" in activity_cols
    assert "remaining_late_finish" in activity_cols


def test_v65_metric_status_check_allows_derived_float(tmp_path: Path) -> None:
    db = tmp_path / "v65_metric_status.db"
    SQLiteMigrator(db_path=str(db)).apply()
    conn = sqlite3.connect(db)
    ddl_row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='schedule_quality_metric_results'"
    ).fetchone()
    assert ddl_row and ddl_row[0]
    for status in METRIC_STATUS_CHECK_VALUES:
        assert status in ddl_row[0]
    conn.execute(
        """
        INSERT INTO schedule_quality_evaluation_runs (
          evaluation_run_id, project_key, schedule_version_key, assessment_profile,
          assessment_profile_version, method_source, trigger_source, idempotency_key,
          engine_version, checker_version
        ) VALUES ('run-1', 'proj', 'proj|v1', 'dcma_14_point_plus_gao', 'v1', 'test', 'manual_rerun', 'key-1', 'e1', 'c1')
        """
    )
    conn.execute(
        """
        INSERT INTO schedule_quality_metric_results (
          evaluation_run_id, project_key, schedule_version_key, metric_code, metric_name,
          metric_family, status
        ) VALUES ('run-1', 'proj', 'proj|v1', 'dcma_high_float', 'High float', 'dcma', 'measured_from_derived_finish_float')
        """
    )
    conn.close()
