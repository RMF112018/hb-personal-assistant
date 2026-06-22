"""V65 schedule schema drift repair: version recorded without physical columns."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator
from hb_assistant.store.schedule_float_tables import (
    METRIC_STATUS_CHECK_VALUES,
    V65_ACTIVITY_ALTER_COLUMNS,
    V65_IMPORT_ALTER_COLUMNS,
)
from hb_assistant.store.schedule_schema_verify import (
    verify_v65_metric_status_check,
    verify_v65_schedule_float_schema,
)


def _cols(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def test_v65_drift_repair_when_migration_row_exists_without_columns(tmp_path: Path) -> None:
    db = tmp_path / "drift.db"
    assert LATEST_SCHEMA_VERSION == 66
    migrator = SQLiteMigrator(db_path=str(db))
    migrator.apply()

    conn = sqlite3.connect(db)
    for col in V65_IMPORT_ALTER_COLUMNS:
        conn.execute(f"ALTER TABLE schedule_file_imports DROP COLUMN {col}")
    for col in V65_ACTIVITY_ALTER_COLUMNS:
        conn.execute(f"ALTER TABLE procore_ep_schedule_activities DROP COLUMN {col}")
    conn.execute("DELETE FROM schema_migrations WHERE version >= 65")
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO schema_migrations (version, name, applied_at) VALUES (65, 'v65_schedule_derived_finish_float', ?)",
        (now,),
    )
    conn.commit()
    assert verify_v65_schedule_float_schema(conn)
    conn.close()

    migrator.apply()
    conn2 = sqlite3.connect(db)
    import_cols = _cols(conn2, "schedule_file_imports")
    activity_cols = _cols(conn2, "procore_ep_schedule_activities")
    assert not verify_v65_schedule_float_schema(conn2)
    assert verify_v65_metric_status_check(conn2)
    ddl = conn2.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='schedule_quality_metric_results'"
    ).fetchone()[0]
    for status in METRIC_STATUS_CHECK_VALUES:
        assert status in ddl
    for col in V65_IMPORT_ALTER_COLUMNS:
        assert col in import_cols
    for col in V65_ACTIVITY_ALTER_COLUMNS:
        assert col in activity_cols
    conn2.close()