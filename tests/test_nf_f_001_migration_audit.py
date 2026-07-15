"""NF-F-001 Stage 6: sanitized migration-guard audit events emit no sensitive material."""

from __future__ import annotations

import logging

import pytest

from hb_assistant.config import db_storage_guard as g
from hb_assistant.config.db_storage_guard import DatabaseStorageClass as SC
from hb_assistant.store.errors import MigrationAuthorizationRequired
from hb_assistant.store.migration_audit import emit_migration_event
from hb_assistant.store.migrator import SQLiteMigrator

_SENSITIVE_KEYS = ("integrity_tag", "secret", "backup_digest", "resolved_path", "db_path", "path")


def test_emit_returns_only_sanitized_fields():
    rec = emit_migration_event(
        "migration_started",
        storage_class="managed_production",
        operation="startup",
        actor_class="startup",
        route_class="startup_schema_policy",
        outcome="started",
        origin_version=124,
        target_version=127,
    )
    assert rec["event"] == "migration_started"
    assert rec["storage_class"] == "managed_production"
    assert rec["origin_version"] == 124
    for key in _SENSITIVE_KEYS:
        assert key not in rec


def test_forbidden_fields_are_never_recorded():
    # Even if a value is passed that looks path-like, no path/secret key ends up in the record.
    rec = emit_migration_event("migration_rejected", storage_class="blocked", outcome="rejected")
    assert set(rec).issubset(
        {"event", "storage_class", "operation", "actor_class", "route_class", "outcome",
         "reason", "origin_version", "target_version"}
    )


def test_rejected_managed_apply_emits_audit_without_path_or_secret(tmp_path, monkeypatch, caplog):
    db = (tmp_path / "managed" / "db" / "hb-personal-assistant.sqlite").resolve()
    db.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(g, "nas_default_db_path", lambda: db)
    monkeypatch.setattr(g, "_mac_managed_db_path", lambda: (tmp_path / "no-mac").resolve())
    monkeypatch.delenv("HB_NAS_RUNTIME", raising=False)
    assert g.classify_storage_class(db) is SC.MANAGED_PRODUCTION

    with (
        caplog.at_level(logging.INFO, logger="hb_assistant.store.migration_audit"),
        pytest.raises(MigrationAuthorizationRequired),
    ):
        SQLiteMigrator(str(db)).apply()

    records = [r for r in caplog.records if hasattr(r, "migration_audit")]
    assert records, "expected a migration_audit record"
    rejected = [r.migration_audit for r in records if r.migration_audit.get("outcome") == "rejected"]
    assert rejected, "expected a rejected audit record"
    for audit in (r.migration_audit for r in records):
        for key in _SENSITIVE_KEYS:
            assert key not in audit
        # No absolute path or the managed filename leaks into any recorded value.
        blob = "|".join(str(v) for v in audit.values())
        assert str(db) not in blob
        assert "hb-personal-assistant.sqlite" not in blob
