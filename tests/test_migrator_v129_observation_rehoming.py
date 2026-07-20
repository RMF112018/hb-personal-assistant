"""V129 — observation re-homing + serving-trust gate + move-signal disposition (ADR-003 R8).

Proves the V129 additive layer that rides the V128 byte-exact permanent-identity oracle (§9): a fresh
migrate reaches head 129 with the four nullable observation/serving columns + the ``idx_locators_reconcile``
index on ``source_index_locators`` and the five nullable disposition columns (two of them applied-only
``resulting_*`` FKs) on ``source_index_move_signals``, each with the exact column-level CHECK domains;
``129`` is recorded exactly once; an in-place V128→V129 upgrade produces byte-identical CREATE SQL; a
re-apply at head is a no-op; a dropped V129 column / reconcile index is detected fail-closed and
re-ensured by the ``_v129_ensure_*`` repair pass; a malformed V129 CHECK is non-repairable and fails
closed (``v129_schema_parity_failed``); and ``PRAGMA foreign_key_check`` is clean. Scratch SQLite DBs only.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hb_assistant.store.migrator import (
    LATEST_SCHEMA_VERSION,
    SQLiteMigrator,
    get_connection,
)

LOCATOR_V129_COLS = (
    "last_seen_generation", "last_seen_at", "last_indexed_fingerprint", "policy_validation_state",
)
MOVE_SIGNAL_V129_COLS = (
    "disposition", "disposition_at", "disposition_reason",
    "resulting_entity_id", "resulting_locator_id",
)


def _cols(db: str, table: str) -> list[str]:
    with sqlite3.connect(db) as c:
        return [r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall()]


def _col_meta(db: str, table: str) -> dict[str, tuple[str, int, int]]:
    # name -> (declared type upper, notnull, pk)
    with sqlite3.connect(db) as c:
        return {
            r[1]: (str(r[2] or "").upper(), int(r[3]), int(r[5]))
            for r in c.execute(f"PRAGMA table_info({table})").fetchall()
        }


def _indexes(db: str, table: str) -> set[str]:
    with sqlite3.connect(db) as c:
        return {r[1] for r in c.execute(f"PRAGMA index_list({table})").fetchall()}


def _idx_cols(db: str, idx: str) -> list[str]:
    with sqlite3.connect(db) as c:
        return [r[2] for r in c.execute(f"PRAGMA index_info({idx})").fetchall()]


def _idx_flags(db: str, table: str, idx: str) -> tuple[int, int]:
    # (unique, partial)
    with sqlite3.connect(db) as c:
        for r in c.execute(f"PRAGMA index_list({table})").fetchall():
            if r[1] == idx:
                return int(r[2]), int(r[4])
    raise AssertionError(f"index {idx} absent")


def _obj_sql(db: str, name: str, typ: str = "table") -> str:
    with sqlite3.connect(db) as c:
        row = c.execute(
            "SELECT sql FROM sqlite_master WHERE type=? AND name=?", (typ, name)
        ).fetchone()
    return " ".join((row[0] or "").split()) if row and row[0] else ""


def _fk_map(db: str, table: str) -> dict[str, tuple[str, str]]:
    # from-column -> (referenced table, referenced column)
    with sqlite3.connect(db) as c:
        return {
            r[3]: (r[2], r[4])
            for r in c.execute(f"PRAGMA foreign_key_list({table})").fetchall()
        }


def _versions(db: str) -> list[int]:
    with sqlite3.connect(db) as c:
        return [r[0] for r in c.execute("SELECT version FROM schema_migrations").fetchall()]


def _fk_check(db: str) -> list:
    with sqlite3.connect(db) as c:
        return c.execute("PRAGMA foreign_key_check").fetchall()


@pytest.fixture()
def fresh(tmp_path: Path) -> str:
    db = str(tmp_path / "db.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return db


def _make_v128_db(tmp_path: Path, name: str = "v128.sqlite") -> str:
    """A genuine V128-shaped DB: migrate to head, then strip every V129 addition (all four locator
    columns, all five move-signal columns, the reconcile index) and remove the version-129 record, so
    ``apply()`` re-enters the V128 oracle's failed-parity branch and drives the real V128→V129 upgrade
    (repair) path. The stripped columns are the whole additive suffix, so re-ensuring them appends in
    the same order a fresh migrate uses (byte-exact)."""
    db = str(tmp_path / name)
    SQLiteMigrator(db_path=db).apply()
    with sqlite3.connect(db) as c:
        for col in LOCATOR_V129_COLS:
            c.execute(f"ALTER TABLE source_index_locators DROP COLUMN {col}")
        for col in MOVE_SIGNAL_V129_COLS:
            c.execute(f"ALTER TABLE source_index_move_signals DROP COLUMN {col}")
        c.execute("DROP INDEX idx_locators_reconcile")
        c.execute("DELETE FROM schema_migrations WHERE version=129")
    return db


# ---------------------------------------------------------------------------------------------------
# Fresh-migrate shape + version record
# ---------------------------------------------------------------------------------------------------


def test_latest_version_is_129(fresh) -> None:
    assert LATEST_SCHEMA_VERSION == 129
    assert 129 in _versions(fresh)
    # V128 remains reachable/recorded (V129 rides the V128 oracle, not a replacement).
    assert 128 in _versions(fresh)


def test_v129_recorded_exactly_once(fresh) -> None:
    assert _versions(fresh).count(129) == 1


def test_locator_observation_columns_present_and_nullable(fresh) -> None:
    meta = _col_meta(fresh, "source_index_locators")
    for col in LOCATOR_V129_COLS:
        assert meta.get(col) == ("TEXT", 0, 0), f"{col} must be nullable non-PK TEXT"
    # last_seen_generation (UUID token) is a NEW column, distinct from the integer generation_seq.
    assert meta["generation_seq"][0] == "INTEGER"
    assert meta["last_seen_generation"][0] == "TEXT"


def test_reconcile_index_present_shape(fresh) -> None:
    assert "idx_locators_reconcile" in _indexes(fresh, "source_index_locators")
    assert _idx_cols(fresh, "idx_locators_reconcile") == ["source_root_key", "source_id"]
    unique, partial = _idx_flags(fresh, "source_index_locators", "idx_locators_reconcile")
    assert unique == 0  # non-unique
    assert partial == 1  # current-locator partial
    assert "is_current_locator=1" in _obj_sql(fresh, "idx_locators_reconcile", "index")
    # Deliberately NOT last_seen_generation-leading (§4.4).
    assert _idx_cols(fresh, "idx_locators_reconcile")[0] != "last_seen_generation"


def test_move_signal_disposition_columns_present_and_nullable(fresh) -> None:
    meta = _col_meta(fresh, "source_index_move_signals")
    for col in MOVE_SIGNAL_V129_COLS:
        assert meta.get(col) == ("TEXT", 0, 0), f"{col} must be nullable non-PK TEXT"


def test_resulting_fk_edges_present(fresh) -> None:
    fks = _fk_map(fresh, "source_index_move_signals")
    assert fks.get("resulting_entity_id") == ("source_index_entities", "source_entity_id")
    assert fks.get("resulting_locator_id") == ("source_index_locators", "locator_id")


def test_foreign_key_check_clean_after_v129(fresh) -> None:
    # V129 adds two FK edges on move_signals; the table is empty, so the check is trivially clean.
    assert _fk_check(fresh) == []


# ---------------------------------------------------------------------------------------------------
# CHECK domains (column-level enum + serving gate)
# ---------------------------------------------------------------------------------------------------


def test_disposition_check_rejects_out_of_domain(fresh) -> None:
    with sqlite3.connect(fresh) as c:
        c.execute("INSERT INTO source_index_move_signals(move_signal_id) VALUES('m1')")
        with pytest.raises(sqlite3.IntegrityError):
            c.execute("UPDATE source_index_move_signals SET disposition='bogus' WHERE move_signal_id='m1'")
        # NULL (pending) and every terminal value are accepted.
        for val in ("applied", "rejected_stale", "rejected_target_occupied", "malformed"):
            c.execute(
                "UPDATE source_index_move_signals SET disposition=? WHERE move_signal_id='m1'", (val,)
            )
        c.execute("UPDATE source_index_move_signals SET disposition=NULL WHERE move_signal_id='m1'")


def test_disposition_reason_check_rejects_out_of_domain(fresh) -> None:
    valid = (
        "ok", "source_locator_not_current", "source_locator_tombstoned",
        "missing_source_locator", "target_path_occupied", "malformed_payload",
    )
    with sqlite3.connect(fresh) as c:
        c.execute("INSERT INTO source_index_move_signals(move_signal_id) VALUES('m2')")
        with pytest.raises(sqlite3.IntegrityError):
            c.execute(
                "UPDATE source_index_move_signals SET disposition_reason='nope' WHERE move_signal_id='m2'"
            )
        for val in valid:
            c.execute(
                "UPDATE source_index_move_signals SET disposition_reason=? WHERE move_signal_id='m2'",
                (val,),
            )


def test_policy_validation_state_check_rejects_out_of_domain(fresh) -> None:
    with sqlite3.connect(fresh) as c:
        c.execute(
            "INSERT INTO source_index_entities(source_entity_id, created_at, status) "
            "VALUES('e1','2026-01-01','LIVE')"
        )
        c.execute(
            "INSERT INTO source_index_locators(locator_id, source_entity_id, source_id, "
            "is_current_locator, policy_validation_state) VALUES('l1','e1','s1',1,'policy_stale')"
        )
        with pytest.raises(sqlite3.IntegrityError):
            c.execute(
                "UPDATE source_index_locators SET policy_validation_state='other' WHERE locator_id='l1'"
            )
        # NULL (validated) is accepted.
        c.execute(
            "UPDATE source_index_locators SET policy_validation_state=NULL WHERE locator_id='l1'"
        )


def test_resulting_entity_fk_enforced(fresh) -> None:
    # An applied disposition pointing resulting_entity_id at a non-existent entity is an FK violation.
    with sqlite3.connect(fresh) as c:
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("INSERT INTO source_index_move_signals(move_signal_id) VALUES('m3')")
        with pytest.raises(sqlite3.IntegrityError):
            c.execute(
                "UPDATE source_index_move_signals SET resulting_entity_id='no_such_entity' "
                "WHERE move_signal_id='m3'"
            )


# ---------------------------------------------------------------------------------------------------
# Idempotency + oracle
# ---------------------------------------------------------------------------------------------------


def test_reapply_at_head_is_noop(fresh) -> None:
    before = _obj_sql(fresh, "source_index_locators")
    assert SQLiteMigrator(db_path=fresh).apply() == 129
    assert SQLiteMigrator(db_path=fresh).apply() == 129
    assert _versions(fresh).count(129) == 1
    assert _obj_sql(fresh, "source_index_locators") == before


def test_oracle_true_at_head(fresh) -> None:
    gc = get_connection(fresh)
    try:
        assert SQLiteMigrator._v128_schema_current(gc) is True
    finally:
        gc.close()


# ---------------------------------------------------------------------------------------------------
# V128 -> V129 upgrade + byte-exact identity
# ---------------------------------------------------------------------------------------------------


def test_upgrade_v128_to_v129(tmp_path: Path) -> None:
    db = _make_v128_db(tmp_path)
    # Before upgrade: the DB is genuinely at head 128 with none of the V129 additions.
    assert max(_versions(db)) == 128
    assert "idx_locators_reconcile" not in _indexes(db, "source_index_locators")
    for col in LOCATOR_V129_COLS:
        assert col not in _cols(db, "source_index_locators")

    gc = get_connection(db)
    try:
        assert SQLiteMigrator._v128_schema_current(gc) is False  # detected (missing V129 additions)
    finally:
        gc.close()

    assert SQLiteMigrator(db_path=db).apply() == 129
    for col in LOCATOR_V129_COLS:
        assert col in _cols(db, "source_index_locators")
    for col in MOVE_SIGNAL_V129_COLS:
        assert col in _cols(db, "source_index_move_signals")
    assert "idx_locators_reconcile" in _indexes(db, "source_index_locators")
    assert _versions(db).count(129) == 1
    assert _fk_check(db) == []


def test_fresh_and_upgraded_create_sql_byte_identical(tmp_path: Path) -> None:
    ref = str(tmp_path / "ref.sqlite")
    SQLiteMigrator(db_path=ref).apply()
    upgraded = _make_v128_db(tmp_path, "up.sqlite")
    SQLiteMigrator(db_path=upgraded).apply()
    for table in ("source_index_locators", "source_index_move_signals"):
        assert _obj_sql(ref, table) == _obj_sql(upgraded, table), f"{table} CREATE SQL diverged"
    assert _obj_sql(ref, "idx_locators_reconcile", "index") == _obj_sql(
        upgraded, "idx_locators_reconcile", "index"
    )


# ---------------------------------------------------------------------------------------------------
# Drift detection + repair (fail-closed)
# ---------------------------------------------------------------------------------------------------


def test_drift_dropped_v129_locator_column_detected_and_repaired(fresh) -> None:
    # Drop the trailing V129 locator column (partial-migration shape). Detection fails closed on the
    # byte-exact oracle; the _v129_ensure_* repair pass re-adds it in order -> byte-exact restored.
    with sqlite3.connect(fresh) as c:
        c.execute("ALTER TABLE source_index_locators DROP COLUMN policy_validation_state")
    assert "policy_validation_state" not in _cols(fresh, "source_index_locators")
    gc = get_connection(fresh)
    try:
        assert SQLiteMigrator._v128_schema_current(gc) is False
    finally:
        gc.close()
    assert SQLiteMigrator(db_path=fresh).apply() == 129
    assert _col_meta(fresh, "source_index_locators")["policy_validation_state"] == ("TEXT", 0, 0)
    gc = get_connection(fresh)
    try:
        assert SQLiteMigrator._v128_schema_current(gc) is True
    finally:
        gc.close()


def test_drift_dropped_v129_move_signal_columns_detected_and_repaired(fresh) -> None:
    # Drop the trailing V129 move-signal columns (incl. a resulting_* FK). Re-ensured in order.
    with sqlite3.connect(fresh) as c:
        for col in ("resulting_locator_id", "resulting_entity_id"):
            c.execute(f"ALTER TABLE source_index_move_signals DROP COLUMN {col}")
    assert "resulting_locator_id" not in _cols(fresh, "source_index_move_signals")
    assert SQLiteMigrator(db_path=fresh).apply() == 129
    fks = _fk_map(fresh, "source_index_move_signals")
    assert fks.get("resulting_locator_id") == ("source_index_locators", "locator_id")
    assert fks.get("resulting_entity_id") == ("source_index_entities", "source_entity_id")
    assert _fk_check(fresh) == []


def test_drift_dropped_reconcile_index_repaired(fresh) -> None:
    with sqlite3.connect(fresh) as c:
        c.execute("DROP INDEX idx_locators_reconcile")
    assert "idx_locators_reconcile" not in _indexes(fresh, "source_index_locators")
    assert SQLiteMigrator(db_path=fresh).apply() == 129
    assert "idx_locators_reconcile" in _indexes(fresh, "source_index_locators")
    assert _idx_cols(fresh, "idx_locators_reconcile") == ["source_root_key", "source_id"]


def test_drift_wrong_reconcile_index_predicate_repaired(fresh) -> None:
    # Same name, correct columns, but a WRONG (non-partial) predicate -> detected + DROP/recreated.
    with sqlite3.connect(fresh) as c:
        c.execute("DROP INDEX idx_locators_reconcile")
        c.execute(
            "CREATE INDEX idx_locators_reconcile "
            "ON source_index_locators(source_root_key, source_id)"  # no WHERE partial
        )
    assert _idx_flags(fresh, "source_index_locators", "idx_locators_reconcile") == (0, 0)
    gc = get_connection(fresh)
    try:
        assert SQLiteMigrator._v128_schema_current(gc) is False
    finally:
        gc.close()
    assert SQLiteMigrator(db_path=fresh).apply() == 129
    assert _idx_flags(fresh, "source_index_locators", "idx_locators_reconcile") == (0, 1)
    assert "is_current_locator=1" in _obj_sql(fresh, "idx_locators_reconcile", "index")


def test_drift_malformed_v129_check_fails_closed(fresh) -> None:
    # A malformed disposition CHECK is non-repairable additively -> apply() fails closed and names the
    # V129 layer (v129_schema_parity_failed); the whole transaction rolls back, DB unchanged.
    with sqlite3.connect(fresh) as c:
        c.execute("PRAGMA writable_schema=ON")
        row = c.execute(
            "SELECT sql FROM sqlite_master WHERE name='source_index_move_signals'"
        ).fetchone()[0]
        bad = row.replace("'rejected_target_occupied'", "'WRONG'")
        c.execute(
            "UPDATE sqlite_master SET sql=? WHERE name='source_index_move_signals'", (bad,)
        )
        c.execute("PRAGMA writable_schema=OFF")
        c.execute("DELETE FROM schema_migrations WHERE version=129")
    with pytest.raises(RuntimeError, match="v129_schema_parity_failed"):
        SQLiteMigrator(db_path=fresh).apply()
    # Rolled back: the malformed CHECK (and absent 129 record) are preserved, not silently normalized.
    assert 129 not in _versions(fresh)


# ===================================================================================================
# IMPL-V129-F-003 corrective matrix (ADR-003 R10) — F-001 prefix-guarded repair (classification only)
# + F-002 reference-derived exact-V128-core attribution.
# ===================================================================================================


def _full_master(db: str) -> list[tuple[str, str, str]]:
    """Normalized ``sqlite_master`` (type, name, sql) over the SOURCE-INDEX schema surface (every
    ``source_*`` table + its indexes) — a complete fingerprint of the V128/V129 owned surface used to
    prove a fail-closed apply() left NO persistent mutation to it (whole-transaction rollback). Scoped
    to ``source_*`` so it is not perturbed by orthogonal ambient (autocommit) schedule-schema
    self-heal, which is unrelated to the V129 migration under test."""
    with sqlite3.connect(db) as c:
        rows = c.execute(
            "SELECT type, name, COALESCE(sql, '') FROM sqlite_master "
            "WHERE tbl_name LIKE 'source_%' ORDER BY type, name"
        ).fetchall()
    return [(t, n, " ".join(s.split())) for t, n, s in rows]


def _head_reference(tmp_path: Path) -> str:
    db = str(tmp_path / "head_ref.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return db


# ---------------------------------------------------------------------------------------------------
# F-001: full prefix/suffix repair matrix (both tables, every canonical prefix length)
# ---------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("table", "canonical"),
    [
        ("source_index_locators", LOCATOR_V129_COLS),
        ("source_index_move_signals", MOVE_SIGNAL_V129_COLS),
    ],
)
def test_prefix_suffix_repair_matrix_byte_identical(
    tmp_path: Path, table: str, canonical: tuple[str, ...]
) -> None:
    """For EVERY canonical prefix length (empty prefix … full), drop the trailing V129 suffix of the
    table, apply(), and assert the repaired CREATE SQL is byte-identical to the canonical head schema
    (D1 additive trailing-suffix repair re-adds the missing suffix in canonical order). The two
    ``resulting_*`` move-signal FK columns retain their exact FK definitions after every repair."""
    head_locators = _obj_sql(_head_reference(tmp_path), "source_index_locators")
    for prefix_len in range(len(canonical) + 1):
        db = str(tmp_path / f"{table}_p{prefix_len}.sqlite")
        SQLiteMigrator(db_path=db).apply()
        head_sql = _obj_sql(db, table)  # pristine head CREATE for this table (byte target)
        drop_cols = canonical[prefix_len:]  # the trailing suffix to remove
        if drop_cols:
            with sqlite3.connect(db) as c:
                for col in reversed(drop_cols):  # drop from the end inward
                    c.execute(f"ALTER TABLE {table} DROP COLUMN {col}")
            for col in drop_cols:
                assert col not in _cols(db, table)
        assert SQLiteMigrator(db_path=db).apply() == 129
        # Byte-identical head CREATE SQL after the trailing repair.
        assert _obj_sql(db, table) == head_sql, f"{table} prefix={prefix_len} not byte-identical"
        # The two resulting_* FK columns retain their exact FK definitions.
        fks = _fk_map(db, "source_index_move_signals")
        assert fks.get("resulting_entity_id") == ("source_index_entities", "source_entity_id")
        assert fks.get("resulting_locator_id") == ("source_index_locators", "locator_id")
        # A repair of one table never disturbs the other identity table's head shape.
        assert _obj_sql(db, "source_index_locators") == head_locators


# ---------------------------------------------------------------------------------------------------
# F-002: negative non-suffix cases — pure-V129 residual defect (no V128 drift) -> v129, no mutation
# ---------------------------------------------------------------------------------------------------


def _non_trailing_cases() -> list[tuple[str, str]]:
    cases: list[tuple[str, str]] = []
    for table, canonical in (
        ("source_index_locators", LOCATOR_V129_COLS),
        ("source_index_move_signals", MOVE_SIGNAL_V129_COLS),
    ):
        for col in canonical[:-1]:  # every NON-trailing column (a later canonical column stays present)
            cases.append((table, col))
    return cases


@pytest.mark.parametrize(("table", "dropped_col"), _non_trailing_cases())
def test_non_suffix_omission_attributes_v129_no_mutation(
    tmp_path: Path, table: str, dropped_col: str
) -> None:
    """Dropping a NON-trailing V129 column (a later canonical column remains present) is a non-suffix
    shape: the prefix guard classifies it ``nonrepairable_v129_shape`` and declines repair. With the
    V128 layer exactly correct the attribution is a pure-V129 residual defect -> ``v129_schema_parity_
    failed``; the whole transaction rolls back (exact pre/post schema equality) with no version-129
    ledger entry."""
    db = str(tmp_path / f"nonsuffix_{table}_{dropped_col}.sqlite")
    SQLiteMigrator(db_path=db).apply()
    with sqlite3.connect(db) as c:
        c.execute(f"ALTER TABLE {table} DROP COLUMN {dropped_col}")
        c.execute("DELETE FROM schema_migrations WHERE version=129")
    before = _full_master(db)
    with pytest.raises(RuntimeError, match="v129_schema_parity_failed"):
        SQLiteMigrator(db_path=db).apply()
    assert _full_master(db) == before, "non-repairable shape must leave the schema byte-unchanged"
    assert 129 not in _versions(db)


# ---------------------------------------------------------------------------------------------------
# F-002: the two R10.5 binding combined-drift examples -> v128_schema_parity_failed
# ---------------------------------------------------------------------------------------------------


def test_r10_5_example_a_non_suffix_plus_v128_drift_is_v128(tmp_path: Path) -> None:
    """R10.5 (a): a non-suffix V129 omission on ``source_index_move_signals`` (``disposition_reason``
    absent while the later ``resulting_locator_id`` is present) co-occurring with an independent V128
    drift (an altered owned explicit index). The prefix guard makes NO schema change and assigns NO
    reason; the exact-layer attribution sees V128 drift outside the projected V129 delta -> v128."""
    db = str(tmp_path / "ex_a.sqlite")
    SQLiteMigrator(db_path=db).apply()
    with sqlite3.connect(db) as c:
        c.execute("ALTER TABLE source_index_move_signals DROP COLUMN disposition_reason")  # non-suffix
        assert "resulting_locator_id" in _cols(db, "source_index_move_signals")  # a later col present
        # Independent V128 drift: an owned explicit index altered to the WRONG columns. The additive
        # repair's CREATE INDEX IF NOT EXISTS sees the (wrong) name present and skips it, so it persists.
        c.execute("DROP INDEX idx_si_sources_active")
        c.execute("CREATE INDEX idx_si_sources_active ON source_intelligence_sources(active)")
        c.execute("DELETE FROM schema_migrations WHERE version=129")
    before = _full_master(db)
    with pytest.raises(RuntimeError, match="v128_schema_parity_failed"):
        SQLiteMigrator(db_path=db).apply()
    assert _full_master(db) == before
    assert 129 not in _versions(db)


def test_r10_5_example_b_valid_v129_plus_owned_index_drift_is_v128(tmp_path: Path) -> None:
    """R10.5 (b): the V129 layer on the two identity tables is exactly correct, but an OTHER V128-owned
    object has drifted (an owned explicit index altered). Because the reference-derived delta is
    projected out ONLY from the two V129-touched tables/indexes, the drifted owned index makes the
    projected live V128-core unequal to the 128-reference -> v128, regardless of the intact V129 layer."""
    db = str(tmp_path / "ex_b.sqlite")
    SQLiteMigrator(db_path=db).apply()
    with sqlite3.connect(db) as c:
        # V129 layer untouched (all columns + reconcile index intact); drift an owned supporting index.
        c.execute("DROP INDEX idx_si_metadata_sha")
        c.execute(
            "CREATE INDEX idx_si_metadata_sha "
            "ON source_intelligence_metadata(content_sha256, fts_rowid)"  # wrong (extra) column
        )
        c.execute("DELETE FROM schema_migrations WHERE version=129")
    before = _full_master(db)
    with pytest.raises(RuntimeError, match="v128_schema_parity_failed"):
        SQLiteMigrator(db_path=db).apply()
    assert _full_master(db) == before
    assert 129 not in _versions(db)


# ---------------------------------------------------------------------------------------------------
# F-003: populated V128 -> V129 upgrade preserves data
# ---------------------------------------------------------------------------------------------------

_LOCATOR_V128_COLS = (
    "locator_id", "source_entity_id", "source_id", "source_root_key", "rel_path",
    "is_current_locator", "tombstoned_at", "generation_seq",
)
_MOVE_SIGNAL_V128_COLS = (
    "move_signal_id", "source_locator_id", "source_root_key", "source_rel_path",
    "target_root_key", "target_rel_path", "detected_at", "generation_id", "applied_at",
)


def _rows(db: str, table: str, cols: tuple[str, ...]) -> list[tuple]:
    with sqlite3.connect(db) as c:
        return c.execute(
            f"SELECT {', '.join(cols)} FROM {table} ORDER BY 1"
        ).fetchall()


def test_populated_v128_to_v129_upgrade_preserves_data(tmp_path: Path) -> None:
    """Seed real V128 entity/locator/move-signal rows on a genuine V128 DB, then upgrade to V129: the
    four locator + five move-signal new columns are NULL on every pre-existing row, row counts are
    unchanged, the complete pre-existing V128 payloads are byte-for-byte unchanged, and PRAGMA
    foreign_key_check is clean."""
    db = _make_v128_db(tmp_path, "populated.sqlite")
    with sqlite3.connect(db) as c:
        c.execute("PRAGMA foreign_keys=ON")
        c.execute(
            "INSERT INTO source_index_entities(source_entity_id, created_at, status) "
            "VALUES('e1','2026-01-01T00:00:00Z','LIVE'), ('e2','2026-01-02T00:00:00Z','TOMBSTONED')"
        )
        c.execute(
            "INSERT INTO source_index_locators(locator_id, source_entity_id, source_id, "
            "source_root_key, rel_path, is_current_locator, tombstoned_at, generation_seq) VALUES"
            "('l1','e1','s1','root','a/b.txt',1,NULL,3),"
            "('l2','e2','s2','root','c/d.txt',0,'2026-01-03T00:00:00Z',7)"
        )
        c.execute(
            "INSERT INTO source_index_move_signals(move_signal_id, source_locator_id, source_root_key, "
            "source_rel_path, target_root_key, target_rel_path, detected_at, generation_id, applied_at) "
            "VALUES('m1','l1','root','a/b.txt','root','a/moved.txt','2026-01-04T00:00:00Z','g1',NULL)"
        )
    ent_before = _rows(db, "source_index_entities", ("source_entity_id", "created_at", "status"))
    loc_before = _rows(db, "source_index_locators", _LOCATOR_V128_COLS)
    ms_before = _rows(db, "source_index_move_signals", _MOVE_SIGNAL_V128_COLS)

    assert SQLiteMigrator(db_path=db).apply() == 129

    # Row counts unchanged.
    assert _rows(db, "source_index_entities", ("source_entity_id",)) == [("e1",), ("e2",)]
    assert len(_rows(db, "source_index_locators", ("locator_id",))) == 2
    assert len(_rows(db, "source_index_move_signals", ("move_signal_id",))) == 1
    # Complete pre-existing V128 payloads byte-for-byte unchanged.
    assert _rows(db, "source_index_entities", ("source_entity_id", "created_at", "status")) == ent_before
    assert _rows(db, "source_index_locators", _LOCATOR_V128_COLS) == loc_before
    assert _rows(db, "source_index_move_signals", _MOVE_SIGNAL_V128_COLS) == ms_before
    # The new V129 columns are NULL on every pre-existing row.
    with sqlite3.connect(db) as c:
        loc_new = c.execute(
            f"SELECT {', '.join(LOCATOR_V129_COLS)} FROM source_index_locators"
        ).fetchall()
        ms_new = c.execute(
            f"SELECT {', '.join(MOVE_SIGNAL_V129_COLS)} FROM source_index_move_signals"
        ).fetchall()
    assert all(all(v is None for v in row) for row in loc_new)
    assert all(all(v is None for v in row) for row in ms_new)
    assert _fk_check(db) == []


# ---------------------------------------------------------------------------------------------------
# F-003: mid-migration rollback (exception after >=1 _v129_ensure_* helper) -> whole-transaction undo
# ---------------------------------------------------------------------------------------------------


def test_mid_migration_exception_rolls_back_to_v128(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Inject an exception in the reconcile-index repair — which runs AFTER the two ``_v129_ensure_*``
    column helpers have already added V129 columns in this transaction — and assert the whole apply()
    transaction rolls back: no V129 DDL survives, no version-129 row is recorded, the DB is at the exact
    V128 schema, and PRAGMA foreign_key_check is clean."""
    db = _make_v128_db(tmp_path, "rollback.sqlite")
    pristine_v128 = _full_master(_make_v128_db(tmp_path, "pristine_v128.sqlite"))
    assert _full_master(db) == pristine_v128  # both are genuine, identical V128 schemas

    def _boom(conn: sqlite3.Connection) -> None:
        raise RuntimeError("injected mid-migration failure")

    monkeypatch.setattr(SQLiteMigrator, "_v129_ensure_reconcile_index", staticmethod(_boom))

    with pytest.raises(RuntimeError, match="injected mid-migration failure"):
        SQLiteMigrator(db_path=db).apply()

    # Whole-transaction rollback: no V129 columns, no reconcile index, no version-129 row.
    for col in LOCATOR_V129_COLS:
        assert col not in _cols(db, "source_index_locators")
    for col in MOVE_SIGNAL_V129_COLS:
        assert col not in _cols(db, "source_index_move_signals")
    assert "idx_locators_reconcile" not in _indexes(db, "source_index_locators")
    assert 129 not in _versions(db)
    assert max(_versions(db)) == 128
    # DB is at the exact V128 schema, foreign_key_check clean.
    assert _full_master(db) == pristine_v128
    assert _fk_check(db) == []
