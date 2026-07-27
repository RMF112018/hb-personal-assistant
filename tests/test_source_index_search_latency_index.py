"""V124: the FTS-search join key must be indexed so search does not full-scan metadata.

Regression guard for the ~24s source-file-search latency: the hot join
``source_intelligence_metadata m ON m.fts_rowid = f.rowid`` was unindexed, so SQLite built a
transient automatic index over the whole ~883k-row metadata table on every query.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator


def _migrate(tmp_path: Path) -> sqlite3.Connection:
    db = str(tmp_path / "t.sqlite")
    head = SQLiteMigrator(db_path=db).apply()
    assert head == LATEST_SCHEMA_VERSION
    return sqlite3.connect(db)


def test_metadata_fts_rowid_index_present_after_migration(tmp_path: Path) -> None:
    c = _migrate(tmp_path)
    names = {
        r[0]
        for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND tbl_name='source_intelligence_metadata'"
        )
    }
    assert "idx_si_metadata_fts_rowid" in names


def test_search_join_uses_fts_rowid_index_not_full_scan(tmp_path: Path) -> None:
    c = _migrate(tmp_path)
    plan = c.execute(
        "EXPLAIN QUERY PLAN "
        "SELECT m.source_entity_id FROM source_intelligence_fts f "
        "JOIN source_intelligence_metadata m ON m.fts_rowid = f.rowid "
        "WHERE source_intelligence_fts MATCH 'x'"
    ).fetchall()
    detail = " | ".join(row[-1] for row in plan)
    # metadata is reached via the new index, not a transient automatic index / full scan.
    assert "idx_si_metadata_fts_rowid" in detail, detail
    assert "AUTOMATIC" not in detail.upper(), detail
    assert "SCAN m" not in detail, detail
