"""SQLiteMigrator: idempotent schema application and version tracking.

Embeds v1 of the canonical schema (from resources/sqlite-schema.sql, PRAGMAs handled in connection).
apply() is safe to call repeatedly.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from .connection import get_connection, transaction


class SQLiteMigrator:
    """Manages schema migrations for the local store."""

    # v1 = full initial schema (CREATE IF NOT EXISTS only; PRAGMAs in connection.py)
    # Source of truth: docs/plans/my-pa-phase-0/resources/sqlite-schema.sql
    V1_STATEMENTS: list[str] = [
        # schema_migrations is created first so we can record
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
          version INTEGER PRIMARY KEY,
          name TEXT NOT NULL,
          applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS source_records (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          source_type TEXT NOT NULL,
          source_key TEXT NOT NULL,
          source_system TEXT NOT NULL,
          title_redacted TEXT,
          source_url TEXT,
          external_id TEXT,
          immutable_id TEXT,
          content_hash TEXT,
          metadata_hash TEXT,
          first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          status TEXT NOT NULL DEFAULT 'active',
          UNIQUE(source_type, source_key)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS emails (
          source_record_id INTEGER PRIMARY KEY REFERENCES source_records(id) ON DELETE CASCADE,
          folder TEXT NOT NULL,
          conversation_id TEXT,
          internet_message_id TEXT,
          sender_domain TEXT,
          received_datetime TEXT,
          sent_datetime TEXT,
          has_attachments INTEGER NOT NULL DEFAULT 0,
          body_checked INTEGER NOT NULL DEFAULT 0,
          body_mention_detected INTEGER NOT NULL DEFAULT 0,
          body_detection_method TEXT,
          body_match_excerpt_redacted TEXT,
          web_link TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS calendar_events (
          source_record_id INTEGER PRIMARY KEY REFERENCES source_records(id) ON DELETE CASCADE,
          ical_uid TEXT,
          start_datetime TEXT NOT NULL,
          end_datetime TEXT NOT NULL,
          timezone TEXT,
          is_cancelled INTEGER NOT NULL DEFAULT 0,
          is_private INTEGER NOT NULL DEFAULT 0,
          web_link TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS attachments (
          source_record_id INTEGER PRIMARY KEY REFERENCES source_records(id) ON DELETE CASCADE,
          parent_source_record_id INTEGER NOT NULL REFERENCES source_records(id) ON DELETE CASCADE,
          attachment_id TEXT,
          name TEXT,
          content_type TEXT,
          size_bytes INTEGER,
          is_inline INTEGER NOT NULL DEFAULT 0,
          eligibility_status TEXT NOT NULL DEFAULT 'metadata_only'
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS files (
          source_record_id INTEGER PRIMARY KEY REFERENCES source_records(id) ON DELETE CASCADE,
          drive_id TEXT,
          drive_item_id TEXT,
          name TEXT,
          extension TEXT,
          mime_type TEXT,
          size_bytes INTEGER,
          web_url TEXT,
          sha256 TEXT,
          local_cache_path TEXT,
          download_status TEXT NOT NULL DEFAULT 'not_downloaded',
          parse_status TEXT NOT NULL DEFAULT 'not_parsed'
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS parser_outputs (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          file_source_record_id INTEGER NOT NULL REFERENCES source_records(id) ON DELETE CASCADE,
          parser_name TEXT NOT NULL,
          parser_version TEXT NOT NULL,
          content_hash TEXT NOT NULL,
          extraction_status TEXT NOT NULL,
          text_excerpt TEXT,
          char_count INTEGER,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(file_source_record_id, parser_name, parser_version, content_hash)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS action_items (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          stable_key TEXT NOT NULL UNIQUE,
          action_type TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'open',
          title TEXT NOT NULL,
          due_date TEXT,
          confidence REAL NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          completed_at TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS source_links (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          from_source_record_id INTEGER REFERENCES source_records(id) ON DELETE CASCADE,
          to_source_record_id INTEGER REFERENCES source_records(id) ON DELETE CASCADE,
          action_item_id INTEGER REFERENCES action_items(id) ON DELETE CASCADE,
          link_type TEXT NOT NULL,
          confidence REAL
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS assistant_runs (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          run_type TEXT NOT NULL,
          target_date TEXT NOT NULL,
          trigger TEXT NOT NULL,
          dry_run INTEGER NOT NULL DEFAULT 0,
          status TEXT NOT NULL,
          started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          finished_at TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS sync_state (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          source_name TEXT NOT NULL UNIQUE,
          cursor TEXT,
          last_success_at TEXT,
          status TEXT
        );
        """,
        # Phase 11: embeddings for semantic retrieval (vectors stored as json for pure-python cosine; gated use)
        """
        CREATE TABLE IF NOT EXISTS content_embeddings (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          source_record_id INTEGER NOT NULL REFERENCES source_records(id) ON DELETE CASCADE,
          content_ref TEXT NOT NULL,
          model TEXT NOT NULL,
          dim INTEGER,
          vector_json TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(source_record_id, content_ref, model)
        );
        """,
    ]

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def apply(self) -> int:
        """Apply all pending migrations (idempotent). Returns current schema version."""
        conn = get_connection(self._db_path)
        with transaction(conn):
            # Ensure migrations table exists (first statement is self-contained)
            for stmt in self.V1_STATEMENTS:
                conn.execute(stmt)

            # Record v1 if not present
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 1")
            if cur.fetchone() is None:
                now = datetime.now(timezone.utc).isoformat()
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (1, 'v1_initial_schema', ?)",
                    (now,),
                )

        # Return latest version
        conn2 = get_connection(self._db_path)
        cur = conn2.execute("SELECT MAX(version) FROM schema_migrations")
        row = cur.fetchone()
        return int(row[0]) if row and row[0] is not None else 0

    def current_version(self) -> int:
        """Return the highest applied migration version (0 if none)."""
        try:
            conn = get_connection(self._db_path)
            cur = conn.execute("SELECT MAX(version) FROM schema_migrations")
            row = cur.fetchone()
            return int(row[0]) if row and row[0] is not None else 0
        except sqlite3.OperationalError:
            # Table does not exist yet
            return 0
