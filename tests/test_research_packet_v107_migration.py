"""N8C-11 — V107 research-packet migration: additive, idempotent, head at 107, prior V100–V106 rows survive,
dual-layer (item AND citation) provenance CHECK enforced at the schema level."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

_PACKET_TABLES = {
    "assistant_research_packets",
    "assistant_research_packet_items",
    "assistant_research_packet_citations",
    "assistant_research_packet_receipts",
    "assistant_research_packet_events",
}


def _migrate(db: Path) -> int:
    return SQLiteMigrator(db_path=str(db)).apply()


def test_head_is_107(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    assert _migrate(db) == 107
    assert LATEST_SCHEMA_VERSION == 107


def test_five_packet_tables_created(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c:
        tables = {r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'assistant_research_packet%'")}
    assert tables == _PACKET_TABLES


def test_migration_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    assert _migrate(db) == 107
    assert _migrate(db) == 107  # re-apply is a no-op
    with sqlite3.connect(db) as c:
        row = c.execute("SELECT name FROM schema_migrations WHERE version=107").fetchone()
    assert row[0] == "v107_assistant_research_packet"


def test_prior_v100_v106_rows_survive(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c:
        versions = {r[0] for r in c.execute(
            "SELECT version FROM schema_migrations WHERE version BETWEEN 100 AND 107")}
    assert {100, 101, 102, 103, 104, 105, 106, 107} <= versions


def test_item_provenance_check_rejects_anchorless(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c, pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO assistant_research_packet_items "
                  "(packet_item_id, packet_id, target_kind, target_id, answer_role) "
                  "VALUES ('x','p','claim','t','primary_support')")


def test_citation_provenance_check_rejects_anchorless(tmp_path: Path) -> None:
    # Enforced at the schema level (in addition to model validation).
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c, pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO assistant_research_packet_citations "
                  "(citation_id, packet_id, packet_item_id, citation_type) "
                  "VALUES ('x','p','i','source')")


def test_citation_projection_item_anchor_satisfies_check(tmp_path: Path) -> None:
    # A citation anchored only by projection_item_id (no upstream anchor) is valid.
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO assistant_research_packet_citations "
                  "(citation_id, packet_id, packet_item_id, citation_type, projection_item_id) "
                  "VALUES ('x','p','i','projection_item','pit1')")
        assert c.execute("SELECT COUNT(*) FROM assistant_research_packet_citations").fetchone()[0] == 1
