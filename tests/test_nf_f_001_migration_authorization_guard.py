"""NF-F-001 prove-green: the migration-ownership authorization guard on ``SQLiteMigrator.apply()``.

These tests treat a REAL temp SQLite file as the canonical managed database by redirecting the
canonical managed-path accessors (``nas_default_db_path`` / ``_mac_managed_db_path``) to the temp
file, so the production storage-class classifier and opened-target identity run end-to-end against a
genuine (disposable) DB — no ``/volume2`` access. They assert the invariant: a managed database is
never migrated ambiently, and a genuine managed migration is authorized, target-bound, and validated
BEFORE any DDL.

Prove-red: every managed-enforcement test here fails on the base tree (where ``apply()`` takes no
authorization and migrates any target unconditionally). The base failure is recorded in the evidence
bundle via the stash-isolation procedure.
"""

from __future__ import annotations

import dataclasses
import os
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.config import db_storage_guard as g
from hb_assistant.config.db_storage_guard import DatabaseStorageClass as SC
from hb_assistant.store import migration_authorization as ma
from hb_assistant.store.connection import get_connection
from hb_assistant.store.database_identity import describe_opened_database
from hb_assistant.store.errors import (
    MigrationAuthorizationExpired,
    MigrationAuthorizationInvalid,
    MigrationAuthorizationRequired,
    MigrationStorageClassDenied,
    MigrationTargetMismatch,
    MigrationVersionMismatch,
)
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator


@pytest.fixture
def managed_db(tmp_path, monkeypatch):
    """A real temp SQLite path treated as the canonical MANAGED_PRODUCTION database."""
    db = (tmp_path / "managed" / "db" / "hb-personal-assistant.sqlite").resolve()
    db.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(g, "nas_default_db_path", lambda: db)
    # Ensure nothing else accidentally matches.
    monkeypatch.setattr(g, "_mac_managed_db_path", lambda: (tmp_path / "no-mac").resolve())
    monkeypatch.delenv("HB_NAS_RUNTIME", raising=False)
    assert g.classify_storage_class(db) is SC.MANAGED_PRODUCTION
    return db


@pytest.fixture
def managed_local_db(tmp_path, monkeypatch):
    """A real temp SQLite path treated as the canonical MANAGED_LOCAL database."""
    db = (tmp_path / "local" / "db" / "hb-personal-assistant.sqlite").resolve()
    db.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(g, "_mac_managed_db_path", lambda: db)
    monkeypatch.setattr(g, "nas_default_db_path", lambda: (tmp_path / "no-nas").resolve())
    monkeypatch.delenv("HB_NAS_RUNTIME", raising=False)
    assert g.classify_storage_class(db) is SC.MANAGED_LOCAL
    return db


def _managed_auth(db: Path, *, origin: int, operation=ma.MigrationOperation.STARTUP):
    return ma.issue_managed_authorization(
        operation=operation,
        resolved_path=str(db),
        actor_class="startup",
        route_class="startup_schema_policy",
        execution_id="exec-test",
        expected_origin_version=origin,
        target_version=LATEST_SCHEMA_VERSION,
        backup_receipt=ma.ValidatedBackupReceipt(
            schema_version=origin, generated_utc="2026-07-15T00:00:00Z", backup_digest="deadbeef"
        ),
    )


def _open_fd_count() -> int:
    try:
        return len(os.listdir("/dev/fd"))
    except OSError:
        return len(os.listdir(f"/proc/{os.getpid()}/fd"))


# --- ambient prohibition (prove-red on base) ------------------------------------------------------


def test_managed_apply_without_authorization_is_refused_before_any_ddl(managed_db):
    with pytest.raises(MigrationAuthorizationRequired):
        SQLiteMigrator(str(managed_db)).apply()
    # Fail-closed BEFORE mutation: the schema ledger was never created.
    assert not managed_db.exists() or _schema_version(managed_db) == 0


def test_managed_local_apply_without_authorization_is_refused(managed_local_db):
    with pytest.raises(MigrationAuthorizationRequired):
        SQLiteMigrator(str(managed_local_db)).apply()


