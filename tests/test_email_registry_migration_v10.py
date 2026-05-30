"""Phase 06 Prompt 02 — V10 migration + store-adapter read-only locks.

Proves V10 adds the active-policy + mailbox-source-registry tables additively
(V1-V9 and the V5 deferred-state row preserved), that the SQLite CHECK
constraints reject mutation/full-body/backfill at the database layer, and that
the store adapter raises ValueError before SQL ever runs.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from hb_assistant.construction.store.repositories import ConstructionStore
from hb_assistant.store.migrator import SQLiteMigrator

_V10_TABLES = {"email_intelligence_active_policy", "email_source_locations"}
_V10_INDEXES = {"ix_email_source_locations_owner", "ix_email_source_locations_role"}


def _temp_db() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        return Path(tf.name)


def _migrate(db: Path) -> int:
    return SQLiteMigrator(db_path=str(db)).apply()


def _names(db: Path, kind: str) -> set[str]:
    conn = sqlite3.connect(str(db))
    try:
        return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type=?", (kind,))}
    finally:
        conn.close()


def test_v10_applies_and_creates_tables_and_indexes() -> None:
    db = _temp_db()
    assert _migrate(db) == 10
    tables = _names(db, "table")
    assert not (_V10_TABLES - tables), f"V10 tables missing: {sorted(_V10_TABLES - tables)}"
    indexes = _names(db, "index")
    assert not (_V10_INDEXES - indexes), f"V10 indexes missing: {sorted(_V10_INDEXES - indexes)}"


def test_v10_preserves_v1_v9_and_deferred_state_table() -> None:
    db = _temp_db()
    _migrate(db)
    tables = _names(db, "table")
    assert "source_records" in tables  # V1 core
    assert {"procore_live_records", "procore_financial_contracts"} <= tables  # V6/V8
    # The historical deferred-state table is preserved untouched.
    assert "construction_email_intelligence_deferred_state" in tables


def test_v10_is_idempotent() -> None:
    db = _temp_db()
    assert _migrate(db) == 10
    assert _migrate(db) == 10
    conn = sqlite3.connect(str(db))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM schema_migrations WHERE version = 10"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == 1


@pytest.mark.parametrize(
    "column",
    [
        "writeback_allowed",
        "mailbox_mutation_allowed",
        "full_archive_crawl",
        "source_copy_to_vault",
        "full_email_body_in_obsidian",
        "attachment_content_download_by_default",
    ],
)
def test_active_policy_check_rejects_loosened_flag(column: str) -> None:
    db = _temp_db()
    _migrate(db)
    conn = sqlite3.connect(str(db))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                f"INSERT INTO email_intelligence_active_policy (id, policy_phase, {column}) "
                f"VALUES (1, 'phase_06', 1)"
            )
    finally:
        conn.close()


def test_source_location_check_rejects_read_only_false_and_allowed_flags() -> None:
    db = _temp_db()
    _migrate(db)
    conn = sqlite3.connect(str(db))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO email_source_locations "
                "(source_id, mailbox_owner_hash, folder_role, read_only) "
                "VALUES ('s1', 'h', 'inbox', 0)"
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO email_source_locations "
                "(source_id, mailbox_owner_hash, folder_role, mailbox_mutation_allowed) "
                "VALUES ('s2', 'h', 'inbox', 1)"
            )
    finally:
        conn.close()


# --- store adapter guards (raise before SQL) --------------------------------


def test_set_active_policy_persists_and_round_trips() -> None:
    store = ConstructionStore(str(_temp_db()))
    store.set_email_intelligence_active_policy(policy_phase="phase_06", default_lookback_days=30)
    row = store.get_email_intelligence_active_policy()
    assert row is not None
    assert row["mailbox_mode"] == "read_only"
    assert row["writeback_allowed"] is False
    assert row["mailbox_mutation_allowed"] is False
    assert row["metadata_only_by_default"] is True
    assert row["initial_backfill_mode"] == "pilot_projects_only"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"mailbox_mode": "read_write"},
        {"writeback_allowed": True},
        {"mailbox_mutation_allowed": True},
        {"full_archive_crawl": True},
        {"source_copy_to_vault": True},
        {"full_email_body_in_obsidian": True},
        {"attachment_content_download_by_default": True},
        {"metadata_only_by_default": False},
        {"review_required_for_sensitive": False},
        {"initial_backfill_mode": "full_mailbox"},
        {"ollama_invalid_json_routes_to_review": False},
    ],
)
def test_set_active_policy_adapter_guards(kwargs: dict) -> None:
    store = ConstructionStore(str(_temp_db()))
    with pytest.raises(ValueError):
        store.set_email_intelligence_active_policy(policy_phase="phase_06", **kwargs)


def test_upsert_email_source_location_persists_and_round_trips() -> None:
    store = ConstructionStore(str(_temp_db()))
    store.upsert_email_source_location(
        source_id="outlook:hash:inbox",
        mailbox_owner_hash="hash",
        folder_role="inbox",
        folder_display_name="Inbox",
        include_in_sync=True,
    )
    row = store.get_email_source_location("outlook:hash:inbox")
    assert row is not None
    assert row["read_only"] is True
    assert row["mailbox_mutation_allowed"] is False
    assert row["include_in_sync"] is True
    listed = store.list_email_source_locations(mailbox_owner_hash="hash")
    assert len(listed) == 1


@pytest.mark.parametrize(
    "kwargs",
    [
        {"read_only": False},
        {"mailbox_mutation_allowed": True},
        {"full_archive_crawl_allowed": True},
        {"source_copy_to_vault_allowed": True},
        {"full_email_body_in_obsidian_allowed": True},
    ],
)
def test_upsert_email_source_location_adapter_guards(kwargs: dict) -> None:
    store = ConstructionStore(str(_temp_db()))
    with pytest.raises(ValueError):
        store.upsert_email_source_location(
            source_id="s",
            mailbox_owner_hash="h",
            folder_role="inbox",
            **kwargs,
        )
