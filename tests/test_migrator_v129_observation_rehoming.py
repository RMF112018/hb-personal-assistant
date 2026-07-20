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
