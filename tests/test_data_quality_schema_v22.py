"""Phase 07B Prompt 01 — V22 mart raw-body guardrail.

Proves V22 adds raw_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_persisted = 0)
to the five V21 marts additively (via ALTER TABLE), is idempotent, leaves V1-V21 tables
intact (including their existing CHECK guardrails), and enforces the CHECK.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

_V22_MARTS = [
    "project_source_coverage_mart",
    "data_quality_gate_results",
    "source_record_summary_mart",
    "relationship_quality_mart",
    "cross_domain_context_readiness_mart",
]

_V20_TABLES_WITH_CHECK = [
    "construction_data_quality_runs",
    "source_system_record_map",
    "relationship_resolution_queue",
]


def _migrate(db: Path) -> int:
    return SQLiteMigrator(db_path=str(db)).apply()


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _table_sql(conn: sqlite3.Connection, table: str) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return (row[0] if row else "") or ""


def test_v22_adds_raw_body_guardrail_to_all_marts() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v22.db"
        assert _migrate(db) == LATEST_SCHEMA_VERSION == 22
        conn = sqlite3.connect(str(db))
        for mart in _V22_MARTS:
            cols = _columns(conn, mart)
            assert "raw_body_persisted" in cols, f"{mart} missing raw_body_persisted"
            sql_nospace = _table_sql(conn, mart).replace(" ", "")
            assert "CHECK(raw_body_persisted=0)" in sql_nospace, f"{mart} missing CHECK"


def test_v22_is_idempotent() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v22.db"
        assert _migrate(db) == 22
        assert _migrate(db) == 22  # second apply is a no-op
        conn = sqlite3.connect(str(db))
        # exactly one schema_migrations row for v22
        n = conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE version = 22").fetchone()[0]
        assert n == 1
        # column not duplicated by the second apply
        for mart in _V22_MARTS:
            cols = [r[1] for r in conn.execute(f"PRAGMA table_info({mart})").fetchall()]
            assert cols.count("raw_body_persisted") == 1


def test_v22_leaves_v1_v21_tables_intact() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v22.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        # v20/v21 migration rows still recorded
        for version in (20, 21, 22):
            row = conn.execute(
                "SELECT COUNT(*) FROM schema_migrations WHERE version = ?", (version,)
            ).fetchone()
            assert row[0] == 1, f"missing schema_migrations row for v{version}"
        # the V20 tables retain their original CHECK guardrail
        for table in _V20_TABLES_WITH_CHECK:
            sql_nospace = _table_sql(conn, table).replace(" ", "")
            assert "CHECK(raw_body_persisted=0)" in sql_nospace, f"{table} lost its CHECK"


def test_v22_check_rejects_raw_body_flag() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v22.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO data_quality_gate_results "
                "(gate_result_id, run_id, gate_name, gate_status, raw_body_persisted) "
                "VALUES ('g1', 'r1', 'x', 'pass', 1)"
            )
