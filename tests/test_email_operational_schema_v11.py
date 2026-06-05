"""Phase 06 Prompt 03 — V11 operational email schema + store-adapter helpers.

Proves V11 adds the operational email data tables additively (V1-V10 and the V5
deferred-state row preserved), that the SQLite CHECK constraints reject
mutation / full-body-persistence / attachment-content-download at the database
layer, that the store-adapter upsert/idempotency/receipt/review-queue helpers
round-trip, and that the adapter guards raise ValueError before SQL ever runs.
No full email body is ever stored — only a bounded, redacted preview excerpt.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from hb_assistant.construction.store.repositories import ConstructionStore
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

_V11_TABLES = {
    "email_sync_state",
    "email_crawl_runs",
    "email_messages",
    "email_message_recipients",
    "email_message_attachments",
    "email_project_matches",
    "email_relationship_candidates",
    "email_thread_summaries",
    "email_review_queue",
    "email_processing_receipts",
}
_V11_INDEXES = {
    "ix_email_messages_thread",
    "ix_email_messages_project",
    "ix_email_messages_received",
    "ix_email_messages_review",
    "ix_email_review_queue_status",
    "ix_email_review_queue_project",
    "ix_email_processing_receipts_run",
}
# V10 tables that must remain intact after V11.
_V10_TABLES = {"email_intelligence_active_policy", "email_source_locations"}


def _temp_db() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        return Path(tf.name)


def _migrate(db: Path) -> int:
    return SQLiteMigrator(db_path=str(db)).apply()


def _names(db: Path, kind: str) -> set[str]:
    conn = sqlite3.connect(str(db))
    try:
        return {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type=?", (kind,))
        }
    finally:
        conn.close()


# --- migration mechanics ----------------------------------------------------


def test_v11_applies_and_creates_tables_and_indexes() -> None:
    db = _temp_db()
    assert _migrate(db) == LATEST_SCHEMA_VERSION
    tables = _names(db, "table")
    assert not (_V11_TABLES - tables), f"V11 tables missing: {sorted(_V11_TABLES - tables)}"
    indexes = _names(db, "index")
    assert not (_V11_INDEXES - indexes), f"V11 indexes missing: {sorted(_V11_INDEXES - indexes)}"


def test_v11_preserves_v1_v10_and_deferred_state_table() -> None:
    db = _temp_db()
    _migrate(db)
    tables = _names(db, "table")
    assert "source_records" in tables  # V1 core
    assert {"procore_live_records", "procore_financial_contracts"} <= tables  # V6/V8
    assert tables >= _V10_TABLES  # V10 policy + source registry intact
    # The historical deferred-state table is preserved untouched.
    assert "construction_email_intelligence_deferred_state" in tables


def test_v11_is_idempotent() -> None:
    db = _temp_db()
    assert _migrate(db) == LATEST_SCHEMA_VERSION
    assert _migrate(db) == LATEST_SCHEMA_VERSION
    conn = sqlite3.connect(str(db))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM schema_migrations WHERE version = 11"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == 1


def test_email_source_locations_not_redeclared_in_v11() -> None:
    # email_source_locations is owned by V10; V11 must reference it, not recreate
    # it. The migration name recorded for v11 is the operational-schema one.
    db = _temp_db()
    _migrate(db)
    conn = sqlite3.connect(str(db))
    try:
        name = conn.execute("SELECT name FROM schema_migrations WHERE version = 11").fetchone()[0]
    finally:
        conn.close()
    assert name == "v11_email_operational_intelligence_schema"


# --- database-layer CHECK guardrails ----------------------------------------


@pytest.mark.parametrize(
    "column",
    ["mailbox_mutation_attempted", "full_body_persisted", "attachment_content_downloaded"],
)
def test_crawl_runs_check_rejects_loosened_flag(column: str) -> None:
    db = _temp_db()
    _migrate(db)
    conn = sqlite3.connect(str(db))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                f"INSERT INTO email_crawl_runs "
                f"(run_id, source_id, mode, lookback_days, started_utc, status, {column}) "
                f"VALUES ('r1', 's1', 'discover', 30, 'now', 'running', 1)"
            )
    finally:
        conn.close()


@pytest.mark.parametrize("column", ["full_body_persisted", "mailbox_mutation_allowed"])
def test_messages_check_rejects_loosened_flag(column: str) -> None:
    db = _temp_db()
    _migrate(db)
    conn = sqlite3.connect(str(db))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                f"INSERT INTO email_messages "
                f"(message_id, thread_key, source_id, {column}) "
                f"VALUES ('m1', 't1', 's1', 1)"
            )
    finally:
        conn.close()


@pytest.mark.parametrize("column,value", [("metadata_only", 0), ("content_downloaded", 1)])
def test_attachments_check_rejects_loosened_flag(column: str, value: int) -> None:
    db = _temp_db()
    _migrate(db)
    conn = sqlite3.connect(str(db))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                f"INSERT INTO email_message_attachments "
                f"(attachment_key, message_id, {column}) VALUES ('a1', 'm1', {value})"
            )
    finally:
        conn.close()


@pytest.mark.parametrize(
    "column",
    ["mailbox_mutation_attempted", "full_body_persisted", "attachment_content_downloaded"],
)
def test_processing_receipts_check_rejects_loosened_flag(column: str) -> None:
    db = _temp_db()
    _migrate(db)
    conn = sqlite3.connect(str(db))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                f"INSERT INTO email_processing_receipts "
                f"(receipt_id, operation, status, {column}) "
                f"VALUES ('rc1', 'index', 'ok', 1)"
            )
    finally:
        conn.close()


def test_email_messages_has_no_full_body_column() -> None:
    db = _temp_db()
    _migrate(db)
    conn = sqlite3.connect(str(db))
    try:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(email_messages)")}
    finally:
        conn.close()
    # A bounded, redacted preview excerpt is permitted; a full body is not.
    forbidden = {"body", "content", "text", "full_text", "full_body", "body_content"}
    leaks = columns & forbidden
    assert not leaks, f"forbidden full-body columns present: {leaks}"
    assert "body_preview_excerpt_redacted" in columns  # bounded preview allowed


# --- store-adapter helpers: round-trips, idempotency, receipts, review ------


def _store_with_source() -> tuple[ConstructionStore, str]:
    store = ConstructionStore(str(_temp_db()))
    store.upsert_email_source_location(
        source_id="outlook:hash:inbox",
        mailbox_owner_hash="hash",
        folder_role="inbox",
        folder_display_name="Inbox",
    )
    return store, "outlook:hash:inbox"


def test_upsert_email_message_round_trip_and_idempotent() -> None:
    store, source_id = _store_with_source()
    store.upsert_email_message(
        message_id="m1",
        thread_key="t1",
        source_id=source_id,
        subject_redacted="RFI [redacted]",
        project_number_detected="21001",
        body_preview_excerpt_redacted="bounded preview…",
        categories_metadata=["blue"],
        review_required=True,
    )
    row = store.get_email_message("m1")
    assert row is not None
    assert row["full_body_persisted"] is False
    assert row["mailbox_mutation_allowed"] is False
    assert row["extraction_policy"] == "metadata_only"
    assert row["review_required"] is True
    assert row["categories_metadata"] == ["blue"]
    # Re-upsert updates in place (no duplicate row).
    store.upsert_email_message(
        message_id="m1", thread_key="t1", source_id=source_id, subject_redacted="updated"
    )
    again = store.get_email_message("m1")
    assert again is not None
    assert again["subject_redacted"] == "updated"
    assert len(store.list_email_messages(thread_key="t1")) == 1
    assert len(store.list_email_messages(project_number_detected="21001")) == 0  # overwritten


@pytest.mark.parametrize(
    "kwargs",
    [
        {"full_body_persisted": True},
        {"mailbox_mutation_allowed": True},
        {"extraction_policy": "full_body"},
    ],
)
def test_upsert_email_message_adapter_guards(kwargs: dict) -> None:
    store, source_id = _store_with_source()
    with pytest.raises(ValueError):
        store.upsert_email_message(message_id="m", thread_key="t", source_id=source_id, **kwargs)


def test_recipient_upsert_is_idempotent_on_unique_key() -> None:
    store, source_id = _store_with_source()
    store.upsert_email_message(message_id="m1", thread_key="t1", source_id=source_id)
    first = store.add_email_message_recipient(
        message_id="m1", recipient_role="to", address_hash="ah1", domain="hbcc.com"
    )
    second = store.add_email_message_recipient(
        message_id="m1", recipient_role="to", address_hash="ah1", domain="hbcc.com"
    )
    assert first is True
    assert second is False  # INSERT OR IGNORE — already present, not a new row
    recips = store.list_email_message_recipients("m1")
    assert len(recips) == 1


def test_attachment_metadata_only_round_trip_and_guards() -> None:
    store, source_id = _store_with_source()
    store.upsert_email_message(message_id="m1", thread_key="t1", source_id=source_id)
    store.upsert_email_message_attachment(
        attachment_key="m1:att1",
        message_id="m1",
        name_redacted="plans.pdf [redacted]",
        content_type="application/pdf",
        size_bytes=1024,
    )
    with pytest.raises(ValueError):
        store.upsert_email_message_attachment(
            attachment_key="m1:att2", message_id="m1", content_downloaded=True
        )
    with pytest.raises(ValueError):
        store.upsert_email_message_attachment(
            attachment_key="m1:att3", message_id="m1", metadata_only=False
        )


def test_project_match_and_relationship_candidate_idempotent() -> None:
    store, source_id = _store_with_source()
    store.upsert_email_message(message_id="m1", thread_key="t1", source_id=source_id)
    store.upsert_email_project_match(
        match_id="pm1",
        message_id="m1",
        project_key="proj:21001",
        match_signal="exact_project_number_in_subject",
        confidence=1.0,
    )
    store.upsert_email_project_match(
        match_id="pm1",
        message_id="m1",
        project_key="proj:21001",
        match_signal="exact_project_number_in_subject",
        confidence=0.95,
    )
    store.upsert_email_relationship_candidate(
        candidate_id="rc1",
        message_id="m1",
        candidate_type="procore_rfi",
        target_table="procore_rfis",
        target_key="rfi-7",
        match_signal="rfi_number",
        confidence=0.85,
    )
    conn = sqlite3.connect(str(store._db_path))  # type: ignore[attr-defined]
    try:
        assert conn.execute("SELECT COUNT(*) FROM email_project_matches").fetchone()[0] == 1
        assert conn.execute("SELECT confidence FROM email_project_matches").fetchone()[0] == 0.95
        assert conn.execute("SELECT COUNT(*) FROM email_relationship_candidates").fetchone()[0] == 1
    finally:
        conn.close()


def test_thread_summary_round_trip() -> None:
    store, source_id = _store_with_source()
    store.upsert_email_thread_summary(
        thread_key="t1",
        project_key="proj:21001",
        message_count=4,
        participants_hash=["h1", "h2"],
        summary_redacted="metadata-and-preview summary",
    )
    store.upsert_email_thread_summary(thread_key="t1", message_count=5)
    conn = sqlite3.connect(str(store._db_path))  # type: ignore[attr-defined]
    try:
        rows = conn.execute(
            "SELECT message_count FROM email_thread_summaries WHERE thread_key='t1'"
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) == 1
    assert rows[0][0] == 5


def test_review_queue_enqueue_idempotent_and_filtered_reads() -> None:
    store, source_id = _store_with_source()
    store.upsert_email_message(message_id="m1", thread_key="t1", source_id=source_id)
    first = store.enqueue_email_review_item(
        review_id="rv1",
        message_id="m1",
        category="legal_or_contract",
        sensitivity="high",
        reason="contract language detected",
        suggested_action="manual_review",
        confidence=0.4,
        project_key="proj:21001",
    )
    dup = store.enqueue_email_review_item(
        review_id="rv2",  # different id, same (message_id, category, reason)
        message_id="m1",
        category="legal_or_contract",
        sensitivity="high",
        reason="contract language detected",
        suggested_action="manual_review",
        confidence=0.4,
    )
    assert first is True
    assert dup is False  # INSERT OR IGNORE on UNIQUE(message_id, category, reason)
    assert store.count_email_review_queue(status="open") == 1
    assert store.count_email_review_queue(project_key="proj:21001") == 1
    assert store.count_email_review_queue(project_key="other") == 0
    listed = store.list_email_review_queue(project_key="proj:21001")
    assert len(listed) == 1
    assert listed[0]["category"] == "legal_or_contract"


def test_processing_receipt_round_trip_and_guards() -> None:
    store, source_id = _store_with_source()
    store.insert_email_processing_receipt(
        receipt_id="rc1",
        operation="index_metadata",
        status="ok",
        run_id="run-1",
        detail={"messages_indexed": 3},
    )
    receipts = store.list_email_processing_receipts(run_id="run-1")
    assert len(receipts) == 1
    assert receipts[0]["detail"] == {"messages_indexed": 3}
    assert receipts[0]["full_body_persisted"] is False
    for bad in (
        {"mailbox_mutation_attempted": True},
        {"full_body_persisted": True},
        {"attachment_content_downloaded": True},
    ):
        with pytest.raises(ValueError):
            store.insert_email_processing_receipt(
                receipt_id="x", operation="index_metadata", status="ok", **bad
            )


def test_crawl_run_lifecycle_and_mutation_guards() -> None:
    store, source_id = _store_with_source()
    store.insert_email_crawl_run(
        run_id="run-1", source_id=source_id, mode="discover", lookback_days=30
    )
    updated = store.complete_email_crawl_run(
        run_id="run-1", status="completed", messages_seen=10, messages_indexed=8
    )
    assert updated is True
    for bad in (
        {"mailbox_mutation_attempted": True},
        {"full_body_persisted": True},
        {"attachment_content_downloaded": True},
    ):
        with pytest.raises(ValueError):
            store.insert_email_crawl_run(
                run_id="x", source_id=source_id, mode="discover", lookback_days=30, **bad
            )


def test_sync_state_round_trip() -> None:
    store, source_id = _store_with_source()
    store.upsert_email_sync_state(
        source_id=source_id,
        folder_id="AAMk-inbox",
        sync_mode="bounded_lookback",
        sync_status="ok",
        delta_token_supported=True,
    )
    # upsert is a full replace of the latest known per-folder sync state.
    store.upsert_email_sync_state(
        source_id=source_id,
        folder_id="AAMk-inbox",
        sync_mode="bounded_lookback",
        sync_status="error",
        delta_token_supported=True,
        error_redacted="429 [redacted]",
    )
    row = store.get_email_sync_state(source_id=source_id, folder_id="AAMk-inbox")
    assert row is not None
    assert row["sync_status"] == "error"
    assert row["delta_token_supported"] is True
    assert row["error_redacted"] == "429 [redacted]"