def _schema_version(db: Path) -> int:
    if not db.exists():
        return 0
    con = sqlite3.connect(str(db))
    try:
        row = con.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        return int(row[0]) if row and row[0] is not None else 0
    except sqlite3.OperationalError:
        return 0
    finally:
        con.close()


# --- authorized managed migration succeeds and is bound --------------------------------------------


def test_authorized_managed_migration_reaches_head(managed_db):
    auth = _managed_auth(managed_db, origin=0)
    v = SQLiteMigrator(str(managed_db)).apply(authorization=auth, require_backup_receipt=True)
    assert v == LATEST_SCHEMA_VERSION
    assert _schema_version(managed_db) == LATEST_SCHEMA_VERSION


def test_managed_at_head_is_a_noop_without_authorization(managed_db):
    # First migrate with authorization, then a bare apply() at head is an ordinary no-op.
    SQLiteMigrator(str(managed_db)).apply(
        authorization=_managed_auth(managed_db, origin=0), require_backup_receipt=True
    )
    v = SQLiteMigrator(str(managed_db)).apply()  # no authorization
    assert v == LATEST_SCHEMA_VERSION


# --- rejection matrix (each rejects BEFORE mutation) -----------------------------------------------


def test_forged_authorization_rejected(managed_db):
    auth = _managed_auth(managed_db, origin=0)
    forged = dataclasses.replace(auth, integrity_tag="0" * 64)
    with pytest.raises(MigrationAuthorizationInvalid):
        SQLiteMigrator(str(managed_db)).apply(authorization=forged, require_backup_receipt=True)
    assert _schema_version(managed_db) == 0


def test_expired_authorization_rejected(managed_db):
    from datetime import datetime, timedelta, timezone

    auth = _managed_auth(managed_db, origin=0)
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    # Re-mint with an expiry in the past by rebuilding through the internal issuer.
    expired = ma._issue(
        authorization_id=auth.authorization_id,
        execution_id=auth.execution_id,
        actor_class=auth.actor_class,
        route_class=auth.route_class,
        operation=auth.operation,
        target_identity=auth.target_identity,
        expected_origin_version=auth.expected_origin_version,
        target_version=auth.target_version,
        backup_receipt=auth.backup_receipt,
        issued_at=past - timedelta(hours=1),
        expires_at=past,
    )
    with pytest.raises(MigrationAuthorizationExpired):
        SQLiteMigrator(str(managed_db)).apply(authorization=expired, require_backup_receipt=True)
    assert _schema_version(managed_db) == 0


def test_target_mismatch_rejected(managed_db, tmp_path):
    # Authorization bound to a DIFFERENT path than the one opened.
    other = (tmp_path / "managed" / "db" / "other.sqlite").resolve()
    auth = ma.issue_managed_authorization(
        operation=ma.MigrationOperation.STARTUP,
        resolved_path=str(other),
        actor_class="startup",
        route_class="r",
        execution_id="e",
        expected_origin_version=0,
        target_version=LATEST_SCHEMA_VERSION,
        backup_receipt=ma.ValidatedBackupReceipt(0, "u", "d"),
    )
    # 'other' is not the managed canonical path, so issue bound it as... managed? No: issue_managed
    # forces MANAGED_PRODUCTION regardless, but validate compares resolved_path vs opened.
    with pytest.raises((MigrationTargetMismatch, MigrationStorageClassDenied)):
        SQLiteMigrator(str(managed_db)).apply(authorization=auth, require_backup_receipt=True)
    assert _schema_version(managed_db) == 0


def test_wrong_origin_version_rejected(managed_db):
    # Declare origin 5 but the DB is fresh (origin 0).
    auth = _managed_auth(managed_db, origin=5)
    with pytest.raises(MigrationVersionMismatch):
        SQLiteMigrator(str(managed_db)).apply(authorization=auth, require_backup_receipt=True)
    assert _schema_version(managed_db) == 0


