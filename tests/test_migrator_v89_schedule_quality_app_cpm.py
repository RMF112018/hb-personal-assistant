"""V89 widens the metric-results status CHECK to accept the computed-CPM DCMA status.

Proves BOTH a fresh migrate and an upgrade from a pre-v89 schema (CHECK rebuild + row
preservation).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.schedule_float_tables import (
    METRIC_FAMILY_CHECK_VALUES,
    METRIC_STATUS_CHECK_VALUES,
)

NEW_STATUS = "available_app_cpm_recalculated"


def _insert_metric(conn: sqlite3.Connection, status: str) -> None:
    conn.execute(
        """
        INSERT INTO schedule_quality_metric_results (
          evaluation_run_id, project_key, schedule_version_key, metric_code, metric_name,
          metric_family, status, evidence_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("run1", "tropical", "svk", "dcma_critical_path_test", "Critical path test",
         "dcma", status, "{}"),
    )


def test_v89_fresh_migrate_accepts_app_cpm_status(tmp_path: Path) -> None:
    db = tmp_path / "v89.db"
    SQLiteMigrator(db_path=str(db)).apply()
    with sqlite3.connect(db) as conn:
        ddl = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' "
            "AND name='schedule_quality_metric_results'"
        ).fetchone()[0]
        assert NEW_STATUS in ddl
        # A row with the new measured status inserts successfully.
        _insert_metric(conn, NEW_STATUS)
        count = conn.execute(
            "SELECT COUNT(*) FROM schedule_quality_metric_results WHERE status=?",
            (NEW_STATUS,),
        ).fetchone()[0]
        assert count == 1


def test_v89_upgrade_from_pre_v89_rebuilds_check_and_preserves_rows(tmp_path: Path) -> None:
    db = tmp_path / "pre89.db"
    families = ", ".join(f"'{f}'" for f in METRIC_FAMILY_CHECK_VALUES)
    old_statuses = ", ".join(
        f"'{s}'" for s in METRIC_STATUS_CHECK_VALUES if s != NEW_STATUS
    )
    with sqlite3.connect(db) as conn:
        # Build a pre-v89 metric-results table whose CHECK excludes the new status.
        conn.execute(
            f"""
            CREATE TABLE schedule_quality_metric_results (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              evaluation_run_id TEXT NOT NULL,
              project_key TEXT NOT NULL,
              schedule_version_key TEXT NOT NULL,
              metric_code TEXT NOT NULL,
              metric_name TEXT NOT NULL,
              metric_family TEXT NOT NULL CHECK(metric_family IN ({families})),
              numerator TEXT, denominator TEXT, value TEXT, unit TEXT,
              threshold_warning TEXT, threshold_fail TEXT,
              status TEXT NOT NULL CHECK(status IN ({old_statuses})),
              not_measurable_reason TEXT, evidence_json TEXT,
              related_finding_codes_json TEXT,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        _insert_metric(conn, "available_xer_driving_path")  # pre-existing row
        # The pre-v89 CHECK rejects the new status.
        try:
            _insert_metric(conn, NEW_STATUS)
            raise AssertionError("pre-v89 CHECK should reject the new status")
        except sqlite3.IntegrityError:
            pass

        SQLiteMigrator._reconcile_v89_metric_status_app_cpm(conn)

        ddl = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' "
            "AND name='schedule_quality_metric_results'"
        ).fetchone()[0]
        assert NEW_STATUS in ddl
        # Pre-existing row survived the rebuild.
        assert conn.execute(
            "SELECT COUNT(*) FROM schedule_quality_metric_results WHERE status=?",
            ("available_xer_driving_path",),
        ).fetchone()[0] == 1
        # The rebuilt CHECK now accepts the new status.
        _insert_metric(conn, NEW_STATUS)
        assert conn.execute(
            "SELECT COUNT(*) FROM schedule_quality_metric_results WHERE status=?",
            (NEW_STATUS,),
        ).fetchone()[0] == 1
