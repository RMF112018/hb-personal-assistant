"""PC-WI-01 Stage-2 — migration matrix.

Every supported origin migrates to exactly the execution-time head (V127) and the resulting
``schema_migrations`` ledger contains every version 1..head exactly once (PC-AC-014, PC-AC-015).
Read-only inventory is taken via the Stage-1 assurance engine; the migrator is the real
``SQLiteMigrator``. No production database, NAS, or watcher is touched.
"""

from __future__ import annotations

import sqlite3

import pytest

from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.source_index_migration_assurance import collect_inventory, ledger_complete
from tests.support.source_index_migration_fixture import (
    FRESH,
    HEAD_VERSION,
    SUPPORTED_ORIGINS,
    build_fixture,
)

ALL_ORIGINS: list[int | str] = [*SUPPORTED_ORIGINS, FRESH]


def _migrate_to_head(db_path) -> int:
    """Apply the real migrator, then truncate WAL so the immutable read-only inventory won't reject it."""
    head = SQLiteMigrator(db_path=str(db_path)).apply()
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.commit()
    finally:
        conn.close()
    return head


@pytest.mark.parametrize("origin", ALL_ORIGINS)
def test_every_origin_migrates_to_head(tmp_path, origin):
    res = build_fixture(tmp_path, origin, row_count=6)
    before = collect_inventory(res.db_path)
    assert before.schema_head is not None and before.schema_head <= HEAD_VERSION

    head = _migrate_to_head(res.db_path)
    assert head == HEAD_VERSION

    after = collect_inventory(res.db_path)
    assert after.schema_head == HEAD_VERSION  # PC-AC-014


@pytest.mark.parametrize("origin", ALL_ORIGINS)
def test_ledger_complete_after_migration(tmp_path, origin):
    res = build_fixture(tmp_path, origin, row_count=6)
    _migrate_to_head(res.db_path)
    after = collect_inventory(res.db_path)

    ok, detail = ledger_complete(after)  # PC-AC-015
    assert ok, f"incomplete ledger for origin {origin}: {detail}"
    assert after.schema_versions == list(range(1, HEAD_VERSION + 1))