def test_snapshot_is_never_migrated(tmp_path, monkeypatch):
    snap = (tmp_path / "mcp-snapshot" / "db" / "hb-personal-assistant.sqlite").resolve()
    snap.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(g, "snapshot_db_path", lambda: snap)
    monkeypatch.delenv("HB_NAS_RUNTIME", raising=False)
    assert g.classify_storage_class(snap) is SC.READ_ONLY_SNAPSHOT
    with pytest.raises(MigrationStorageClassDenied):
        SQLiteMigrator(str(snap)).apply()


# --- opened-target identity substitution ----------------------------------------------------------


def test_opened_identity_is_derived_from_live_connection_not_declared_path(managed_db, tmp_path):
    # Anti-spoofing: even when a caller DECLARES the managed canonical path, the opened identity is
    # derived from the file SQLite actually opened (PRAGMA database_list), so a connection on a
    # different file is classified by that real file — a declared managed path cannot launder a
    # non-managed target into managed authorization.
    real = (tmp_path / "actually_here.sqlite").resolve()
    con = get_connection(str(real))
    try:
        opened = describe_opened_database(con, str(managed_db))  # declared = managed canonical
        assert opened.resolved_path == str(real)  # identity reflects the real opened file
        assert opened.storage_class is SC.DISPOSABLE_REHEARSAL  # tmp, not managed
    finally:
        con.close()


def test_apply_on_a_declared_managed_but_actually_nonmanaged_connection_self_heals(managed_db, tmp_path):
    # Consequence of the above: borrowing a connection actually opened on a non-managed file makes
    # apply() treat it as non-managed (ambient self-heal), regardless of self._db_path — the guard
    # follows the opened file, never the label.
    real = tmp_path / "borrowed.sqlite"
    con = get_connection(str(real))
    try:
        v = SQLiteMigrator(str(managed_db)).apply(conn=con)  # db_path says managed; conn says tmp
        assert v == LATEST_SCHEMA_VERSION
    finally:
        con.close()


# --- RC-3 borrowed-connection atomicity -----------------------------------------------------------


def test_rc3_borrowed_connection_in_transaction_is_refused(tmp_path):
    db = tmp_path / "rehearsal.sqlite"  # non-managed (temp) — isolates the RC-3 check
    con = get_connection(str(db))
    con.execute("BEGIN")
    con.execute("CREATE TABLE marker(x)")
    try:
        with pytest.raises(MigrationAuthorizationInvalid):
            SQLiteMigrator(str(db)).apply(conn=con)
    finally:
        con.rollback()
        con.close()


def test_rc3_borrowed_clean_connection_migrates_and_stays_usable(tmp_path):
    db = tmp_path / "rehearsal2.sqlite"
    con = get_connection(str(db))
    try:
        v = SQLiteMigrator(str(db)).apply(conn=con)
        assert v == LATEST_SCHEMA_VERSION
        # Caller still owns the connection (not closed by apply).
        assert con.execute("SELECT 1").fetchone()[0] == 1
    finally:
        con.close()


# --- FD stability ---------------------------------------------------------------------------------


def test_no_fd_growth_under_repeated_at_head_and_rejected_calls(managed_db):
    # After migrating to head: repeated at-head no-op calls (None auth) and repeated rejected calls
    # (forged auth -> validation failure). Neither path may leak the migration connection's fd.
    SQLiteMigrator(str(managed_db)).apply(
        authorization=_managed_auth(managed_db, origin=0), require_backup_receipt=True
    )
    forged = dataclasses.replace(_managed_auth(managed_db, origin=0), integrity_tag="0" * 64)
    baseline = _open_fd_count()
    for _ in range(25):
        assert SQLiteMigrator(str(managed_db)).apply() == LATEST_SCHEMA_VERSION  # at-head no-op
        with pytest.raises(MigrationAuthorizationInvalid):
            SQLiteMigrator(str(managed_db)).apply(authorization=forged, require_backup_receipt=True)
    after = _open_fd_count()
    assert after <= baseline + 2, f"fd leak: baseline={baseline} after={after}"


# --- non-managed self-heal preserved --------------------------------------------------------------


def test_non_managed_temp_fixture_still_self_heals(tmp_path):
    db = tmp_path / "fixture.sqlite"
    v = SQLiteMigrator(str(db)).apply()  # no authorization, rehearsal -> allowed
    assert v == LATEST_SCHEMA_VERSION
