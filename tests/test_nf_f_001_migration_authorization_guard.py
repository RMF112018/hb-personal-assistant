"""NF-F-001 corrective prove-green: the migration-ownership authorization guard on
``SQLiteMigrator.apply()`` after audit AUDIT-...-R1 (NF-AUD-003/004/005).

A REAL temp SQLite file is treated as the canonical managed database by redirecting the canonical
managed-path accessor (``nas_default_db_path``) to it, so the production storage-class classifier and
the opened-target identity run end-to-end against a genuine (disposable) DB — no ``/volume2`` access.
"""

from __future__ import annotations

import dataclasses
import os
import sqlite3
from datetime import timedelta, timezone
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
    db = (tmp_path / "managed" / "db" / "hb-personal-assistant.sqlite").resolve()
    db.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(g, "nas_default_db_path", lambda: db)
    monkeypatch.setattr(g, "_mac_managed_db_path", lambda: (tmp_path / "no-mac").resolve())
    monkeypatch.delenv("HB_NAS_RUNTIME", raising=False)
    assert g.classify_storage_class(db) is SC.MANAGED_PRODUCTION
    return db


def _admin_auth(db: Path, *, origin: int):
    """Mint a managed authorization via the enforced ADMIN capability (no receipt needed)."""
    return ma.authorize_migration(
        ma.acquire_admin_capability({"role": "admin"}),
        resolved_path=str(db),
        expected_origin_version=origin,
        target_version=LATEST_SCHEMA_VERSION,
    )


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


def _open_fd_count() -> int:
    try:
        return len(os.listdir("/dev/fd"))
    except OSError:
        return len(os.listdir(f"/proc/{os.getpid()}/fd"))


# --- NF-AUD-003: no managed at-head bypass --------------------------------------------------------


def test_managed_apply_without_authorization_is_refused(managed_db):
    with pytest.raises(MigrationAuthorizationRequired):
        SQLiteMigrator(str(managed_db)).apply()
    assert _schema_version(managed_db) == 0


def test_managed_at_head_apply_none_is_rejected_no_bypass(managed_db):
    # Migrate to head with authorization, then a bare apply() at head must STILL be rejected — there
    # is no authorization-free managed at-head path (NF-AUD-003).
    SQLiteMigrator(str(managed_db)).apply(authorization=_admin_auth(managed_db, origin=0))
    assert _schema_version(managed_db) == LATEST_SCHEMA_VERSION
    with pytest.raises(MigrationAuthorizationRequired):
        SQLiteMigrator(str(managed_db)).apply()


def test_authorized_managed_migration_reaches_head(managed_db):
    v = SQLiteMigrator(str(managed_db)).apply(authorization=_admin_auth(managed_db, origin=0))
    assert v == LATEST_SCHEMA_VERSION


def test_ensure_schema_ready_does_not_migrate_managed(managed_db):
    from hb_assistant.store.errors import SchemaVersionBehind
    from hb_assistant.store.migrator import ensure_schema_ready

    with pytest.raises(SchemaVersionBehind):
        ensure_schema_ready(str(managed_db))  # behind managed -> readiness raises, never migrates
    assert _schema_version(managed_db) == 0


# --- NF-AUD-004: enforced issuer capability -------------------------------------------------------


def test_capability_cannot_be_constructed_directly():
    with pytest.raises(MigrationAuthorizationInvalid):
        ma.MigrationCapability(
            operation=ma.MigrationOperation.STARTUP,
            actor_class="startup",
            route_class="r",
            allowed_storage_classes=frozenset(),
            backup_receipt=None,
        )


def test_incidental_code_cannot_mint_managed_authorization(managed_db, monkeypatch):
    # There is no public factory that mints a managed authorization from caller-asserted fields.
    # authorize_migration REQUIRES a MigrationCapability; a plain object / None is refused.
    with pytest.raises((MigrationAuthorizationInvalid, AttributeError, TypeError)):
        ma.authorize_migration(
            object(), resolved_path=str(managed_db), expected_origin_version=0, target_version=127
        )
    # And the acquirers enforce their gate: admin requires the admin role.
    with pytest.raises(MigrationAuthorizationRequired):
        ma.acquire_admin_capability({"role": "viewer"})


