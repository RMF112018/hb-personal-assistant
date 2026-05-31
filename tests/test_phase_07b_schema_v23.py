"""Phase 07B Prompt 02 — V23 calendar + email-thread intelligence schema.

Proves V23 additively creates the eight calendar/email-thread tables with their
indexes and guardrail CHECKs, is idempotent, leaves V1-V22 intact (including the
V20/V22 raw-body guardrails), and enforces the read-only / no-raw-body / UNIQUE
constraints.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

_V23_TABLES = [
    "calendar_source_locations",
    "calendar_sync_state",
    "calendar_crawl_runs",
    "calendar_event_index",
    "calendar_event_attendees",
    "calendar_project_match_candidates",
    "meeting_email_relationship_candidates",
    "email_thread_summary_materialization_runs",
]

_V23_INDEXES = [
    "ix_calendar_event_index_source_start",
    "ix_calendar_event_index_project_start",
    "ix_calendar_event_index_review",
    "ix_calendar_project_candidates_project",
    "ix_meeting_email_candidates_project_event",
    "ix_meeting_email_candidates_review",
]


def _migrate(db: Path) -> int:
    return SQLiteMigrator(db_path=str(db)).apply()


def _names(conn: sqlite3.Connection, kind: str) -> set[str]:
    return {r[0] for r in conn.execute(f"SELECT name FROM sqlite_master WHERE type='{kind}'")}


def test_v23_creates_all_tables_and_indexes() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v23.db"
        assert _migrate(db) == LATEST_SCHEMA_VERSION
        conn = sqlite3.connect(str(db))
        tables = _names(conn, "table")
        for t in _V23_TABLES:
            assert t in tables, f"missing table {t}"
        indexes = _names(conn, "index")
        for ix in _V23_INDEXES:
            assert ix in indexes, f"missing index {ix}"


def test_v23_is_idempotent() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v23.db"
        assert _migrate(db) == LATEST_SCHEMA_VERSION
        assert _migrate(db) == LATEST_SCHEMA_VERSION  # second apply is a no-op
        conn = sqlite3.connect(str(db))
        n = conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE version = 23").fetchone()[0]
        assert n == 1


def test_v23_leaves_v1_v22_intact() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v23.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        for version in (1, 20, 21, 22, 23):
            row = conn.execute(
                "SELECT COUNT(*) FROM schema_migrations WHERE version = ?", (version,)
            ).fetchone()
            assert row[0] == 1, f"missing schema_migrations row for v{version}"
        # V20/V22 guardrails still present on a representative table
        sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='source_system_record_map'"
        ).fetchone()[0]
        assert "CHECK(raw_body_persisted=0)" in (sql or "").replace(" ", "")
        # legacy calendar_events (V1) is untouched (no project_key column added)
        legacy_cols = {r[1] for r in conn.execute("PRAGMA table_info(calendar_events)")}
        assert "project_key" not in legacy_cols


def test_v23_source_registry_is_read_only() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v23.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO calendar_source_locations (source_id, mailbox_owner_hash, read_only) "
                "VALUES ('s1', 'h', 0)"
            )


def test_v23_guardrail_checks_reject_raw_persistence() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v23.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        conn.execute(
            "INSERT INTO calendar_source_locations (source_id, mailbox_owner_hash) VALUES ('s1','h')"
        )
        conn.execute(
            "INSERT INTO calendar_event_index "
            "(event_index_id, source_id, graph_event_id_hash, start_datetime_utc, end_datetime_utc) "
            "VALUES ('e1','s1','gh','2026-01-01T00:00:00Z','2026-01-01T01:00:00Z')"
        )
        # raw_body_persisted = 1 must be rejected
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO calendar_event_index "
                "(event_index_id, source_id, graph_event_id_hash, start_datetime_utc, "
                "end_datetime_utc, raw_body_persisted) "
                "VALUES ('e2','s1','gh2','2026-01-01T00:00:00Z','2026-01-01T01:00:00Z',1)"
            )
        # raw_prompt_persisted = 1 rejected on meeting/email candidates
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO meeting_email_relationship_candidates "
                "(candidate_id, event_index_id, thread_key_hash, candidate_type, "
                "source_reference_json, confidence, confidence_class, raw_prompt_persisted) "
                "VALUES ('c1','e1','th','x','{}',0.5,'weak',1)"
            )


def test_v23_unique_constraints() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v23.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        conn.execute(
            "INSERT INTO calendar_source_locations (source_id, mailbox_owner_hash) VALUES ('s1','h')"
        )
        conn.execute(
            "INSERT INTO calendar_event_index "
            "(event_index_id, source_id, graph_event_id_hash, start_datetime_utc, end_datetime_utc) "
            "VALUES ('e1','s1','dup','2026-01-01T00:00:00Z','2026-01-01T01:00:00Z')"
        )
        # duplicate (source_id, graph_event_id_hash) rejected
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO calendar_event_index "
                "(event_index_id, source_id, graph_event_id_hash, start_datetime_utc, "
                "end_datetime_utc) "
                "VALUES ('e2','s1','dup','2026-01-02T00:00:00Z','2026-01-02T01:00:00Z')"
            )
