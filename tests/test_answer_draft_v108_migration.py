"""N8C-14 — V108 answer-draft migration: additive, idempotent, head at 108, prior V100–V107 rows survive,
citation provenance CHECK (packet_citation_id OR ≥1 anchor) enforced at the schema level."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

_DRAFT_TABLES = {
    "assistant_answer_drafts",
    "assistant_answer_draft_sections",
    "assistant_answer_draft_citations",
    "assistant_answer_draft_receipts",
    "assistant_answer_draft_events",
}


def _migrate(db: Path) -> int:
    return SQLiteMigrator(db_path=str(db)).apply()


def test_head_is_108(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    assert _migrate(db) == 108
    assert LATEST_SCHEMA_VERSION == 108


def test_five_draft_tables_created(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c:
        tables = {r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'assistant_answer_draft%'")}
    assert tables == _DRAFT_TABLES


def test_migration_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    assert _migrate(db) == 108
    assert _migrate(db) == 108  # re-apply is a no-op
    with sqlite3.connect(db) as c:
        row = c.execute("SELECT name FROM schema_migrations WHERE version=108").fetchone()
    assert row[0] == "v108_assistant_answer_draft"


def test_prior_v100_v107_rows_survive(tmp_path: Path) -> None:
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c:
        versions = {r[0] for r in c.execute(
            "SELECT version FROM schema_migrations WHERE version BETWEEN 100 AND 108")}
    assert {100, 101, 102, 103, 104, 105, 106, 107, 108} <= versions


def test_prior_v107_packet_tables_survive(tmp_path: Path) -> None:
    # The V108 additive migration must not drop or rewrite the N8C-11 packet tables it reads from.
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c:
        tables = {r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'assistant_research_packet%'")}
    assert "assistant_research_packets" in tables and "assistant_research_packet_citations" in tables


def test_citation_check_rejects_anchorless_and_lineageless(tmp_path: Path) -> None:
    # A draft citation with neither packet_citation_id NOR any provenance anchor is rejected at the schema
    # level (in addition to model validation).
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c, pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO assistant_answer_draft_citations "
                  "(draft_citation_id, draft_id, draft_section_id, citation_type) "
                  "VALUES ('x','d','s','source')")


def test_citation_packet_lineage_satisfies_check(tmp_path: Path) -> None:
    # packet_citation_id alone satisfies the anchor requirement (lineage preserved).
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO assistant_answer_draft_citations "
                  "(draft_citation_id, draft_id, draft_section_id, citation_type, packet_citation_id) "
                  "VALUES ('x','d','s','claim','pc1')")
        assert c.execute("SELECT COUNT(*) FROM assistant_answer_draft_citations").fetchone()[0] == 1


def test_citation_provenance_anchor_satisfies_check(tmp_path: Path) -> None:
    # A degraded-lineage citation (no packet_citation_id) is valid with ≥1 provenance anchor.
    db = tmp_path / "h.db"
    _migrate(db)
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO assistant_answer_draft_citations "
                  "(draft_citation_id, draft_id, draft_section_id, citation_type, projection_item_id) "
                  "VALUES ('y','d','s','projection_item','pit1')")
        assert c.execute("SELECT COUNT(*) FROM assistant_answer_draft_citations").fetchone()[0] == 1


def test_no_finality_columns_on_draft_tables(tmp_path: Path) -> None:
    # There must be NO final/authoritative answer column anywhere on the draft tables.
    db = tmp_path / "h.db"
    _migrate(db)
    forbidden = {"final_answer", "answer_text", "generated_answer", "authoritative_answer",
                 "operator_approved_answer"}
    with sqlite3.connect(db) as c:
        for table in _DRAFT_TABLES:
            cols = {r[1] for r in c.execute(f"PRAGMA table_info({table})")}
            assert not (forbidden & cols), (table, forbidden & cols)
