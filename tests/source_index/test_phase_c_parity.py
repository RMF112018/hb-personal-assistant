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
    compare_semantic_inventories,
    compare_source_index_structure,
    source_index_semantic_inventory,
)
from tests.support.source_index_migration_fixture import (
    HEAD_VERSION,
    SUPPORTED_ORIGINS,
    build_fixture,
)

# Origins that require an actual upward migration (the execution-time head and ``fresh`` do not).
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


# --- Semantic parity + negative mutation tests (PC-WI-01 corrective R2, PC-AC-020..025) ----------


def _mutate(db_path, statements):
    """Apply write statements to a fixture copy, then truncate WAL for the fail-closed read-only engine."""
    conn = sqlite3.connect(str(db_path))
    try:
        for sql, params in statements:
            conn.execute(sql, params)
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.commit()
    finally:
        conn.close()


def _origin_then_head(tmp_path, origin, name):
    """Build a legacy origin, snapshot its semantic inventory, migrate it to head; return (db, before)."""
    res = build_fixture(tmp_path, origin, row_count=6, filename=name)
    before = source_index_semantic_inventory(res.db_path)
    _migrate_to_head(res.db_path)
    return res.db_path, before


@pytest.mark.parametrize("origin", LEGACY_ORIGINS)
def test_migration_preserves_semantic_parity(tmp_path, origin):
    db, before = _origin_then_head(tmp_path, origin, f"sem_v{origin}.sqlite")
    after = source_index_semantic_inventory(db)
    result = compare_semantic_inventories(before, after)  # PC-AC-020..025 preserved on clean migration
    assert result.ok, f"semantic parity failures for origin {origin}: {result.failures()}"


def test_event_deletion_is_detected(tmp_path):  # PC-AC-024
    db, before = _origin_then_head(tmp_path, 126, "ev_del.sqlite")
    _mutate(db, [(
        "DELETE FROM source_intelligence_events "
        "WHERE rowid IN (SELECT rowid FROM source_intelligence_events LIMIT 1)", (),
    )])
    after = source_index_semantic_inventory(db)
    assert not compare_semantic_inventories(before, after).ok


def test_event_field_alteration_is_detected(tmp_path):  # PC-AC-024
    db, before = _origin_then_head(tmp_path, 126, "ev_alt.sqlite")
    _mutate(db, [(
        "UPDATE source_intelligence_events SET attempts = attempts + 1 "
        "WHERE rowid IN (SELECT rowid FROM source_intelligence_events LIMIT 1)", (),
    )])
    after = source_index_semantic_inventory(db)
    result = compare_semantic_inventories(before, after)
    assert not result.ok
    assert any(f.field == "events.identity_digests" for f in result.failures())


def test_fts_null_all_links_is_detected(tmp_path):  # PC-AC-020 (the zeroed-state false positive)
    db, before = _origin_then_head(tmp_path, 126, "fts_null.sqlite")
    _mutate(db, [("UPDATE source_intelligence_metadata SET fts_rowid = NULL", ())])
    after = source_index_semantic_inventory(db)
    result = compare_semantic_inventories(before, after)
    assert not result.ok  # fts.present drops, matched drops, orphan appears — no longer a false pass


def test_fts_row_deletion_is_detected(tmp_path):  # PC-AC-020
    db, before = _origin_then_head(tmp_path, 126, "fts_del.sqlite")
    _mutate(db, [("DELETE FROM source_intelligence_fts", ())])
    after = source_index_semantic_inventory(db)
    assert not compare_semantic_inventories(before, after).ok


def test_generation_authority_change_is_detected(tmp_path):  # PC-AC-021
    # Note: the DB itself enforces one active generation per root (partial-unique index), so the
    # comparator's single-active check is defensive. Here we change a non-active generation's status
    # (completed -> abandoned; both non-active, no constraint violation) and require it be detected.
    db, before = _origin_then_head(tmp_path, 126, "gen_auth.sqlite")
    _mutate(db, [("UPDATE source_index_scan_generations SET status = 'abandoned' WHERE status = 'completed'", ())])
    after = source_index_semantic_inventory(db)
    result = compare_semantic_inventories(before, after)
    assert not result.ok
    assert any(f.field == "generation_authority.per_root" for f in result.failures())


