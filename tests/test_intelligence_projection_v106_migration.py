"""V106 intelligence-projection migration (N8C-10): additive, idempotent, prior rows survive, CHECK."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

_PROJECTION_TABLES = {
    "assistant_intelligence_projections",
    "assistant_intelligence_projection_items",
    "assistant_intelligence_projection_receipts",
    "assistant_intelligence_projection_events",
}


def _tables(db: str) -> set[str]:
    with sqlite3.connect(db) as c:
        return {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def test_head_is_106() -> None:
    assert LATEST_SCHEMA_VERSION == 106


def test_apply_creates_four_projection_tables(tmp_path: Path) -> None:
    db = str(tmp_path / "db.sqlite")
    head = SQLiteMigrator(db_path=db).apply()
    assert head == LATEST_SCHEMA_VERSION
    assert _tables(db) >= _PROJECTION_TABLES


def test_reapply_idempotent(tmp_path: Path) -> None:
    db = str(tmp_path / "db.sqlite")
    assert SQLiteMigrator(db_path=db).apply() == LATEST_SCHEMA_VERSION
    assert SQLiteMigrator(db_path=db).apply() == LATEST_SCHEMA_VERSION
    with sqlite3.connect(db) as c:
        n = c.execute("SELECT COUNT(*) FROM schema_migrations WHERE version = 106").fetchone()[0]
    assert n == 1


def test_prior_version_rows_survive(tmp_path: Path) -> None:
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    tabs = _tables(db)
    # V100..V105 tables must remain after the additive V106 migration.
    assert {"assistant_claims", "assistant_enrichment_jobs"} <= tabs
    assert {"assistant_context_packs", "assistant_memory_nodes"} <= tabs
    assert {"assistant_decision_records", "assistant_open_loop_records"} <= tabs
    assert {"assistant_review_items", "assistant_review_dispositions", "assistant_review_events"} <= tabs


def test_provenance_check_rejects_anchorless_item(tmp_path: Path) -> None:
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    with sqlite3.connect(db) as c, pytest.raises(sqlite3.IntegrityError):
        c.execute(
            "INSERT INTO assistant_intelligence_projection_items "
            "(projection_item_id, projection_id, target_kind, target_id, inclusion_state) "
            "VALUES (?,?,?,?,?)",
            ("x", "p1", "claim", "t1", "candidate"),
        )