def test_startup_capability_requires_operator_flag(managed_db, monkeypatch):
    monkeypatch.delenv("HB_ALLOW_STARTUP_MIGRATIONS", raising=False)
    with pytest.raises(MigrationAuthorizationRequired):
        ma.acquire_startup_capability()


def test_local_bootstrap_capability_cannot_target_production(managed_db):
    # The local-bootstrap capability is scoped to MANAGED_LOCAL; used against managed-production it
    # is denied — it can never migrate the NAS managed DB.
    with pytest.raises(MigrationStorageClassDenied):
        ma.authorize_migration(
            ma.acquire_local_bootstrap_capability(),
            resolved_path=str(managed_db),
            expected_origin_version=0,
            target_version=LATEST_SCHEMA_VERSION,
        )


def test_forged_authorization_rejected(managed_db):
    forged = dataclasses.replace(_admin_auth(managed_db, origin=0), integrity_tag="0" * 64)
    with pytest.raises(MigrationAuthorizationInvalid):
        SQLiteMigrator(str(managed_db)).apply(authorization=forged)
    assert _schema_version(managed_db) == 0


def test_actor_route_tamper_rejected(managed_db):
    # Rebinding actor/route without re-signing breaks the HMAC (actor/route are part of the payload).
    auth = _admin_auth(managed_db, origin=0)
    tampered = dataclasses.replace(auth, actor_class="startup", route_class="startup_schema_policy")
    with pytest.raises(MigrationAuthorizationInvalid):
        SQLiteMigrator(str(managed_db)).apply(authorization=tampered)


def test_wrong_origin_version_rejected(managed_db):
    with pytest.raises(MigrationVersionMismatch):
        SQLiteMigrator(str(managed_db)).apply(authorization=_admin_auth(managed_db, origin=5))
    assert _schema_version(managed_db) == 0


def test_expired_authorization_rejected(managed_db):
    from datetime import datetime

    auth = _admin_auth(managed_db, origin=0)
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    expired = ma.authorize_migration(
        ma.acquire_admin_capability({"role": "admin"}),
        resolved_path=str(managed_db),
        expected_origin_version=0,
        target_version=LATEST_SCHEMA_VERSION,
        expires_at=past,
    )
    with pytest.raises(MigrationAuthorizationExpired):
        SQLiteMigrator(str(managed_db)).apply(authorization=expired)
    assert auth is not None


def test_snapshot_is_never_migrated(tmp_path, monkeypatch):
    snap = (tmp_path / "mcp-snapshot" / "db" / "hb-personal-assistant.sqlite").resolve()
    snap.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(g, "snapshot_db_path", lambda: snap)
    monkeypatch.delenv("HB_NAS_RUNTIME", raising=False)
    assert g.classify_storage_class(snap) is SC.READ_ONLY_SNAPSHOT
    with pytest.raises(MigrationStorageClassDenied):
        SQLiteMigrator(str(snap)).apply()


# --- NF-AUD-005: FD-stable opened-target identity -------------------------------------------------


def test_authorization_binds_device_inode_when_target_exists(managed_db):
    # First migration creates the file; a subsequent authorization (file now exists) binds device/inode.
    SQLiteMigrator(str(managed_db)).apply(authorization=_admin_auth(managed_db, origin=0))
    auth = _admin_auth(managed_db, origin=LATEST_SCHEMA_VERSION)
    assert auth.target_identity.device is not None
    assert auth.target_identity.inode is not None


