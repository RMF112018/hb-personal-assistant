"""PC-WI-01 Stage-2 — idempotency.

Reapplying the migrator at head produces no schema/protected-data change: the logical inventory hash
(page-layout- and ``applied_at``-independent) is unchanged (PC-AC-016).
"""

from __future__ import annotations

import sqlite3

import pytest

from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.source_index_migration_assurance import (
    collect_inventory,
    source_index_logical_hash,
)
from tests.support.source_index_migration_fixture import (
    FRESH,
    HEAD_VERSION,
    SUPPORTED_ORIGINS,
    build_fixture,
)

LEGACY_ORIGINS: list[int] = [o for o in SUPPORTED_ORIGINS if o < HEAD_VERSION]


def _reapply(db_path) -> None:
    SQLiteMigrator(db_path=str(db_path)).apply()
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.commit()
    finally:
        conn.close()


@pytest.mark.parametrize("origin", [HEAD_VERSION, FRESH])
def test_reapply_at_head_is_noop(tmp_path, origin):
    res = build_fixture(tmp_path, origin, row_count=6)
    assert collect_inventory(res.db_path).schema_head == HEAD_VERSION
    before = source_index_logical_hash(res.db_path)  # source-index-scoped (PC-AC-016)

    _reapply(res.db_path)

    after = source_index_logical_hash(res.db_path)
    assert after == before  # no source-index schema/protected-data change


@pytest.mark.parametrize("origin", LEGACY_ORIGINS)
def test_migrate_then_reapply_is_stable(tmp_path, origin):
    res = build_fixture(tmp_path, origin, row_count=6)
    _reapply(res.db_path)  # origin -> head
    once = source_index_logical_hash(res.db_path)

    _reapply(res.db_path)  # reapply at head must not change source-index logical content
    twice = source_index_logical_hash(res.db_path)

    assert twice == once
    assert collect_inventory(res.db_path).schema_head == HEAD_VERSION
