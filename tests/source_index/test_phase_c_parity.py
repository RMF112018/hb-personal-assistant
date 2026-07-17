"""PC-WI-01 Stage-2 — migration parity matrix.

After migrating each legacy origin to head: source-content row counts are preserved, root-scoped
identity and cross-root duplicate relpaths are preserved, generation/quarantine/lineage state is
preserved, FTS linkage stays clean, and the resulting *structure* is byte-identical to a fresh
head database (PC-AC-017..025).
"""

from __future__ import annotations

import sqlite3

import pytest

from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.source_index_migration_assurance import (
    collect_inventory,
    compare_migration_parity,
    compare_source_index_structure,
)
from tests.support.source_index_migration_fixture import (
    HEAD_VERSION,
    SUPPORTED_ORIGINS,
    build_fixture,
)

# Origins that require an actual upward migration (head is already at V127; ``fresh`` too).
LEGACY_ORIGINS: list[int] = [o for o in SUPPORTED_ORIGINS if o < HEAD_VERSION]


def _migrate_to_head(db_path) -> None:
    SQLiteMigrator(db_path=str(db_path)).apply()
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.commit()
    finally:
        conn.close()


@pytest.mark.parametrize("origin", LEGACY_ORIGINS)
def test_migration_preserves_data_parity(tmp_path, origin):
    res = build_fixture(tmp_path, origin, row_count=6)
    before = collect_inventory(res.db_path)

    _migrate_to_head(res.db_path)
    after = collect_inventory(res.db_path)

    result = compare_migration_parity(before, after)  # PC-AC-018..025 data preservation
    assert result.ok, f"parity failures for origin {origin}: {result.failures()}"


@pytest.mark.parametrize("origin", LEGACY_ORIGINS)
def test_migrated_structure_matches_fresh_head(tmp_path, origin):
    res = build_fixture(tmp_path, origin, row_count=6, filename=f"origin_v{origin}.sqlite")
    _migrate_to_head(res.db_path)

    ref = build_fixture(tmp_path, HEAD_VERSION, row_count=6, filename="reference_head.sqlite")

    # PC-AC-017: source-index structure after migration is canonical (== fresh head), scoped to the
    # source-index schema so unrelated domains cannot mask or fake the result.
    result = compare_source_index_structure(res.db_path, ref.db_path)
    assert result.ok, f"source-index structure diff for migrated origin {origin}: {result.failures()}"
    assert collect_inventory(res.db_path).schema_head == HEAD_VERSION


def test_generation_quarantine_lineage_preserved(tmp_path):
    # Origin 126 carries generations (V122+), unresolved quarantine (V125+), and rename lineage (V126+).
    res = build_fixture(tmp_path, 126, row_count=6)
    before = collect_inventory(res.db_path)
    assert before.generation_counts_by_status, "precondition: origin 126 has generation states"
    assert before.quarantine_unresolved_count > 0, "precondition: origin 126 has unresolved quarantine"
    assert before.lineage_count > 0, "precondition: origin 126 has rename lineage"

    _migrate_to_head(res.db_path)
    after = collect_inventory(res.db_path)

    assert after.generation_counts_by_status == before.generation_counts_by_status  # PC-AC-021
    assert after.quarantine_unresolved_count == before.quarantine_unresolved_count  # PC-AC-022
    assert after.lineage_count == before.lineage_count  # PC-AC-023
    assert after.fts_parity.dangling == 0 and after.fts_parity.orphan == 0  # PC-AC-020


def test_cross_root_duplicate_relpaths_preserved(tmp_path):
    # V124+ origins seed cross-root duplicate relpaths (narrow unique index dropped at V123).
    res = build_fixture(tmp_path, 124, row_count=6)
    before = collect_inventory(res.db_path)
    assert before.duplicate_relpath_across_roots > 0, "precondition: origin 124 has cross-root dups"

    _migrate_to_head(res.db_path)
    after = collect_inventory(res.db_path)

    assert after.duplicate_relpath_across_roots == before.duplicate_relpath_across_roots  # PC-AC-019
    assert after.root_count == before.root_count
