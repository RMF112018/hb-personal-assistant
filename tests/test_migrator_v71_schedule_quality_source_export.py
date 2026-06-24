"""V71 schedule quality source_export metric_family migration."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.schedule_quality_repository import ScheduleQualityRepository


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


def test_v71_round_trips_msp_source_export_metric_through_repository(tmp_path: Path) -> None:
    db = tmp_path / "v71_msp_metric.db"
    SQLiteMigrator(db_path=str(db)).apply()
    repo = ScheduleQualityRepository(db_path=str(db))
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            INSERT INTO schedule_quality_evaluation_runs (
              evaluation_run_id, project_key, schedule_version_key, assessment_profile,
              assessment_profile_version, method_source, trigger_source, idempotency_key,
              engine_version, checker_version, status
            ) VALUES (
              'run-v71-msp', 'tropical', 'tropical|1|2026-01-01', 'dcma_14_point_plus_gao',
              '1.0.0', 'DCMA_14PT+GAO+AACE', 'manual_rerun', 'key-v71-msp', 'e1', 'c1',
              'completed'
            )
            """
        )
        conn.commit()

    inserted = repo.insert_metric_results(
        [
            {
                "evaluation_run_id": "run-v71-msp",
                "project_key": "tropical",
                "schedule_version_key": "tropical|1|2026-01-01",
                "metric_code": "source_msp_critical_slack_available",
                "metric_name": "MSP source critical/slack consistency",
                "metric_family": "source_export",
                "numerator": "2",
                "denominator": "2",
                "value": "1.0",
                "unit": "ratio",
                "status": "measured_from_msp_critical_flag",
                "evidence_json": "{}",
                "related_finding_codes_json": "[]",
            }
        ]
    )
    assert inserted == 1
    metric = repo.list_metrics("run-v71-msp")[0]
    assert metric["metric_code"] == "source_msp_critical_slack_available"
    assert metric["metric_family"] == "source_export"
    assert metric["status"] == "measured_from_msp_critical_flag"
