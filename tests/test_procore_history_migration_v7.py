"""Phase 04B V7 migration — historical-memory + enrichment + inspection schema.

Proves the migration is additive + idempotent, creates every required table and
index, enforces the no-raw-body / always-redacted CHECK constraints, and leaves
the V1-V6 migrations intact from an empty DB.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from hb_assistant.store.migrator import SQLiteMigrator

_HISTORY_TABLES = {
    "procore_live_record_state_index",
    "procore_live_record_snapshots",
    "procore_live_record_change_events",
    "procore_record_timeline_events",
}
_ENRICHMENT_TABLES = {
    "procore_people_entities",
    "procore_company_entities",
    "procore_location_entities",
    "procore_attachment_refs",
    "procore_custom_field_values",
    "procore_record_edges",
    "procore_action_signals",
    "procore_text_intelligence",
}
_INSPECTION_TABLES = {
    "procore_inspection_records",
    "procore_inspection_sections",
    "procore_inspection_items",
    "procore_inspection_response_sets",
    "procore_inspection_response_options",
    "procore_inspection_evidence_rules",
}
_V7_TABLES = _HISTORY_TABLES | _ENRICHMENT_TABLES | _INSPECTION_TABLES

_REQUIRED_INDEXES = {
    # record-history lookups by record_key + observed/detected time
    "ix_procore_snapshots_record_observed",
    "ix_procore_change_events_record_detected",
    "ix_procore_timeline_record_time",
    # project lookback queries by project_key + event time
    "ix_procore_snapshots_project_endpoint",
    "ix_procore_change_events_project_detected",
    "ix_procore_timeline_project_time",
}


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


def test_v7_creates_all_history_enrichment_inspection_tables() -> None:
    db = _temp_db()
    assert _migrate(db) == 9
    tables = _names(db, "table")
    missing = _V7_TABLES - tables
    assert not missing, f"V7 tables missing: {sorted(missing)}"


def test_v7_creates_required_history_and_project_indexes() -> None:
    db = _temp_db()
    _migrate(db)
    indexes = _names(db, "index")
    missing = _REQUIRED_INDEXES - indexes
    assert not missing, f"required V7 indexes missing: {sorted(missing)}"


def test_v7_creates_convenience_views() -> None:
    db = _temp_db()
    _migrate(db)
    views = _names(db, "view")
    assert {"v_procore_open_action_signals", "v_procore_inspection_unanswered_items"} <= views


def test_v7_is_idempotent() -> None:
    db = _temp_db()
    assert _migrate(db) == 9
    assert _migrate(db) == 9
    conn = sqlite3.connect(str(db))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM schema_migrations WHERE version = 7"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == 1


def test_v7_check_rejects_raw_body_persisted() -> None:
    db = _temp_db()
    _migrate(db)
    conn = sqlite3.connect(str(db))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO procore_live_record_snapshots (
                  snapshot_id, record_key, project_key, endpoint_id,
                  procore_record_id, observed_at_utc, canonical_hash,
                  canonical_json_redacted, raw_body_persisted
                ) VALUES ('s1', 'k1', 'tropical', 'rfis', '1',
                  '2026-01-01T00:00:00Z', 'h', '{}', 1)
                """
            )
    finally:
        conn.close()


def test_v7_check_rejects_redaction_not_applied() -> None:
    db = _temp_db()
    _migrate(db)
    conn = sqlite3.connect(str(db))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO procore_live_record_state_index (
                  record_key, project_key, endpoint_id, procore_record_id,
                  first_seen_at_utc, last_seen_at_utc, redaction_applied
                ) VALUES ('k1', 'tropical', 'rfis', '1',
                  '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z', 0)
                """
            )
    finally:
        conn.close()


def test_existing_migrations_still_run_from_empty_db() -> None:
    """A fresh DB reaches the latest version (v9) and retains representative V1 +
    V6 tables — i.e. later migrations are purely additive and do not break the
    earlier ones."""
    db = _temp_db()
    assert _migrate(db) == 9
    tables = _names(db, "table")
    # V1 core + V6 Procore live records must still exist alongside the V7 tables.
    assert "source_records" in tables
    assert {"procore_live_records", "procore_live_sync_runs"} <= tables


def test_v7_inspection_items_status_index_present() -> None:
    db = _temp_db()
    _migrate(db)
    assert "ix_procore_inspection_items_project_status" in _names(db, "index")
