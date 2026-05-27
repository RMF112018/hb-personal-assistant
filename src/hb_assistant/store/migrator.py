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

    # v2 = construction-agent delta crawler tables (metadata only; no body/content)
    V2_STATEMENTS: list[str] = [
        """
        CREATE TABLE IF NOT EXISTS construction_source_resolutions (
          source_key TEXT PRIMARY KEY,
          kind TEXT NOT NULL,
          site_id TEXT,
          drive_id TEXT,
          web_url TEXT,
          resolution_status TEXT NOT NULL DEFAULT 'pending',
          resolved_at TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS construction_delta_tokens (
          source_key TEXT PRIMARY KEY,
          drive_id TEXT NOT NULL,
          delta_link TEXT,
          page_count INTEGER NOT NULL DEFAULT 0,
          last_status TEXT,
          last_sync_at TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS construction_drive_item_inventory (
          source_key TEXT NOT NULL,
          drive_id TEXT NOT NULL,
          item_id TEXT NOT NULL,
          name TEXT,
          web_url TEXT,
          parent_path TEXT,
          size_bytes INTEGER,
          is_folder INTEGER NOT NULL DEFAULT 0,
          last_modified TEXT,
          etag TEXT,
          status TEXT NOT NULL DEFAULT 'active',
          first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY (source_key, item_id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS construction_crawl_receipts (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          run_id TEXT NOT NULL,
          source_key TEXT NOT NULL,
          mode TEXT NOT NULL,
          started_at TEXT NOT NULL,
          finished_at TEXT,
          pages_seen INTEGER NOT NULL DEFAULT 0,
          items_seen INTEGER NOT NULL DEFAULT 0,
          items_new INTEGER NOT NULL DEFAULT 0,
          items_updated INTEGER NOT NULL DEFAULT 0,
          items_deleted INTEGER NOT NULL DEFAULT 0,
          delta_link_recorded INTEGER NOT NULL DEFAULT 0,
          status TEXT NOT NULL,
          error_redacted TEXT
        );
        """,
    ]

    # v3 = construction-agent review queue (metadata only; one row per rule match)
    V3_STATEMENTS: list[str] = [
        """
        CREATE TABLE IF NOT EXISTS construction_review_queue (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          source_key TEXT NOT NULL,
          project_key TEXT,
          item_id TEXT NOT NULL,
          name TEXT,
          parent_path TEXT,
          rule_id TEXT NOT NULL,
          classification_label TEXT NOT NULL,
          sensitivity TEXT NOT NULL,
          reason TEXT NOT NULL,
          suggested_action TEXT NOT NULL,
          confidence REAL NOT NULL DEFAULT 1.0,
          status TEXT NOT NULL DEFAULT 'open',
          routed_at TEXT NOT NULL,
          resolved_at TEXT,
          UNIQUE(source_key, item_id, rule_id)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_construction_review_queue_status
          ON construction_review_queue(status);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_construction_review_queue_source
          ON construction_review_queue(source_key);
        """,
    ]

    # v5 = Phase 02 canonical construction-index alignment (additive only;
    # source: Phase 02 implementation package
    # resources/sql/phase_02_construction_index_schema_alignment.sql).
    # Ten new tables modeling the canonical source location / sync state /
    # drive item / project identity / document card / processing receipt /
    # sync error / email-intelligence-deferred-state shape. Phase 01
    # V2/V3/V4 tables remain untouched. SQL CHECKs enforce read-only +
    # no-mailbox-writeback + no-full-body hard guardrails at the schema
    # level (defense-in-depth alongside model + adapter guards).
    V5_STATEMENTS: list[str] = [
        """
        CREATE TABLE IF NOT EXISTS construction_source_locations (
          source_id TEXT PRIMARY KEY,
          source_system TEXT NOT NULL,
          source_scope TEXT NOT NULL,
          source_name TEXT NOT NULL,
          project_key TEXT,
          project_number TEXT,
          project_name TEXT,
          tenant_id TEXT,
          site_url TEXT,
          site_id TEXT,
          drive_id TEXT,
          folder_item_id TEXT,
          folder_path TEXT,
          folder_web_url TEXT,
          library_name TEXT,
          list_id TEXT,
          local_sync_path TEXT,
          sync_mode TEXT,
          sync_frequency_minutes INTEGER,
          enabled INTEGER NOT NULL DEFAULT 1,
          read_only INTEGER NOT NULL DEFAULT 1 CHECK(read_only = 1),
          baseline_policy_json TEXT,
          folder_policies_json TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS construction_source_sync_state (
          source_id TEXT PRIMARY KEY REFERENCES construction_source_locations(source_id),
          drive_id TEXT,
          folder_item_id TEXT,
          delta_link TEXT,
          delta_link_fingerprint TEXT,
          last_successful_sync_utc TEXT,
          last_attempted_sync_utc TEXT,
          last_baseline_item_count INTEGER,
          last_change_count INTEGER,
          sync_status TEXT NOT NULL DEFAULT 'pending',
          error_message_redacted TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS construction_source_crawl_runs (
          run_id TEXT PRIMARY KEY,
          source_id TEXT NOT NULL REFERENCES construction_source_locations(source_id),
          source_scope TEXT NOT NULL,
          mode TEXT NOT NULL,
          started_at TEXT NOT NULL,
          completed_at TEXT,
          pages_seen INTEGER NOT NULL DEFAULT 0,
          items_seen INTEGER NOT NULL DEFAULT 0,
          items_in_scope INTEGER NOT NULL DEFAULT 0,
          items_out_of_scope_filtered INTEGER NOT NULL DEFAULT 0,
          delta_link_recorded INTEGER NOT NULL DEFAULT 0,
          status TEXT NOT NULL,
          error_redacted TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS construction_drive_items (
          source_id TEXT NOT NULL REFERENCES construction_source_locations(source_id),
          drive_id TEXT NOT NULL,
          drive_item_id TEXT NOT NULL,
          parent_drive_item_id TEXT,
          site_id TEXT,
          list_id TEXT,
          list_item_id TEXT,
          name TEXT,
          path TEXT,
          web_url TEXT,
          is_folder INTEGER NOT NULL DEFAULT 0,
          is_file INTEGER NOT NULL DEFAULT 0,
          file_extension TEXT,
          mime_type TEXT,
          size_bytes INTEGER,
          last_modified_datetime TEXT,
          deleted INTEGER NOT NULL DEFAULT 0,
          quick_xor_hash TEXT,
          project_number_detected TEXT,
          document_type_detected TEXT,
          indexing_policy TEXT,
          classification_status TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY (source_id, drive_item_id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS construction_project_identity (
          project_key TEXT PRIMARY KEY,
          hb_project_number TEXT,
          project_name_raw TEXT,
          project_name_normalized TEXT,
          is_active INTEGER NOT NULL DEFAULT 1,
          procore_project_id TEXT,
          project_stage TEXT,
          last_seen_utc TEXT,
          last_validated_utc TEXT,
          match_status TEXT,
          match_confidence TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS construction_project_source_matches (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          project_key TEXT REFERENCES construction_project_identity(project_key),
          source_id TEXT REFERENCES construction_source_locations(source_id),
          match_method TEXT NOT NULL,
          match_confidence TEXT NOT NULL,
          review_required INTEGER NOT NULL DEFAULT 0,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(project_key, source_id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS construction_document_cards (
          card_id TEXT PRIMARY KEY,
          source_id TEXT NOT NULL,
          drive_item_id TEXT,
          project_key TEXT,
          document_type TEXT,
          status TEXT NOT NULL DEFAULT 'candidate',
          confidence REAL,
          needs_review INTEGER NOT NULL DEFAULT 1,
          card_path TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS construction_processing_receipts (
          receipt_id TEXT PRIMARY KEY,
          source_id TEXT NOT NULL,
          operation TEXT NOT NULL,
          status TEXT NOT NULL,
          generated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          detail_json TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS construction_sync_errors (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          source_id TEXT,
          operation TEXT NOT NULL,
          error_class TEXT NOT NULL,
          error_redacted TEXT,
          occurred_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          resolved_utc TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS construction_email_intelligence_deferred_state (
          id INTEGER PRIMARY KEY CHECK (id = 1),
          mail_read_all_granted INTEGER NOT NULL,
          mail_readwrite_all_granted INTEGER NOT NULL,
          mailbox_writeback_allowed INTEGER NOT NULL DEFAULT 0 CHECK(mailbox_writeback_allowed = 0),
          persist_full_body INTEGER NOT NULL DEFAULT 0 CHECK(persist_full_body = 0),
          updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """,
        # Helpful indexes for hot paths.
        """
        CREATE INDEX IF NOT EXISTS ix_construction_source_locations_project
          ON construction_source_locations(project_key);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_construction_drive_items_project
          ON construction_drive_items(project_number_detected);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_construction_drive_items_source_modified
          ON construction_drive_items(source_id, last_modified_datetime);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_construction_project_source_matches_review
          ON construction_project_source_matches(review_required);
        """,
    ]

    # v4 = construction-agent Ollama model-decisions audit (metadata only;
    # recommendation-only, controller policy remains authoritative)
    V4_STATEMENTS: list[str] = [
        """
        CREATE TABLE IF NOT EXISTS construction_model_decisions (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          source_key TEXT NOT NULL,
          item_id TEXT NOT NULL,
          project_key TEXT,
          model_name TEXT NOT NULL,
          model_task TEXT NOT NULL,
          proposed_label TEXT NOT NULL,
          confidence REAL NOT NULL,
          rationale_truncated TEXT,
          raw_output_truncated TEXT,
          status TEXT NOT NULL,
          routing_reason TEXT NOT NULL,
          routed_at TEXT NOT NULL
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_construction_model_decisions_status
          ON construction_model_decisions(status);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_construction_model_decisions_item
          ON construction_model_decisions(source_key, item_id);
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

            now = datetime.now(timezone.utc).isoformat()

            # Record v1 if not present
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 1")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (1, 'v1_initial_schema', ?)",
                    (now,),
                )

            # v2 construction-agent delta crawler tables (additive, metadata only)
            for stmt in self.V2_STATEMENTS:
                conn.execute(stmt)

            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 2")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (2, 'v2_construction_delta', ?)",
                    (now,),
                )

            # v3 construction-agent review queue (additive, metadata only)
            for stmt in self.V3_STATEMENTS:
                conn.execute(stmt)

            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 3")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (3, 'v3_construction_review_queue', ?)",
                    (now,),
                )

            # v4 construction-agent Ollama model-decisions audit (additive,
            # metadata only; recommendation-only)
            for stmt in self.V4_STATEMENTS:
                conn.execute(stmt)

            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 4")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (4, 'v4_construction_model_decisions', ?)",
                    (now,),
                )

            # v5 Phase 02 canonical construction-index schema alignment
            # (additive only; V1-V4 tables untouched).
            for stmt in self.V5_STATEMENTS:
                conn.execute(stmt)

            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 5")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (5, 'v5_construction_canonical_alignment', ?)",
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
