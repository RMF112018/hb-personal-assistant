"""V64 schedule quality evaluation schema tests."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator
from hb_assistant.store.schedule_quality_tables import V64_TABLES


def test_v64_tables_present() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v64.db"
        assert SQLiteMigrator(db_path=str(db)).apply() == LATEST_SCHEMA_VERSION
        conn = sqlite3.connect(db)
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        for t in V64_TABLES:
            assert t in names


def test_v64_finding_columns() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v64.db"
        SQLiteMigrator(db_path=str(db)).apply()
        conn = sqlite3.connect(db)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(schedule_quality_findings)")}
        conn.close()
        assert "evaluation_run_id" in cols
        assert "metric_code" in cols