def test_lineage_cycle_is_detected(tmp_path):  # PC-AC-023
    db, before = _origin_then_head(tmp_path, 126, "lin_cyc.sqlite")
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        edge = conn.execute(
            "SELECT l.source_id, s.renamed_from_source_id "
            "FROM source_intelligence_sources s "
            "JOIN source_index_locators l ON l.source_entity_id = s.source_entity_id "
            "AND l.is_current_locator = 1 "
            "WHERE s.renamed_from_source_id IS NOT NULL LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    new, predecessor = edge[0], edge[1]  # new.renamed_from = predecessor
    _mutate(db, [(  # predecessor.renamed_from = new  -> 2-cycle
        "UPDATE source_intelligence_sources SET renamed_from_source_id = ? "
        "WHERE source_entity_id = (SELECT source_entity_id FROM source_index_locators "
        "WHERE source_id = ? AND is_current_locator = 1)",
        (new, predecessor),
    )])
    after = source_index_semantic_inventory(db)
    assert not compare_semantic_inventories(before, after).ok
    assert not after.lineage_acyclic


def test_lineage_dangling_predecessor_is_detected(tmp_path):  # PC-AC-023
    db, before = _origin_then_head(tmp_path, 126, "lin_dan.sqlite")
    _mutate(db, [(
        "UPDATE source_intelligence_sources SET renamed_from_source_id = 'NONEXISTENT-PRED' "
        "WHERE renamed_from_source_id IS NOT NULL", (),
    )])
    after = source_index_semantic_inventory(db)
    assert not compare_semantic_inventories(before, after).ok
    assert not after.lineage_all_predecessors_exist


def test_v128_permanent_identity_mapping_change_is_detected(tmp_path):  # PC-AC-018/023
    db, before = _origin_then_head(tmp_path, 128, "identity_map.sqlite")
    _mutate(db, [(
        "UPDATE source_index_locators SET source_id = 'tampered-source-id' "
        "WHERE rowid IN (SELECT rowid FROM source_index_locators LIMIT 1)",
        (),
    )])
    after = source_index_semantic_inventory(db)
    result = compare_semantic_inventories(before, after)
    assert not result.ok
    assert any(
        f.field == "permanent_identity.identity_digests" for f in result.failures()
    )


def test_card_alteration_is_detected(tmp_path):  # PC-AC-025
    db, before = _origin_then_head(tmp_path, 126, "card.sqlite")
    _mutate(db, [(
        "UPDATE source_intelligence_generated_notes "
        "SET generation_status = CASE WHEN generation_status = 'stale' THEN 'generated' ELSE 'stale' END "
        "WHERE rowid IN (SELECT rowid FROM source_intelligence_generated_notes LIMIT 1)", (),
    )])
    after = source_index_semantic_inventory(db)
    result = compare_semantic_inventories(before, after)
    assert not result.ok
    assert any(f.field == "cards.identity_digests" for f in result.failures())


def test_zero_state_quarantine_fabrication_is_detected(tmp_path):  # PC-AC-022 / F-004
    # Origin 124 carries no quarantine; fabricating an unresolved row after migration must be caught.
    db, before = _origin_then_head(tmp_path, 124, "q0.sqlite")
    assert before.quarantine_unresolved_count == 0 and before.quarantine_digests == []
    _mutate(db, [(
        "INSERT INTO source_index_scan_quarantine "
        "(quarantine_id, source_root_key, rel_path, failure_stage, error_code, first_seen_at, "
        " last_seen_at, status, resolution_state) "
        "VALUES ('fab-q1','root-x','docs/fabricated.md','observe','parse_failed',"
        "'2026-01-01T00:00:00+00:00','2026-01-01T00:00:00+00:00','quarantined','unresolved')", (),
    )])
    after = source_index_semantic_inventory(db)
    result = compare_semantic_inventories(before, after)
    assert not result.ok
    assert any(f.field == "quarantine.unresolved_count" for f in result.failures())


def test_zero_state_generation_fabrication_is_detected(tmp_path):  # PC-AC-021 / F-004
    # Origin 121 predates the generations table; fabricating a generation after migration must be caught.
    res = build_fixture(tmp_path, 121, row_count=6, filename="g0.sqlite")
    before = collect_inventory(res.db_path)
    assert before.generation_counts_by_status == {}, "precondition: origin 121 has no generations"
    _migrate_to_head(res.db_path)
    _mutate(res.db_path, [(
        "INSERT INTO source_index_scan_generations "
        "(generation_id, root_key, status, root_path_hash, policy_fingerprint) "
        "VALUES ('fab-gen1','root-x','running','rph-x','fp-x')", (),
    )])
    after = collect_inventory(res.db_path)
    result = compare_migration_parity(before, after)  # truthiness guard removed -> fabrication caught
    assert not result.ok
    assert any(f.field == "generation_counts_by_status" for f in result.failures())