def test_inode_substitution_between_mint_and_open_is_rejected(managed_db):
    # Migrate to head, then mint a fresh at-head authorization bound to the current inode.
    SQLiteMigrator(str(managed_db)).apply(authorization=_admin_auth(managed_db, origin=0))
    auth = _admin_auth(managed_db, origin=LATEST_SCHEMA_VERSION)
    bound_ino = auth.target_identity.inode
    assert bound_ino is not None
    # Replace the file at the same path with a DIFFERENT inode (rename-replace) before apply opens it.
    replacement = managed_db.parent / "replacement.sqlite"
    # a valid at-head DB copy so classification stays managed and open succeeds
    import shutil

    shutil.copy2(managed_db, replacement)
    os.replace(replacement, managed_db)  # atomic swap -> new inode at the same path
    assert os.stat(managed_db).st_ino != bound_ino
    with pytest.raises(MigrationTargetMismatch):
        SQLiteMigrator(str(managed_db)).apply(authorization=auth)


def test_opened_identity_carries_guard_fd_and_device_inode(managed_db):
    SQLiteMigrator(str(managed_db)).apply(authorization=_admin_auth(managed_db, origin=0))
    con = get_connection(str(managed_db))
    opened = describe_opened_database(con, str(managed_db))
    try:
        assert opened.guard_fd is not None
        assert opened.device is not None and opened.inode is not None
        st = os.fstat(opened.guard_fd)
        assert (st.st_dev, st.st_ino) == (opened.device, opened.inode)
    finally:
        if opened.guard_fd is not None:
            os.close(opened.guard_fd)
        con.close()


def test_opened_identity_is_derived_from_live_connection_not_declared_path(managed_db, tmp_path):
    real = (tmp_path / "actually_here.sqlite").resolve()
    con = get_connection(str(real))
    try:
        opened = describe_opened_database(con, str(managed_db))  # declared = managed canonical
        assert opened.resolved_path == str(real)
        assert opened.storage_class is SC.DISPOSABLE_REHEARSAL
    finally:
        if opened.guard_fd is not None:
            os.close(opened.guard_fd)
        con.close()


def test_hardlink_to_managed_is_still_the_same_inode(managed_db, tmp_path):
    # A hardlink shares the inode, so an authorization bound to the managed inode remains valid when
    # opened via the hardlink path only if it still classifies managed; here we assert the identity
    # (device/inode) is shared, which is the property the guard relies on.
    SQLiteMigrator(str(managed_db)).apply(authorization=_admin_auth(managed_db, origin=0))
    link = tmp_path / "hardlink.sqlite"
    os.link(managed_db, link)
    assert os.stat(link).st_ino == os.stat(managed_db).st_ino


# --- RC-3 borrowed-connection atomicity + FD stability --------------------------------------------


def test_rc3_borrowed_connection_in_transaction_is_refused(tmp_path):
    db = tmp_path / "rehearsal.sqlite"
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
        assert con.execute("SELECT 1").fetchone()[0] == 1
    finally:
        con.close()


def test_no_fd_growth_under_repeated_rejected_calls(managed_db):
    SQLiteMigrator(str(managed_db)).apply(authorization=_admin_auth(managed_db, origin=0))
    forged = dataclasses.replace(_admin_auth(managed_db, origin=LATEST_SCHEMA_VERSION), integrity_tag="0" * 64)
    baseline = _open_fd_count()
    for _ in range(25):
        with pytest.raises(MigrationAuthorizationRequired):
            SQLiteMigrator(str(managed_db)).apply()  # at-head, no auth -> rejected
        with pytest.raises(MigrationAuthorizationInvalid):
            SQLiteMigrator(str(managed_db)).apply(authorization=forged)  # forged -> rejected
    after = _open_fd_count()
    assert after <= baseline + 2, f"fd leak: baseline={baseline} after={after}"


def test_non_managed_temp_fixture_still_self_heals(tmp_path):
    db = tmp_path / "fixture.sqlite"
    assert SQLiteMigrator(str(db)).apply() == LATEST_SCHEMA_VERSION
