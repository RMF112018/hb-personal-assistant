"""NF-F-001 Stage 8: runtime reachability — ordinary request paths perform 0 managed migrations.

Instruments the migrator's ``migration_started`` audit event to COUNT actual managed migrations while
an ordinary analytics request path (the ``ConstructionStore`` constructor, N-A4) runs against a
managed-classified fixture. A real temp SQLite file is treated as the canonical managed DB (canonical
path accessors redirected) — no ``/volume2`` access.
"""

from __future__ import annotations

import logging

import pytest

from hb_assistant.config import db_storage_guard as g
from hb_assistant.config.db_storage_guard import DatabaseStorageClass as SC
from hb_assistant.construction.store.repositories import ConstructionStore
from hb_assistant.store import migration_authorization as ma
from hb_assistant.store.errors import SchemaVersionBehind
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator


def _admin_auth(db, *, origin):
    return ma.authorize_migration(
        ma.acquire_admin_capability({"role": "admin"}),
        resolved_path=str(db),
        expected_origin_version=origin,
        target_version=LATEST_SCHEMA_VERSION,
    )


def _managed_fixture(tmp_path, monkeypatch):
    db = (tmp_path / "managed" / "db" / "hb-personal-assistant.sqlite").resolve()
    db.parent.mkdir(parents=True, exist_ok=True)
    db.touch()  # RC-C: the managed-production DB exists in reality; bind identity at mint
    monkeypatch.setattr(g, "nas_default_db_path", lambda: db)
    monkeypatch.setattr(g, "_mac_managed_db_path", lambda: (tmp_path / "no-mac").resolve())
    monkeypatch.delenv("HB_NAS_RUNTIME", raising=False)
    assert g.classify_storage_class(db) is SC.MANAGED_PRODUCTION
    return db


def _count_migration_started(caplog) -> int:
    return sum(
        1
        for r in caplog.records
        if getattr(r, "migration_audit", {}).get("outcome") == "started"
    )


def test_constructor_on_behind_managed_db_performs_zero_migrations(tmp_path, monkeypatch, caplog):
    db = _managed_fixture(tmp_path, monkeypatch)
    # Bring the managed fixture to head-1 by authorizing a real migration, then rewind the ledger to
    # simulate a behind managed DB.
    auth = _admin_auth(db, origin=0)
    SQLiteMigrator(str(db)).apply(authorization=auth)
    import sqlite3

    con = sqlite3.connect(str(db))
    con.execute("DELETE FROM schema_migrations WHERE version = ?", (LATEST_SCHEMA_VERSION,))
    con.commit()
    con.close()

    with (
        caplog.at_level(logging.INFO, logger="hb_assistant.store.migration_audit"),
        pytest.raises(SchemaVersionBehind),
    ):
        ConstructionStore(str(db))  # ordinary construction must NOT migrate the managed DB

    assert _count_migration_started(caplog) == 0, "constructor ambiently migrated the managed DB"


def test_constructor_on_at_head_managed_db_is_ready_without_migration(tmp_path, monkeypatch, caplog):
    db = _managed_fixture(tmp_path, monkeypatch)
    auth = _admin_auth(db, origin=0)
    SQLiteMigrator(str(db)).apply(authorization=auth)

    with caplog.at_level(logging.INFO, logger="hb_assistant.store.migration_audit"):
        ConstructionStore(str(db))  # at head -> readiness passes, no migration

    assert _count_migration_started(caplog) == 0
