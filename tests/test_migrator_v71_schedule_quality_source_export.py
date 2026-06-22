"""V71 schedule quality source_export metric_family migration."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from hb_assistant.store.migrator import SQLiteMigrator


def test_v71_allows_source_export_metric_family(tmp_path: Path) -> None:
    db = tmp_path / "v71.db"
    SQLiteMigrator(db_path=str(db)).apply()
    with sqlite3.connect(db) as conn:
        ddl = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='schedule_quality_metric_results'"
        ).fetchone()[0]
        assert "source_export" in ddl
        assert "available_xer_driving_path" in ddl
        conn.execute(
            """
            INSERT INTO schedule_quality_evaluation_runs (
              evaluation_run_id, project_key, schedule_version_key, assessment_profile,
              assessment_profile_version, method_source, trigger_source, idempotency_key,
              engine_version, checker_version
            ) VALUES (
              'run-v71', 'tropical', 'tropical|1|2026-01-01', 'dcma_14_point_plus_gao',
              '1.0.0', 'DCMA_14PT+GAO+AACE', 'manual_rerun', 'key-v71', 'e1', 'c1'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO schedule_quality_metric_results (
              evaluation_run_id, project_key, schedule_version_key, metric_code, metric_name,
              metric_family, status
            ) VALUES (
              'run-v71', 'tropical', 'tropical|1|2026-01-01',
              'source_critical_path_available', 'Source critical path available',
              'source_export', 'available_xer_total_float_threshold'
            )
            """
        )
        conn.commit()