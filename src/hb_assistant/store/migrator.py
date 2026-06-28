"""SQLiteMigrator: idempotent schema application and version tracking.

Embeds v1 of the canonical schema (from resources/sqlite-schema.sql, PRAGMAs handled in connection).
apply() is safe to call repeatedly.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from .connection import get_connection, transaction

# Single source of truth for the head schema version. Bump this with every new
# migration block in apply(). Tests should assert against this constant rather
# than hard-coding a literal so version bumps do not break unrelated tests.
LATEST_SCHEMA_VERSION = 87


class StaffingMigrationError(RuntimeError):
    """Raised when a destructive staffing migration would touch non-empty data."""


class SQLiteMigrator:
    """Manages schema migrations for the local store."""

    # v42 Phase 10A raw content (email + calendar bodies under policy). Additive tables only;
    # these are the *exempt* holders for plaintext when raw mode is active (no 13-guard CHECKs).
    V42_STATEMENTS: list[str] = [
        """
        CREATE TABLE IF NOT EXISTS raw_content_policy_state (
          policy_id TEXT PRIMARY KEY,
          enabled INTEGER NOT NULL DEFAULT 0,
          mode TEXT NOT NULL DEFAULT 'disabled',
          default_endpoint_behavior TEXT NOT NULL DEFAULT 'metadata',
          email_enabled INTEGER NOT NULL DEFAULT 0,
          calendar_enabled INTEGER NOT NULL DEFAULT 0,
          files_enabled INTEGER NOT NULL DEFAULT 0,
          mcp_raw_enabled INTEGER NOT NULL DEFAULT 0,
          obsidian_raw_enabled INTEGER NOT NULL DEFAULT 0,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS email_message_raw_content (
          raw_email_id TEXT PRIMARY KEY,
          message_id_hash TEXT NOT NULL,
          internet_message_id_hash TEXT,
          conversation_id_hash TEXT,
          source_ref_hash TEXT,
          project_key TEXT,
          subject TEXT,
          body_preview TEXT,
          body_text TEXT,
          body_html TEXT,
          from_name TEXT,
          from_address TEXT,
          to_recipients_json TEXT NOT NULL DEFAULT '[]',
          cc_recipients_json TEXT NOT NULL DEFAULT '[]',
          bcc_recipients_json TEXT NOT NULL DEFAULT '[]',
          sent_at_utc TEXT,
          received_at_utc TEXT,
          has_attachments INTEGER NOT NULL DEFAULT 0,
          attachment_metadata_json TEXT NOT NULL DEFAULT '[]',
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_email_message_raw_content_conversation ON email_message_raw_content(conversation_id_hash);",
        "CREATE INDEX IF NOT EXISTS idx_email_message_raw_content_received ON email_message_raw_content(received_at_utc);",
        """
        CREATE TABLE IF NOT EXISTS email_thread_raw_context (
          raw_thread_context_id TEXT PRIMARY KEY,
          thread_ref TEXT NOT NULL,
          conversation_id_hash TEXT,
          project_key TEXT,
          message_count INTEGER NOT NULL DEFAULT 0,
          participant_count INTEGER NOT NULL DEFAULT 0,
          thread_subject TEXT,
          messages_json TEXT NOT NULL,
          source_refs_json TEXT NOT NULL DEFAULT '[]',
          model_ready INTEGER NOT NULL DEFAULT 1,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(thread_ref)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS calendar_event_raw_content (
          raw_calendar_event_id TEXT PRIMARY KEY,
          event_index_id TEXT,
          graph_event_id_hash TEXT NOT NULL,
          source_ref_hash TEXT,
          project_key TEXT,
          subject TEXT,
          body_preview TEXT,
          body_text TEXT,
          body_html TEXT,
          location_display TEXT,
          organizer_name TEXT,
          organizer_email TEXT,
          attendees_json TEXT NOT NULL DEFAULT '[]',
          online_meeting_provider TEXT,
          join_url TEXT,
          recurrence_json TEXT,
          start_datetime_utc TEXT,
          end_datetime_utc TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_calendar_event_raw_content_start ON calendar_event_raw_content(start_datetime_utc);",
        """
        CREATE TABLE IF NOT EXISTS raw_content_model_context_packets (
          packet_id TEXT PRIMARY KEY,
          packet_type TEXT NOT NULL,
          source_family TEXT NOT NULL,
          source_ref_hash TEXT,
          project_key TEXT,
          raw_content_included INTEGER NOT NULL DEFAULT 1,
          packet_json TEXT NOT NULL,
          token_estimate INTEGER,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS raw_content_access_events (
          access_event_id TEXT PRIMARY KEY,
          source_family TEXT NOT NULL,
          source_ref_hash TEXT,
          endpoint_or_command TEXT NOT NULL,
          raw_content_included INTEGER NOT NULL DEFAULT 1,
          purpose TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """,
    ]

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

    # v6 = Phase 04A Procore live sync tables. Three tables: sync run history,
    # canonical live records (one row per Procore entity, upsert keyed by
    # project + endpoint + parent + record), and per-endpoint watermarks.
    # Hard CHECK constraints enforce the no-raw-body / always-redacted rules at
    # the schema level.
    V6_STATEMENTS: list[str] = [
        """
        CREATE TABLE IF NOT EXISTS procore_live_sync_runs (
          sync_run_id TEXT PRIMARY KEY,
          endpoint_id TEXT NOT NULL,
          command_endpoint TEXT NOT NULL,
          legacy_endpoint_alias TEXT,
          project_key TEXT NOT NULL,
          procore_project_id TEXT NOT NULL,
          company_id TEXT NOT NULL,
          mode TEXT NOT NULL,
          started_at_utc TEXT NOT NULL,
          completed_at_utc TEXT,
          request_count INTEGER NOT NULL DEFAULT 0,
          retrieved_count INTEGER NOT NULL DEFAULT 0,
          normalized_count INTEGER NOT NULL DEFAULT 0,
          sqlite_upserted_count INTEGER NOT NULL DEFAULT 0,
          status TEXT NOT NULL,
          state TEXT NOT NULL,
          reason_codes_json TEXT,
          evidence_path TEXT,
          redaction_applied INTEGER NOT NULL DEFAULT 1 CHECK(redaction_applied = 1),
          raw_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_persisted = 0),
          no_live_call_performed INTEGER NOT NULL DEFAULT 0
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_procore_live_sync_runs_endpoint
          ON procore_live_sync_runs(endpoint_id, project_key);
        """,
        """
        CREATE TABLE IF NOT EXISTS procore_live_records (
          project_key TEXT NOT NULL,
          procore_project_id TEXT NOT NULL,
          endpoint_id TEXT NOT NULL,
          parent_procore_id TEXT NOT NULL DEFAULT '',
          procore_record_id TEXT NOT NULL,
          procore_record_number TEXT,
          title_redacted TEXT,
          status TEXT,
          updated_at_utc TEXT,
          source_url_redacted TEXT,
          canonical_json_redacted TEXT NOT NULL,
          review_required INTEGER NOT NULL DEFAULT 0,
          sensitive_reason TEXT,
          first_seen_at_utc TEXT NOT NULL,
          last_seen_at_utc TEXT NOT NULL,
          last_sync_run_id TEXT NOT NULL,
          raw_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_persisted = 0),
          PRIMARY KEY (project_key, endpoint_id, parent_procore_id, procore_record_id),
          FOREIGN KEY (last_sync_run_id) REFERENCES procore_live_sync_runs(sync_run_id)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_procore_live_records_review
          ON procore_live_records(review_required);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_procore_live_records_endpoint
          ON procore_live_records(endpoint_id, project_key);
        """,
        """
        CREATE TABLE IF NOT EXISTS procore_live_sync_watermarks (
          company_id TEXT NOT NULL,
          project_key TEXT NOT NULL,
          procore_project_id TEXT NOT NULL,
          endpoint_id TEXT NOT NULL,
          last_success_at_utc TEXT,
          last_receipt_id TEXT,
          cursor_redacted TEXT,
          PRIMARY KEY (company_id, project_key, procore_project_id, endpoint_id)
        );
        """,
    ]

    # v7 = Phase 04B historical-memory + enrichment + inspection schema.
    # Additive only; never touches V1-V6 tables. Source of truth for the DDL is
    # resources/sql/phase_04b_schema_additions.sql in the Phase 04B package.
    # History tables track per-record snapshots / field-level change events /
    # assistant-ready timeline events keyed by a stable ``record_key``; the
    # cross-cutting tables project people/company/location/attachment/custom-field
    # entities, relationship edges, action signals and text intelligence; the
    # inspection tables hold the checklist projection. Hard CHECK constraints keep
    # raw bodies out and assert redaction at the schema level, mirroring V6.
    V7_STATEMENTS: list[str] = [
        # ----- history -----
        """
        CREATE TABLE IF NOT EXISTS procore_live_record_state_index (
          record_key TEXT PRIMARY KEY,
          project_key TEXT NOT NULL,
          endpoint_id TEXT NOT NULL,
          parent_procore_id TEXT,
          procore_record_id TEXT NOT NULL,
          current_canonical_hash TEXT,
          current_text_hash TEXT,
          first_seen_at_utc TEXT NOT NULL,
          last_seen_at_utc TEXT NOT NULL,
          last_changed_at_utc TEXT,
          last_snapshot_id TEXT,
          last_sync_run_id TEXT,
          normalizer_version TEXT,
          raw_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_persisted = 0),
          redaction_applied INTEGER NOT NULL DEFAULT 1 CHECK(redaction_applied = 1)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_procore_state_index_project_endpoint
          ON procore_live_record_state_index(project_key, endpoint_id);
        """,
        """
        CREATE TABLE IF NOT EXISTS procore_live_record_snapshots (
          snapshot_id TEXT PRIMARY KEY,
          record_key TEXT NOT NULL,
          project_key TEXT NOT NULL,
          endpoint_id TEXT NOT NULL,
          parent_procore_id TEXT,
          procore_record_id TEXT NOT NULL,
          sync_run_id TEXT,
          observed_at_utc TEXT NOT NULL,
          source_updated_at_utc TEXT,
          canonical_hash TEXT NOT NULL,
          canonical_json_redacted TEXT NOT NULL,
          text_intelligence_hash TEXT,
          raw_payload_hash TEXT,
          changed_from_previous INTEGER NOT NULL DEFAULT 1,
          change_summary_json TEXT,
          normalizer_version TEXT,
          raw_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_persisted = 0),
          redaction_applied INTEGER NOT NULL DEFAULT 1 CHECK(redaction_applied = 1),
          UNIQUE(record_key, canonical_hash)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_procore_snapshots_record_observed
          ON procore_live_record_snapshots(record_key, observed_at_utc);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_procore_snapshots_project_endpoint
          ON procore_live_record_snapshots(project_key, endpoint_id, observed_at_utc);
        """,
        """
        CREATE TABLE IF NOT EXISTS procore_live_record_change_events (
          change_event_id TEXT PRIMARY KEY,
          record_key TEXT NOT NULL,
          project_key TEXT NOT NULL,
          endpoint_id TEXT NOT NULL,
          parent_procore_id TEXT,
          procore_record_id TEXT NOT NULL,
          sync_run_id TEXT,
          from_snapshot_id TEXT,
          to_snapshot_id TEXT,
          detected_at_utc TEXT NOT NULL,
          source_updated_at_utc TEXT,
          field_path TEXT NOT NULL,
          old_value_redacted TEXT,
          new_value_redacted TEXT,
          old_value_hash TEXT,
          new_value_hash TEXT,
          change_type TEXT NOT NULL,
          change_category TEXT NOT NULL,
          importance TEXT NOT NULL DEFAULT 'medium',
          review_required INTEGER NOT NULL DEFAULT 0,
          raw_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_persisted = 0)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_procore_change_events_record_detected
          ON procore_live_record_change_events(record_key, detected_at_utc);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_procore_change_events_project_detected
          ON procore_live_record_change_events(project_key, detected_at_utc);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_procore_change_events_category
          ON procore_live_record_change_events(change_category);
        """,
        """
        CREATE TABLE IF NOT EXISTS procore_record_timeline_events (
          timeline_event_id TEXT PRIMARY KEY,
          record_key TEXT NOT NULL,
          project_key TEXT NOT NULL,
          endpoint_id TEXT NOT NULL,
          parent_procore_id TEXT,
          procore_record_id TEXT NOT NULL,
          source_change_event_id TEXT,
          source_snapshot_id TEXT,
          event_type TEXT NOT NULL,
          event_time_utc TEXT NOT NULL,
          summary_redacted TEXT NOT NULL,
          importance TEXT NOT NULL DEFAULT 'medium',
          actor_entity_key TEXT,
          target_entity_key TEXT,
          action_signal_id TEXT,
          metadata_json TEXT,
          raw_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_persisted = 0)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_procore_timeline_project_time
          ON procore_record_timeline_events(project_key, event_time_utc);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_procore_timeline_record_time
          ON procore_record_timeline_events(record_key, event_time_utc);
        """,
        # ----- cross-cutting enrichment -----
        """
        CREATE TABLE IF NOT EXISTS procore_people_entities (
          person_entity_key TEXT PRIMARY KEY,
          procore_user_id TEXT,
          login_hash TEXT,
          display_name_redacted TEXT,
          company_name_redacted TEXT,
          first_seen_at_utc TEXT NOT NULL,
          last_seen_at_utc TEXT NOT NULL,
          source_count INTEGER NOT NULL DEFAULT 1,
          raw_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_persisted = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS procore_company_entities (
          company_entity_key TEXT PRIMARY KEY,
          procore_company_id TEXT,
          name_redacted TEXT,
          first_seen_at_utc TEXT NOT NULL,
          last_seen_at_utc TEXT NOT NULL,
          source_count INTEGER NOT NULL DEFAULT 1
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS procore_location_entities (
          location_entity_key TEXT PRIMARY KEY,
          project_key TEXT NOT NULL,
          procore_location_id TEXT,
          name_redacted TEXT,
          node_name_redacted TEXT,
          parent_location_id TEXT,
          path_redacted TEXT,
          first_seen_at_utc TEXT NOT NULL,
          last_seen_at_utc TEXT NOT NULL
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS procore_attachment_refs (
          attachment_ref_id TEXT PRIMARY KEY,
          project_key TEXT NOT NULL,
          source_record_key TEXT NOT NULL,
          source_endpoint_id TEXT NOT NULL,
          parent_record_key TEXT,
          procore_attachment_id TEXT,
          filename_redacted TEXT,
          filename_hash TEXT,
          url_hash TEXT,
          url_path_redacted TEXT,
          content_type TEXT,
          size_bytes INTEGER,
          download_eligibility TEXT NOT NULL DEFAULT 'metadata_only',
          sensitivity TEXT NOT NULL DEFAULT 'medium',
          first_seen_at_utc TEXT NOT NULL,
          last_seen_at_utc TEXT NOT NULL,
          raw_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_persisted = 0)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_procore_attachment_refs_source
          ON procore_attachment_refs(source_record_key);
        """,
        """
        CREATE TABLE IF NOT EXISTS procore_custom_field_values (
          custom_field_value_id TEXT PRIMARY KEY,
          project_key TEXT NOT NULL,
          record_key TEXT NOT NULL,
          endpoint_id TEXT NOT NULL,
          procore_record_id TEXT NOT NULL,
          custom_field_key TEXT NOT NULL,
          data_type TEXT,
          value_json_redacted TEXT,
          value_hash TEXT,
          value_label_redacted TEXT,
          updated_at_utc TEXT,
          first_seen_at_utc TEXT NOT NULL,
          last_seen_at_utc TEXT NOT NULL,
          UNIQUE(record_key, custom_field_key)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS procore_record_edges (
          edge_id TEXT PRIMARY KEY,
          project_key TEXT NOT NULL,
          from_record_key TEXT NOT NULL,
          to_record_key TEXT,
          to_entity_key TEXT,
          edge_type TEXT NOT NULL,
          source_endpoint_id TEXT NOT NULL,
          confidence REAL NOT NULL DEFAULT 1.0,
          first_seen_at_utc TEXT NOT NULL,
          last_seen_at_utc TEXT NOT NULL,
          metadata_json TEXT
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_procore_record_edges_from
          ON procore_record_edges(from_record_key);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_procore_record_edges_to_record
          ON procore_record_edges(to_record_key);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_procore_record_edges_to_entity
          ON procore_record_edges(to_entity_key);
        """,
        """
        CREATE TABLE IF NOT EXISTS procore_action_signals (
          action_signal_id TEXT PRIMARY KEY,
          project_key TEXT NOT NULL,
          record_key TEXT NOT NULL,
          endpoint_id TEXT NOT NULL,
          signal_type TEXT NOT NULL,
          signal_status TEXT NOT NULL DEFAULT 'open',
          importance TEXT NOT NULL DEFAULT 'medium',
          due_at_utc TEXT,
          owner_entity_key TEXT,
          title_redacted TEXT NOT NULL,
          summary_redacted TEXT,
          reason_codes_json TEXT,
          first_detected_at_utc TEXT NOT NULL,
          last_seen_at_utc TEXT NOT NULL,
          resolved_at_utc TEXT,
          source_change_event_id TEXT,
          metadata_json TEXT
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_procore_action_signals_project_status
          ON procore_action_signals(project_key, signal_status, importance);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_procore_action_signals_type
          ON procore_action_signals(signal_type);
        """,
        """
        CREATE TABLE IF NOT EXISTS procore_text_intelligence (
          text_intelligence_id TEXT PRIMARY KEY,
          project_key TEXT NOT NULL,
          record_key TEXT NOT NULL,
          endpoint_id TEXT NOT NULL,
          source_field_path TEXT NOT NULL,
          text_hash TEXT NOT NULL,
          text_length INTEGER,
          excerpt_redacted TEXT,
          topics_json TEXT,
          mentioned_records_json TEXT,
          action_candidates_json TEXT,
          risk_terms_json TEXT,
          sensitivity TEXT NOT NULL DEFAULT 'medium',
          review_required INTEGER NOT NULL DEFAULT 0,
          encrypted_full_text_ref TEXT,
          created_at_utc TEXT NOT NULL,
          raw_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_persisted = 0),
          UNIQUE(record_key, source_field_path, text_hash)
        );
        """,
        # ----- inspection projection -----
        """
        CREATE TABLE IF NOT EXISTS procore_inspection_records (
          inspection_record_key TEXT PRIMARY KEY,
          project_key TEXT NOT NULL,
          inspection_id TEXT NOT NULL,
          name_redacted TEXT,
          identifier TEXT,
          number TEXT,
          status TEXT,
          inspection_date TEXT,
          due_at_utc TEXT,
          closed_at_utc TEXT,
          list_template_id TEXT,
          list_template_name_redacted TEXT,
          inspection_type_name TEXT,
          is_safety INTEGER NOT NULL DEFAULT 0,
          private INTEGER,
          overdue INTEGER,
          item_count INTEGER,
          respondable_item_count INTEGER,
          inspected_item_count INTEGER,
          conforming_item_count INTEGER,
          deficient_item_count INTEGER,
          observations_count INTEGER,
          closed_observations_count INTEGER,
          created_at_utc TEXT,
          updated_at_utc TEXT,
          last_sync_run_id TEXT,
          UNIQUE(project_key, inspection_id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS procore_inspection_sections (
          inspection_section_key TEXT PRIMARY KEY,
          project_key TEXT NOT NULL,
          section_id TEXT NOT NULL,
          inspection_id TEXT,
          template_section_id TEXT,
          name_redacted TEXT,
          position INTEGER,
          risk_category TEXT,
          updated_at_utc TEXT,
          UNIQUE(project_key, section_id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS procore_inspection_items (
          inspection_item_key TEXT PRIMARY KEY,
          project_key TEXT NOT NULL,
          item_id TEXT NOT NULL,
          inspection_id TEXT,
          list_id TEXT,
          section_id TEXT,
          template_item_id TEXT,
          parent_item_id TEXT,
          item_number TEXT,
          item_name_redacted TEXT,
          status TEXT,
          responded_with TEXT,
          response_id TEXT,
          response_name TEXT,
          response_status TEXT,
          is_unanswered INTEGER NOT NULL DEFAULT 0,
          is_deficient INTEGER NOT NULL DEFAULT 0,
          is_conforming INTEGER NOT NULL DEFAULT 0,
          is_not_applicable INTEGER NOT NULL DEFAULT 0,
          position INTEGER,
          relative_position INTEGER,
          updated_at_utc TEXT,
          last_sync_run_id TEXT,
          UNIQUE(project_key, item_id)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_procore_inspection_items_project_status
          ON procore_inspection_items(project_key, is_unanswered, is_deficient);
        """,
        """
        CREATE TABLE IF NOT EXISTS procore_inspection_response_sets (
          response_set_key TEXT PRIMARY KEY,
          project_key TEXT NOT NULL,
          response_set_id TEXT NOT NULL,
          name_redacted TEXT,
          active INTEGER,
          procore_standard INTEGER,
          created_at_utc TEXT,
          updated_at_utc TEXT,
          UNIQUE(project_key, response_set_id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS procore_inspection_response_options (
          response_option_key TEXT PRIMARY KEY,
          project_key TEXT NOT NULL,
          response_set_id TEXT NOT NULL,
          response_option_id TEXT NOT NULL,
          name_redacted TEXT,
          item_status_id TEXT,
          status_category TEXT,
          UNIQUE(project_key, response_set_id, response_option_id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS procore_inspection_evidence_rules (
          evidence_rule_key TEXT PRIMARY KEY,
          project_key TEXT NOT NULL,
          item_id TEXT NOT NULL,
          item_reference_ids_json TEXT,
          observation_response_option_ids_json TEXT,
          observation_status_ids_json TEXT,
          photo_response_option_ids_json TEXT,
          photo_status_ids_json TEXT,
          requires_observation INTEGER NOT NULL DEFAULT 0,
          requires_photo INTEGER NOT NULL DEFAULT 0,
          updated_at_utc TEXT,
          UNIQUE(project_key, item_id)
        );
        """,
        # ----- convenience views (additive; reference tables created above) -----
        """
        CREATE VIEW IF NOT EXISTS v_procore_open_action_signals AS
        SELECT *
        FROM procore_action_signals
        WHERE signal_status = 'open';
        """,
        """
        CREATE VIEW IF NOT EXISTS v_procore_inspection_unanswered_items AS
        SELECT
          i.project_key,
          r.name_redacted AS inspection_name_redacted,
          s.name_redacted AS section_name_redacted,
          i.item_number,
          i.item_name_redacted,
          i.responded_with,
          i.status,
          i.updated_at_utc
        FROM procore_inspection_items i
        LEFT JOIN procore_inspection_records r
          ON r.project_key = i.project_key AND r.inspection_id = i.inspection_id
        LEFT JOIN procore_inspection_sections s
          ON s.project_key = i.project_key AND s.section_id = i.section_id
        WHERE i.is_unanswered = 1;
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

    # v8 = Phase 05 Procore contracts & financials projection tables (additive
    # only; does not touch V1-V7 tables). The first 10 tables + 4 indexes are
    # transcribed verbatim from the package's
    # resources/sql/phase_05_financial_schema_additions.sql. All money columns
    # are TEXT to preserve decimal precision (no binary-float coercion). Every
    # table carries the Phase 04B redaction guards
    # (CHECK(raw_body_persisted = 0) / CHECK(redaction_applied = 1)).
    #
    # The final 3 tables (change_order_line_items, budget_changes,
    # compliance_documents) are HB-authored EXTENSIONS beyond the authoritative
    # SQL, modeled on the ledger prose + the verbatim schema conventions. Their
    # columns are provisional and reconciled against live payloads at promotion.
    V8_STATEMENTS: list[str] = [
        """
        CREATE TABLE IF NOT EXISTS procore_financial_contracts (
          record_key TEXT PRIMARY KEY,
          project_key TEXT NOT NULL,
          endpoint_id TEXT NOT NULL,
          contract_id TEXT NOT NULL,
          contract_family TEXT NOT NULL,
          contract_type TEXT,
          number TEXT,
          title_redacted TEXT,
          status TEXT,
          executed INTEGER,
          private INTEGER,
          accounting_method TEXT,
          vendor_entity_key TEXT,
          company_entity_key TEXT,
          grand_total TEXT,
          original_contract_sum TEXT,
          revised_contract_sum TEXT,
          approved_change_orders_amount TEXT,
          pending_change_orders_amount TEXT,
          retainage_percent TEXT,
          currency_iso_code TEXT,
          base_currency_iso_code TEXT,
          currency_exchange_rate TEXT,
          contract_date TEXT,
          start_date TEXT,
          completion_date TEXT,
          updated_at_utc TEXT,
          last_sync_run_id TEXT,
          raw_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_persisted = 0),
          redaction_applied INTEGER NOT NULL DEFAULT 1 CHECK(redaction_applied = 1)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS procore_financial_line_items (
          line_item_key TEXT PRIMARY KEY,
          project_key TEXT NOT NULL,
          parent_record_key TEXT NOT NULL,
          endpoint_id TEXT NOT NULL,
          line_item_id TEXT NOT NULL,
          line_item_kind TEXT NOT NULL,
          description_summary_json TEXT,
          wbs_code_id TEXT,
          wbs_flat_code TEXT,
          wbs_description_redacted TEXT,
          cost_code_id TEXT,
          line_item_type_id TEXT,
          tax_code_id TEXT,
          quantity TEXT,
          uom TEXT,
          unit_cost TEXT,
          amount TEXT,
          scheduled_value TEXT,
          billed_to_date TEXT,
          work_completed_this_period TEXT,
          materials_presently_stored TEXT,
          retainage_held TEXT,
          position INTEGER,
          currency_iso_code TEXT,
          raw_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_persisted = 0),
          redaction_applied INTEGER NOT NULL DEFAULT 1 CHECK(redaction_applied = 1)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS procore_financial_change_orders (
          record_key TEXT PRIMARY KEY,
          project_key TEXT NOT NULL,
          endpoint_id TEXT NOT NULL,
          change_order_id TEXT NOT NULL,
          change_order_family TEXT NOT NULL,
          contract_record_key TEXT,
          contract_id TEXT,
          number TEXT,
          title_redacted TEXT,
          status TEXT,
          executed INTEGER,
          paid INTEGER,
          private INTEGER,
          field_change INTEGER,
          signature_required INTEGER,
          grand_total TEXT,
          schedule_impact_amount TEXT,
          due_date TEXT,
          invoiced_date TEXT,
          paid_date TEXT,
          reviewed_at_utc TEXT,
          updated_at_utc TEXT,
          raw_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_persisted = 0),
          redaction_applied INTEGER NOT NULL DEFAULT 1 CHECK(redaction_applied = 1)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS procore_financial_payment_applications (
          record_key TEXT PRIMARY KEY,
          project_key TEXT NOT NULL,
          endpoint_id TEXT NOT NULL,
          payment_application_id TEXT NOT NULL,
          contract_record_key TEXT,
          prime_contract_id TEXT,
          billing_period_id TEXT,
          invoice_number TEXT,
          number TEXT,
          status TEXT,
          billing_date TEXT,
          period_start TEXT,
          period_end TEXT,
          percent_complete TEXT,
          current_payment_due TEXT,
          total_amount_paid TEXT,
          total_retainage TEXT,
          balance_to_finish_including_retainage TEXT,
          contract_sum_to_date TEXT,
          updated_at_utc TEXT,
          raw_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_persisted = 0),
          redaction_applied INTEGER NOT NULL DEFAULT 1 CHECK(redaction_applied = 1)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS procore_financial_invoice_items (
          invoice_item_key TEXT PRIMARY KEY,
          project_key TEXT NOT NULL,
          endpoint_id TEXT NOT NULL,
          invoice_record_key TEXT,
          requisition_id TEXT,
          item_id TEXT NOT NULL,
          item_type TEXT,
          line_item_id TEXT,
          cost_code_id TEXT,
          wbs_flat_code TEXT,
          description_summary_json TEXT,
          scheduled_value TEXT,
          work_completed_this_period TEXT,
          materials_presently_stored TEXT,
          total_completed_and_stored_to_date TEXT,
          retainage_held TEXT,
          subcontractor_claimed_amount TEXT,
          status TEXT,
          position INTEGER,
          raw_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_persisted = 0),
          redaction_applied INTEGER NOT NULL DEFAULT 1 CHECK(redaction_applied = 1)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS procore_financial_rfqs (
          record_key TEXT PRIMARY KEY,
          project_key TEXT NOT NULL,
          endpoint_id TEXT NOT NULL,
          rfq_id TEXT NOT NULL,
          commitment_contract_id TEXT,
          number TEXT,
          title_redacted TEXT,
          status TEXT,
          private INTEGER,
          due_date TEXT,
          estimated_amount TEXT,
          estimated_schedule_impact TEXT,
          estimated_status TEXT,
          intent_to_quote INTEGER,
          original_quote TEXT,
          updated_at_utc TEXT,
          raw_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_persisted = 0),
          redaction_applied INTEGER NOT NULL DEFAULT 1 CHECK(redaction_applied = 1)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS procore_financial_change_events (
          record_key TEXT PRIMARY KEY,
          project_key TEXT NOT NULL,
          endpoint_id TEXT NOT NULL,
          change_event_id TEXT NOT NULL,
          number TEXT,
          title_redacted TEXT,
          status TEXT,
          scope TEXT,
          estimated_cost TEXT,
          estimated_revenue TEXT,
          schedule_impact_amount TEXT,
          owner_cost_amount TEXT,
          commitment_cost_amount TEXT,
          updated_at_utc TEXT,
          raw_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_persisted = 0),
          redaction_applied INTEGER NOT NULL DEFAULT 1 CHECK(redaction_applied = 1)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS procore_financial_budget_views (
          budget_view_key TEXT PRIMARY KEY,
          project_key TEXT NOT NULL,
          budget_view_id TEXT NOT NULL,
          name_redacted TEXT,
          description_summary_json TEXT,
          updated_at_utc TEXT,
          raw_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_persisted = 0),
          redaction_applied INTEGER NOT NULL DEFAULT 1 CHECK(redaction_applied = 1)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS procore_financial_budget_rows (
          budget_row_key TEXT PRIMARY KEY,
          project_key TEXT NOT NULL,
          budget_view_key TEXT,
          endpoint_id TEXT NOT NULL,
          row_id TEXT NOT NULL,
          wbs_code_id TEXT,
          wbs_flat_code TEXT,
          cost_code_id TEXT,
          line_item_type_id TEXT,
          column_values_json_redacted TEXT,
          raw_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_persisted = 0),
          redaction_applied INTEGER NOT NULL DEFAULT 1 CHECK(redaction_applied = 1)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS procore_financial_amount_facts (
          amount_fact_id TEXT PRIMARY KEY,
          project_key TEXT NOT NULL,
          record_key TEXT NOT NULL,
          endpoint_id TEXT NOT NULL,
          amount_name TEXT NOT NULL,
          amount_value TEXT NOT NULL,
          currency_iso_code TEXT,
          base_currency_iso_code TEXT,
          period_start TEXT,
          period_end TEXT,
          wbs_code_id TEXT,
          cost_code_id TEXT,
          source_field_path TEXT NOT NULL,
          created_at_utc TEXT NOT NULL,
          raw_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_persisted = 0)
        );
        """,
        # --- HB-authored extension tables (beyond the authoritative SQL) ---
        """
        CREATE TABLE IF NOT EXISTS procore_financial_change_order_line_items (
          line_item_key TEXT PRIMARY KEY,
          project_key TEXT NOT NULL,
          change_order_record_key TEXT NOT NULL,
          endpoint_id TEXT NOT NULL,
          line_item_id TEXT NOT NULL,
          change_order_family TEXT NOT NULL,
          description_summary_json TEXT,
          wbs_code_id TEXT,
          wbs_flat_code TEXT,
          cost_code_id TEXT,
          line_item_type_id TEXT,
          quantity TEXT,
          uom TEXT,
          unit_cost TEXT,
          amount TEXT,
          position INTEGER,
          currency_iso_code TEXT,
          raw_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_persisted = 0),
          redaction_applied INTEGER NOT NULL DEFAULT 1 CHECK(redaction_applied = 1)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS procore_financial_budget_changes (
          budget_change_key TEXT PRIMARY KEY,
          project_key TEXT NOT NULL,
          endpoint_id TEXT NOT NULL,
          budget_change_kind TEXT NOT NULL,
          budget_change_id TEXT NOT NULL,
          budget_view_key TEXT,
          parent_change_key TEXT,
          number TEXT,
          status TEXT,
          title_redacted TEXT,
          wbs_code_id TEXT,
          wbs_flat_code TEXT,
          cost_code_id TEXT,
          adjustment_amount TEXT,
          from_amount TEXT,
          to_amount TEXT,
          approved_at_utc TEXT,
          updated_at_utc TEXT,
          raw_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_persisted = 0),
          redaction_applied INTEGER NOT NULL DEFAULT 1 CHECK(redaction_applied = 1)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS procore_financial_compliance_documents (
          compliance_key TEXT PRIMARY KEY,
          project_key TEXT NOT NULL,
          contract_record_key TEXT,
          endpoint_id TEXT NOT NULL,
          compliance_id TEXT NOT NULL,
          document_type TEXT,
          status TEXT,
          compliant INTEGER,
          effective_date TEXT,
          expiration_date TEXT,
          attachment_path_redacted TEXT,
          notes_summary_redacted TEXT,
          updated_at_utc TEXT,
          raw_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_persisted = 0),
          redaction_applied INTEGER NOT NULL DEFAULT 1 CHECK(redaction_applied = 1)
        );
        """,
        # --- Indexes (verbatim from package SQL + extension-table indexes) ---
        """
        CREATE INDEX IF NOT EXISTS ix_procore_financial_contracts_project_family
          ON procore_financial_contracts(project_key, contract_family, status);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_procore_financial_line_items_parent
          ON procore_financial_line_items(parent_record_key);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_procore_financial_change_orders_project_status
          ON procore_financial_change_orders(project_key, status, executed, paid);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_procore_financial_amount_facts_project_name
          ON procore_financial_amount_facts(project_key, amount_name);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_procore_financial_change_order_line_items_parent
          ON procore_financial_change_order_line_items(change_order_record_key);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_procore_financial_budget_changes_project_kind
          ON procore_financial_budget_changes(project_key, budget_change_kind);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_procore_financial_compliance_documents_project_status
          ON procore_financial_compliance_documents(project_key, status);
        """,
    ]

    # v9 Phase 05 subcontractor billing surface: billing-period anchors +
    # subcontractor-invoice (requisition) headers. Additive only; invoice *items*
    # reuse the V8 procore_financial_invoice_items table. Subcontractor address /
    # contact summary_text is never projected (no column maps to it). Amounts are
    # decimal-safe TEXT; raw bodies never persist (CHECK guards).
    V9_STATEMENTS: list[str] = [
        """
        CREATE TABLE IF NOT EXISTS procore_financial_billing_periods (
          billing_period_key TEXT PRIMARY KEY,
          project_key TEXT NOT NULL,
          endpoint_id TEXT NOT NULL,
          billing_period_id TEXT NOT NULL,
          status TEXT,
          start_date TEXT,
          end_date TEXT,
          due_date TEXT,
          position INTEGER,
          updated_at_utc TEXT,
          raw_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_persisted = 0),
          redaction_applied INTEGER NOT NULL DEFAULT 1 CHECK(redaction_applied = 1)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS procore_financial_subcontractor_invoices (
          record_key TEXT PRIMARY KEY,
          project_key TEXT NOT NULL,
          endpoint_id TEXT NOT NULL,
          invoice_id TEXT NOT NULL,
          commitment_record_key TEXT,
          commitment_id TEXT,
          billing_period_key TEXT,
          billing_period_id TEXT,
          previous_invoice_id TEXT,
          vendor_id TEXT,
          vendor_entity_key TEXT,
          invoice_number TEXT,
          number TEXT,
          invoice_type TEXT,
          status TEXT,
          final INTEGER,
          billing_date TEXT,
          period_start TEXT,
          period_end TEXT,
          percent_complete TEXT,
          payment_date TEXT,
          submitted_at TEXT,
          erp_status TEXT,
          current_payment_due TEXT,
          total_claimed_amount TEXT,
          original_contract_sum TEXT,
          contract_sum_to_date TEXT,
          total_completed_and_stored_to_date TEXT,
          total_retainage TEXT,
          total_earned_less_retainage TEXT,
          balance_to_finish_including_retainage TEXT,
          updated_at_utc TEXT,
          raw_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_persisted = 0),
          redaction_applied INTEGER NOT NULL DEFAULT 1 CHECK(redaction_applied = 1)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_procore_financial_billing_periods_project_status
          ON procore_financial_billing_periods(project_key, status);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_procore_financial_subcontractor_invoices_project_filters
          ON procore_financial_subcontractor_invoices(project_key, status, billing_period_id, vendor_id);
        """,
    ]

    # v10 = Phase 06 operational email intelligence: ACTIVE policy singleton +
    # mailbox source registry (Bobby's mailbox + included/excluded folders).
    # Additive only; never touches V1-V9 tables, and in particular leaves the
    # V5 construction_email_intelligence_deferred_state row untouched as
    # preserved historical evidence. Hard CHECK constraints lock the read-only /
    # no-mutation / no-full-body / no-source-copy / no-attachment-download /
    # metadata-only / pilot-only-backfill guardrails at the schema level
    # (defense in depth beneath the Pydantic Literal locks + adapter guards).
    V10_STATEMENTS: list[str] = [
        """
        CREATE TABLE IF NOT EXISTS email_intelligence_active_policy (
          id INTEGER PRIMARY KEY CHECK (id = 1),
          policy_phase TEXT NOT NULL,
          mailbox_mode TEXT NOT NULL DEFAULT 'read_only' CHECK(mailbox_mode = 'read_only'),
          writeback_allowed INTEGER NOT NULL DEFAULT 0 CHECK(writeback_allowed = 0),
          mailbox_mutation_allowed INTEGER NOT NULL DEFAULT 0 CHECK(mailbox_mutation_allowed = 0),
          full_archive_crawl INTEGER NOT NULL DEFAULT 0 CHECK(full_archive_crawl = 0),
          source_copy_to_vault INTEGER NOT NULL DEFAULT 0 CHECK(source_copy_to_vault = 0),
          full_email_body_in_obsidian INTEGER NOT NULL DEFAULT 0 CHECK(full_email_body_in_obsidian = 0),
          attachment_content_download_by_default INTEGER NOT NULL DEFAULT 0 CHECK(attachment_content_download_by_default = 0),
          metadata_only_by_default INTEGER NOT NULL DEFAULT 1 CHECK(metadata_only_by_default = 1),
          review_required_for_sensitive INTEGER NOT NULL DEFAULT 1 CHECK(review_required_for_sensitive = 1),
          initial_backfill_mode TEXT NOT NULL DEFAULT 'pilot_projects_only' CHECK(initial_backfill_mode = 'pilot_projects_only'),
          ollama_invalid_json_routes_to_review INTEGER NOT NULL DEFAULT 1 CHECK(ollama_invalid_json_routes_to_review = 1),
          default_lookback_days INTEGER NOT NULL DEFAULT 30,
          ollama_enabled_for_email_intelligence INTEGER NOT NULL DEFAULT 1,
          low_confidence_threshold REAL NOT NULL DEFAULT 0.75,
          updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS email_source_locations (
          source_id TEXT PRIMARY KEY,
          source_system TEXT NOT NULL DEFAULT 'outlook',
          mailbox_owner_hash TEXT NOT NULL,
          mailbox_display_name_redacted TEXT,
          mailbox_user_principal_name_hash TEXT,
          folder_id TEXT,
          folder_display_name TEXT,
          folder_role TEXT NOT NULL,
          include_in_sync INTEGER NOT NULL DEFAULT 1,
          sync_mode TEXT NOT NULL DEFAULT 'bounded_lookback',
          default_lookback_days INTEGER NOT NULL DEFAULT 30,
          read_only INTEGER NOT NULL DEFAULT 1 CHECK(read_only = 1),
          mailbox_mutation_allowed INTEGER NOT NULL DEFAULT 0 CHECK(mailbox_mutation_allowed = 0),
          full_archive_crawl_allowed INTEGER NOT NULL DEFAULT 0 CHECK(full_archive_crawl_allowed = 0),
          source_copy_to_vault_allowed INTEGER NOT NULL DEFAULT 0 CHECK(source_copy_to_vault_allowed = 0),
          full_email_body_in_obsidian_allowed INTEGER NOT NULL DEFAULT 0 CHECK(full_email_body_in_obsidian_allowed = 0),
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_email_source_locations_owner
          ON email_source_locations(mailbox_owner_hash);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_email_source_locations_role
          ON email_source_locations(folder_role);
        """,
    ]

    # v11 = Phase 06 operational email-intelligence data schema: the tables the
    # read-only pipeline writes to (sync state, crawl-run receipts, message
    # metadata + recipients + attachment metadata, project matches, relationship
    # candidates, thread summaries, review queue, processing receipts).
    # Additive only; never touches V1-V10 (in particular the V10 email policy +
    # source-registry tables and the V5 deferred-state row are left intact).
    # email_source_locations is NOT re-declared here — it already exists in V10
    # and the foreign keys below reference that existing table. Hard CHECK
    # constraints lock no-mutation / no-full-body-persistence / no-attachment-
    # content-download / metadata-only at the schema level (defense in depth
    # beneath the adapter ValueError guards). No full email body is stored: only
    # a bounded, redacted preview excerpt + hashes.
    V11_STATEMENTS: list[str] = [
        """
        CREATE TABLE IF NOT EXISTS email_sync_state (
          source_id TEXT NOT NULL REFERENCES email_source_locations(source_id),
          folder_id TEXT NOT NULL,
          sync_mode TEXT NOT NULL,
          lookback_days INTEGER NOT NULL DEFAULT 30,
          last_successful_sync_utc TEXT,
          last_attempted_sync_utc TEXT,
          latest_received_datetime TEXT,
          latest_sent_datetime TEXT,
          delta_token_fingerprint TEXT,
          delta_token_supported INTEGER NOT NULL DEFAULT 0,
          sync_status TEXT NOT NULL DEFAULT 'pending',
          error_redacted TEXT,
          PRIMARY KEY (source_id, folder_id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS email_crawl_runs (
          run_id TEXT PRIMARY KEY,
          source_id TEXT NOT NULL REFERENCES email_source_locations(source_id),
          project_key TEXT,
          project_number TEXT,
          mode TEXT NOT NULL,
          dry_run INTEGER NOT NULL DEFAULT 1,
          lookback_days INTEGER NOT NULL,
          started_utc TEXT NOT NULL,
          completed_utc TEXT,
          folders_seen INTEGER NOT NULL DEFAULT 0,
          messages_seen INTEGER NOT NULL DEFAULT 0,
          messages_in_scope INTEGER NOT NULL DEFAULT 0,
          messages_indexed INTEGER NOT NULL DEFAULT 0,
          messages_skipped INTEGER NOT NULL DEFAULT 0,
          relationship_candidates_created INTEGER NOT NULL DEFAULT 0,
          review_items_created INTEGER NOT NULL DEFAULT 0,
          mailbox_mutation_attempted INTEGER NOT NULL DEFAULT 0 CHECK(mailbox_mutation_attempted = 0),
          full_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(full_body_persisted = 0),
          attachment_content_downloaded INTEGER NOT NULL DEFAULT 0 CHECK(attachment_content_downloaded = 0),
          status TEXT NOT NULL,
          error_redacted TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS email_messages (
          message_id TEXT PRIMARY KEY,
          internet_message_id TEXT,
          conversation_id TEXT,
          thread_key TEXT NOT NULL,
          source_id TEXT NOT NULL REFERENCES email_source_locations(source_id),
          folder_id TEXT,
          folder_display_name TEXT,
          subject_redacted TEXT,
          subject_hash TEXT,
          sender_name_redacted TEXT,
          sender_address_hash TEXT,
          sender_domain TEXT,
          to_recipient_count INTEGER NOT NULL DEFAULT 0,
          cc_recipient_count INTEGER NOT NULL DEFAULT 0,
          bcc_recipient_count INTEGER NOT NULL DEFAULT 0,
          received_datetime TEXT,
          sent_datetime TEXT,
          last_modified_datetime TEXT,
          has_attachments INTEGER NOT NULL DEFAULT 0,
          importance TEXT,
          categories_metadata_json TEXT,
          sensitivity_metadata TEXT,
          web_link TEXT,
          body_preview_hash TEXT,
          body_preview_excerpt_redacted TEXT,
          body_checked INTEGER NOT NULL DEFAULT 0,
          body_mention_detected INTEGER NOT NULL DEFAULT 0,
          project_number_detected TEXT,
          project_match_confidence REAL,
          sensitivity_classification TEXT,
          extraction_policy TEXT NOT NULL DEFAULT 'metadata_only',
          review_required INTEGER NOT NULL DEFAULT 0,
          full_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(full_body_persisted = 0),
          mailbox_mutation_allowed INTEGER NOT NULL DEFAULT 0 CHECK(mailbox_mutation_allowed = 0),
          indexed_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_email_messages_thread ON email_messages(thread_key);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_email_messages_project ON email_messages(project_number_detected);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_email_messages_received ON email_messages(received_datetime);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_email_messages_review ON email_messages(review_required);
        """,
        """
        CREATE TABLE IF NOT EXISTS email_message_recipients (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          message_id TEXT NOT NULL REFERENCES email_messages(message_id) ON DELETE CASCADE,
          recipient_role TEXT NOT NULL,
          display_name_redacted TEXT,
          address_hash TEXT,
          domain TEXT,
          is_bobby INTEGER NOT NULL DEFAULT 0,
          known_project_participant INTEGER NOT NULL DEFAULT 0,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(message_id, recipient_role, address_hash)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS email_message_attachments (
          attachment_key TEXT PRIMARY KEY,
          message_id TEXT NOT NULL REFERENCES email_messages(message_id) ON DELETE CASCADE,
          attachment_id TEXT,
          name_redacted TEXT,
          name_hash TEXT,
          content_type TEXT,
          size_bytes INTEGER,
          is_inline INTEGER NOT NULL DEFAULT 0,
          metadata_only INTEGER NOT NULL DEFAULT 1 CHECK(metadata_only = 1),
          content_downloaded INTEGER NOT NULL DEFAULT 0 CHECK(content_downloaded = 0),
          sharepoint_or_onedrive_link_detected INTEGER NOT NULL DEFAULT 0,
          linked_drive_item_id TEXT,
          sensitivity_hint TEXT,
          review_required INTEGER NOT NULL DEFAULT 0,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS email_project_matches (
          match_id TEXT PRIMARY KEY,
          message_id TEXT NOT NULL REFERENCES email_messages(message_id) ON DELETE CASCADE,
          project_key TEXT,
          project_number TEXT,
          project_name_normalized TEXT,
          match_signal TEXT NOT NULL,
          match_value_hash TEXT,
          confidence REAL NOT NULL,
          review_required INTEGER NOT NULL DEFAULT 0,
          evidence_redacted TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(message_id, project_key, match_signal)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS email_relationship_candidates (
          candidate_id TEXT PRIMARY KEY,
          message_id TEXT NOT NULL REFERENCES email_messages(message_id) ON DELETE CASCADE,
          project_key TEXT,
          candidate_type TEXT NOT NULL,
          target_source_system TEXT,
          target_table TEXT,
          target_key TEXT,
          match_signal TEXT NOT NULL,
          confidence REAL NOT NULL,
          evidence_redacted TEXT,
          review_required INTEGER NOT NULL DEFAULT 0,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(message_id, candidate_type, target_table, target_key, match_signal)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS email_thread_summaries (
          thread_key TEXT PRIMARY KEY,
          project_key TEXT,
          conversation_id TEXT,
          message_count INTEGER NOT NULL DEFAULT 0,
          first_message_datetime TEXT,
          last_message_datetime TEXT,
          participants_hash_json TEXT,
          summary_redacted TEXT,
          summary_policy TEXT NOT NULL DEFAULT 'metadata_and_preview_only',
          review_required INTEGER NOT NULL DEFAULT 0,
          model_used TEXT,
          model_output_validated INTEGER NOT NULL DEFAULT 0,
          generated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS email_review_queue (
          review_id TEXT PRIMARY KEY,
          message_id TEXT NOT NULL REFERENCES email_messages(message_id) ON DELETE CASCADE,
          project_key TEXT,
          category TEXT NOT NULL,
          sensitivity TEXT NOT NULL,
          reason TEXT NOT NULL,
          suggested_action TEXT NOT NULL,
          confidence REAL NOT NULL,
          status TEXT NOT NULL DEFAULT 'open',
          routed_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          resolved_utc TEXT,
          UNIQUE(message_id, category, reason)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS email_processing_receipts (
          receipt_id TEXT PRIMARY KEY,
          run_id TEXT,
          message_id TEXT,
          project_key TEXT,
          operation TEXT NOT NULL,
          status TEXT NOT NULL,
          detail_json TEXT,
          mailbox_mutation_attempted INTEGER NOT NULL DEFAULT 0 CHECK(mailbox_mutation_attempted = 0),
          full_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(full_body_persisted = 0),
          attachment_content_downloaded INTEGER NOT NULL DEFAULT 0 CHECK(attachment_content_downloaded = 0),
          generated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_email_review_queue_status
          ON email_review_queue(status);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_email_review_queue_project
          ON email_review_queue(project_key);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_email_processing_receipts_run
          ON email_processing_receipts(run_id);
        """,
    ]

    # v12 = Phase 06 Prompt 08A controlled encrypted full-body storage. The body
    # is fetched read-only, encrypted via the text vault (outside the repo), and
    # ONLY a deterministic encrypted_full_body_ref + hash/length/metadata are
    # stored here. No plaintext column exists; CHECK constraints lock plaintext /
    # obsidian / evidence / log body persistence to 0 (defense in depth beneath
    # the Pydantic policy locks). Additive only; V1-V11 untouched, and the V11
    # email_messages.full_body_persisted=0 CHECK is preserved (the body never
    # lives as plaintext in email_messages or any SQLite table).
    V12_STATEMENTS: list[str] = [
        """
        CREATE TABLE IF NOT EXISTS email_message_body_vault_refs (
          message_id TEXT PRIMARY KEY REFERENCES email_messages(message_id) ON DELETE CASCADE,
          internet_message_id TEXT,
          conversation_id TEXT,
          body_content_type TEXT,
          body_hash TEXT NOT NULL,
          body_length INTEGER NOT NULL,
          encrypted_full_body_ref TEXT NOT NULL,
          encrypted_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          encryption_method TEXT NOT NULL DEFAULT 'fernet_text_vault',
          plaintext_persisted INTEGER NOT NULL DEFAULT 0 CHECK(plaintext_persisted = 0),
          obsidian_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(obsidian_body_persisted = 0),
          evidence_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(evidence_body_persisted = 0),
          log_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(log_body_persisted = 0),
          extraction_policy TEXT NOT NULL,
          review_required INTEGER NOT NULL DEFAULT 0,
          sensitivity_classification TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_email_body_vault_refs_review
          ON email_message_body_vault_refs(review_required);
        """,
    ]

    # v13 Phase 06 Prompt 10 email review routing + encrypted-body eligibility.
    # Additive only: extends the existing V11 email_review_queue with the per-message
    # encrypted-body capture decision metadata (eligibility flags + the redacted
    # decision JSON). No plaintext body column is added; ADD COLUMN only — V1-V12
    # tables are untouched and no destructive ALTER/DROP is performed.
    V13_STATEMENTS: list[str] = [
        "ALTER TABLE email_review_queue ADD COLUMN body_capture_eligible "
        "INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE email_review_queue ADD COLUMN encrypted_body_capture_allowed "
        "INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE email_review_queue ADD COLUMN review_required_before_body_use "
        "INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE email_review_queue ADD COLUMN body_capture_decision_json TEXT",
    ]

    # v14 Phase 06 Prompt 11 advisory Ollama email-classification read model.
    # Additive only: a durable, idempotent, queryable home for the structured,
    # redacted advisory model output (Prompt 12 / Obsidian read from it; receipts
    # remain the per-run audit trail). Advisory only — never a legal/contractual/
    # claims/financial/personnel/entitlement determination. CHECK constraints lock
    # advisory_only=1 and plaintext-body / raw-prompt / raw-response persistence to 0
    # (defense in depth: no decrypted body, no full-body plaintext, no raw prompt,
    # no raw model response is ever stored). V1-V13 untouched; CREATE TABLE only.
    V14_STATEMENTS: list[str] = [
        """
        CREATE TABLE IF NOT EXISTS email_model_classifications (
          classification_id TEXT PRIMARY KEY,
          message_id TEXT NOT NULL REFERENCES email_messages(message_id) ON DELETE CASCADE,
          conversation_id TEXT,
          project_key TEXT,
          model_name TEXT NOT NULL,
          model_version TEXT,
          schema_version TEXT NOT NULL,
          classification_status TEXT NOT NULL,
          project_match_confidence REAL,
          topic_labels_json TEXT,
          relationship_candidates_json TEXT,
          risk_flags_json TEXT,
          sensitive_categories_json TEXT,
          review_required INTEGER NOT NULL DEFAULT 0,
          review_reasons_json TEXT,
          advisory_only INTEGER NOT NULL DEFAULT 1 CHECK(advisory_only = 1),
          plaintext_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(plaintext_body_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(message_id, model_name, schema_version)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_email_model_classifications_project
          ON email_model_classifications(project_key);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_email_model_classifications_review
          ON email_model_classifications(review_required);
        """,
    ]

    # v15 Phase 06 (SharePoint/OneDrive Files) Prompt 06 rich driveItem metadata.
    # Additive ADD COLUMN only: extends the V5 construction_drive_items canonical
    # table with the package facet, change tags, created time, parent path, folder
    # child count, sharepoint web/listItem ids, redacted facet JSON, and first/last
    # -seen lifecycle so the normalizer can persist durable rich metadata. No
    # source document text, no @microsoft.graph.downloadUrl column. V1-V14 untouched.
    V15_STATEMENTS: list[str] = [
        "ALTER TABLE construction_drive_items ADD COLUMN is_package INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE construction_drive_items ADD COLUMN e_tag TEXT",
        "ALTER TABLE construction_drive_items ADD COLUMN c_tag TEXT",
        "ALTER TABLE construction_drive_items ADD COLUMN created_datetime TEXT",
        "ALTER TABLE construction_drive_items ADD COLUMN parent_reference_path TEXT",
        "ALTER TABLE construction_drive_items ADD COLUMN folder_child_count INTEGER",
        "ALTER TABLE construction_drive_items ADD COLUMN sharepoint_web_id TEXT",
        "ALTER TABLE construction_drive_items ADD COLUMN sharepoint_list_item_id TEXT",
        "ALTER TABLE construction_drive_items ADD COLUMN file_hashes_json TEXT",
        "ALTER TABLE construction_drive_items ADD COLUMN package_json_redacted TEXT",
        "ALTER TABLE construction_drive_items ADD COLUMN remote_item_json_redacted TEXT",
        "ALTER TABLE construction_drive_items ADD COLUMN first_seen_utc TEXT",
        "ALTER TABLE construction_drive_items ADD COLUMN last_seen_utc TEXT",
        "CREATE INDEX IF NOT EXISTS ix_construction_drive_items_deleted "
        "ON construction_drive_items(deleted)",
    ]

    # v16 Phase 06A user-provided link → ID resolution. Additive CREATE TABLE only.
    # Stores ONLY redacted/fingerprinted link provenance + resolved canonical IDs;
    # the raw tokenized sharing URL is never persisted (CHECK locks
    # raw_tokenized_url_persisted = 0). Read-only resolution via the Graph Shares
    # API — no sharing-link redemption, no writeback. V1-V15 untouched.
    V16_STATEMENTS: list[str] = [
        """
        CREATE TABLE IF NOT EXISTS construction_graph_link_resolution (
          resolution_id TEXT PRIMARY KEY,
          source_id TEXT,
          redacted_url TEXT,
          hostname TEXT,
          normalized_path TEXT,
          url_fingerprint TEXT,
          share_token_fingerprint TEXT,
          resolution_method TEXT,
          status TEXT NOT NULL,
          site_id TEXT,
          drive_id TEXT,
          drive_item_id TEXT,
          folder_item_id TEXT,
          parent_drive_id TEXT,
          parent_drive_item_id TEXT,
          list_id TEXT,
          list_item_id TEXT,
          web_url TEXT,
          name TEXT,
          item_kind TEXT,
          error_redacted TEXT,
          raw_tokenized_url_persisted INTEGER NOT NULL DEFAULT 0
            CHECK(raw_tokenized_url_persisted = 0),
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_construction_graph_link_resolution_source
          ON construction_graph_link_resolution(source_id);
        """,
    ]

    # v17 Phase 06A Prompt 09 per-file project matching. Additive ADD COLUMN only:
    # extends construction_drive_items with the project-match result fields so
    # deterministic/heuristic matches (confidence/status/reason) and review routing
    # are durable per file. No content; no writeback. V1-V16 untouched.
    V17_STATEMENTS: list[str] = [
        "ALTER TABLE construction_drive_items ADD COLUMN project_key TEXT",
        "ALTER TABLE construction_drive_items ADD COLUMN match_confidence TEXT",
        "ALTER TABLE construction_drive_items ADD COLUMN match_status TEXT",
        "ALTER TABLE construction_drive_items ADD COLUMN review_required INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE construction_drive_items ADD COLUMN review_reason TEXT",
        "ALTER TABLE construction_drive_items ADD COLUMN match_signals_json TEXT",
        "CREATE INDEX IF NOT EXISTS ix_construction_drive_items_project_key "
        "ON construction_drive_items(project_key)",
        "CREATE INDEX IF NOT EXISTS ix_construction_drive_items_match_status "
        "ON construction_drive_items(match_status)",
        "CREATE INDEX IF NOT EXISTS ix_construction_drive_items_review_required "
        "ON construction_drive_items(review_required)",
    ]

    # v18 Phase 06A Prompt 10 file ingestion eligibility decisions. Additive
    # CREATE TABLE only. One decision row per source file; the CHECK enforces the
    # block_review_required_extraction guardrail at the DB layer (a review-required
    # file can never carry extraction_allowed = 1). No content; no writeback.
    V18_STATEMENTS: list[str] = [
        """
        CREATE TABLE IF NOT EXISTS construction_file_ingestion_decisions (
          decision_id TEXT PRIMARY KEY,
          source_id TEXT NOT NULL,
          drive_id TEXT,
          drive_item_id TEXT NOT NULL,
          project_key TEXT,
          project_number_detected TEXT,
          document_type_detected TEXT,
          ingestion_disposition TEXT NOT NULL,
          review_required INTEGER NOT NULL DEFAULT 0,
          review_reason TEXT,
          extraction_allowed INTEGER NOT NULL DEFAULT 0,
          download_allowed INTEGER NOT NULL DEFAULT 0,
          reason_codes_json TEXT,
          decided_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(source_id, drive_item_id),
          CHECK(review_required = 0 OR extraction_allowed = 0)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_construction_file_ingestion_decisions_source
          ON construction_file_ingestion_decisions(source_id);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_construction_file_ingestion_decisions_review
          ON construction_file_ingestion_decisions(review_required);
        """,
    ]

    # v19 Phase 06A Prompt 11 controlled download + bounded extraction receipts.
    # Additive CREATE TABLE only. Hard CHECKs enforce the content-safety invariants
    # at the DB layer: a download receipt can NEVER record a persisted raw download
    # URL or a source file copied to the vault, and an extraction run can NEVER
    # record full source text persisted. Only redacted bounded excerpts + hashes +
    # redacted cache basenames are stored. V1-V18 untouched.
    V19_STATEMENTS: list[str] = [
        """
        CREATE TABLE IF NOT EXISTS construction_graph_download_receipts (
          receipt_id TEXT PRIMARY KEY,
          source_id TEXT NOT NULL,
          drive_id TEXT,
          drive_item_id TEXT NOT NULL,
          project_key TEXT,
          mode TEXT NOT NULL,
          download_attempted INTEGER NOT NULL DEFAULT 0,
          download_completed INTEGER NOT NULL DEFAULT 0,
          bytes_written INTEGER,
          sha256 TEXT,
          cache_path_redacted TEXT,
          cache_deleted_after_parse INTEGER NOT NULL DEFAULT 0,
          status TEXT NOT NULL,
          error_redacted TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_download_url_persisted INTEGER NOT NULL DEFAULT 0
            CHECK(raw_download_url_persisted = 0),
          source_file_copied_to_vault INTEGER NOT NULL DEFAULT 0
            CHECK(source_file_copied_to_vault = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS construction_file_extraction_runs (
          extraction_id TEXT PRIMARY KEY,
          source_id TEXT NOT NULL,
          drive_id TEXT,
          drive_item_id TEXT NOT NULL,
          project_key TEXT,
          parser_name TEXT NOT NULL,
          parser_version TEXT NOT NULL,
          content_hash TEXT,
          extraction_status TEXT NOT NULL,
          text_excerpt_redacted TEXT,
          char_count INTEGER NOT NULL DEFAULT 0,
          full_text_persisted INTEGER NOT NULL DEFAULT 0
            CHECK(full_text_persisted = 0),
          review_required INTEGER NOT NULL DEFAULT 0,
          error_redacted TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_construction_graph_download_receipts_item
          ON construction_graph_download_receipts(source_id, drive_item_id);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_construction_file_extraction_runs_item
          ON construction_file_extraction_runs(source_id, drive_item_id);
        """,
    ]

    # v20 Phase 07A Prompt 01 — data quality, canonical source-record map,
    # relationship resolution queue, project coverage mart, and gate results.
    # Additive only; V1-V19 tables untouched. All tables include the Phase 07A
    # guardrail CHECKs (raw_body_persisted=0, external_writeback_performed=0,
    # and full_text_persisted=0 where applicable). Source: package
    # 05_SCHEMA_AND_DATA_MODEL.md + resources/sql/phase_07a_data_quality_schema_proposal.sql.
    V20_STATEMENTS: list[str] = [
        """
        CREATE TABLE IF NOT EXISTS construction_data_quality_runs (
          run_id TEXT PRIMARY KEY,
          phase TEXT NOT NULL,
          started_utc TEXT NOT NULL,
          completed_utc TEXT,
          status TEXT NOT NULL,
          repo_sha TEXT,
          schema_version INTEGER,
          summary_json TEXT,
          raw_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS construction_table_lifecycle_registry (
          table_name TEXT PRIMARY KEY,
          table_family TEXT NOT NULL,
          lifecycle_status TEXT NOT NULL,
          expected_population_status TEXT NOT NULL,
          phase_owner TEXT,
          blocking_for_phase TEXT,
          notes_redacted TEXT,
          last_audited_run_id TEXT,
          updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS source_system_record_map (
          canonical_record_id TEXT PRIMARY KEY,
          project_key TEXT,
          project_number TEXT,
          source_system TEXT NOT NULL,
          source_table TEXT NOT NULL,
          source_primary_key TEXT NOT NULL,
          record_type TEXT,
          record_status TEXT,
          title_redacted TEXT,
          source_url_redacted TEXT,
          first_seen_utc TEXT,
          last_seen_utc TEXT,
          source_updated_utc TEXT,
          confidence_class TEXT NOT NULL,
          review_required INTEGER NOT NULL DEFAULT 0,
          mapping_signals_json TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_persisted = 0),
          full_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(full_text_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          UNIQUE(source_system, source_table, source_primary_key)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS relationship_resolution_queue (
          relationship_id TEXT PRIMARY KEY,
          from_canonical_record_id TEXT,
          to_canonical_record_id TEXT,
          from_source_system TEXT NOT NULL,
          to_source_system TEXT,
          relationship_type TEXT NOT NULL,
          relationship_status TEXT NOT NULL,
          confidence_class TEXT NOT NULL,
          confidence REAL,
          evidence_redacted TEXT,
          review_required INTEGER NOT NULL DEFAULT 0,
          promotion_status TEXT NOT NULL DEFAULT 'not_promoted',
          rejection_reason TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_persisted = 0),
          full_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(full_text_persisted = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS project_source_coverage_mart (
          coverage_id TEXT PRIMARY KEY,
          run_id TEXT NOT NULL,
          project_key TEXT NOT NULL,
          project_number TEXT,
          source_domain TEXT NOT NULL,
          record_count INTEGER NOT NULL DEFAULT 0,
          mapped_count INTEGER NOT NULL DEFAULT 0,
          unmapped_count INTEGER NOT NULL DEFAULT 0,
          relationship_count INTEGER NOT NULL DEFAULT 0,
          orphan_count INTEGER NOT NULL DEFAULT 0,
          quality_status TEXT NOT NULL,
          blocking_reasons_json TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS data_quality_gate_results (
          gate_result_id TEXT PRIMARY KEY,
          run_id TEXT NOT NULL,
          gate_name TEXT NOT NULL,
          gate_status TEXT NOT NULL,
          threshold_json TEXT,
          observed_json TEXT,
          blocking INTEGER NOT NULL DEFAULT 0,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_source_record_map_project_system
          ON source_system_record_map(project_key, source_system);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_source_record_map_source_key
          ON source_system_record_map(source_system, source_table, source_primary_key);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_source_record_map_type_status
          ON source_system_record_map(record_type, record_status);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_relationship_resolution_status_confidence
          ON relationship_resolution_queue(relationship_status, confidence_class);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_relationship_resolution_from
          ON relationship_resolution_queue(from_canonical_record_id);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_relationship_resolution_to
          ON relationship_resolution_queue(to_canonical_record_id);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_project_source_coverage_project_domain
          ON project_source_coverage_mart(project_key, source_domain);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_data_quality_gate_results_run_status
          ON data_quality_gate_results(run_id, gate_status, blocking);
        """,
    ]

    # v21 Phase 07A Prompt 05 — agent-ready query marts (additive only).
    # Three new materialised read models + supporting indexes.
    # V1-V20 untouched. Source of truth for DDL shape: package
    # 09_AGENT_READY... + 05_SCHEMA... + Prompt 05 plan.
    V21_STATEMENTS: list[str] = [
        """
        CREATE TABLE IF NOT EXISTS source_record_summary_mart (
          summary_id TEXT PRIMARY KEY,
          run_id TEXT NOT NULL,
          project_key TEXT NOT NULL,
          source_system TEXT NOT NULL,
          source_table TEXT NOT NULL,
          record_count INTEGER NOT NULL DEFAULT 0,
          mapped_count INTEGER NOT NULL DEFAULT 0,
          unmapped_count INTEGER NOT NULL DEFAULT 0,
          review_required_count INTEGER NOT NULL DEFAULT 0,
          stale_count INTEGER NOT NULL DEFAULT 0,
          quality_status TEXT NOT NULL,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_source_record_summary_project_system
          ON source_record_summary_mart(project_key, source_system);
        """,
        """
        CREATE TABLE IF NOT EXISTS relationship_quality_mart (
          quality_id TEXT PRIMARY KEY,
          run_id TEXT NOT NULL,
          project_key TEXT,
          relationship_type TEXT NOT NULL,
          confidence_class TEXT NOT NULL,
          relationship_status TEXT NOT NULL,
          total_count INTEGER NOT NULL DEFAULT 0,
          review_required_count INTEGER NOT NULL DEFAULT 0,
          orphan_count INTEGER NOT NULL DEFAULT 0,
          quality_status TEXT NOT NULL,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_relationship_quality_project_status
          ON relationship_quality_mart(project_key, relationship_status);
        """,
        """
        CREATE TABLE IF NOT EXISTS cross_domain_context_readiness_mart (
          readiness_id TEXT PRIMARY KEY,
          run_id TEXT NOT NULL,
          project_key TEXT NOT NULL,
          meeting_prep_ready INTEGER NOT NULL DEFAULT 0,
          risk_digest_ready INTEGER NOT NULL DEFAULT 0,
          financial_review_ready INTEGER NOT NULL DEFAULT 0,
          blocking_reasons_json TEXT,
          overall_status TEXT NOT NULL,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_readiness_project
          ON cross_domain_context_readiness_mart(project_key);
        """,
    ]

    # v22 Phase 07B Prompt 01 — close the V21 mart raw-body guardrail gap. The five
    # V21 marts were created without the standard CHECK(raw_body_persisted = 0) that
    # the V20 tables carry. v22 adds the column + CHECK additively via ALTER TABLE
    # (SQLite rewrites sqlite_master.sql so the no-writeback prover detects it).
    V22_MART_TABLES: list[str] = [
        "project_source_coverage_mart",
        "data_quality_gate_results",
        "source_record_summary_mart",
        "relationship_quality_mart",
        "cross_domain_context_readiness_mart",
    ]

    # v23 Phase 07B Prompt 02 — calendar + email-thread intelligence foundation.
    # Additive only (CREATE TABLE/INDEX IF NOT EXISTS); V1-V22 untouched. Every
    # event/candidate/run table carries the standard no-raw-body / no-full-text /
    # no-raw-prompt / no-raw-response / no-external-writeback CHECK guardrails, and
    # the calendar source registry is immutable read-only (CHECK(read_only = 1)).
    # Subjects/organizers/locations/attendees/web links/iCal UIDs/thread keys are
    # stored hashed or redacted only.
    V23_STATEMENTS: list[str] = [
        """
        CREATE TABLE IF NOT EXISTS calendar_source_locations (
          source_id TEXT PRIMARY KEY,
          mailbox_owner_hash TEXT NOT NULL,
          mailbox_owner_domain TEXT,
          calendar_id_hash TEXT,
          calendar_role TEXT NOT NULL DEFAULT 'primary',
          calendar_display_name_hash TEXT,
          enabled INTEGER NOT NULL DEFAULT 1,
          read_only INTEGER NOT NULL DEFAULT 1 CHECK(read_only = 1),
          lookback_days INTEGER NOT NULL DEFAULT 14,
          lookahead_days INTEGER NOT NULL DEFAULT 30,
          max_items_per_run INTEGER NOT NULL DEFAULT 250,
          policy_id TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS calendar_sync_state (
          source_id TEXT PRIMARY KEY REFERENCES calendar_source_locations(source_id),
          last_successful_sync_utc TEXT,
          last_attempted_sync_utc TEXT,
          window_start_utc TEXT,
          window_end_utc TEXT,
          last_event_count INTEGER NOT NULL DEFAULT 0,
          sync_status TEXT NOT NULL DEFAULT 'pending',
          error_redacted TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS calendar_crawl_runs (
          run_id TEXT PRIMARY KEY,
          source_id TEXT NOT NULL REFERENCES calendar_source_locations(source_id),
          mode TEXT NOT NULL,
          started_at_utc TEXT NOT NULL,
          completed_at_utc TEXT,
          window_start_utc TEXT,
          window_end_utc TEXT,
          events_seen INTEGER NOT NULL DEFAULT 0,
          events_indexed INTEGER NOT NULL DEFAULT 0,
          events_private INTEGER NOT NULL DEFAULT 0,
          events_cancelled INTEGER NOT NULL DEFAULT 0,
          events_review_required INTEGER NOT NULL DEFAULT 0,
          status TEXT NOT NULL,
          error_redacted TEXT,
          raw_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_persisted = 0),
          full_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(full_text_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS calendar_event_index (
          event_index_id TEXT PRIMARY KEY,
          source_id TEXT NOT NULL REFERENCES calendar_source_locations(source_id),
          graph_event_id_hash TEXT NOT NULL,
          ical_uid_hash TEXT,
          series_master_id_hash TEXT,
          web_link_hash TEXT,
          subject_hash TEXT,
          subject_redacted TEXT,
          subject_token_hashes_json TEXT,
          organizer_hash TEXT,
          organizer_domain TEXT,
          location_hash TEXT,
          location_redacted TEXT,
          start_datetime_utc TEXT NOT NULL,
          end_datetime_utc TEXT NOT NULL,
          timezone TEXT,
          is_cancelled INTEGER NOT NULL DEFAULT 0,
          is_private INTEGER NOT NULL DEFAULT 0,
          is_online_meeting INTEGER NOT NULL DEFAULT 0,
          online_meeting_provider TEXT,
          has_attachments INTEGER NOT NULL DEFAULT 0,
          project_key TEXT,
          project_match_method TEXT,
          project_match_confidence REAL,
          review_required INTEGER NOT NULL DEFAULT 0,
          review_reasons_json TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_persisted = 0),
          full_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(full_text_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          UNIQUE(source_id, graph_event_id_hash)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS calendar_event_attendees (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          event_index_id TEXT NOT NULL REFERENCES calendar_event_index(event_index_id),
          attendee_hash TEXT NOT NULL,
          attendee_domain TEXT,
          attendee_role TEXT,
          response_status TEXT,
          review_required INTEGER NOT NULL DEFAULT 0,
          UNIQUE(event_index_id, attendee_hash)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS calendar_project_match_candidates (
          candidate_id TEXT PRIMARY KEY,
          event_index_id TEXT NOT NULL REFERENCES calendar_event_index(event_index_id),
          project_key TEXT NOT NULL,
          candidate_type TEXT NOT NULL,
          signals_json TEXT NOT NULL,
          confidence REAL NOT NULL,
          confidence_class TEXT NOT NULL,
          deterministic INTEGER NOT NULL DEFAULT 0,
          model_proposed INTEGER NOT NULL DEFAULT 0,
          review_required INTEGER NOT NULL DEFAULT 1,
          promotion_status TEXT NOT NULL DEFAULT 'candidate',
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS meeting_email_relationship_candidates (
          candidate_id TEXT PRIMARY KEY,
          event_index_id TEXT NOT NULL REFERENCES calendar_event_index(event_index_id),
          thread_key_hash TEXT NOT NULL,
          project_key TEXT,
          candidate_type TEXT NOT NULL,
          time_window_signal TEXT,
          participant_signal TEXT,
          subject_topic_signal TEXT,
          source_reference_json TEXT NOT NULL,
          confidence REAL NOT NULL,
          confidence_class TEXT NOT NULL,
          deterministic INTEGER NOT NULL DEFAULT 0,
          model_proposed INTEGER NOT NULL DEFAULT 0,
          review_required INTEGER NOT NULL DEFAULT 1,
          promotion_status TEXT NOT NULL DEFAULT 'candidate',
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS email_thread_summary_materialization_runs (
          run_id TEXT PRIMARY KEY,
          mode TEXT NOT NULL,
          started_at_utc TEXT NOT NULL,
          completed_at_utc TEXT,
          project_key TEXT,
          threads_considered INTEGER NOT NULL DEFAULT 0,
          threads_summarized INTEGER NOT NULL DEFAULT 0,
          review_required_count INTEGER NOT NULL DEFAULT 0,
          status TEXT NOT NULL,
          error_redacted TEXT,
          raw_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_calendar_event_index_source_start
          ON calendar_event_index(source_id, start_datetime_utc);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_calendar_event_index_project_start
          ON calendar_event_index(project_key, start_datetime_utc);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_calendar_event_index_review
          ON calendar_event_index(review_required);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_calendar_project_candidates_project
          ON calendar_project_match_candidates(project_key, confidence_class);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_meeting_email_candidates_project_event
          ON meeting_email_relationship_candidates(project_key, event_index_id);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_meeting_email_candidates_review
          ON meeting_email_relationship_candidates(review_required);
        """,
    ]

    # v24 Phase 07C Prompt 02 — document intelligence schema additions. Additive only:
    # the existing (empty) V5 construction_document_cards table is *extended* via
    # ALTER ADD COLUMN (it cannot be greenfield-recreated — CREATE IF NOT EXISTS would
    # no-op), and five document satellite tables are created fresh. document_card_id is
    # the canonical 07C card identity (UNIQUE INDEX); the legacy card_id PRIMARY KEY is
    # retained untouched. Every document-intelligence column/table carries the hard
    # no-raw-document-text / no-raw-payload / no-signed-url / no-download-url /
    # no-source-file-copy / no-external-writeback CHECK(... = 0) guardrails. Only hashed
    # / redacted / bounded fields are stored — never raw text, full paths, or URLs.
    # (column_name, full ALTER-COLUMN DDL). NOT NULL columns carry a constant DEFAULT
    # (SQLite ALTER requirement); hash/id columns are nullable TEXT on the empty table
    # and the materializer (Prompt 04) enforces presence per the contract required_fields.
    V24_CARD_COLUMNS: list[tuple[str, str]] = [
        ("document_card_id", "document_card_id TEXT"),
        ("drive_id_hash", "drive_id_hash TEXT"),
        ("drive_item_id_hash", "drive_item_id_hash TEXT"),
        ("project_number_hash", "project_number_hash TEXT"),
        ("title_hash", "title_hash TEXT"),
        ("title_redacted", "title_redacted TEXT"),
        ("file_extension", "file_extension TEXT"),
        ("mime_type", "mime_type TEXT"),
        (
            "size_class",
            "size_class TEXT NOT NULL DEFAULT 'unknown' "
            "CHECK(size_class IN ('small','medium','large','oversize','unknown'))",
        ),
        ("source_path_hash", "source_path_hash TEXT"),
        ("source_path_token_hashes_json", "source_path_token_hashes_json TEXT"),
        ("last_modified_datetime", "last_modified_datetime TEXT"),
        ("source_reference_json", "source_reference_json TEXT"),
        (
            "review_status",
            "review_status TEXT NOT NULL DEFAULT 'pending' "
            "CHECK(review_status IN ('not_required','pending','approved','rejected','blocked'))",
        ),
        ("review_required", "review_required INTEGER NOT NULL DEFAULT 0"),
        ("review_reasons_json", "review_reasons_json TEXT"),
        (
            "extraction_eligibility",
            "extraction_eligibility TEXT NOT NULL DEFAULT 'not_evaluated' "
            "CHECK(extraction_eligibility IN "
            "('not_evaluated','metadata_only','eligible','manual_approval_required','blocked','skipped'))",
        ),
        (
            "confidence_class",
            "confidence_class TEXT NOT NULL DEFAULT 'unknown' "
            "CHECK(confidence_class IN "
            "('deterministic','high_heuristic','moderate_heuristic','weak_heuristic','model_proposed','unknown'))",
        ),
        ("guardrail_flags_json", "guardrail_flags_json TEXT"),
        (
            "raw_document_text_persisted",
            "raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 "
            "CHECK(raw_document_text_persisted = 0)",
        ),
        (
            "raw_payload_persisted",
            "raw_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_payload_persisted = 0)",
        ),
        (
            "signed_url_persisted",
            "signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0)",
        ),
        (
            "download_url_persisted",
            "download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0)",
        ),
        (
            "source_file_copied_to_vault",
            "source_file_copied_to_vault INTEGER NOT NULL DEFAULT 0 "
            "CHECK(source_file_copied_to_vault = 0)",
        ),
        (
            "external_writeback_performed",
            "external_writeback_performed INTEGER NOT NULL DEFAULT 0 "
            "CHECK(external_writeback_performed = 0)",
        ),
    ]

    V24_STATEMENTS: list[str] = [
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_document_cards_document_card_id
          ON construction_document_cards(document_card_id);
        """,
        """
        CREATE TABLE IF NOT EXISTS construction_document_classification_candidates (
          candidate_id TEXT PRIMARY KEY,
          document_card_id TEXT NOT NULL REFERENCES construction_document_cards(document_card_id),
          document_type TEXT NOT NULL,
          classifier_name TEXT NOT NULL,
          signal_class TEXT NOT NULL CHECK(signal_class IN ('deterministic','heuristic','model_proposed')),
          confidence REAL NOT NULL,
          confidence_class TEXT NOT NULL,
          signals_json TEXT,
          review_required INTEGER NOT NULL DEFAULT 0,
          promotion_status TEXT NOT NULL DEFAULT 'candidate',
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS construction_document_project_match_candidates (
          candidate_id TEXT PRIMARY KEY,
          document_card_id TEXT NOT NULL REFERENCES construction_document_cards(document_card_id),
          project_key TEXT NOT NULL,
          candidate_type TEXT NOT NULL,
          confidence REAL NOT NULL,
          confidence_class TEXT NOT NULL,
          deterministic INTEGER NOT NULL DEFAULT 0,
          model_proposed INTEGER NOT NULL DEFAULT 0,
          review_required INTEGER NOT NULL DEFAULT 1,
          promotion_status TEXT NOT NULL DEFAULT 'candidate',
          signals_json TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS construction_document_relationship_candidates (
          candidate_id TEXT PRIMARY KEY,
          document_card_id TEXT NOT NULL REFERENCES construction_document_cards(document_card_id),
          target_system TEXT NOT NULL,
          target_record_type TEXT NOT NULL,
          target_record_key_hash TEXT NOT NULL,
          relationship_type TEXT NOT NULL,
          candidate_type TEXT NOT NULL CHECK(candidate_type IN ('deterministic','heuristic','model_proposed')),
          confidence REAL NOT NULL,
          confidence_class TEXT NOT NULL,
          source_reference_json TEXT,
          signals_json TEXT,
          review_required INTEGER NOT NULL DEFAULT 1,
          promotion_status TEXT NOT NULL DEFAULT 'candidate',
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS construction_document_intelligence_previews (
          preview_id TEXT PRIMARY KEY,
          project_key TEXT,
          document_card_id TEXT REFERENCES construction_document_cards(document_card_id),
          preview_kind TEXT NOT NULL,
          preview_redacted TEXT,
          warnings_json TEXT,
          confidence_class TEXT NOT NULL,
          review_required INTEGER NOT NULL DEFAULT 0,
          generated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS construction_document_projection_runs (
          run_id TEXT PRIMARY KEY,
          mode TEXT NOT NULL,
          cards_considered INTEGER NOT NULL DEFAULT 0,
          cards_written INTEGER NOT NULL DEFAULT 0,
          review_required_count INTEGER NOT NULL DEFAULT 0,
          status TEXT NOT NULL,
          error_redacted TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_document_cards_project_type
          ON construction_document_cards(project_key, document_type, confidence_class);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_document_cards_source
          ON construction_document_cards(source_id, drive_item_id_hash);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_document_cards_review
          ON construction_document_cards(review_required, review_status);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_document_relationship_candidates_target
          ON construction_document_relationship_candidates(target_system, target_record_type, target_record_key_hash);
        """,
    ]

    # v25 Phase 07D Prompt 02 — cross-source relationship + meeting-prep substrate.
    # Additive-only (CREATE IF NOT EXISTS): ten local read-model tables that ship empty
    # and are populated by later 07D prompts (relationship normalization, meeting-prep
    # briefs, issue history, risk digest, aging/exposure, Obsidian projections, 07D
    # gates/validation). Every table carries the eight no-raw / no-writeback guard
    # columns (CHECK(... = 0)) from 05_SCHEMA_AND_MIGRATION_PLAN; deterministic-hash PKs
    # + UNIQUE edge keys make apply() idempotent and dedup-safe. V1-V24 untouched.
    V25_STATEMENTS: list[str] = [
        """
        CREATE TABLE IF NOT EXISTS cross_source_relationship_candidates (
          candidate_id TEXT PRIMARY KEY,
          project_key TEXT,
          source_family TEXT NOT NULL,
          source_record_type TEXT NOT NULL,
          source_record_ref TEXT NOT NULL,
          target_family TEXT NOT NULL,
          target_record_type TEXT NOT NULL,
          target_record_ref TEXT NOT NULL,
          relationship_type TEXT NOT NULL,
          confidence_score REAL NOT NULL,
          confidence_class TEXT NOT NULL CHECK(confidence_class IN ('deterministic','strong_heuristic','weak_heuristic','model_proposed','human_promoted','rejected','stale_or_unresolved')),
          deterministic INTEGER NOT NULL DEFAULT 0,
          model_proposed INTEGER NOT NULL DEFAULT 0,
          sensitive_high_impact INTEGER NOT NULL DEFAULT 0,
          review_required INTEGER NOT NULL DEFAULT 1,
          promotion_status TEXT NOT NULL DEFAULT 'candidate' CHECK(promotion_status IN ('candidate','promoted','rejected','stale','needs_review')),
          signals_json TEXT,
          source_reference_json TEXT NOT NULL,
          evidence_trail_id TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          UNIQUE(source_family, source_record_ref, target_family, target_record_ref, relationship_type)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_cross_source_relationship_candidates_project
          ON cross_source_relationship_candidates(project_key, confidence_class, review_required);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_cross_source_relationship_candidates_source
          ON cross_source_relationship_candidates(source_family, source_record_type);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_cross_source_relationship_candidates_target
          ON cross_source_relationship_candidates(target_family, target_record_type);
        """,
        """
        CREATE TABLE IF NOT EXISTS cross_source_relationships (
          relationship_id TEXT PRIMARY KEY,
          candidate_id TEXT REFERENCES cross_source_relationship_candidates(candidate_id),
          project_key TEXT,
          source_family TEXT NOT NULL,
          source_record_type TEXT NOT NULL,
          source_record_ref TEXT NOT NULL,
          target_family TEXT NOT NULL,
          target_record_type TEXT NOT NULL,
          target_record_ref TEXT NOT NULL,
          relationship_type TEXT NOT NULL,
          confidence_class TEXT NOT NULL CHECK(confidence_class IN ('deterministic','strong_heuristic','weak_heuristic','model_proposed','human_promoted','rejected','stale_or_unresolved')),
          promotion_status TEXT NOT NULL DEFAULT 'promoted' CHECK(promotion_status IN ('promoted','human_promoted','rejected','stale')),
          promoted_by TEXT NOT NULL DEFAULT 'deterministic' CHECK(promoted_by IN ('deterministic','human')),
          review_required INTEGER NOT NULL DEFAULT 0,
          signals_json TEXT,
          source_reference_json TEXT NOT NULL,
          evidence_trail_id TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          UNIQUE(source_family, source_record_ref, target_family, target_record_ref, relationship_type)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_cross_source_relationships_project
          ON cross_source_relationships(project_key, confidence_class, review_required);
        """,
        """
        CREATE TABLE IF NOT EXISTS source_evidence_trails (
          evidence_trail_id TEXT PRIMARY KEY,
          project_key TEXT,
          evidence_kind TEXT NOT NULL,
          relationship_candidate_id TEXT,
          source_refs_json TEXT NOT NULL,
          confidence_class TEXT NOT NULL,
          review_required INTEGER NOT NULL DEFAULT 0,
          stale_unknown_flags_json TEXT,
          generated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_source_evidence_trails_project
          ON source_evidence_trails(project_key, confidence_class, review_required);
        """,
        """
        CREATE TABLE IF NOT EXISTS meeting_prep_brief_runs (
          brief_run_id TEXT PRIMARY KEY,
          project_key TEXT NOT NULL,
          event_index_id TEXT,
          mode TEXT NOT NULL CHECK(mode IN ('dry_run','apply')),
          lookahead_days INTEGER NOT NULL,
          status TEXT NOT NULL,
          sections_written INTEGER NOT NULL DEFAULT 0,
          review_required_count INTEGER NOT NULL DEFAULT 0,
          generated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_meeting_prep_brief_runs_project
          ON meeting_prep_brief_runs(project_key, status);
        """,
        """
        CREATE TABLE IF NOT EXISTS meeting_prep_brief_sections (
          section_id TEXT PRIMARY KEY,
          brief_run_id TEXT NOT NULL REFERENCES meeting_prep_brief_runs(brief_run_id) ON DELETE CASCADE,
          section_kind TEXT NOT NULL,
          section_redacted TEXT NOT NULL,
          evidence_trail_id TEXT,
          confidence_class TEXT NOT NULL,
          review_required INTEGER NOT NULL DEFAULT 0,
          stale_unknown_flags_json TEXT,
          generated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_meeting_prep_brief_sections_run
          ON meeting_prep_brief_sections(brief_run_id, section_kind);
        """,
        """
        CREATE TABLE IF NOT EXISTS project_issue_history_items (
          issue_family_id TEXT PRIMARY KEY,
          project_key TEXT NOT NULL,
          issue_kind TEXT,
          status TEXT NOT NULL,
          age_days INTEGER NOT NULL DEFAULT 0,
          latest_activity_utc TEXT,
          source_families_json TEXT NOT NULL,
          evidence_trail_id TEXT,
          confidence_class TEXT NOT NULL,
          review_required INTEGER NOT NULL DEFAULT 0,
          stale_unknown_flags_json TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_project_issue_history_items_project
          ON project_issue_history_items(project_key, status, review_required);
        """,
        """
        CREATE TABLE IF NOT EXISTS project_risk_digest_items (
          risk_digest_id TEXT PRIMARY KEY,
          project_key TEXT NOT NULL,
          risk_indicator_type TEXT NOT NULL,
          risk_source_class TEXT NOT NULL CHECK(risk_source_class IN ('source_stated','inferred_candidate','model_proposed','review_required')),
          summary_redacted TEXT NOT NULL,
          evidence_trail_id TEXT,
          confidence_class TEXT NOT NULL,
          review_required INTEGER NOT NULL DEFAULT 0,
          stale_unknown_flags_json TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_project_risk_digest_items_project
          ON project_risk_digest_items(project_key, risk_source_class, review_required);
        """,
        """
        CREATE TABLE IF NOT EXISTS aging_exposure_report_items (
          aging_item_id TEXT PRIMARY KEY,
          project_key TEXT NOT NULL,
          record_family TEXT NOT NULL,
          record_ref TEXT NOT NULL,
          status TEXT NOT NULL,
          age_days INTEGER NOT NULL DEFAULT 0,
          threshold_band TEXT NOT NULL,
          stale_flag INTEGER NOT NULL DEFAULT 0,
          missing_status_flag INTEGER NOT NULL DEFAULT 0,
          evidence_trail_id TEXT,
          confidence_class TEXT,
          review_required INTEGER NOT NULL DEFAULT 0,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          UNIQUE(project_key, record_family, record_ref)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_aging_exposure_report_items_project
          ON aging_exposure_report_items(project_key, threshold_band, review_required);
        """,
        """
        CREATE TABLE IF NOT EXISTS cross_source_intelligence_obsidian_runs (
          obsidian_run_id TEXT PRIMARY KEY,
          project_key TEXT,
          mode TEXT NOT NULL CHECK(mode IN ('dry_run','apply')),
          output_kind TEXT NOT NULL,
          notes_written INTEGER NOT NULL DEFAULT 0,
          review_required_count INTEGER NOT NULL DEFAULT 0,
          status TEXT NOT NULL,
          error_redacted TEXT,
          generated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS phase_07d_validation_runs (
          validation_run_id TEXT PRIMARY KEY,
          mode TEXT NOT NULL CHECK(mode IN ('dry_run','apply')),
          status TEXT NOT NULL,
          schema_version INTEGER,
          commands_json TEXT,
          passed_count INTEGER NOT NULL DEFAULT 0,
          failed_count INTEGER NOT NULL DEFAULT 0,
          error_redacted TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0)
        );
        """,
    ]

    # v26 Phase 08A Prompt 02 — local-first second-brain runtime substrate.
    # Additive-only (CREATE IF NOT EXISTS): 21 metadata/bounded-output tables that ship
    # EMPTY and are populated by later 08A prompts (config, obsidian index, retrieval,
    # query tools, chat, memory, daily brief, launchd, validation) plus the addendum
    # research -> evaluation -> synthesis -> capture pipeline (research packets,
    # evaluation runs, operator feedback, preference profiles, memory quality signals).
    # No raw email/document/calendar body, raw prompt/response, retrieved context, signed
    # /download URL, secret, or external writeback may ever be stored: each table carries
    # the relevant no-raw / no-writeback guard CHECK(... = 0) columns. Review tiers
    # (1/2/3) + reason codes and memory origin/provenance ride on the output-bearing
    # tables. Deterministic-hash PKs make apply() idempotent. V1-V25 untouched.
    V26_STATEMENTS: list[str] = [
        """
        CREATE TABLE IF NOT EXISTS second_brain_runtime_config_receipts (
          config_receipt_id TEXT PRIMARY KEY,
          mode TEXT NOT NULL CHECK(mode IN ('mock','live','disabled')),
          config_status TEXT NOT NULL,
          dependency_status_json TEXT,
          policy_version TEXT,
          generated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          retrieved_context_persisted INTEGER NOT NULL DEFAULT 0 CHECK(retrieved_context_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          arbitrary_sql_allowed INTEGER NOT NULL DEFAULT 0 CHECK(arbitrary_sql_allowed = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS obsidian_index_manifests (
          manifest_id TEXT PRIMARY KEY,
          mode TEXT NOT NULL CHECK(mode IN ('dry_run','apply')),
          vault_root_fingerprint TEXT,
          approved_roots_json TEXT NOT NULL,
          entry_count INTEGER NOT NULL DEFAULT 0,
          excluded_count INTEGER NOT NULL DEFAULT 0,
          policy_version TEXT NOT NULL,
          generated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          retrieved_context_persisted INTEGER NOT NULL DEFAULT 0 CHECK(retrieved_context_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          arbitrary_sql_allowed INTEGER NOT NULL DEFAULT 0 CHECK(arbitrary_sql_allowed = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS obsidian_index_entries (
          entry_id TEXT PRIMARY KEY,
          manifest_id TEXT NOT NULL REFERENCES obsidian_index_manifests(manifest_id) ON DELETE CASCADE,
          note_path_redacted TEXT NOT NULL,
          note_path_hash TEXT NOT NULL,
          section_marker TEXT,
          heading_redacted TEXT,
          content_hash TEXT NOT NULL,
          modified_utc TEXT,
          project_key TEXT,
          source_type TEXT,
          confidence_class TEXT,
          review_status TEXT,
          source_refs_json TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(manifest_id, note_path_hash, section_marker, content_hash)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_obsidian_index_entries_project
          ON obsidian_index_entries(project_key, source_type, review_status);
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_obsidian_index_entries_hash
          ON obsidian_index_entries(note_path_hash, content_hash);
        """,
        """
        CREATE TABLE IF NOT EXISTS retrieval_query_receipts (
          retrieval_receipt_id TEXT PRIMARY KEY,
          mode TEXT NOT NULL CHECK(mode IN ('mock','live','dry_run')),
          query_hash TEXT NOT NULL,
          project_key TEXT,
          tool_names_json TEXT,
          research_packet_id TEXT,
          source_ref_count INTEGER NOT NULL DEFAULT 0,
          review_required_count INTEGER NOT NULL DEFAULT 0,
          stale_unknown_count INTEGER NOT NULL DEFAULT 0,
          conflict_count INTEGER NOT NULL DEFAULT 0,
          context_char_count INTEGER NOT NULL DEFAULT 0,
          truncated INTEGER NOT NULL DEFAULT 0,
          answer_generated INTEGER NOT NULL DEFAULT 0,
          context_quality_class TEXT,
          degradation_mode TEXT,
          review_tier INTEGER CHECK(review_tier IS NULL OR review_tier IN (1,2,3)),
          review_tier_reason_code TEXT,
          advisory_classification TEXT NOT NULL DEFAULT 'advisory' CHECK(advisory_classification IN ('advisory','actionable')),
          policy_version TEXT NOT NULL,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          retrieved_context_persisted INTEGER NOT NULL DEFAULT 0 CHECK(retrieved_context_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          arbitrary_sql_allowed INTEGER NOT NULL DEFAULT 0 CHECK(arbitrary_sql_allowed = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_retrieval_query_receipts_project
          ON retrieval_query_receipts(project_key, created_utc);
        """,
        """
        CREATE TABLE IF NOT EXISTS retrieval_context_refs (
          context_ref_id TEXT PRIMARY KEY,
          retrieval_receipt_id TEXT NOT NULL REFERENCES retrieval_query_receipts(retrieval_receipt_id) ON DELETE CASCADE,
          source_family TEXT NOT NULL,
          source_ref TEXT NOT NULL,
          evidence_trail_id TEXT,
          confidence_class TEXT,
          review_required INTEGER NOT NULL DEFAULT 0,
          stale_unknown INTEGER NOT NULL DEFAULT 0,
          included INTEGER NOT NULL DEFAULT 1,
          exclusion_reason TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS query_tool_receipts (
          tool_receipt_id TEXT PRIMARY KEY,
          retrieval_receipt_id TEXT,
          tool_name TEXT NOT NULL,
          project_key TEXT,
          row_count INTEGER NOT NULL DEFAULT 0,
          char_count INTEGER NOT NULL DEFAULT 0,
          truncated INTEGER NOT NULL DEFAULT 0,
          status TEXT NOT NULL,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          arbitrary_sql_allowed INTEGER NOT NULL DEFAULT 0 CHECK(arbitrary_sql_allowed = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_query_tool_receipts_tool
          ON query_tool_receipts(tool_name, project_key, status);
        """,
        """
        CREATE TABLE IF NOT EXISTS interactive_chat_sessions (
          session_id TEXT PRIMARY KEY,
          mode TEXT NOT NULL CHECK(mode IN ('mock','live')),
          project_key TEXT,
          status TEXT NOT NULL,
          started_utc TEXT NOT NULL,
          ended_utc TEXT,
          bounded_summary_redacted TEXT,
          clear_requested INTEGER NOT NULL DEFAULT 0,
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          retrieved_context_persisted INTEGER NOT NULL DEFAULT 0 CHECK(retrieved_context_persisted = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS interactive_chat_message_receipts (
          message_receipt_id TEXT PRIMARY KEY,
          session_id TEXT NOT NULL REFERENCES interactive_chat_sessions(session_id) ON DELETE CASCADE,
          turn_index INTEGER NOT NULL,
          user_message_hash TEXT NOT NULL,
          model_response_hash TEXT,
          retrieval_receipt_id TEXT,
          memory_candidate_count INTEGER NOT NULL DEFAULT 0,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS long_term_memory_items (
          memory_id TEXT PRIMARY KEY,
          memory_type TEXT NOT NULL,
          statement_redacted TEXT NOT NULL,
          project_key TEXT,
          entity_key TEXT,
          origin_id TEXT,
          provenance_class TEXT,
          confidence_class TEXT NOT NULL,
          review_status TEXT NOT NULL CHECK(review_status IN ('accepted','pending_review','rejected','superseded')),
          sensitivity_class TEXT NOT NULL DEFAULT 'normal',
          supersedes_memory_id TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          retrieved_context_persisted INTEGER NOT NULL DEFAULT 0 CHECK(retrieved_context_persisted = 0)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_long_term_memory_items_project
          ON long_term_memory_items(project_key, review_status);
        """,
        """
        CREATE TABLE IF NOT EXISTS long_term_memory_source_refs (
          memory_source_ref_id TEXT PRIMARY KEY,
          memory_id TEXT NOT NULL REFERENCES long_term_memory_items(memory_id) ON DELETE CASCADE,
          source_family TEXT NOT NULL,
          source_ref TEXT NOT NULL,
          evidence_trail_id TEXT,
          confidence_class TEXT,
          review_required INTEGER NOT NULL DEFAULT 0
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_long_term_memory_source_refs_memory
          ON long_term_memory_source_refs(memory_id);
        """,
        """
        CREATE TABLE IF NOT EXISTS long_term_memory_quality_signals (
          signal_id TEXT PRIMARY KEY,
          memory_id TEXT NOT NULL REFERENCES long_term_memory_items(memory_id) ON DELETE CASCADE,
          signal_type TEXT NOT NULL CHECK(signal_type IN ('origin','provenance','quality','freshness','conflict','feedback')),
          origin_id TEXT,
          provenance_class TEXT,
          quality_score REAL,
          freshness_class TEXT,
          conflict_flag INTEGER NOT NULL DEFAULT 0,
          feedback_id TEXT,
          review_required INTEGER NOT NULL DEFAULT 0,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_long_term_memory_quality_signals_memory
          ON long_term_memory_quality_signals(memory_id, signal_type);
        """,
        """
        CREATE TABLE IF NOT EXISTS memory_update_candidates (
          candidate_id TEXT PRIMARY KEY,
          proposed_memory_type TEXT NOT NULL,
          statement_redacted TEXT NOT NULL,
          project_key TEXT,
          origin_id TEXT,
          provenance_class TEXT,
          confidence_class TEXT NOT NULL,
          review_required INTEGER NOT NULL DEFAULT 1,
          review_tier INTEGER CHECK(review_tier IS NULL OR review_tier IN (1,2,3)),
          review_tier_reason_code TEXT,
          sensitivity_class TEXT NOT NULL DEFAULT 'normal',
          source_refs_json TEXT NOT NULL,
          status TEXT NOT NULL CHECK(status IN ('proposed','accepted','rejected','superseded')),
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_memory_update_candidates_review
          ON memory_update_candidates(status, review_required);
        """,
        """
        CREATE TABLE IF NOT EXISTS memory_update_reviews (
          review_id TEXT PRIMARY KEY,
          candidate_id TEXT NOT NULL REFERENCES memory_update_candidates(candidate_id) ON DELETE CASCADE,
          decision TEXT NOT NULL CHECK(decision IN ('accepted','rejected','superseded','deferred')),
          reviewer_ref TEXT NOT NULL DEFAULT 'operator',
          decision_reason_redacted TEXT,
          reviewed_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_memory_update_reviews_candidate
          ON memory_update_reviews(candidate_id, decision);
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_research_packets (
          packet_id TEXT PRIMARY KEY,
          mode TEXT NOT NULL CHECK(mode IN ('mock','live','dry_run')),
          topic_hash TEXT NOT NULL,
          project_key TEXT,
          retrieval_receipt_id TEXT,
          source_ref_count INTEGER NOT NULL DEFAULT 0,
          review_required_count INTEGER NOT NULL DEFAULT 0,
          stale_unknown_count INTEGER NOT NULL DEFAULT 0,
          conflict_count INTEGER NOT NULL DEFAULT 0,
          coverage_warnings_json TEXT,
          context_quality_class TEXT,
          degradation_mode TEXT,
          confidence_class TEXT,
          review_tier INTEGER NOT NULL DEFAULT 3 CHECK(review_tier IN (1,2,3)),
          review_tier_reason_code TEXT,
          review_status TEXT NOT NULL DEFAULT 'pending_review' CHECK(review_status IN ('accepted','pending_review','rejected','superseded')),
          advisory_classification TEXT NOT NULL DEFAULT 'advisory' CHECK(advisory_classification IN ('advisory','actionable')),
          summary_redacted TEXT,
          status TEXT NOT NULL,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          retrieved_context_persisted INTEGER NOT NULL DEFAULT 0 CHECK(retrieved_context_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          arbitrary_sql_allowed INTEGER NOT NULL DEFAULT 0 CHECK(arbitrary_sql_allowed = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_second_brain_research_packets_project
          ON second_brain_research_packets(project_key, status, review_tier);
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_evaluation_runs (
          evaluation_run_id TEXT PRIMARY KEY,
          mode TEXT NOT NULL CHECK(mode IN ('mock','live','dry_run')),
          target_kind TEXT NOT NULL,
          target_id TEXT NOT NULL,
          research_packet_id TEXT,
          checklist_json TEXT,
          checklist_total INTEGER NOT NULL DEFAULT 0,
          checklist_passed INTEGER NOT NULL DEFAULT 0,
          score REAL,
          passed INTEGER NOT NULL DEFAULT 0,
          confidence_class TEXT,
          review_tier INTEGER CHECK(review_tier IS NULL OR review_tier IN (1,2,3)),
          review_tier_reason_code TEXT,
          review_status TEXT NOT NULL DEFAULT 'pending_review' CHECK(review_status IN ('accepted','pending_review','rejected','superseded')),
          degradation_mode TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          retrieved_context_persisted INTEGER NOT NULL DEFAULT 0 CHECK(retrieved_context_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_second_brain_evaluation_runs_target
          ON second_brain_evaluation_runs(target_kind, target_id);
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_operator_feedback (
          feedback_id TEXT PRIMARY KEY,
          target_kind TEXT NOT NULL,
          target_id TEXT NOT NULL,
          origin_id TEXT,
          feedback_class TEXT NOT NULL CHECK(feedback_class IN ('accept','reject','correct','prefer','flag_review','defer')),
          rating INTEGER,
          reason_redacted TEXT,
          review_tier INTEGER CHECK(review_tier IS NULL OR review_tier IN (1,2,3)),
          review_tier_reason_code TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_second_brain_operator_feedback_target
          ON second_brain_operator_feedback(target_kind, target_id);
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_operator_preference_profiles (
          preference_id TEXT PRIMARY KEY,
          scope TEXT NOT NULL CHECK(scope IN ('global','project','entity')),
          scope_key TEXT,
          preference_key TEXT NOT NULL,
          preference_value_redacted TEXT,
          confidence_class TEXT,
          signal_count INTEGER NOT NULL DEFAULT 0,
          source_feedback_refs_json TEXT,
          review_status TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          UNIQUE(scope, scope_key, preference_key)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS daily_brief_runs (
          brief_run_id TEXT PRIMARY KEY,
          brief_date TEXT NOT NULL,
          mode TEXT NOT NULL CHECK(mode IN ('dry_run','apply')),
          status TEXT NOT NULL,
          project_count INTEGER NOT NULL DEFAULT 0,
          source_ref_count INTEGER NOT NULL DEFAULT 0,
          review_required_count INTEGER NOT NULL DEFAULT 0,
          stale_unknown_count INTEGER NOT NULL DEFAULT 0,
          research_packet_id TEXT,
          evaluation_run_id TEXT,
          review_tier INTEGER CHECK(review_tier IS NULL OR review_tier IN (1,2,3)),
          review_tier_reason_code TEXT,
          degradation_mode TEXT,
          output_path_redacted TEXT,
          output_path_hash TEXT,
          generated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          retrieved_context_persisted INTEGER NOT NULL DEFAULT 0 CHECK(retrieved_context_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_daily_brief_runs_date
          ON daily_brief_runs(brief_date, status);
        """,
        """
        CREATE TABLE IF NOT EXISTS daily_brief_source_refs (
          daily_brief_source_ref_id TEXT PRIMARY KEY,
          brief_run_id TEXT NOT NULL REFERENCES daily_brief_runs(brief_run_id) ON DELETE CASCADE,
          source_family TEXT NOT NULL,
          source_ref TEXT NOT NULL,
          evidence_trail_id TEXT,
          confidence_class TEXT,
          review_required INTEGER NOT NULL DEFAULT 0,
          stale_unknown INTEGER NOT NULL DEFAULT 0
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS launchd_schedule_previews (
          launchd_preview_id TEXT PRIMARY KEY,
          mode TEXT NOT NULL CHECK(mode = 'dry_run'),
          label TEXT NOT NULL,
          schedule_json TEXT NOT NULL,
          plist_path_redacted TEXT,
          log_dir_redacted TEXT,
          generated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS phase_08a_validation_runs (
          validation_run_id TEXT PRIMARY KEY,
          status TEXT NOT NULL,
          schema_version INTEGER,
          commands_json TEXT NOT NULL,
          passed_count INTEGER NOT NULL DEFAULT 0,
          failed_count INTEGER NOT NULL DEFAULT 0,
          error_redacted TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0)
        );
        """,
    ]

    # v27 Phase 08B Prompt 01 — durable delivery-handoff recovery. One additive table that
    # persists the structured delivery-handoff *lines* (section + ordered redacted titles +
    # review tier + safe source-ref pairs) so a full safe handoff can be reconstructed after
    # process exit. Metadata-only; the same per-row no-raw / no-writeback CHECK(col = 0) guard
    # columns as daily_brief_runs. Ships empty. V1-V26 untouched.
    V27_STATEMENTS: list[str] = [
        """
        CREATE TABLE IF NOT EXISTS daily_brief_handoff_lines (
          line_id TEXT PRIMARY KEY,
          brief_run_id TEXT NOT NULL REFERENCES daily_brief_runs(brief_run_id) ON DELETE CASCADE,
          section TEXT NOT NULL,
          line_index INTEGER NOT NULL,
          title_redacted TEXT NOT NULL,
          review_tier INTEGER CHECK(review_tier IS NULL OR review_tier IN (1,2,3)),
          source_refs_json TEXT NOT NULL DEFAULT '[]',
          generated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          retrieved_context_persisted INTEGER NOT NULL DEFAULT 0 CHECK(retrieved_context_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_daily_brief_handoff_lines_run
          ON daily_brief_handoff_lines(brief_run_id, section, line_index);
        """,
    ]

    # v28 Phase 08B Prompt 02 — persisted agent receipts (model-call + agent-run). Metadata-only:
    # content hashes + token counts + structured reason codes; the same per-row no-raw /
    # no-writeback CHECK(col = 0) guard columns as the V26/V27 tables. These replace the prior
    # in-memory-only / V27-deferred receipts. Ship empty. V1-V27 untouched.
    V28_STATEMENTS: list[str] = [
        """
        CREATE TABLE IF NOT EXISTS second_brain_agent_run_receipts (
          agent_run_id TEXT PRIMARY KEY,
          agent_id TEXT NOT NULL,
          run_kind TEXT NOT NULL,
          status TEXT NOT NULL,
          reason_code TEXT,
          review_tier INTEGER CHECK(review_tier IS NULL OR review_tier IN (1,2,3)),
          degradation_mode TEXT,
          model_receipt_count INTEGER NOT NULL DEFAULT 0,
          started_utc TEXT,
          finished_utc TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          retrieved_context_persisted INTEGER NOT NULL DEFAULT 0 CHECK(retrieved_context_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_agent_run_receipts_agent
          ON second_brain_agent_run_receipts(agent_id, created_utc);
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_agent_model_receipts (
          model_receipt_id TEXT PRIMARY KEY,
          agent_run_id TEXT REFERENCES second_brain_agent_run_receipts(agent_run_id) ON DELETE CASCADE,
          model_profile_id TEXT NOT NULL,
          model_id TEXT,
          input_context_hash TEXT NOT NULL,
          output_hash TEXT NOT NULL,
          input_token_count INTEGER NOT NULL DEFAULT 0,
          output_token_count INTEGER NOT NULL DEFAULT 0,
          temperature REAL,
          effort TEXT,
          review_tier_reason_code TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          retrieved_context_persisted INTEGER NOT NULL DEFAULT 0 CHECK(retrieved_context_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_agent_model_receipts_run
          ON second_brain_agent_model_receipts(agent_run_id, created_utc);
        """,
    ]

    # v29 Phase 08B Prompt 05 — durable run-accounting substrate: a run registry + a run-step
    # ledger for the no-overlap automation run (lock acquire/reclaim/release events recorded as
    # steps). Metadata-only with the same per-row no-raw / no-writeback CHECK(col = 0) guards as
    # V26-V28. The cross-process exclusion mechanism is an atomic lock FILE outside the repo;
    # ``lock_token``/``lock_status`` here are an audit trail, not the lock itself. ``assistant_run_id``
    # is a nullable bridge to the V1 ``assistant_runs`` ledger for the future executor. Ships empty;
    # V1-V28 untouched.
    V29_STATEMENTS: list[str] = [
        """
        CREATE TABLE IF NOT EXISTS second_brain_run_registry (
          run_registry_id TEXT PRIMARY KEY,
          run_kind TEXT NOT NULL,
          status TEXT NOT NULL,
          reason_code TEXT,
          lock_token TEXT,
          lock_status TEXT,
          assistant_run_id INTEGER REFERENCES assistant_runs(id),
          step_count INTEGER NOT NULL DEFAULT 0,
          dry_run INTEGER NOT NULL DEFAULT 0,
          started_utc TEXT,
          finished_utc TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          retrieved_context_persisted INTEGER NOT NULL DEFAULT 0 CHECK(retrieved_context_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_run_registry_kind
          ON second_brain_run_registry(run_kind, created_utc);
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_run_steps (
          run_step_id TEXT PRIMARY KEY,
          run_registry_id TEXT REFERENCES second_brain_run_registry(run_registry_id) ON DELETE CASCADE,
          step_name TEXT NOT NULL,
          step_order INTEGER NOT NULL,
          status TEXT NOT NULL,
          reason_code TEXT,
          detail TEXT,
          started_utc TEXT,
          finished_utc TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          retrieved_context_persisted INTEGER NOT NULL DEFAULT 0 CHECK(retrieved_context_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_run_steps_registry
          ON second_brain_run_steps(run_registry_id, step_order);
        """,
    ]

    # v30 Phase 08B Prompt 06 — retry/backoff receipts. One metadata-only row per retry attempt
    # (attempt number, max attempts, outcome, backoff seconds, structured reason code), with the
    # same per-row no-raw / no-writeback CHECK(col = 0) guards as V26-V29. The Run Recovery Agent
    # reuses the V28 ``second_brain_agent_run_receipts`` table (no new table for recovery). Ships
    # empty; V1-V29 untouched.
    V30_STATEMENTS: list[str] = [
        """
        CREATE TABLE IF NOT EXISTS second_brain_retry_receipts (
          retry_receipt_id TEXT PRIMARY KEY,
          run_kind TEXT NOT NULL,
          run_registry_id TEXT REFERENCES second_brain_run_registry(run_registry_id) ON DELETE CASCADE,
          attempt_number INTEGER NOT NULL,
          max_attempts INTEGER NOT NULL,
          outcome TEXT NOT NULL,
          reason_code TEXT,
          backoff_seconds INTEGER NOT NULL DEFAULT 0,
          next_attempt_utc TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          retrieved_context_persisted INTEGER NOT NULL DEFAULT 0 CHECK(retrieved_context_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_retry_receipts_kind
          ON second_brain_retry_receipts(run_kind, created_utc);
        """,
    ]

    # v31 Phase 08B Prompt 09 — daily-brief delivery receipts. One metadata-only row per
    # local-only delivery (the redacted vault path + content hash + structured reason code) so the
    # Daily Brief Delivery Agent is idempotent and auditable. ``delivery_channel`` is hard-pinned to
    # ``obsidian_vault`` by a CHECK so no external delivery channel can ever be recorded; the same
    # per-row no-raw / no-writeback CHECK(col = 0) guards as V26-V30 apply. Ships empty; V1-V30
    # untouched.
    V31_STATEMENTS: list[str] = [
        """
        CREATE TABLE IF NOT EXISTS daily_brief_delivery_receipts (
          delivery_receipt_id TEXT PRIMARY KEY,
          brief_run_id TEXT REFERENCES daily_brief_runs(brief_run_id),
          brief_date TEXT NOT NULL,
          delivery_channel TEXT NOT NULL DEFAULT 'obsidian_vault' CHECK(delivery_channel = 'obsidian_vault'),
          delivery_status TEXT NOT NULL,
          reason_code TEXT,
          mode TEXT NOT NULL CHECK(mode IN ('dry_run', 'apply')),
          content_hash TEXT,
          output_path_redacted TEXT,
          output_path_hash TEXT,
          delivered_utc TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          retrieved_context_persisted INTEGER NOT NULL DEFAULT 0 CHECK(retrieved_context_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_delivery_receipts_date
          ON daily_brief_delivery_receipts(brief_date, created_utc);
        """,
    ]

    # v32 Phase 08B Prompt 10 — local HTML brief render receipts. One metadata-only row per
    # self-contained HTML rendering (redacted app-support path + content hash). The raw HTML is
    # NEVER persisted here. ``no_external_assets`` is a fail-closed positive invariant
    # (CHECK(... = 1)) — a receipt can only be written for HTML that passed the external-asset /
    # network scan; ``mode`` is CHECK-pinned to dry_run|apply; the same 9 per-row no-raw/
    # no-writeback CHECK(col = 0) guards as V26-V31 apply. Ships empty; V1-V31 untouched.
    V32_STATEMENTS: list[str] = [
        """
        CREATE TABLE IF NOT EXISTS daily_brief_html_render_receipts (
          html_render_receipt_id TEXT PRIMARY KEY,
          brief_run_id TEXT REFERENCES daily_brief_runs(brief_run_id),
          brief_date TEXT NOT NULL,
          render_status TEXT NOT NULL,
          reason_code TEXT,
          mode TEXT NOT NULL CHECK(mode IN ('dry_run', 'apply')),
          content_hash TEXT,
          html_path_redacted TEXT,
          html_path_hash TEXT,
          no_external_assets INTEGER NOT NULL DEFAULT 1 CHECK(no_external_assets = 1),
          rendered_utc TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          retrieved_context_persisted INTEGER NOT NULL DEFAULT 0 CHECK(retrieved_context_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_html_render_receipts_date
          ON daily_brief_html_render_receipts(brief_date, created_utc);
        """,
    ]

    # v33 Phase 08B Prompt 11 — local macOS notification receipts. One metadata-only row per
    # notification preview/emit. ``channel`` is hard-pinned to ``local_macos`` (CHECK) so no external
    # channel can ever be recorded; only redacted counts + a title HASH are stored (never the raw
    # notification text); ``mode`` is CHECK-pinned to dry_run|apply; the same 9 per-row no-raw/
    # no-writeback CHECK(col = 0) guards as V26-V32 apply. The actual osascript emission is
    # real-but-policy-gated (fail-closed). Ships empty; V1-V32 untouched.
    V33_STATEMENTS: list[str] = [
        """
        CREATE TABLE IF NOT EXISTS daily_brief_notification_receipts (
          notification_receipt_id TEXT PRIMARY KEY,
          brief_run_id TEXT REFERENCES daily_brief_runs(brief_run_id),
          brief_date TEXT NOT NULL,
          channel TEXT NOT NULL DEFAULT 'local_macos' CHECK(channel = 'local_macos'),
          notify_status TEXT NOT NULL,
          reason_code TEXT,
          mode TEXT NOT NULL CHECK(mode IN ('dry_run', 'apply')),
          attention_count INTEGER NOT NULL DEFAULT 0,
          review_required_count INTEGER NOT NULL DEFAULT 0,
          warning_count INTEGER NOT NULL DEFAULT 0,
          project_count INTEGER NOT NULL DEFAULT 0,
          title_hash TEXT,
          emitted_utc TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          retrieved_context_persisted INTEGER NOT NULL DEFAULT 0 CHECK(retrieved_context_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_notification_receipts_date
          ON daily_brief_notification_receipts(brief_date, created_utc);
        """,
    ]

    # v34 Phase 08B Prompt 12 — local brief-open receipts. One metadata-only row per "open the
    # delivered brief" action (macOS ``open`` of the delivered vault note or rendered HTML).
    # ``open_target`` is CHECK-pinned to the two LOCAL artifacts ('vault' | 'html'); only a redacted
    # path + a path HASH are stored (never raw content); ``mode`` is CHECK-pinned to dry_run|apply;
    # the same 9 per-row no-raw/no-writeback CHECK(col = 0) guards as V26-V33 apply. The actual
    # ``open`` is real-but-policy-gated (fail-closed). Ships empty; V1-V33 untouched.
    V34_STATEMENTS: list[str] = [
        """
        CREATE TABLE IF NOT EXISTS daily_brief_open_receipts (
          open_receipt_id TEXT PRIMARY KEY,
          brief_run_id TEXT REFERENCES daily_brief_runs(brief_run_id),
          brief_date TEXT NOT NULL,
          open_target TEXT NOT NULL CHECK(open_target IN ('vault', 'html')),
          open_status TEXT NOT NULL,
          reason_code TEXT,
          mode TEXT NOT NULL CHECK(mode IN ('dry_run', 'apply')),
          path_redacted TEXT,
          path_hash TEXT,
          opened_utc TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          retrieved_context_persisted INTEGER NOT NULL DEFAULT 0 CHECK(retrieved_context_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0)
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_open_receipts_date
          ON daily_brief_open_receipts(brief_date, created_utc);
        """,
    ]

    V35_STATEMENTS: list[str] = [
        """
        CREATE TABLE IF NOT EXISTS second_brain_financial_fact_normalization_runs (
          id INTEGER PRIMARY KEY,
          run_id TEXT NOT NULL UNIQUE,
          project_key TEXT,
          started_utc TEXT NOT NULL,
          completed_utc TEXT,
          status TEXT NOT NULL CHECK(status IN ('started','succeeded','failed','blocked')),
          advisory_only INTEGER NOT NULL DEFAULT 1 CHECK(advisory_only = 1),
          notes_redacted TEXT,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
          raw_financial_source_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_financial_source_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          financial_determination_performed INTEGER NOT NULL DEFAULT 0 CHECK(financial_determination_performed = 0),
          payment_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(payment_decision_performed = 0),
          claim_or_entitlement_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(claim_or_entitlement_decision_performed = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_financial_amount_facts_normalized (
          id INTEGER PRIMARY KEY,
          run_id TEXT NOT NULL,
          project_key TEXT NOT NULL,
          source_family TEXT NOT NULL,
          source_table TEXT NOT NULL,
          source_record_ref TEXT NOT NULL,
          source_field_path TEXT NOT NULL,
          source_value_hash TEXT,
          parse_status TEXT NOT NULL CHECK(parse_status IN ('parseable','rejected','missing','ambiguous','stale','conflicting','review_required')),
          canonical_decimal_text TEXT,
          minor_units INTEGER,
          currency_code TEXT,
          currency_status TEXT,
          rejection_reason TEXT,
          confidence_label TEXT NOT NULL,
          review_tier TEXT NOT NULL,
          advisory_only INTEGER NOT NULL DEFAULT 1 CHECK(advisory_only = 1),
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
          raw_financial_source_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_financial_source_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          financial_determination_performed INTEGER NOT NULL DEFAULT 0 CHECK(financial_determination_performed = 0),
          payment_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(payment_decision_performed = 0),
          claim_or_entitlement_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(claim_or_entitlement_decision_performed = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_financial_currency_completeness_snapshots (
          id INTEGER PRIMARY KEY,
          run_id TEXT NOT NULL,
          project_key TEXT,
          currency_status TEXT NOT NULL CHECK(currency_status IN ('explicit_source_currency','evidence_backed_project_default','missing_currency','inconsistent_currency','ambiguous_currency','review_required')),
          project_default_applied INTEGER NOT NULL DEFAULT 0,
          evidence_backed_count INTEGER NOT NULL DEFAULT 0,
          inconsistent_count INTEGER NOT NULL DEFAULT 0,
          missing_count INTEGER NOT NULL DEFAULT 0,
          advisory_only INTEGER NOT NULL DEFAULT 1 CHECK(advisory_only = 1),
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
          raw_financial_source_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_financial_source_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          financial_determination_performed INTEGER NOT NULL DEFAULT 0 CHECK(financial_determination_performed = 0),
          payment_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(payment_decision_performed = 0),
          claim_or_entitlement_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(claim_or_entitlement_decision_performed = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_financial_wbs_cost_code_snapshots (
          id INTEGER PRIMARY KEY,
          run_id TEXT NOT NULL,
          project_key TEXT,
          wbs_present_count INTEGER NOT NULL DEFAULT 0,
          cost_code_present_count INTEGER NOT NULL DEFAULT 0,
          line_item_type_present_count INTEGER NOT NULL DEFAULT 0,
          missing_wbs_count INTEGER NOT NULL DEFAULT 0,
          missing_cost_code_count INTEGER NOT NULL DEFAULT 0,
          ambiguous_count INTEGER NOT NULL DEFAULT 0,
          review_required_count INTEGER NOT NULL DEFAULT 0,
          advisory_only INTEGER NOT NULL DEFAULT 1 CHECK(advisory_only = 1),
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
          raw_financial_source_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_financial_source_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          financial_determination_performed INTEGER NOT NULL DEFAULT 0 CHECK(financial_determination_performed = 0),
          payment_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(payment_decision_performed = 0),
          claim_or_entitlement_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(claim_or_entitlement_decision_performed = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_financial_source_coverage_snapshots (
          id INTEGER PRIMARY KEY,
          run_id TEXT NOT NULL,
          project_key TEXT,
          source_family TEXT NOT NULL,
          endpoint_id TEXT,
          local_table TEXT,
          live_verification_status TEXT,
          coverage_status TEXT NOT NULL,
          row_count INTEGER NOT NULL DEFAULT 0,
          amount_field_count INTEGER NOT NULL DEFAULT 0,
          currency_field_count INTEGER NOT NULL DEFAULT 0,
          wbs_cost_code_field_count INTEGER NOT NULL DEFAULT 0,
          relationship_key_count INTEGER NOT NULL DEFAULT 0,
          advisory_only INTEGER NOT NULL DEFAULT 1 CHECK(advisory_only = 1),
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
          raw_financial_source_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_financial_source_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          financial_determination_performed INTEGER NOT NULL DEFAULT 0 CHECK(financial_determination_performed = 0),
          payment_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(payment_decision_performed = 0),
          claim_or_entitlement_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(claim_or_entitlement_decision_performed = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_financial_exposure_summary_items (
          id INTEGER PRIMARY KEY,
          run_id TEXT NOT NULL,
          project_key TEXT NOT NULL,
          exposure_category TEXT NOT NULL,
          item_label TEXT,
          normalized_amount_ref TEXT,
          confidence_label TEXT NOT NULL,
          review_tier TEXT NOT NULL,
          advisory_status TEXT NOT NULL,
          advisory_only INTEGER NOT NULL DEFAULT 1 CHECK(advisory_only = 1),
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
          raw_financial_source_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_financial_source_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          financial_determination_performed INTEGER NOT NULL DEFAULT 0 CHECK(financial_determination_performed = 0),
          payment_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(payment_decision_performed = 0),
          claim_or_entitlement_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(claim_or_entitlement_decision_performed = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_financial_forecast_readiness_runs (
          id INTEGER PRIMARY KEY,
          run_id TEXT NOT NULL UNIQUE,
          project_key TEXT,
          readiness_status TEXT NOT NULL CHECK(readiness_status IN ('ready_for_trend_support','ready_with_review_required','insufficient_context','blocked_by_guardrail','deferred_not_evaluated')),
          gate_status TEXT NOT NULL,
          context_items_count INTEGER NOT NULL DEFAULT 0,
          review_items_count INTEGER NOT NULL DEFAULT 0,
          advisory_only INTEGER NOT NULL DEFAULT 1 CHECK(advisory_only = 1),
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
          raw_financial_source_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_financial_source_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          financial_determination_performed INTEGER NOT NULL DEFAULT 0 CHECK(financial_determination_performed = 0),
          payment_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(payment_decision_performed = 0),
          claim_or_entitlement_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(claim_or_entitlement_decision_performed = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_financial_review_required_items (
          id INTEGER PRIMARY KEY,
          run_id TEXT NOT NULL,
          project_key TEXT NOT NULL,
          trigger_category TEXT NOT NULL,
          source_ref TEXT,
          amount_ref TEXT,
          review_tier TEXT NOT NULL,
          advisory_only INTEGER NOT NULL DEFAULT 1 CHECK(advisory_only = 1),
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
          raw_financial_source_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_financial_source_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          financial_determination_performed INTEGER NOT NULL DEFAULT 0 CHECK(financial_determination_performed = 0),
          payment_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(payment_decision_performed = 0),
          claim_or_entitlement_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(claim_or_entitlement_decision_performed = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_financial_readiness_agent_runs (
          id INTEGER PRIMARY KEY,
          run_id TEXT NOT NULL UNIQUE,
          project_key TEXT,
          status TEXT NOT NULL CHECK(status IN ('started','succeeded','failed','blocked')),
          items_evaluated INTEGER NOT NULL DEFAULT 0,
          review_required_count INTEGER NOT NULL DEFAULT 0,
          advisory_only INTEGER NOT NULL DEFAULT 1 CHECK(advisory_only = 1),
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
          raw_financial_source_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_financial_source_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          financial_determination_performed INTEGER NOT NULL DEFAULT 0 CHECK(financial_determination_performed = 0),
          payment_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(payment_decision_performed = 0),
          claim_or_entitlement_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(claim_or_entitlement_decision_performed = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_phase_08c_validation_runs (
          id INTEGER PRIMARY KEY,
          run_id TEXT NOT NULL UNIQUE,
          started_utc TEXT NOT NULL,
          completed_utc TEXT,
          status TEXT NOT NULL CHECK(status IN ('started','succeeded','failed','blocked')),
          matrix_json_redacted TEXT,
          advisory_only INTEGER NOT NULL DEFAULT 1 CHECK(advisory_only = 1),
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
          raw_financial_source_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_financial_source_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          financial_determination_performed INTEGER NOT NULL DEFAULT 0 CHECK(financial_determination_performed = 0),
          payment_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(payment_decision_performed = 0),
          claim_or_entitlement_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(claim_or_entitlement_decision_performed = 0)
        );
        """,
    ]

    # v36 Phase 08C — review-required routing: persist a confidence label on each
    # routed review item (additive column only; V1-V35 tables otherwise untouched).
    # The existing trigger_category is the reason code, source_ref/amount_ref are
    # the (metadata-only) source references, review_tier is the tier, and the 14
    # guard columns are already present on the table.
    V36_STATEMENTS: list[str] = [
        "ALTER TABLE second_brain_financial_review_required_items "
        "ADD COLUMN confidence_label TEXT;",
    ]

    # v37 Phase 08D Prompt 02 — local MCP bridge metadata substrate (additive only;
    # V1-V36 untouched). Ten tables: server-config / tool-registry / resource-registry /
    # prompt-registry snapshots, tool-call + denial receipts, permission-audit + policy-gate
    # runs, the Claude Desktop config preview, and the phase-08D validation runs. Every table
    # is metadata-only (hashes, counts, status, reason codes, policy/schema version, evidence
    # path, correlation id) and carries the full twenty no-raw / no-writeback / no-direct-api /
    # no-determination guard columns CHECK(... = 0). No server, broker, or runtime dispatch is
    # wired in this prompt — the substrate ships empty (operational_empty_expected).
    V37_STATEMENTS: list[str] = [
        """
        CREATE TABLE IF NOT EXISTS second_brain_mcp_server_config_snapshots (
          snapshot_id TEXT PRIMARY KEY,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          transport TEXT NOT NULL,
          config_hash TEXT NOT NULL,
          policy_version TEXT NOT NULL,
          schema_version INTEGER NOT NULL,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
          raw_financial_source_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_financial_source_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          graph_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(graph_api_call_performed = 0),
          procore_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(procore_api_call_performed = 0),
          email_send_performed INTEGER NOT NULL DEFAULT 0 CHECK(email_send_performed = 0),
          calendar_update_performed INTEGER NOT NULL DEFAULT 0 CHECK(calendar_update_performed = 0),
          source_system_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(source_system_writeback_performed = 0),
          arbitrary_sql_performed INTEGER NOT NULL DEFAULT 0 CHECK(arbitrary_sql_performed = 0),
          raw_store_access_performed INTEGER NOT NULL DEFAULT 0 CHECK(raw_store_access_performed = 0),
          financial_determination_performed INTEGER NOT NULL DEFAULT 0 CHECK(financial_determination_performed = 0),
          payment_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(payment_decision_performed = 0),
          claim_or_entitlement_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(claim_or_entitlement_decision_performed = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_mcp_tool_registry_snapshots (
          snapshot_id TEXT PRIMARY KEY,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          allowed_tool_count INTEGER NOT NULL,
          denied_action_count INTEGER NOT NULL,
          registry_hash TEXT NOT NULL,
          policy_version TEXT NOT NULL,
          schema_version INTEGER NOT NULL,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
          raw_financial_source_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_financial_source_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          graph_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(graph_api_call_performed = 0),
          procore_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(procore_api_call_performed = 0),
          email_send_performed INTEGER NOT NULL DEFAULT 0 CHECK(email_send_performed = 0),
          calendar_update_performed INTEGER NOT NULL DEFAULT 0 CHECK(calendar_update_performed = 0),
          source_system_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(source_system_writeback_performed = 0),
          arbitrary_sql_performed INTEGER NOT NULL DEFAULT 0 CHECK(arbitrary_sql_performed = 0),
          raw_store_access_performed INTEGER NOT NULL DEFAULT 0 CHECK(raw_store_access_performed = 0),
          financial_determination_performed INTEGER NOT NULL DEFAULT 0 CHECK(financial_determination_performed = 0),
          payment_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(payment_decision_performed = 0),
          claim_or_entitlement_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(claim_or_entitlement_decision_performed = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_mcp_resource_registry_snapshots (
          snapshot_id TEXT PRIMARY KEY,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          resource_count INTEGER NOT NULL,
          registry_hash TEXT NOT NULL,
          policy_version TEXT NOT NULL,
          schema_version INTEGER NOT NULL,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
          raw_financial_source_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_financial_source_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          graph_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(graph_api_call_performed = 0),
          procore_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(procore_api_call_performed = 0),
          email_send_performed INTEGER NOT NULL DEFAULT 0 CHECK(email_send_performed = 0),
          calendar_update_performed INTEGER NOT NULL DEFAULT 0 CHECK(calendar_update_performed = 0),
          source_system_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(source_system_writeback_performed = 0),
          arbitrary_sql_performed INTEGER NOT NULL DEFAULT 0 CHECK(arbitrary_sql_performed = 0),
          raw_store_access_performed INTEGER NOT NULL DEFAULT 0 CHECK(raw_store_access_performed = 0),
          financial_determination_performed INTEGER NOT NULL DEFAULT 0 CHECK(financial_determination_performed = 0),
          payment_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(payment_decision_performed = 0),
          claim_or_entitlement_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(claim_or_entitlement_decision_performed = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_mcp_prompt_registry_snapshots (
          snapshot_id TEXT PRIMARY KEY,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          prompt_count INTEGER NOT NULL,
          registry_hash TEXT NOT NULL,
          policy_version TEXT NOT NULL,
          schema_version INTEGER NOT NULL,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
          raw_financial_source_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_financial_source_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          graph_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(graph_api_call_performed = 0),
          procore_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(procore_api_call_performed = 0),
          email_send_performed INTEGER NOT NULL DEFAULT 0 CHECK(email_send_performed = 0),
          calendar_update_performed INTEGER NOT NULL DEFAULT 0 CHECK(calendar_update_performed = 0),
          source_system_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(source_system_writeback_performed = 0),
          arbitrary_sql_performed INTEGER NOT NULL DEFAULT 0 CHECK(arbitrary_sql_performed = 0),
          raw_store_access_performed INTEGER NOT NULL DEFAULT 0 CHECK(raw_store_access_performed = 0),
          financial_determination_performed INTEGER NOT NULL DEFAULT 0 CHECK(financial_determination_performed = 0),
          payment_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(payment_decision_performed = 0),
          claim_or_entitlement_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(claim_or_entitlement_decision_performed = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_mcp_tool_call_receipts (
          receipt_id TEXT PRIMARY KEY,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          client_name TEXT,
          tool_name TEXT NOT NULL,
          decision TEXT NOT NULL CHECK(decision IN ('allowed','denied')),
          workflow_wrapper TEXT,
          policy_version TEXT NOT NULL,
          schema_version INTEGER NOT NULL,
          output_classification TEXT,
          source_count INTEGER NOT NULL DEFAULT 0,
          result_count INTEGER NOT NULL DEFAULT 0,
          evidence_path TEXT,
          correlation_id TEXT,
          args_hash TEXT,
          result_hash TEXT,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
          raw_financial_source_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_financial_source_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          graph_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(graph_api_call_performed = 0),
          procore_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(procore_api_call_performed = 0),
          email_send_performed INTEGER NOT NULL DEFAULT 0 CHECK(email_send_performed = 0),
          calendar_update_performed INTEGER NOT NULL DEFAULT 0 CHECK(calendar_update_performed = 0),
          source_system_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(source_system_writeback_performed = 0),
          arbitrary_sql_performed INTEGER NOT NULL DEFAULT 0 CHECK(arbitrary_sql_performed = 0),
          raw_store_access_performed INTEGER NOT NULL DEFAULT 0 CHECK(raw_store_access_performed = 0),
          financial_determination_performed INTEGER NOT NULL DEFAULT 0 CHECK(financial_determination_performed = 0),
          payment_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(payment_decision_performed = 0),
          claim_or_entitlement_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(claim_or_entitlement_decision_performed = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_mcp_denial_receipts (
          receipt_id TEXT PRIMARY KEY,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          client_name TEXT,
          requested_action TEXT NOT NULL,
          decision TEXT NOT NULL DEFAULT 'denied' CHECK(decision = 'denied'),
          denial_reason_code TEXT NOT NULL,
          policy_version TEXT NOT NULL,
          schema_version INTEGER NOT NULL,
          correlation_id TEXT,
          request_hash TEXT,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
          raw_financial_source_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_financial_source_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          graph_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(graph_api_call_performed = 0),
          procore_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(procore_api_call_performed = 0),
          email_send_performed INTEGER NOT NULL DEFAULT 0 CHECK(email_send_performed = 0),
          calendar_update_performed INTEGER NOT NULL DEFAULT 0 CHECK(calendar_update_performed = 0),
          source_system_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(source_system_writeback_performed = 0),
          arbitrary_sql_performed INTEGER NOT NULL DEFAULT 0 CHECK(arbitrary_sql_performed = 0),
          raw_store_access_performed INTEGER NOT NULL DEFAULT 0 CHECK(raw_store_access_performed = 0),
          financial_determination_performed INTEGER NOT NULL DEFAULT 0 CHECK(financial_determination_performed = 0),
          payment_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(payment_decision_performed = 0),
          claim_or_entitlement_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(claim_or_entitlement_decision_performed = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_mcp_permission_audit_runs (
          audit_run_id TEXT PRIMARY KEY,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          status TEXT NOT NULL,
          checks_json TEXT NOT NULL,
          finding_count INTEGER NOT NULL DEFAULT 0,
          policy_version TEXT NOT NULL,
          schema_version INTEGER NOT NULL,
          evidence_path TEXT,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
          raw_financial_source_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_financial_source_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          graph_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(graph_api_call_performed = 0),
          procore_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(procore_api_call_performed = 0),
          email_send_performed INTEGER NOT NULL DEFAULT 0 CHECK(email_send_performed = 0),
          calendar_update_performed INTEGER NOT NULL DEFAULT 0 CHECK(calendar_update_performed = 0),
          source_system_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(source_system_writeback_performed = 0),
          arbitrary_sql_performed INTEGER NOT NULL DEFAULT 0 CHECK(arbitrary_sql_performed = 0),
          raw_store_access_performed INTEGER NOT NULL DEFAULT 0 CHECK(raw_store_access_performed = 0),
          financial_determination_performed INTEGER NOT NULL DEFAULT 0 CHECK(financial_determination_performed = 0),
          payment_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(payment_decision_performed = 0),
          claim_or_entitlement_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(claim_or_entitlement_decision_performed = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_mcp_policy_gate_runs (
          gate_run_id TEXT PRIMARY KEY,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          ok INTEGER NOT NULL CHECK(ok IN (0,1)),
          status_counts_json TEXT NOT NULL,
          readiness_overstated INTEGER NOT NULL DEFAULT 0 CHECK(readiness_overstated IN (0,1)),
          policy_version TEXT NOT NULL,
          schema_version INTEGER NOT NULL,
          evidence_path TEXT,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
          raw_financial_source_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_financial_source_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          graph_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(graph_api_call_performed = 0),
          procore_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(procore_api_call_performed = 0),
          email_send_performed INTEGER NOT NULL DEFAULT 0 CHECK(email_send_performed = 0),
          calendar_update_performed INTEGER NOT NULL DEFAULT 0 CHECK(calendar_update_performed = 0),
          source_system_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(source_system_writeback_performed = 0),
          arbitrary_sql_performed INTEGER NOT NULL DEFAULT 0 CHECK(arbitrary_sql_performed = 0),
          raw_store_access_performed INTEGER NOT NULL DEFAULT 0 CHECK(raw_store_access_performed = 0),
          financial_determination_performed INTEGER NOT NULL DEFAULT 0 CHECK(financial_determination_performed = 0),
          payment_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(payment_decision_performed = 0),
          claim_or_entitlement_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(claim_or_entitlement_decision_performed = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_mcp_claude_desktop_config_previews (
          preview_id TEXT PRIMARY KEY,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          client_name TEXT NOT NULL,
          safe INTEGER NOT NULL CHECK(safe IN (0,1)),
          transport TEXT NOT NULL,
          command_redacted TEXT NOT NULL,
          args_json TEXT NOT NULL,
          env_keys_json TEXT NOT NULL,
          config_hash TEXT NOT NULL,
          policy_version TEXT NOT NULL,
          schema_version INTEGER NOT NULL,
          evidence_path TEXT,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
          raw_financial_source_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_financial_source_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          graph_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(graph_api_call_performed = 0),
          procore_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(procore_api_call_performed = 0),
          email_send_performed INTEGER NOT NULL DEFAULT 0 CHECK(email_send_performed = 0),
          calendar_update_performed INTEGER NOT NULL DEFAULT 0 CHECK(calendar_update_performed = 0),
          source_system_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(source_system_writeback_performed = 0),
          arbitrary_sql_performed INTEGER NOT NULL DEFAULT 0 CHECK(arbitrary_sql_performed = 0),
          raw_store_access_performed INTEGER NOT NULL DEFAULT 0 CHECK(raw_store_access_performed = 0),
          financial_determination_performed INTEGER NOT NULL DEFAULT 0 CHECK(financial_determination_performed = 0),
          payment_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(payment_decision_performed = 0),
          claim_or_entitlement_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(claim_or_entitlement_decision_performed = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_phase_08d_validation_runs (
          validation_run_id TEXT PRIMARY KEY,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          ok INTEGER NOT NULL CHECK(ok IN (0,1)),
          command_count INTEGER NOT NULL,
          pass_count INTEGER NOT NULL,
          warning_count INTEGER NOT NULL DEFAULT 0,
          fail_count INTEGER NOT NULL DEFAULT 0,
          validation_json TEXT NOT NULL,
          policy_version TEXT NOT NULL,
          schema_version INTEGER NOT NULL,
          evidence_path TEXT,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
          raw_financial_source_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_financial_source_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          graph_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(graph_api_call_performed = 0),
          procore_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(procore_api_call_performed = 0),
          email_send_performed INTEGER NOT NULL DEFAULT 0 CHECK(email_send_performed = 0),
          calendar_update_performed INTEGER NOT NULL DEFAULT 0 CHECK(calendar_update_performed = 0),
          source_system_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(source_system_writeback_performed = 0),
          arbitrary_sql_performed INTEGER NOT NULL DEFAULT 0 CHECK(arbitrary_sql_performed = 0),
          raw_store_access_performed INTEGER NOT NULL DEFAULT 0 CHECK(raw_store_access_performed = 0),
          financial_determination_performed INTEGER NOT NULL DEFAULT 0 CHECK(financial_determination_performed = 0),
          payment_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(payment_decision_performed = 0),
          claim_or_entitlement_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(claim_or_entitlement_decision_performed = 0)
        );
        """,
    ]

    # v38 Phase 09 Prompt 12 — retrieval / memory / agent metadata substrate (additive only;
    # V1-V37 untouched). Nineteen metadata-only tables (LlamaIndex config snapshots, approved
    # source manifests, vector-index runs/items, embedding-model evals, hybrid query runs/results,
    # eval sets/cases/runs, benchmark runs, source-linked proof runs, unsupported-claim checks,
    # context-budget runs, memory quality-review runs, memory consolidation candidates/review
    # items, agent-performance feedback runs, and the Phase 09 validation runs). Every table is
    # metadata-only (hashes, counts, labels, refs, review tier, confidence class, freshness,
    # status, policy/schema version) and carries the full twenty-three guard columns
    # CHECK(... = 0): the twenty no-raw / no-writeback / no-direct-api / no-determination guards
    # plus the three Phase 09 guards unsupported_claim_performed, raw_vector_content_persisted,
    # and semantic_retrieval_bypassed_policy. No LlamaIndex / embeddings / vector / semantic
    # retrieval runtime is wired here — the substrate ships empty (placeholder_deferred).
    V38_STATEMENTS: list[str] = [
        """
        CREATE TABLE IF NOT EXISTS second_brain_retrieval_llamaindex_config_snapshots (
          snapshot_id TEXT PRIMARY KEY,
          created_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          policy_version TEXT NOT NULL,
          schema_version INTEGER NOT NULL,
          config_hash TEXT NOT NULL,
          embedding_model_label TEXT,
          index_kind TEXT,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
          raw_financial_source_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_financial_source_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          graph_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(graph_api_call_performed = 0),
          procore_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(procore_api_call_performed = 0),
          email_send_performed INTEGER NOT NULL DEFAULT 0 CHECK(email_send_performed = 0),
          calendar_update_performed INTEGER NOT NULL DEFAULT 0 CHECK(calendar_update_performed = 0),
          source_system_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(source_system_writeback_performed = 0),
          arbitrary_sql_performed INTEGER NOT NULL DEFAULT 0 CHECK(arbitrary_sql_performed = 0),
          raw_store_access_performed INTEGER NOT NULL DEFAULT 0 CHECK(raw_store_access_performed = 0),
          financial_determination_performed INTEGER NOT NULL DEFAULT 0 CHECK(financial_determination_performed = 0),
          payment_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(payment_decision_performed = 0),
          claim_or_entitlement_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(claim_or_entitlement_decision_performed = 0),
          unsupported_claim_performed INTEGER NOT NULL DEFAULT 0 CHECK(unsupported_claim_performed = 0),
          raw_vector_content_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_vector_content_persisted = 0),
          semantic_retrieval_bypassed_policy INTEGER NOT NULL DEFAULT 0 CHECK(semantic_retrieval_bypassed_policy = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_retrieval_approved_source_manifests (
          manifest_id TEXT PRIMARY KEY,
          created_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          policy_version TEXT NOT NULL,
          schema_version INTEGER NOT NULL,
          manifest_hash TEXT NOT NULL,
          approved_family_count INTEGER NOT NULL DEFAULT 0,
          approved_ref_count INTEGER NOT NULL DEFAULT 0,
          review_tier TEXT,
          status TEXT,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
          raw_financial_source_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_financial_source_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          graph_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(graph_api_call_performed = 0),
          procore_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(procore_api_call_performed = 0),
          email_send_performed INTEGER NOT NULL DEFAULT 0 CHECK(email_send_performed = 0),
          calendar_update_performed INTEGER NOT NULL DEFAULT 0 CHECK(calendar_update_performed = 0),
          source_system_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(source_system_writeback_performed = 0),
          arbitrary_sql_performed INTEGER NOT NULL DEFAULT 0 CHECK(arbitrary_sql_performed = 0),
          raw_store_access_performed INTEGER NOT NULL DEFAULT 0 CHECK(raw_store_access_performed = 0),
          financial_determination_performed INTEGER NOT NULL DEFAULT 0 CHECK(financial_determination_performed = 0),
          payment_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(payment_decision_performed = 0),
          claim_or_entitlement_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(claim_or_entitlement_decision_performed = 0),
          unsupported_claim_performed INTEGER NOT NULL DEFAULT 0 CHECK(unsupported_claim_performed = 0),
          raw_vector_content_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_vector_content_persisted = 0),
          semantic_retrieval_bypassed_policy INTEGER NOT NULL DEFAULT 0 CHECK(semantic_retrieval_bypassed_policy = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_retrieval_vector_index_runs (
          run_id TEXT PRIMARY KEY,
          created_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          policy_version TEXT NOT NULL,
          schema_version INTEGER NOT NULL,
          manifest_id TEXT,
          config_snapshot_id TEXT,
          project_key TEXT,
          item_count INTEGER NOT NULL DEFAULT 0,
          status TEXT,
          config_hash TEXT,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
          raw_financial_source_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_financial_source_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          graph_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(graph_api_call_performed = 0),
          procore_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(procore_api_call_performed = 0),
          email_send_performed INTEGER NOT NULL DEFAULT 0 CHECK(email_send_performed = 0),
          calendar_update_performed INTEGER NOT NULL DEFAULT 0 CHECK(calendar_update_performed = 0),
          source_system_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(source_system_writeback_performed = 0),
          arbitrary_sql_performed INTEGER NOT NULL DEFAULT 0 CHECK(arbitrary_sql_performed = 0),
          raw_store_access_performed INTEGER NOT NULL DEFAULT 0 CHECK(raw_store_access_performed = 0),
          financial_determination_performed INTEGER NOT NULL DEFAULT 0 CHECK(financial_determination_performed = 0),
          payment_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(payment_decision_performed = 0),
          claim_or_entitlement_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(claim_or_entitlement_decision_performed = 0),
          unsupported_claim_performed INTEGER NOT NULL DEFAULT 0 CHECK(unsupported_claim_performed = 0),
          raw_vector_content_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_vector_content_persisted = 0),
          semantic_retrieval_bypassed_policy INTEGER NOT NULL DEFAULT 0 CHECK(semantic_retrieval_bypassed_policy = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_retrieval_vector_index_items (
          item_id TEXT PRIMARY KEY,
          created_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          policy_version TEXT NOT NULL,
          schema_version INTEGER NOT NULL,
          run_id TEXT NOT NULL,
          source_family TEXT,
          source_ref_hash TEXT,
          content_hash TEXT,
          confidence_class TEXT,
          freshness_label TEXT,
          chunk_count INTEGER NOT NULL DEFAULT 0,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
          raw_financial_source_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_financial_source_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          graph_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(graph_api_call_performed = 0),
          procore_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(procore_api_call_performed = 0),
          email_send_performed INTEGER NOT NULL DEFAULT 0 CHECK(email_send_performed = 0),
          calendar_update_performed INTEGER NOT NULL DEFAULT 0 CHECK(calendar_update_performed = 0),
          source_system_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(source_system_writeback_performed = 0),
          arbitrary_sql_performed INTEGER NOT NULL DEFAULT 0 CHECK(arbitrary_sql_performed = 0),
          raw_store_access_performed INTEGER NOT NULL DEFAULT 0 CHECK(raw_store_access_performed = 0),
          financial_determination_performed INTEGER NOT NULL DEFAULT 0 CHECK(financial_determination_performed = 0),
          payment_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(payment_decision_performed = 0),
          claim_or_entitlement_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(claim_or_entitlement_decision_performed = 0),
          unsupported_claim_performed INTEGER NOT NULL DEFAULT 0 CHECK(unsupported_claim_performed = 0),
          raw_vector_content_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_vector_content_persisted = 0),
          semantic_retrieval_bypassed_policy INTEGER NOT NULL DEFAULT 0 CHECK(semantic_retrieval_bypassed_policy = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_retrieval_embedding_model_evals (
          eval_id TEXT PRIMARY KEY,
          created_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          policy_version TEXT NOT NULL,
          schema_version INTEGER NOT NULL,
          embedding_model_label TEXT,
          metric_name TEXT,
          metric_value_label TEXT,
          sample_count INTEGER NOT NULL DEFAULT 0,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
          raw_financial_source_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_financial_source_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          graph_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(graph_api_call_performed = 0),
          procore_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(procore_api_call_performed = 0),
          email_send_performed INTEGER NOT NULL DEFAULT 0 CHECK(email_send_performed = 0),
          calendar_update_performed INTEGER NOT NULL DEFAULT 0 CHECK(calendar_update_performed = 0),
          source_system_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(source_system_writeback_performed = 0),
          arbitrary_sql_performed INTEGER NOT NULL DEFAULT 0 CHECK(arbitrary_sql_performed = 0),
          raw_store_access_performed INTEGER NOT NULL DEFAULT 0 CHECK(raw_store_access_performed = 0),
          financial_determination_performed INTEGER NOT NULL DEFAULT 0 CHECK(financial_determination_performed = 0),
          payment_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(payment_decision_performed = 0),
          claim_or_entitlement_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(claim_or_entitlement_decision_performed = 0),
          unsupported_claim_performed INTEGER NOT NULL DEFAULT 0 CHECK(unsupported_claim_performed = 0),
          raw_vector_content_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_vector_content_persisted = 0),
          semantic_retrieval_bypassed_policy INTEGER NOT NULL DEFAULT 0 CHECK(semantic_retrieval_bypassed_policy = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_retrieval_hybrid_query_runs (
          run_id TEXT PRIMARY KEY,
          created_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          policy_version TEXT NOT NULL,
          schema_version INTEGER NOT NULL,
          project_key TEXT,
          query_hash TEXT,
          mode TEXT,
          result_count INTEGER NOT NULL DEFAULT 0,
          latency_bucket TEXT,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
          raw_financial_source_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_financial_source_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          graph_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(graph_api_call_performed = 0),
          procore_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(procore_api_call_performed = 0),
          email_send_performed INTEGER NOT NULL DEFAULT 0 CHECK(email_send_performed = 0),
          calendar_update_performed INTEGER NOT NULL DEFAULT 0 CHECK(calendar_update_performed = 0),
          source_system_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(source_system_writeback_performed = 0),
          arbitrary_sql_performed INTEGER NOT NULL DEFAULT 0 CHECK(arbitrary_sql_performed = 0),
          raw_store_access_performed INTEGER NOT NULL DEFAULT 0 CHECK(raw_store_access_performed = 0),
          financial_determination_performed INTEGER NOT NULL DEFAULT 0 CHECK(financial_determination_performed = 0),
          payment_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(payment_decision_performed = 0),
          claim_or_entitlement_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(claim_or_entitlement_decision_performed = 0),
          unsupported_claim_performed INTEGER NOT NULL DEFAULT 0 CHECK(unsupported_claim_performed = 0),
          raw_vector_content_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_vector_content_persisted = 0),
          semantic_retrieval_bypassed_policy INTEGER NOT NULL DEFAULT 0 CHECK(semantic_retrieval_bypassed_policy = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_retrieval_hybrid_query_results (
          result_id TEXT PRIMARY KEY,
          created_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          policy_version TEXT NOT NULL,
          schema_version INTEGER NOT NULL,
          run_id TEXT NOT NULL,
          rank INTEGER,
          source_family TEXT,
          source_ref_hash TEXT,
          confidence_class TEXT,
          score_bucket TEXT,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
          raw_financial_source_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_financial_source_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          graph_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(graph_api_call_performed = 0),
          procore_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(procore_api_call_performed = 0),
          email_send_performed INTEGER NOT NULL DEFAULT 0 CHECK(email_send_performed = 0),
          calendar_update_performed INTEGER NOT NULL DEFAULT 0 CHECK(calendar_update_performed = 0),
          source_system_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(source_system_writeback_performed = 0),
          arbitrary_sql_performed INTEGER NOT NULL DEFAULT 0 CHECK(arbitrary_sql_performed = 0),
          raw_store_access_performed INTEGER NOT NULL DEFAULT 0 CHECK(raw_store_access_performed = 0),
          financial_determination_performed INTEGER NOT NULL DEFAULT 0 CHECK(financial_determination_performed = 0),
          payment_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(payment_decision_performed = 0),
          claim_or_entitlement_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(claim_or_entitlement_decision_performed = 0),
          unsupported_claim_performed INTEGER NOT NULL DEFAULT 0 CHECK(unsupported_claim_performed = 0),
          raw_vector_content_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_vector_content_persisted = 0),
          semantic_retrieval_bypassed_policy INTEGER NOT NULL DEFAULT 0 CHECK(semantic_retrieval_bypassed_policy = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_retrieval_eval_sets (
          eval_set_id TEXT PRIMARY KEY,
          created_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          policy_version TEXT NOT NULL,
          schema_version INTEGER NOT NULL,
          name_hash TEXT,
          case_count INTEGER NOT NULL DEFAULT 0,
          review_tier TEXT,
          status TEXT,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
          raw_financial_source_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_financial_source_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          graph_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(graph_api_call_performed = 0),
          procore_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(procore_api_call_performed = 0),
          email_send_performed INTEGER NOT NULL DEFAULT 0 CHECK(email_send_performed = 0),
          calendar_update_performed INTEGER NOT NULL DEFAULT 0 CHECK(calendar_update_performed = 0),
          source_system_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(source_system_writeback_performed = 0),
          arbitrary_sql_performed INTEGER NOT NULL DEFAULT 0 CHECK(arbitrary_sql_performed = 0),
          raw_store_access_performed INTEGER NOT NULL DEFAULT 0 CHECK(raw_store_access_performed = 0),
          financial_determination_performed INTEGER NOT NULL DEFAULT 0 CHECK(financial_determination_performed = 0),
          payment_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(payment_decision_performed = 0),
          claim_or_entitlement_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(claim_or_entitlement_decision_performed = 0),
          unsupported_claim_performed INTEGER NOT NULL DEFAULT 0 CHECK(unsupported_claim_performed = 0),
          raw_vector_content_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_vector_content_persisted = 0),
          semantic_retrieval_bypassed_policy INTEGER NOT NULL DEFAULT 0 CHECK(semantic_retrieval_bypassed_policy = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_retrieval_eval_cases (
          eval_case_id TEXT PRIMARY KEY,
          created_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          policy_version TEXT NOT NULL,
          schema_version INTEGER NOT NULL,
          eval_set_id TEXT NOT NULL,
          question_hash TEXT,
          expected_source_ref_hash TEXT,
          confidence_class TEXT,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
          raw_financial_source_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_financial_source_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          graph_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(graph_api_call_performed = 0),
          procore_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(procore_api_call_performed = 0),
          email_send_performed INTEGER NOT NULL DEFAULT 0 CHECK(email_send_performed = 0),
          calendar_update_performed INTEGER NOT NULL DEFAULT 0 CHECK(calendar_update_performed = 0),
          source_system_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(source_system_writeback_performed = 0),
          arbitrary_sql_performed INTEGER NOT NULL DEFAULT 0 CHECK(arbitrary_sql_performed = 0),
          raw_store_access_performed INTEGER NOT NULL DEFAULT 0 CHECK(raw_store_access_performed = 0),
          financial_determination_performed INTEGER NOT NULL DEFAULT 0 CHECK(financial_determination_performed = 0),
          payment_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(payment_decision_performed = 0),
          claim_or_entitlement_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(claim_or_entitlement_decision_performed = 0),
          unsupported_claim_performed INTEGER NOT NULL DEFAULT 0 CHECK(unsupported_claim_performed = 0),
          raw_vector_content_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_vector_content_persisted = 0),
          semantic_retrieval_bypassed_policy INTEGER NOT NULL DEFAULT 0 CHECK(semantic_retrieval_bypassed_policy = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_retrieval_eval_runs (
          run_id TEXT PRIMARY KEY,
          created_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          policy_version TEXT NOT NULL,
          schema_version INTEGER NOT NULL,
          eval_set_id TEXT NOT NULL,
          config_snapshot_id TEXT,
          case_count INTEGER NOT NULL DEFAULT 0,
          pass_count INTEGER NOT NULL DEFAULT 0,
          status TEXT,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
          raw_financial_source_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_financial_source_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          graph_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(graph_api_call_performed = 0),
          procore_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(procore_api_call_performed = 0),
          email_send_performed INTEGER NOT NULL DEFAULT 0 CHECK(email_send_performed = 0),
          calendar_update_performed INTEGER NOT NULL DEFAULT 0 CHECK(calendar_update_performed = 0),
          source_system_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(source_system_writeback_performed = 0),
          arbitrary_sql_performed INTEGER NOT NULL DEFAULT 0 CHECK(arbitrary_sql_performed = 0),
          raw_store_access_performed INTEGER NOT NULL DEFAULT 0 CHECK(raw_store_access_performed = 0),
          financial_determination_performed INTEGER NOT NULL DEFAULT 0 CHECK(financial_determination_performed = 0),
          payment_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(payment_decision_performed = 0),
          claim_or_entitlement_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(claim_or_entitlement_decision_performed = 0),
          unsupported_claim_performed INTEGER NOT NULL DEFAULT 0 CHECK(unsupported_claim_performed = 0),
          raw_vector_content_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_vector_content_persisted = 0),
          semantic_retrieval_bypassed_policy INTEGER NOT NULL DEFAULT 0 CHECK(semantic_retrieval_bypassed_policy = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_retrieval_benchmark_runs (
          run_id TEXT PRIMARY KEY,
          created_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          policy_version TEXT NOT NULL,
          schema_version INTEGER NOT NULL,
          eval_set_id TEXT,
          config_snapshot_id TEXT,
          metric_name TEXT,
          metric_value_label TEXT,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
          raw_financial_source_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_financial_source_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          graph_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(graph_api_call_performed = 0),
          procore_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(procore_api_call_performed = 0),
          email_send_performed INTEGER NOT NULL DEFAULT 0 CHECK(email_send_performed = 0),
          calendar_update_performed INTEGER NOT NULL DEFAULT 0 CHECK(calendar_update_performed = 0),
          source_system_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(source_system_writeback_performed = 0),
          arbitrary_sql_performed INTEGER NOT NULL DEFAULT 0 CHECK(arbitrary_sql_performed = 0),
          raw_store_access_performed INTEGER NOT NULL DEFAULT 0 CHECK(raw_store_access_performed = 0),
          financial_determination_performed INTEGER NOT NULL DEFAULT 0 CHECK(financial_determination_performed = 0),
          payment_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(payment_decision_performed = 0),
          claim_or_entitlement_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(claim_or_entitlement_decision_performed = 0),
          unsupported_claim_performed INTEGER NOT NULL DEFAULT 0 CHECK(unsupported_claim_performed = 0),
          raw_vector_content_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_vector_content_persisted = 0),
          semantic_retrieval_bypassed_policy INTEGER NOT NULL DEFAULT 0 CHECK(semantic_retrieval_bypassed_policy = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_retrieval_source_linked_proof_runs (
          run_id TEXT PRIMARY KEY,
          created_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          policy_version TEXT NOT NULL,
          schema_version INTEGER NOT NULL,
          project_key TEXT,
          checked_count INTEGER NOT NULL DEFAULT 0,
          source_linked_count INTEGER NOT NULL DEFAULT 0,
          unlinked_count INTEGER NOT NULL DEFAULT 0,
          status TEXT,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
          raw_financial_source_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_financial_source_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          graph_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(graph_api_call_performed = 0),
          procore_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(procore_api_call_performed = 0),
          email_send_performed INTEGER NOT NULL DEFAULT 0 CHECK(email_send_performed = 0),
          calendar_update_performed INTEGER NOT NULL DEFAULT 0 CHECK(calendar_update_performed = 0),
          source_system_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(source_system_writeback_performed = 0),
          arbitrary_sql_performed INTEGER NOT NULL DEFAULT 0 CHECK(arbitrary_sql_performed = 0),
          raw_store_access_performed INTEGER NOT NULL DEFAULT 0 CHECK(raw_store_access_performed = 0),
          financial_determination_performed INTEGER NOT NULL DEFAULT 0 CHECK(financial_determination_performed = 0),
          payment_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(payment_decision_performed = 0),
          claim_or_entitlement_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(claim_or_entitlement_decision_performed = 0),
          unsupported_claim_performed INTEGER NOT NULL DEFAULT 0 CHECK(unsupported_claim_performed = 0),
          raw_vector_content_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_vector_content_persisted = 0),
          semantic_retrieval_bypassed_policy INTEGER NOT NULL DEFAULT 0 CHECK(semantic_retrieval_bypassed_policy = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_retrieval_unsupported_claim_checks (
          check_id TEXT PRIMARY KEY,
          created_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          policy_version TEXT NOT NULL,
          schema_version INTEGER NOT NULL,
          run_id TEXT,
          claim_count INTEGER NOT NULL DEFAULT 0,
          unsupported_count INTEGER NOT NULL DEFAULT 0,
          status TEXT,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
          raw_financial_source_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_financial_source_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          graph_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(graph_api_call_performed = 0),
          procore_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(procore_api_call_performed = 0),
          email_send_performed INTEGER NOT NULL DEFAULT 0 CHECK(email_send_performed = 0),
          calendar_update_performed INTEGER NOT NULL DEFAULT 0 CHECK(calendar_update_performed = 0),
          source_system_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(source_system_writeback_performed = 0),
          arbitrary_sql_performed INTEGER NOT NULL DEFAULT 0 CHECK(arbitrary_sql_performed = 0),
          raw_store_access_performed INTEGER NOT NULL DEFAULT 0 CHECK(raw_store_access_performed = 0),
          financial_determination_performed INTEGER NOT NULL DEFAULT 0 CHECK(financial_determination_performed = 0),
          payment_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(payment_decision_performed = 0),
          claim_or_entitlement_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(claim_or_entitlement_decision_performed = 0),
          unsupported_claim_performed INTEGER NOT NULL DEFAULT 0 CHECK(unsupported_claim_performed = 0),
          raw_vector_content_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_vector_content_persisted = 0),
          semantic_retrieval_bypassed_policy INTEGER NOT NULL DEFAULT 0 CHECK(semantic_retrieval_bypassed_policy = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_retrieval_context_budget_runs (
          run_id TEXT PRIMARY KEY,
          created_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          policy_version TEXT NOT NULL,
          schema_version INTEGER NOT NULL,
          project_key TEXT,
          requested_token_bucket TEXT,
          assembled_chunk_count INTEGER NOT NULL DEFAULT 0,
          truncated INTEGER NOT NULL DEFAULT 0 CHECK(truncated IN (0, 1)),
          status TEXT,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
          raw_financial_source_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_financial_source_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          graph_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(graph_api_call_performed = 0),
          procore_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(procore_api_call_performed = 0),
          email_send_performed INTEGER NOT NULL DEFAULT 0 CHECK(email_send_performed = 0),
          calendar_update_performed INTEGER NOT NULL DEFAULT 0 CHECK(calendar_update_performed = 0),
          source_system_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(source_system_writeback_performed = 0),
          arbitrary_sql_performed INTEGER NOT NULL DEFAULT 0 CHECK(arbitrary_sql_performed = 0),
          raw_store_access_performed INTEGER NOT NULL DEFAULT 0 CHECK(raw_store_access_performed = 0),
          financial_determination_performed INTEGER NOT NULL DEFAULT 0 CHECK(financial_determination_performed = 0),
          payment_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(payment_decision_performed = 0),
          claim_or_entitlement_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(claim_or_entitlement_decision_performed = 0),
          unsupported_claim_performed INTEGER NOT NULL DEFAULT 0 CHECK(unsupported_claim_performed = 0),
          raw_vector_content_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_vector_content_persisted = 0),
          semantic_retrieval_bypassed_policy INTEGER NOT NULL DEFAULT 0 CHECK(semantic_retrieval_bypassed_policy = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_memory_quality_review_runs (
          run_id TEXT PRIMARY KEY,
          created_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          policy_version TEXT NOT NULL,
          schema_version INTEGER NOT NULL,
          project_key TEXT,
          reviewed_count INTEGER NOT NULL DEFAULT 0,
          flagged_count INTEGER NOT NULL DEFAULT 0,
          review_tier TEXT,
          status TEXT,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
          raw_financial_source_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_financial_source_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          graph_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(graph_api_call_performed = 0),
          procore_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(procore_api_call_performed = 0),
          email_send_performed INTEGER NOT NULL DEFAULT 0 CHECK(email_send_performed = 0),
          calendar_update_performed INTEGER NOT NULL DEFAULT 0 CHECK(calendar_update_performed = 0),
          source_system_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(source_system_writeback_performed = 0),
          arbitrary_sql_performed INTEGER NOT NULL DEFAULT 0 CHECK(arbitrary_sql_performed = 0),
          raw_store_access_performed INTEGER NOT NULL DEFAULT 0 CHECK(raw_store_access_performed = 0),
          financial_determination_performed INTEGER NOT NULL DEFAULT 0 CHECK(financial_determination_performed = 0),
          payment_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(payment_decision_performed = 0),
          claim_or_entitlement_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(claim_or_entitlement_decision_performed = 0),
          unsupported_claim_performed INTEGER NOT NULL DEFAULT 0 CHECK(unsupported_claim_performed = 0),
          raw_vector_content_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_vector_content_persisted = 0),
          semantic_retrieval_bypassed_policy INTEGER NOT NULL DEFAULT 0 CHECK(semantic_retrieval_bypassed_policy = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_memory_consolidation_candidates (
          candidate_id TEXT PRIMARY KEY,
          created_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          policy_version TEXT NOT NULL,
          schema_version INTEGER NOT NULL,
          run_id TEXT,
          source_memory_ref_hash TEXT,
          cluster_hash TEXT,
          confidence_class TEXT,
          review_tier TEXT,
          status TEXT,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
          raw_financial_source_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_financial_source_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          graph_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(graph_api_call_performed = 0),
          procore_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(procore_api_call_performed = 0),
          email_send_performed INTEGER NOT NULL DEFAULT 0 CHECK(email_send_performed = 0),
          calendar_update_performed INTEGER NOT NULL DEFAULT 0 CHECK(calendar_update_performed = 0),
          source_system_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(source_system_writeback_performed = 0),
          arbitrary_sql_performed INTEGER NOT NULL DEFAULT 0 CHECK(arbitrary_sql_performed = 0),
          raw_store_access_performed INTEGER NOT NULL DEFAULT 0 CHECK(raw_store_access_performed = 0),
          financial_determination_performed INTEGER NOT NULL DEFAULT 0 CHECK(financial_determination_performed = 0),
          payment_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(payment_decision_performed = 0),
          claim_or_entitlement_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(claim_or_entitlement_decision_performed = 0),
          unsupported_claim_performed INTEGER NOT NULL DEFAULT 0 CHECK(unsupported_claim_performed = 0),
          raw_vector_content_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_vector_content_persisted = 0),
          semantic_retrieval_bypassed_policy INTEGER NOT NULL DEFAULT 0 CHECK(semantic_retrieval_bypassed_policy = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_memory_consolidation_review_items (
          review_item_id TEXT PRIMARY KEY,
          created_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          policy_version TEXT NOT NULL,
          schema_version INTEGER NOT NULL,
          candidate_id TEXT NOT NULL,
          review_tier TEXT,
          review_status TEXT,
          decision_note_hash TEXT,
          advisory_only INTEGER NOT NULL DEFAULT 1 CHECK(advisory_only = 1),
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
          raw_financial_source_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_financial_source_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          graph_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(graph_api_call_performed = 0),
          procore_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(procore_api_call_performed = 0),
          email_send_performed INTEGER NOT NULL DEFAULT 0 CHECK(email_send_performed = 0),
          calendar_update_performed INTEGER NOT NULL DEFAULT 0 CHECK(calendar_update_performed = 0),
          source_system_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(source_system_writeback_performed = 0),
          arbitrary_sql_performed INTEGER NOT NULL DEFAULT 0 CHECK(arbitrary_sql_performed = 0),
          raw_store_access_performed INTEGER NOT NULL DEFAULT 0 CHECK(raw_store_access_performed = 0),
          financial_determination_performed INTEGER NOT NULL DEFAULT 0 CHECK(financial_determination_performed = 0),
          payment_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(payment_decision_performed = 0),
          claim_or_entitlement_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(claim_or_entitlement_decision_performed = 0),
          unsupported_claim_performed INTEGER NOT NULL DEFAULT 0 CHECK(unsupported_claim_performed = 0),
          raw_vector_content_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_vector_content_persisted = 0),
          semantic_retrieval_bypassed_policy INTEGER NOT NULL DEFAULT 0 CHECK(semantic_retrieval_bypassed_policy = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_agent_performance_feedback_runs (
          run_id TEXT PRIMARY KEY,
          created_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          policy_version TEXT NOT NULL,
          schema_version INTEGER NOT NULL,
          agent_name TEXT,
          project_key TEXT,
          signal_count INTEGER NOT NULL DEFAULT 0,
          metric_name TEXT,
          metric_value_label TEXT,
          status TEXT,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
          raw_financial_source_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_financial_source_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          graph_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(graph_api_call_performed = 0),
          procore_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(procore_api_call_performed = 0),
          email_send_performed INTEGER NOT NULL DEFAULT 0 CHECK(email_send_performed = 0),
          calendar_update_performed INTEGER NOT NULL DEFAULT 0 CHECK(calendar_update_performed = 0),
          source_system_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(source_system_writeback_performed = 0),
          arbitrary_sql_performed INTEGER NOT NULL DEFAULT 0 CHECK(arbitrary_sql_performed = 0),
          raw_store_access_performed INTEGER NOT NULL DEFAULT 0 CHECK(raw_store_access_performed = 0),
          financial_determination_performed INTEGER NOT NULL DEFAULT 0 CHECK(financial_determination_performed = 0),
          payment_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(payment_decision_performed = 0),
          claim_or_entitlement_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(claim_or_entitlement_decision_performed = 0),
          unsupported_claim_performed INTEGER NOT NULL DEFAULT 0 CHECK(unsupported_claim_performed = 0),
          raw_vector_content_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_vector_content_persisted = 0),
          semantic_retrieval_bypassed_policy INTEGER NOT NULL DEFAULT 0 CHECK(semantic_retrieval_bypassed_policy = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_phase_09_validation_runs (
          run_id TEXT PRIMARY KEY,
          created_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          policy_version TEXT NOT NULL,
          schema_version INTEGER NOT NULL,
          gate_count INTEGER NOT NULL DEFAULT 0,
          pass_count INTEGER NOT NULL DEFAULT 0,
          fail_count INTEGER NOT NULL DEFAULT 0,
          overall_status TEXT,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
          raw_financial_source_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_financial_source_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          graph_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(graph_api_call_performed = 0),
          procore_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(procore_api_call_performed = 0),
          email_send_performed INTEGER NOT NULL DEFAULT 0 CHECK(email_send_performed = 0),
          calendar_update_performed INTEGER NOT NULL DEFAULT 0 CHECK(calendar_update_performed = 0),
          source_system_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(source_system_writeback_performed = 0),
          arbitrary_sql_performed INTEGER NOT NULL DEFAULT 0 CHECK(arbitrary_sql_performed = 0),
          raw_store_access_performed INTEGER NOT NULL DEFAULT 0 CHECK(raw_store_access_performed = 0),
          financial_determination_performed INTEGER NOT NULL DEFAULT 0 CHECK(financial_determination_performed = 0),
          payment_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(payment_decision_performed = 0),
          claim_or_entitlement_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(claim_or_entitlement_decision_performed = 0),
          unsupported_claim_performed INTEGER NOT NULL DEFAULT 0 CHECK(unsupported_claim_performed = 0),
          raw_vector_content_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_vector_content_persisted = 0),
          semantic_retrieval_bypassed_policy INTEGER NOT NULL DEFAULT 0 CHECK(semantic_retrieval_bypassed_policy = 0)
        );
        """,
        "CREATE INDEX IF NOT EXISTS ix_second_brain_retrieval_vector_index_items_run_id "
        "ON second_brain_retrieval_vector_index_items(run_id);",
        "CREATE INDEX IF NOT EXISTS ix_second_brain_retrieval_vector_index_runs_project_key "
        "ON second_brain_retrieval_vector_index_runs(project_key);",
        "CREATE INDEX IF NOT EXISTS ix_second_brain_retrieval_hybrid_query_results_run_id "
        "ON second_brain_retrieval_hybrid_query_results(run_id);",
        "CREATE INDEX IF NOT EXISTS ix_second_brain_retrieval_hybrid_query_runs_project_key "
        "ON second_brain_retrieval_hybrid_query_runs(project_key);",
        "CREATE INDEX IF NOT EXISTS ix_second_brain_retrieval_eval_cases_eval_set_id "
        "ON second_brain_retrieval_eval_cases(eval_set_id);",
        "CREATE INDEX IF NOT EXISTS ix_second_brain_retrieval_eval_runs_eval_set_id "
        "ON second_brain_retrieval_eval_runs(eval_set_id);",
        "CREATE INDEX IF NOT EXISTS ix_second_brain_memory_consolidation_candidates_run_id "
        "ON second_brain_memory_consolidation_candidates(run_id);",
        "CREATE INDEX IF NOT EXISTS ix_second_brain_memory_consolidation_review_items_candidate_id "
        "ON second_brain_memory_consolidation_review_items(candidate_id);",
        "CREATE INDEX IF NOT EXISTS ix_second_brain_agent_performance_feedback_runs_project_key "
        "ON second_brain_agent_performance_feedback_runs(project_key);",
    ]

    # v39 Phase 09 review burden reduction (additive only). Three metadata-only tables for
    # the exception-based two-step review burden policy (family eligibility necessary +
    # item impact/risk decisive; high-impact beats family; financial ledger separate;
    # high-impact always summarized as clustered + totals within operator budget;
    # top_examples hash-only; 23 guard columns CHECK=0 on every row). No raw content,
    # no determinations, no writeback. The tables ship empty; used by review burden
    # marts/proofs/CLI for clustering, runs, and policy evals.
    V39_STATEMENTS: list[str] = [
        """
        CREATE TABLE IF NOT EXISTS second_brain_review_burden_runs (
          run_id TEXT PRIMARY KEY,
          created_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          policy_version TEXT NOT NULL,
          schema_version INTEGER NOT NULL,
          project_key TEXT,
          total_distinct INTEGER NOT NULL DEFAULT 0,
          auto_advisory INTEGER NOT NULL DEFAULT 0,
          batch_review INTEGER NOT NULL DEFAULT 0,
          mandatory_review INTEGER NOT NULL DEFAULT 0,
          hard_stop INTEGER NOT NULL DEFAULT 0,
          financial_raw INTEGER NOT NULL DEFAULT 0,
          financial_distinct INTEGER NOT NULL DEFAULT 0,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
          raw_financial_source_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_financial_source_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          graph_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(graph_api_call_performed = 0),
          procore_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(procore_api_call_performed = 0),
          email_send_performed INTEGER NOT NULL DEFAULT 0 CHECK(email_send_performed = 0),
          calendar_update_performed INTEGER NOT NULL DEFAULT 0 CHECK(calendar_update_performed = 0),
          source_system_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(source_system_writeback_performed = 0),
          arbitrary_sql_performed INTEGER NOT NULL DEFAULT 0 CHECK(arbitrary_sql_performed = 0),
          raw_store_access_performed INTEGER NOT NULL DEFAULT 0 CHECK(raw_store_access_performed = 0),
          financial_determination_performed INTEGER NOT NULL DEFAULT 0 CHECK(financial_determination_performed = 0),
          payment_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(payment_decision_performed = 0),
          claim_or_entitlement_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(claim_or_entitlement_decision_performed = 0),
          unsupported_claim_performed INTEGER NOT NULL DEFAULT 0 CHECK(unsupported_claim_performed = 0),
          raw_vector_content_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_vector_content_persisted = 0),
          semantic_retrieval_bypassed_policy INTEGER NOT NULL DEFAULT 0 CHECK(semantic_retrieval_bypassed_policy = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_review_burden_clusters (
          cluster_id TEXT NOT NULL,
          run_id TEXT NOT NULL,
          created_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          policy_version TEXT NOT NULL,
          schema_version INTEGER NOT NULL,
          project_key TEXT,
          source_family TEXT NOT NULL,
          impact_category TEXT NOT NULL,
          confidence_class TEXT,
          review_reason TEXT,
          item_count INTEGER NOT NULL DEFAULT 0,
          top_examples_json TEXT,
          cluster_hash TEXT,
          tier TEXT,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
          raw_financial_source_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_financial_source_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          graph_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(graph_api_call_performed = 0),
          procore_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(procore_api_call_performed = 0),
          email_send_performed INTEGER NOT NULL DEFAULT 0 CHECK(email_send_performed = 0),
          calendar_update_performed INTEGER NOT NULL DEFAULT 0 CHECK(calendar_update_performed = 0),
          source_system_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(source_system_writeback_performed = 0),
          arbitrary_sql_performed INTEGER NOT NULL DEFAULT 0 CHECK(arbitrary_sql_performed = 0),
          raw_store_access_performed INTEGER NOT NULL DEFAULT 0 CHECK(raw_store_access_performed = 0),
          financial_determination_performed INTEGER NOT NULL DEFAULT 0 CHECK(financial_determination_performed = 0),
          payment_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(payment_decision_performed = 0),
          claim_or_entitlement_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(claim_or_entitlement_decision_performed = 0),
          unsupported_claim_performed INTEGER NOT NULL DEFAULT 0 CHECK(unsupported_claim_performed = 0),
          raw_vector_content_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_vector_content_persisted = 0),
          semantic_retrieval_bypassed_policy INTEGER NOT NULL DEFAULT 0 CHECK(semantic_retrieval_bypassed_policy = 0),
          PRIMARY KEY (cluster_id, run_id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS second_brain_review_burden_policy_evals (
          eval_id TEXT PRIMARY KEY,
          created_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          policy_version TEXT NOT NULL,
          schema_version INTEGER NOT NULL,
          run_id TEXT,
          project_key TEXT,
          advisory_retrieval_allowed INTEGER NOT NULL DEFAULT 0,
          promotion_blocked_for_high INTEGER NOT NULL DEFAULT 0,
          blanket_review_block INTEGER NOT NULL DEFAULT 0,
          total_distinct INTEGER NOT NULL DEFAULT 0,
          auto_advisory INTEGER NOT NULL DEFAULT 0,
          batch_review INTEGER NOT NULL DEFAULT 0,
          mandatory_review INTEGER NOT NULL DEFAULT 0,
          hard_stop INTEGER NOT NULL DEFAULT 0,
          financial_distinct INTEGER NOT NULL DEFAULT 0,
          operator_visible INTEGER NOT NULL DEFAULT 0,
          suppressed INTEGER NOT NULL DEFAULT 0,
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
          raw_financial_source_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_financial_source_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          graph_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(graph_api_call_performed = 0),
          procore_api_call_performed INTEGER NOT NULL DEFAULT 0 CHECK(procore_api_call_performed = 0),
          email_send_performed INTEGER NOT NULL DEFAULT 0 CHECK(email_send_performed = 0),
          calendar_update_performed INTEGER NOT NULL DEFAULT 0 CHECK(calendar_update_performed = 0),
          source_system_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(source_system_writeback_performed = 0),
          arbitrary_sql_performed INTEGER NOT NULL DEFAULT 0 CHECK(arbitrary_sql_performed = 0),
          raw_store_access_performed INTEGER NOT NULL DEFAULT 0 CHECK(raw_store_access_performed = 0),
          financial_determination_performed INTEGER NOT NULL DEFAULT 0 CHECK(financial_determination_performed = 0),
          payment_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(payment_decision_performed = 0),
          claim_or_entitlement_decision_performed INTEGER NOT NULL DEFAULT 0 CHECK(claim_or_entitlement_decision_performed = 0),
          unsupported_claim_performed INTEGER NOT NULL DEFAULT 0 CHECK(unsupported_claim_performed = 0),
          raw_vector_content_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_vector_content_persisted = 0),
          semantic_retrieval_bypassed_policy INTEGER NOT NULL DEFAULT 0 CHECK(semantic_retrieval_bypassed_policy = 0)
        );
        """,
        "CREATE INDEX IF NOT EXISTS ix_second_brain_review_burden_clusters_run_id ON second_brain_review_burden_clusters(run_id);",
        "CREATE INDEX IF NOT EXISTS ix_second_brain_review_burden_runs_project_key ON second_brain_review_burden_runs(project_key);",
    ]

    # v40 FastAPI Analytics Prompt 05 / UI-05 — project keyword training registry (additive only;
    # V1–V39 untouched). Per-project operator-managed keywords for project matching explainability
    # in the CM-first analytics UI. Supports add/edit/disable/delete/excluded + strength
    # (strong/normal/weak). Standard/template folder names (Drawings, RFIs, etc.) are rejected
    # at the service layer and never stored. 8 guard CHECK columns (construction family, not
    # full Phase-09 23-guard set). Provenance tracked; notes_redacted only. Ships empty;
    # populated via /projects/{key}/keywords surfaces. FK to construction_project_identity.
    V40_STATEMENTS: list[str] = [
        """
        CREATE TABLE IF NOT EXISTS construction_project_keyword_registry (
          keyword_id TEXT PRIMARY KEY,
          project_key TEXT NOT NULL
            REFERENCES construction_project_identity(project_key),
          keyword_hash TEXT NOT NULL,
          keyword_normalized TEXT NOT NULL
            CHECK(length(keyword_normalized) BETWEEN 1 AND 128),
          keyword_class TEXT NOT NULL DEFAULT 'phrase'
            CHECK(keyword_class IN (
              'project_number','project_name','domain','alias','phrase','exclusion_pattern'
            )),
          strength TEXT NOT NULL DEFAULT 'normal'
            CHECK(strength IN ('strong','normal','weak')),
          registry_status TEXT NOT NULL DEFAULT 'enabled'
            CHECK(registry_status IN ('enabled','disabled','excluded')),
          provenance TEXT NOT NULL
            CHECK(provenance IN (
              'user_manual','seed_registry','confirmed_match',
              'import_procore','import_sharepoint','system_suggested'
            )),
          provenance_ref_hash TEXT,
          notes_redacted TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          last_applied_utc TEXT,
          -- construction-family guards (no raw content, no writeback)
          raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
          raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
          raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
          raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
          raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
          signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
          download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          UNIQUE(project_key, keyword_hash)
        );
        """,
        "CREATE INDEX IF NOT EXISTS ix_project_keyword_registry_project_status ON construction_project_keyword_registry(project_key, registry_status);",
        "CREATE INDEX IF NOT EXISTS ix_project_keyword_registry_project_strength ON construction_project_keyword_registry(project_key, strength) WHERE registry_status = 'enabled';",
    ]

    # v41 Phase 10 Local Action Intelligence — additive substrate for local model runtime,
    # AI jobs, action candidates, follow-ups, relationships, daily-brief candidates, the
    # Obsidian index, and Claude/MCP packets (V1–V40 untouched; coexists with the V42 raw
    # content tables). Every table carries the full 13 Phase-10 guard columns (no raw content,
    # no writeback). Only redacted/hashed columns are stored. Environment isolation lives on
    # ai_job_queue. The guard fragment is defined once so all 21 tables share an identical set.
    _P10_GUARDS = """,
      raw_email_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_email_body_persisted = 0),
      raw_document_text_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_document_text_persisted = 0),
      raw_calendar_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_calendar_payload_persisted = 0),
      raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted = 0),
      raw_prompt_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_prompt_persisted = 0),
      raw_response_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_response_persisted = 0),
      signed_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(signed_url_persisted = 0),
      download_url_persisted INTEGER NOT NULL DEFAULT 0 CHECK(download_url_persisted = 0),
      external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
      graph_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(graph_writeback_performed = 0),
      procore_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(procore_writeback_performed = 0),
      email_send_performed INTEGER NOT NULL DEFAULT 0 CHECK(email_send_performed = 0),
      calendar_mutation_performed INTEGER NOT NULL DEFAULT 0 CHECK(calendar_mutation_performed = 0)"""

    V41_STATEMENTS: list[str] = [
        # --- Local model runtime ---
        f"""
        CREATE TABLE IF NOT EXISTS local_model_profiles (
          profile_id TEXT PRIMARY KEY,
          provider TEXT NOT NULL,
          model_name TEXT NOT NULL,
          role TEXT NOT NULL,
          enabled INTEGER NOT NULL DEFAULT 0,
          max_context_tokens INTEGER,
          timeout_seconds INTEGER NOT NULL DEFAULT 120,
          concurrency_limit INTEGER NOT NULL DEFAULT 1,
          heavy_profile INTEGER NOT NULL DEFAULT 0,
          requires_explicit_enable INTEGER NOT NULL DEFAULT 0,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP{_P10_GUARDS}
        );
        """,
        f"""
        CREATE TABLE IF NOT EXISTS local_model_status_receipts (
          status_receipt_id TEXT PRIMARY KEY,
          provider TEXT NOT NULL,
          generated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          ready INTEGER NOT NULL DEFAULT 0,
          daemon_reachable INTEGER NOT NULL DEFAULT 0,
          profile_count INTEGER NOT NULL DEFAULT 0,
          available_profile_count INTEGER NOT NULL DEFAULT 0,
          blockers_json TEXT NOT NULL DEFAULT '[]',
          detail_json TEXT{_P10_GUARDS}
        );
        """,
        f"""
        CREATE TABLE IF NOT EXISTS local_model_run_receipts (
          model_run_receipt_id TEXT PRIMARY KEY,
          profile_id TEXT NOT NULL,
          provider TEXT NOT NULL,
          model_name TEXT NOT NULL,
          task_type TEXT NOT NULL,
          status TEXT NOT NULL,
          input_context_hash TEXT NOT NULL,
          output_hash TEXT,
          schema_name TEXT,
          schema_valid INTEGER NOT NULL DEFAULT 0,
          input_token_count INTEGER,
          output_token_count INTEGER,
          latency_ms INTEGER,
          fallback_used INTEGER NOT NULL DEFAULT 0,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP{_P10_GUARDS}
        );
        """,
        # --- AI jobs ---
        f"""
        CREATE TABLE IF NOT EXISTS ai_job_queue (
          job_id TEXT PRIMARY KEY,
          environment TEXT NOT NULL,
          job_type TEXT NOT NULL,
          status TEXT NOT NULL,
          priority INTEGER NOT NULL DEFAULT 100,
          idempotency_key TEXT NOT NULL,
          source_watermark TEXT,
          payload_json TEXT NOT NULL DEFAULT '{{}}',
          queued_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          started_utc TEXT,
          finished_utc TEXT,
          retry_count INTEGER NOT NULL DEFAULT 0,
          max_retries INTEGER NOT NULL DEFAULT 2,
          last_error_redacted TEXT{_P10_GUARDS},
          UNIQUE(environment, job_type, idempotency_key)
        );
        """,
        f"""
        CREATE TABLE IF NOT EXISTS ai_job_runs (
          run_id TEXT PRIMARY KEY,
          job_id TEXT NOT NULL REFERENCES ai_job_queue(job_id) ON DELETE CASCADE,
          run_kind TEXT NOT NULL,
          status TEXT NOT NULL,
          dry_run INTEGER NOT NULL DEFAULT 1,
          profile_id TEXT,
          started_utc TEXT NOT NULL,
          finished_utc TEXT,
          candidate_count INTEGER NOT NULL DEFAULT 0,
          accepted_count INTEGER NOT NULL DEFAULT 0,
          rejected_count INTEGER NOT NULL DEFAULT 0,
          warning_count INTEGER NOT NULL DEFAULT 0,
          blockers_json TEXT NOT NULL DEFAULT '[]'{_P10_GUARDS}
        );
        """,
        # --- Action intelligence / candidates ---
        f"""
        CREATE TABLE IF NOT EXISTS task_candidates (
          candidate_id TEXT PRIMARY KEY,
          stable_key TEXT NOT NULL UNIQUE,
          title_redacted TEXT NOT NULL,
          project_key TEXT,
          assignee_class TEXT NOT NULL,
          due_at_utc TEXT,
          urgency TEXT NOT NULL,
          waiting_state TEXT NOT NULL,
          safety_category TEXT NOT NULL,
          confidence REAL NOT NULL,
          reason_redacted TEXT,
          recommended_next_action TEXT NOT NULL,
          review_status TEXT NOT NULL DEFAULT 'pending',
          model_profile_id TEXT,
          prompt_template_version TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP{_P10_GUARDS}
        );
        """,
        f"""
        CREATE TABLE IF NOT EXISTS commitment_candidates (
          candidate_id TEXT PRIMARY KEY,
          stable_key TEXT NOT NULL UNIQUE,
          title_redacted TEXT NOT NULL,
          project_key TEXT,
          commitment_actor_class TEXT NOT NULL,
          promised_at_utc TEXT,
          due_at_utc TEXT,
          urgency TEXT NOT NULL,
          waiting_state TEXT NOT NULL,
          safety_category TEXT NOT NULL,
          confidence REAL NOT NULL,
          reason_redacted TEXT,
          recommended_next_action TEXT NOT NULL,
          review_status TEXT NOT NULL DEFAULT 'pending',
          model_profile_id TEXT,
          prompt_template_version TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP{_P10_GUARDS}
        );
        """,
        f"""
        CREATE TABLE IF NOT EXISTS candidate_source_refs (
          source_ref_id TEXT PRIMARY KEY,
          candidate_type TEXT NOT NULL,
          candidate_id TEXT NOT NULL,
          source_family TEXT NOT NULL,
          source_ref_hash TEXT NOT NULL,
          source_table TEXT,
          source_primary_key_hash TEXT,
          evidence_redacted TEXT,
          confidence REAL,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP{_P10_GUARDS}
        );
        """,
        f"""
        CREATE TABLE IF NOT EXISTS candidate_review_events (
          review_event_id TEXT PRIMARY KEY,
          candidate_type TEXT NOT NULL,
          candidate_id TEXT NOT NULL,
          action TEXT NOT NULL,
          prior_status TEXT,
          new_status TEXT,
          user_note_redacted TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP{_P10_GUARDS}
        );
        """,
        # --- Follow-ups ---
        f"""
        CREATE TABLE IF NOT EXISTS accepted_tasks (
          accepted_task_id TEXT PRIMARY KEY,
          candidate_id TEXT REFERENCES task_candidates(candidate_id),
          title_redacted TEXT NOT NULL,
          project_key TEXT,
          status TEXT NOT NULL DEFAULT 'open',
          due_at_utc TEXT,
          waiting_state TEXT NOT NULL,
          safety_category TEXT NOT NULL,
          accepted_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          completed_utc TEXT{_P10_GUARDS}
        );
        """,
        f"""
        CREATE TABLE IF NOT EXISTS accepted_commitments (
          accepted_commitment_id TEXT PRIMARY KEY,
          candidate_id TEXT REFERENCES commitment_candidates(candidate_id),
          title_redacted TEXT NOT NULL,
          project_key TEXT,
          status TEXT NOT NULL DEFAULT 'open',
          due_at_utc TEXT,
          waiting_state TEXT NOT NULL,
          safety_category TEXT NOT NULL,
          accepted_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          completed_utc TEXT{_P10_GUARDS}
        );
        """,
        f"""
        CREATE TABLE IF NOT EXISTS follow_up_watch_items (
          watch_item_id TEXT PRIMARY KEY,
          accepted_task_id TEXT,
          accepted_commitment_id TEXT,
          project_key TEXT,
          watch_status TEXT NOT NULL,
          waiting_state TEXT NOT NULL,
          next_check_utc TEXT,
          last_checked_utc TEXT,
          stale_after_utc TEXT,
          reason_redacted TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP{_P10_GUARDS}
        );
        """,
        f"""
        CREATE TABLE IF NOT EXISTS follow_up_status_events (
          status_event_id TEXT PRIMARY KEY,
          watch_item_id TEXT NOT NULL REFERENCES follow_up_watch_items(watch_item_id) ON DELETE CASCADE,
          prior_status TEXT,
          new_status TEXT NOT NULL,
          signal_type TEXT NOT NULL,
          source_ref_hash TEXT,
          evidence_redacted TEXT,
          confidence REAL,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP{_P10_GUARDS}
        );
        """,
        # --- Relationships ---
        f"""
        CREATE TABLE IF NOT EXISTS phase10_relationship_candidates (
          relationship_candidate_id TEXT PRIMARY KEY,
          from_source_family TEXT NOT NULL,
          from_source_ref_hash TEXT NOT NULL,
          to_source_family TEXT NOT NULL,
          to_source_ref_hash TEXT NOT NULL,
          relationship_type TEXT NOT NULL,
          project_key TEXT,
          confidence REAL NOT NULL,
          confidence_class TEXT NOT NULL,
          deterministic INTEGER NOT NULL DEFAULT 0,
          model_proposed INTEGER NOT NULL DEFAULT 0,
          review_status TEXT NOT NULL DEFAULT 'pending',
          reason_redacted TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP{_P10_GUARDS}
        );
        """,
        # --- Daily brief ---
        f"""
        CREATE TABLE IF NOT EXISTS daily_brief_action_candidates (
          daily_brief_action_candidate_id TEXT PRIMARY KEY,
          brief_date TEXT NOT NULL,
          section TEXT NOT NULL,
          title_redacted TEXT NOT NULL,
          project_key TEXT,
          priority INTEGER NOT NULL DEFAULT 100,
          status TEXT NOT NULL DEFAULT 'candidate',
          confidence REAL NOT NULL,
          reason_redacted TEXT,
          recommended_next_action TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP{_P10_GUARDS}
        );
        """,
        # --- Obsidian index ---
        f"""
        CREATE TABLE IF NOT EXISTS obsidian_note_index (
          note_id TEXT PRIMARY KEY,
          vault_profile TEXT NOT NULL,
          note_path_hash TEXT NOT NULL,
          note_path_redacted TEXT NOT NULL,
          title_redacted TEXT,
          note_type TEXT,
          last_modified_utc TEXT,
          indexed_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          managed_section_count INTEGER NOT NULL DEFAULT 0{_P10_GUARDS},
          UNIQUE(vault_profile, note_path_hash)
        );
        """,
        f"""
        CREATE TABLE IF NOT EXISTS obsidian_note_tag_index (
          note_tag_id TEXT PRIMARY KEY,
          note_id TEXT NOT NULL REFERENCES obsidian_note_index(note_id) ON DELETE CASCADE,
          tag TEXT NOT NULL,
          source TEXT NOT NULL,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP{_P10_GUARDS}
        );
        """,
        f"""
        CREATE TABLE IF NOT EXISTS obsidian_managed_section_registry (
          managed_section_id TEXT PRIMARY KEY,
          note_id TEXT NOT NULL REFERENCES obsidian_note_index(note_id) ON DELETE CASCADE,
          section_key TEXT NOT NULL,
          marker_start TEXT NOT NULL,
          marker_end TEXT NOT NULL,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          last_written_utc TEXT{_P10_GUARDS},
          UNIQUE(note_id, section_key)
        );
        """,
        f"""
        CREATE TABLE IF NOT EXISTS obsidian_note_update_receipts (
          update_receipt_id TEXT PRIMARY KEY,
          note_id TEXT,
          operation TEXT NOT NULL,
          mode TEXT NOT NULL CHECK(mode IN ('dry_run','apply')),
          status TEXT NOT NULL,
          content_hash TEXT,
          path_hash TEXT,
          section_key TEXT,
          changed_outside_managed_section INTEGER NOT NULL DEFAULT 0 CHECK(changed_outside_managed_section = 0),
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP{_P10_GUARDS}
        );
        """,
        # --- Claude / MCP packets ---
        f"""
        CREATE TABLE IF NOT EXISTS claude_context_packets (
          packet_id TEXT PRIMARY KEY,
          packet_type TEXT NOT NULL,
          project_key TEXT,
          packet_date TEXT,
          status TEXT NOT NULL,
          source_ref_count INTEGER NOT NULL DEFAULT 0,
          token_estimate INTEGER,
          packet_hash TEXT NOT NULL,
          output_path_redacted TEXT,
          output_path_hash TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP{_P10_GUARDS}
        );
        """,
        f"""
        CREATE TABLE IF NOT EXISTS claude_context_packet_items (
          packet_item_id TEXT PRIMARY KEY,
          packet_id TEXT NOT NULL REFERENCES claude_context_packets(packet_id) ON DELETE CASCADE,
          item_order INTEGER NOT NULL,
          item_type TEXT NOT NULL,
          title_redacted TEXT NOT NULL,
          source_ref_hash TEXT NOT NULL,
          confidence REAL,
          freshness_label TEXT,
          review_required INTEGER NOT NULL DEFAULT 0,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP{_P10_GUARDS}
        );
        """,
        # --- Indexes (additive; support later-prompt access paths) ---
        "CREATE INDEX IF NOT EXISTS ix_ai_job_queue_env_status ON ai_job_queue(environment, status);",
        "CREATE INDEX IF NOT EXISTS ix_task_candidates_review_status ON task_candidates(review_status);",
        "CREATE INDEX IF NOT EXISTS ix_commitment_candidates_review_status ON commitment_candidates(review_status);",
        "CREATE INDEX IF NOT EXISTS ix_candidate_source_refs_candidate ON candidate_source_refs(candidate_type, candidate_id);",
        "CREATE INDEX IF NOT EXISTS ix_follow_up_watch_items_status_check ON follow_up_watch_items(watch_status, next_check_utc);",
        "CREATE INDEX IF NOT EXISTS ix_daily_brief_action_candidates_date_section ON daily_brief_action_candidates(brief_date, section);",
        "CREATE INDEX IF NOT EXISTS ix_claude_context_packets_type_date ON claude_context_packets(packet_type, packet_date);",
    ]

    # v43 Phase 10A candidate review lifecycle (snooze/edit/audit). Additive
    # ADD COLUMN only on V41 candidate tables (all nullable TEXT; no CHECK — SQLite
    # cannot add CHECK via ALTER, and the 13 _P10_GUARDS already protect these rows).
    V43_STATEMENTS: list[str] = [
        # task_candidates review-lifecycle columns
        "ALTER TABLE task_candidates ADD COLUMN snoozed_until_utc TEXT",
        "ALTER TABLE task_candidates ADD COLUMN reviewed_utc TEXT",
        "ALTER TABLE task_candidates ADD COLUMN reviewed_by TEXT",
        "ALTER TABLE task_candidates ADD COLUMN review_note_redacted TEXT",
        # commitment_candidates review-lifecycle columns (mirror)
        "ALTER TABLE commitment_candidates ADD COLUMN snoozed_until_utc TEXT",
        "ALTER TABLE commitment_candidates ADD COLUMN reviewed_utc TEXT",
        "ALTER TABLE commitment_candidates ADD COLUMN reviewed_by TEXT",
        "ALTER TABLE commitment_candidates ADD COLUMN review_note_redacted TEXT",
        # candidate_review_events audit-detail columns
        "ALTER TABLE candidate_review_events ADD COLUMN changes_json_redacted TEXT",
        "ALTER TABLE candidate_review_events ADD COLUMN snoozed_until_utc TEXT",
        "ALTER TABLE candidate_review_events ADD COLUMN reviewer_ref TEXT",
        # snooze access-path indexes (mirror existing ix_*_review_status style)
        "CREATE INDEX IF NOT EXISTS ix_task_candidates_snoozed_until ON task_candidates(snoozed_until_utc);",
        "CREATE INDEX IF NOT EXISTS ix_commitment_candidates_snoozed_until ON commitment_candidates(snoozed_until_utc);",
    ]

    # v50 Phase 10 candidate cross-family lifecycle overlay (review queue / disposition /
    # merge / suppression). Additive, append-only substrate that extends — never replaces —
    # the V41/V43 per-family review status. candidate_review_events stays task/commitment-only
    # and canonical for those families; these three tables carry cross-family lifecycle that no
    # existing table can represent (merge across arbitrary subjects, group-key suppression,
    # close/reopen across daily-brief/accepted/watch). Every table carries the full 13 Phase 10
    # guard columns (no raw content, no writeback). Only redacted/hashed columns are stored.
    # No materialized review queue table: the queue is a computed read model. V1-V49 untouched.
    V50_STATEMENTS: list[str] = [
        f"""
        CREATE TABLE IF NOT EXISTS candidate_lifecycle_events (
          lifecycle_event_id TEXT PRIMARY KEY,
          idempotency_key TEXT NOT NULL UNIQUE,
          subject_type TEXT NOT NULL,
          subject_id TEXT NOT NULL,
          candidate_id TEXT,
          family TEXT,
          event_type TEXT NOT NULL,
          prior_state TEXT,
          new_state TEXT,
          reason_code TEXT,
          reason_redacted TEXT,
          effective_until_utc TEXT,
          target_subject_type TEXT,
          target_subject_id TEXT,
          duplicate_group_key TEXT,
          reviewer_ref TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP{_P10_GUARDS}
        );
        """,
        "CREATE INDEX IF NOT EXISTS ix_candidate_lifecycle_events_subject ON candidate_lifecycle_events(subject_type, subject_id, created_utc);",
        "CREATE INDEX IF NOT EXISTS ix_candidate_lifecycle_events_candidate ON candidate_lifecycle_events(candidate_id);",
        "CREATE INDEX IF NOT EXISTS ix_candidate_lifecycle_events_new_state ON candidate_lifecycle_events(new_state);",
        "CREATE INDEX IF NOT EXISTS ix_candidate_lifecycle_events_group ON candidate_lifecycle_events(duplicate_group_key);",
        "CREATE INDEX IF NOT EXISTS ix_candidate_lifecycle_events_effective ON candidate_lifecycle_events(effective_until_utc);",
        f"""
        CREATE TABLE IF NOT EXISTS candidate_merge_links (
          merge_link_id TEXT PRIMARY KEY,
          idempotency_key TEXT NOT NULL UNIQUE,
          source_subject_type TEXT NOT NULL,
          source_subject_id TEXT NOT NULL,
          target_subject_type TEXT NOT NULL,
          target_subject_id TEXT NOT NULL,
          duplicate_group_key TEXT,
          merge_reason_code TEXT NOT NULL,
          reviewer_ref TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP{_P10_GUARDS}
        );
        """,
        "CREATE INDEX IF NOT EXISTS ix_candidate_merge_links_source ON candidate_merge_links(source_subject_type, source_subject_id);",
        "CREATE INDEX IF NOT EXISTS ix_candidate_merge_links_target ON candidate_merge_links(target_subject_type, target_subject_id);",
        "CREATE INDEX IF NOT EXISTS ix_candidate_merge_links_group ON candidate_merge_links(duplicate_group_key);",
        f"""
        CREATE TABLE IF NOT EXISTS candidate_suppression_rules (
          suppression_rule_id TEXT PRIMARY KEY,
          idempotency_key TEXT NOT NULL UNIQUE,
          scope TEXT NOT NULL,
          subject_type TEXT,
          subject_id TEXT,
          duplicate_group_key TEXT,
          reason_code TEXT NOT NULL,
          reason_redacted TEXT,
          active INTEGER NOT NULL DEFAULT 1,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP{_P10_GUARDS}
        );
        """,
        "CREATE INDEX IF NOT EXISTS ix_candidate_suppression_rules_scope ON candidate_suppression_rules(scope);",
        "CREATE INDEX IF NOT EXISTS ix_candidate_suppression_rules_group ON candidate_suppression_rules(duplicate_group_key);",
        "CREATE INDEX IF NOT EXISTS ix_candidate_suppression_rules_subject ON candidate_suppression_rules(subject_type, subject_id);",
        "CREATE INDEX IF NOT EXISTS ix_candidate_suppression_rules_active ON candidate_suppression_rules(active);",
    ]

    # v51 Phase 10 Ollama-assisted candidate ranking + daily-brief assembly overlay.
    # Additive, append-only ranking/assembly read-models layered on the V41 candidate
    # projection and the V50 lifecycle overlay. CREATE IF NOT EXISTS so re-apply is a
    # no-op. V1-V50 untouched: no lifecycle semantics or render path is altered. Model
    # output is advisory only — every table carries the full 13 Phase-10 guard columns
    # (no raw content, no writeback), and only redacted/hashed columns are stored. Model
    # calls reuse the V41 local_model_run_receipts hash-only receipt; these tables store
    # only receipt ids / hashes / status metadata, never prompts or responses.
    V51_STATEMENTS: list[str] = [
        # --- Ranking run metadata (one raw-free row per ranking attempt) ---
        f"""
        CREATE TABLE IF NOT EXISTS daily_brief_ranking_runs (
          ranking_run_id TEXT PRIMARY KEY,
          brief_date TEXT NOT NULL,
          policy_version TEXT NOT NULL,
          algorithm_version TEXT NOT NULL,
          candidate_set_hash TEXT NOT NULL,
          feedback_digest_hash TEXT NOT NULL,
          model_profile_id TEXT,
          model_name TEXT,
          model_status TEXT NOT NULL,
          model_receipt_id TEXT,
          deterministic_fallback_used INTEGER NOT NULL DEFAULT 0,
          degraded_reason TEXT,
          candidate_count INTEGER NOT NULL DEFAULT 0,
          ranked_count INTEGER NOT NULL DEFAULT 0,
          source_ref_coverage REAL NOT NULL DEFAULT 0,
          usefulness_score REAL NOT NULL DEFAULT 0,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP{_P10_GUARDS}
        );
        """,
        "CREATE INDEX IF NOT EXISTS ix_daily_brief_ranking_runs_date ON daily_brief_ranking_runs(brief_date);",
        "CREATE INDEX IF NOT EXISTS ix_daily_brief_ranking_runs_model_status ON daily_brief_ranking_runs(model_status);",
        # --- Per-candidate ranking overlay for a run ---
        f"""
        CREATE TABLE IF NOT EXISTS daily_brief_ranked_candidates (
          ranking_run_id TEXT NOT NULL,
          daily_brief_action_candidate_id TEXT NOT NULL,
          rank_position INTEGER NOT NULL,
          section_key TEXT NOT NULL,
          group_key TEXT,
          duplicate_cluster_id TEXT,
          deterministic_score REAL NOT NULL,
          feedback_score REAL NOT NULL,
          model_advisory_score REAL,
          final_score REAL NOT NULL,
          why_this_matters_redacted TEXT,
          model_reason_codes_json TEXT,
          source_ref_count INTEGER NOT NULL DEFAULT 0,
          lifecycle_state_snapshot TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP{_P10_GUARDS},
          PRIMARY KEY (ranking_run_id, daily_brief_action_candidate_id)
        );
        """,
        "CREATE INDEX IF NOT EXISTS ix_daily_brief_ranked_candidates_run ON daily_brief_ranked_candidates(ranking_run_id);",
        "CREATE INDEX IF NOT EXISTS ix_daily_brief_ranked_candidates_candidate ON daily_brief_ranked_candidates(daily_brief_action_candidate_id);",
        "CREATE INDEX IF NOT EXISTS ix_daily_brief_ranked_candidates_cluster ON daily_brief_ranked_candidates(duplicate_cluster_id);",
        # --- Raw-free advisory similarity/duplicate edges (never auto-merge/suppress) ---
        f"""
        CREATE TABLE IF NOT EXISTS candidate_similarity_edges (
          similarity_edge_id TEXT PRIMARY KEY,
          brief_date TEXT NOT NULL,
          candidate_a_id TEXT NOT NULL,
          candidate_b_id TEXT NOT NULL,
          similarity_score REAL NOT NULL,
          similarity_method TEXT NOT NULL,
          cluster_id TEXT,
          deterministic_features_json TEXT,
          model_label TEXT,
          review_recommendation TEXT NOT NULL DEFAULT 'review_duplicate_candidate',
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP{_P10_GUARDS}
        );
        """,
        "CREATE INDEX IF NOT EXISTS ix_candidate_similarity_edges_date ON candidate_similarity_edges(brief_date);",
        "CREATE INDEX IF NOT EXISTS ix_candidate_similarity_edges_a ON candidate_similarity_edges(candidate_a_id);",
        "CREATE INDEX IF NOT EXISTS ix_candidate_similarity_edges_b ON candidate_similarity_edges(candidate_b_id);",
        "CREATE INDEX IF NOT EXISTS ix_candidate_similarity_edges_cluster ON candidate_similarity_edges(cluster_id);",
        # --- Assembled daily brief metadata (one row per assembly) ---
        f"""
        CREATE TABLE IF NOT EXISTS daily_brief_assembly_runs (
          assembly_run_id TEXT PRIMARY KEY,
          brief_date TEXT NOT NULL,
          ranking_run_id TEXT,
          assembly_policy_version TEXT NOT NULL,
          model_layer_status TEXT NOT NULL,
          deterministic_fallback_used INTEGER NOT NULL DEFAULT 0,
          section_count INTEGER NOT NULL DEFAULT 0,
          candidate_count INTEGER NOT NULL DEFAULT 0,
          withheld_reason TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP{_P10_GUARDS}
        );
        """,
        "CREATE INDEX IF NOT EXISTS ix_daily_brief_assembly_runs_date ON daily_brief_assembly_runs(brief_date);",
        "CREATE INDEX IF NOT EXISTS ix_daily_brief_assembly_runs_ranking ON daily_brief_assembly_runs(ranking_run_id);",
        "CREATE INDEX IF NOT EXISTS ix_daily_brief_assembly_runs_model_status ON daily_brief_assembly_runs(model_layer_status);",
        # --- Section-level raw-free candidate ordering ---
        f"""
        CREATE TABLE IF NOT EXISTS daily_brief_assembly_sections (
          assembly_run_id TEXT NOT NULL,
          section_key TEXT NOT NULL,
          display_order INTEGER NOT NULL,
          title_redacted TEXT NOT NULL,
          candidate_ids_json TEXT NOT NULL,
          section_score REAL NOT NULL DEFAULT 0,
          degraded_reason TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP{_P10_GUARDS},
          PRIMARY KEY (assembly_run_id, section_key)
        );
        """,
        "CREATE INDEX IF NOT EXISTS ix_daily_brief_assembly_sections_run ON daily_brief_assembly_sections(assembly_run_id);",
    ]

    # v52 Phase 10 daily-brief effectiveness / ranking-policy telemetry. Additive, append-only;
    # CREATE IF NOT EXISTS so re-apply is a no-op. Pure observational telemetry layered on the V41
    # candidate projection, V50 lifecycle overlay, and V51 ranking/assembly overlay — it READS those
    # and persists only raw-free counts/scores/hashes/reason codes. It mutates none of them. Every
    # table carries the identical 13 Phase-10 guard columns (no raw content, no writeback). V1-V51
    # untouched.
    V52_STATEMENTS: list[str] = [
        # --- Surfaced-item exposure proxies (derived from persisted V51 ranking/assembly rows;
        #     NOT confirmed render impressions). One raw-free row per surfaced candidate/section. ---
        f"""
        CREATE TABLE IF NOT EXISTS daily_brief_exposure_events (
          exposure_event_id TEXT PRIMARY KEY,
          brief_date TEXT NOT NULL,
          assembly_run_id TEXT,
          ranking_run_id TEXT,
          event_type TEXT NOT NULL,
          section_key TEXT,
          daily_brief_action_candidate_id TEXT,
          rank_position INTEGER,
          exposure_surface TEXT,
          policy_version TEXT,
          artifact_hash TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP{_P10_GUARDS}
        );
        """,
        "CREATE INDEX IF NOT EXISTS ix_daily_brief_exposure_events_date ON daily_brief_exposure_events(brief_date);",
        "CREATE INDEX IF NOT EXISTS ix_daily_brief_exposure_events_ranking ON daily_brief_exposure_events(ranking_run_id);",
        "CREATE INDEX IF NOT EXISTS ix_daily_brief_exposure_events_assembly ON daily_brief_exposure_events(assembly_run_id);",
        "CREATE INDEX IF NOT EXISTS ix_daily_brief_exposure_events_candidate ON daily_brief_exposure_events(daily_brief_action_candidate_id);",
        "CREATE INDEX IF NOT EXISTS ix_daily_brief_exposure_events_created ON daily_brief_exposure_events(created_utc);",
        # --- Post-brief lifecycle outcomes mapped back to exposed items (derived, never creates
        #     lifecycle events). ``ignored_lag_hours`` records the threshold used to call an item
        #     ignored (default 72h). ---
        f"""
        CREATE TABLE IF NOT EXISTS daily_brief_item_outcome_events (
          outcome_event_id TEXT PRIMARY KEY,
          brief_date TEXT NOT NULL,
          daily_brief_action_candidate_id TEXT NOT NULL,
          ranking_run_id TEXT,
          assembly_run_id TEXT,
          exposure_event_id TEXT,
          lifecycle_event_id TEXT,
          outcome_type TEXT NOT NULL,
          outcome_lag_hours REAL,
          ignored_lag_hours INTEGER NOT NULL DEFAULT 72,
          rank_position INTEGER,
          section_key TEXT,
          candidate_family TEXT,
          project_key TEXT,
          source_ref_count INTEGER NOT NULL DEFAULT 0,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP{_P10_GUARDS}
        );
        """,
        "CREATE INDEX IF NOT EXISTS ix_daily_brief_item_outcome_events_date ON daily_brief_item_outcome_events(brief_date);",
        "CREATE INDEX IF NOT EXISTS ix_daily_brief_item_outcome_events_candidate ON daily_brief_item_outcome_events(daily_brief_action_candidate_id);",
        "CREATE INDEX IF NOT EXISTS ix_daily_brief_item_outcome_events_type ON daily_brief_item_outcome_events(outcome_type);",
        "CREATE INDEX IF NOT EXISTS ix_daily_brief_item_outcome_events_created ON daily_brief_item_outcome_events(created_utc);",
        # --- Ranking-policy evaluation runs over a brief-date window (observational only) ---
        f"""
        CREATE TABLE IF NOT EXISTS ranking_policy_eval_runs (
          eval_run_id TEXT PRIMARY KEY,
          window_start TEXT NOT NULL,
          window_end TEXT NOT NULL,
          policy_version TEXT,
          eval_mode TEXT NOT NULL,
          ranking_algorithm_version TEXT,
          assembly_policy_version TEXT,
          model_profile_id TEXT,
          model_name TEXT,
          feedback_calibration_version TEXT,
          ignored_lag_hours INTEGER NOT NULL DEFAULT 72,
          candidate_count INTEGER NOT NULL DEFAULT 0,
          outcome_count INTEGER NOT NULL DEFAULT 0,
          source_ref_coverage REAL,
          brief_usefulness_score REAL,
          rank_outcome_score REAL,
          model_degradation_rate REAL,
          procore_noise_score REAL,
          sample_sufficient INTEGER NOT NULL DEFAULT 0,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP{_P10_GUARDS}
        );
        """,
        "CREATE INDEX IF NOT EXISTS ix_ranking_policy_eval_runs_window ON ranking_policy_eval_runs(window_start, window_end);",
        "CREATE INDEX IF NOT EXISTS ix_ranking_policy_eval_runs_policy ON ranking_policy_eval_runs(policy_version);",
        "CREATE INDEX IF NOT EXISTS ix_ranking_policy_eval_runs_mode ON ranking_policy_eval_runs(eval_mode);",
        "CREATE INDEX IF NOT EXISTS ix_ranking_policy_eval_runs_created ON ranking_policy_eval_runs(created_utc);",
        # --- Per-candidate evaluation facts for a policy eval run ---
        f"""
        CREATE TABLE IF NOT EXISTS ranking_policy_eval_items (
          eval_run_id TEXT NOT NULL,
          daily_brief_action_candidate_id TEXT NOT NULL,
          rank_position INTEGER,
          section_key TEXT,
          candidate_family TEXT,
          source_family TEXT,
          project_key TEXT,
          deterministic_score REAL,
          feedback_score REAL,
          model_advisory_score REAL,
          final_score REAL,
          model_advisory_used INTEGER NOT NULL DEFAULT 0,
          outcome_type TEXT,
          outcome_weight REAL,
          outcome_lag_hours REAL,
          source_ref_count INTEGER NOT NULL DEFAULT 0,
          eval_notes_json TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP{_P10_GUARDS},
          PRIMARY KEY (eval_run_id, daily_brief_action_candidate_id)
        );
        """,
        "CREATE INDEX IF NOT EXISTS ix_ranking_policy_eval_items_run ON ranking_policy_eval_items(eval_run_id);",
        "CREATE INDEX IF NOT EXISTS ix_ranking_policy_eval_items_candidate ON ranking_policy_eval_items(daily_brief_action_candidate_id);",
        "CREATE INDEX IF NOT EXISTS ix_ranking_policy_eval_items_family ON ranking_policy_eval_items(candidate_family);",
        # --- Aggregate local-model profile reliability/utility (receipt metadata only) ---
        f"""
        CREATE TABLE IF NOT EXISTS model_profile_eval_results (
          model_profile_eval_id TEXT PRIMARY KEY,
          window_start TEXT NOT NULL,
          window_end TEXT NOT NULL,
          task_type TEXT,
          model_profile_id TEXT,
          model_name TEXT,
          attempt_count INTEGER NOT NULL DEFAULT 0,
          success_count INTEGER NOT NULL DEFAULT 0,
          schema_invalid_count INTEGER NOT NULL DEFAULT 0,
          safety_withheld_count INTEGER NOT NULL DEFAULT 0,
          timeout_count INTEGER NOT NULL DEFAULT 0,
          unknown_alias_count INTEGER NOT NULL DEFAULT 0,
          lifecycle_excluded_ref_count INTEGER NOT NULL DEFAULT 0,
          fallback_count INTEGER NOT NULL DEFAULT 0,
          avg_latency_ms REAL,
          p95_latency_ms REAL,
          advisory_adoption_proxy REAL,
          model_degradation_rate REAL,
          sample_sufficient INTEGER NOT NULL DEFAULT 0,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP{_P10_GUARDS}
        );
        """,
        "CREATE INDEX IF NOT EXISTS ix_model_profile_eval_results_window ON model_profile_eval_results(window_start, window_end);",
        "CREATE INDEX IF NOT EXISTS ix_model_profile_eval_results_profile ON model_profile_eval_results(model_profile_id);",
        "CREATE INDEX IF NOT EXISTS ix_model_profile_eval_results_created ON model_profile_eval_results(created_utc);",
        # --- Raw-free daily/window/project/family/source/model trend rollups ---
        f"""
        CREATE TABLE IF NOT EXISTS brief_effectiveness_rollups (
          rollup_id TEXT PRIMARY KEY,
          scope TEXT NOT NULL,
          scope_key TEXT NOT NULL,
          window_start TEXT NOT NULL,
          window_end TEXT NOT NULL,
          policy_version TEXT,
          brief_count INTEGER NOT NULL DEFAULT 0,
          candidate_count INTEGER NOT NULL DEFAULT 0,
          outcome_count INTEGER NOT NULL DEFAULT 0,
          accepted_rate REAL,
          rejected_rate REAL,
          snoozed_rate REAL,
          ignored_rate REAL,
          brief_usefulness_score REAL,
          rank_outcome_score REAL,
          source_ref_coverage REAL,
          procore_noise_score REAL,
          model_degradation_rate REAL,
          duplicate_precision_proxy REAL,
          feedback_calibration_lift REAL,
          sample_sufficient INTEGER NOT NULL DEFAULT 0,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP{_P10_GUARDS}
        );
        """,
        "CREATE INDEX IF NOT EXISTS ix_brief_effectiveness_rollups_scope ON brief_effectiveness_rollups(scope, scope_key);",
        "CREATE INDEX IF NOT EXISTS ix_brief_effectiveness_rollups_window ON brief_effectiveness_rollups(window_start, window_end);",
        "CREATE INDEX IF NOT EXISTS ix_brief_effectiveness_rollups_created ON brief_effectiveness_rollups(created_utc);",
    ]

    # v54 Phase 10 (252) "New Today" overnight change digest. Additive, append-only; CREATE IF NOT
    # EXISTS so re-apply is a no-op. One raw-free, source-linked business-event row per New Today item
    # (deterministic facts authoritative; redacted/title-only columns; advisory model receipt is
    # hash-only via model_run_receipt_id) + a hash-only source-ref child table. V1-V53 untouched.
    V54_STATEMENTS: list[str] = [
        f"""
        CREATE TABLE IF NOT EXISTS daily_brief_change_events (
          change_event_id TEXT PRIMARY KEY,
          brief_date TEXT NOT NULL,
          refresh_window_start_utc TEXT,
          refresh_window_end_utc TEXT,
          source_family TEXT NOT NULL,
          source_record_id TEXT,
          source_ref_count INTEGER NOT NULL DEFAULT 0,
          project_key TEXT,
          project_display_name TEXT,
          actor_display_name TEXT,
          actor_company TEXT,
          event_type TEXT,
          event_timestamp_utc TEXT,
          business_record_type TEXT,
          business_record_number TEXT,
          business_record_title_redacted TEXT,
          business_record_status TEXT,
          amount TEXT,
          due_date TEXT,
          meeting_start_utc TEXT,
          meeting_end_utc TEXT,
          meeting_location_or_mode TEXT,
          summary_text TEXT,
          why_it_matters TEXT,
          recommended_action TEXT,
          attention_class TEXT NOT NULL,
          confidence REAL,
          enrichment_status TEXT NOT NULL DEFAULT 'deterministic',
          model_profile_id TEXT,
          model_name TEXT,
          model_run_receipt_id TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP{_P10_GUARDS}
        );
        """,
        "CREATE INDEX IF NOT EXISTS ix_daily_brief_change_events_date ON daily_brief_change_events(brief_date);",
        "CREATE INDEX IF NOT EXISTS ix_daily_brief_change_events_family ON daily_brief_change_events(source_family);",
        "CREATE INDEX IF NOT EXISTS ix_daily_brief_change_events_attention ON daily_brief_change_events(attention_class);",
        "CREATE INDEX IF NOT EXISTS ix_daily_brief_change_events_created ON daily_brief_change_events(created_utc);",
        f"""
        CREATE TABLE IF NOT EXISTS daily_brief_change_event_refs (
          change_event_id TEXT NOT NULL,
          source_table TEXT NOT NULL,
          source_ref_hash TEXT NOT NULL,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP{_P10_GUARDS},
          PRIMARY KEY (change_event_id, source_table, source_ref_hash)
        );
        """,
        "CREATE INDEX IF NOT EXISTS ix_daily_brief_change_event_refs_event ON daily_brief_change_event_refs(change_event_id);",
    ]

    # v55 Procore Budget Detail Rows endpoint-specific forecasting read model.
    # Additive only. These tables intentionally mirror the existing procore_ep_budget_*
    # metadata/hash/timestamp/guard conventions while adding queryable common amount
    # fields and normalized dynamic cell values for tenant/view-specific columns.
    V55_STATEMENTS: list[str] = [
        """
        CREATE TABLE IF NOT EXISTS procore_ep_budget_detail_rows (
          record_key TEXT PRIMARY KEY,
          raw_payload_id TEXT,
          endpoint_key TEXT NOT NULL,
          endpoint_family TEXT,
          project_key TEXT,
          project_id TEXT,
          project_id_hash TEXT,
          company_id TEXT,
          company_id_hash TEXT,
          record_id TEXT NOT NULL,
          record_id_hash TEXT,
          parent_record_id TEXT,
          parent_record_id_hash TEXT,
          budget_view_id TEXT,
          budget_row_id TEXT,
          row_id TEXT,
          wbs_code_id TEXT,
          wbs_flat_code TEXT,
          budget_code TEXT,
          canonical_budget_code_key TEXT,
          cost_code_id TEXT,
          cost_code TEXT,
          cost_type_id TEXT,
          cost_type TEXT,
          line_item_type_id TEXT,
          description TEXT,
          original_budget_amount TEXT,
          revised_budget TEXT,
          approved_change_orders TEXT,
          pending_budget_changes TEXT,
          projected_budget TEXT,
          committed_costs TEXT,
          direct_costs TEXT,
          actual_cost TEXT,
          projected_costs TEXT,
          forecast_to_complete TEXT,
          estimated_cost_at_completion TEXT,
          projected_over_under TEXT,
          erp_job_to_date_costs TEXT,
          payload_sidecar_json TEXT,
          payload_hash TEXT,
          source_quality TEXT NOT NULL,
          payload_seen_first_utc TEXT,
          payload_seen_last_utc TEXT,
          is_current INTEGER NOT NULL DEFAULT 1 CHECK(is_current IN (0, 1)),
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          raw_payload_emitted_to_read_model INTEGER NOT NULL DEFAULT 0 CHECK(raw_payload_emitted_to_read_model = 0),
          raw_payload_emitted_to_evidence INTEGER NOT NULL DEFAULT 0 CHECK(raw_payload_emitted_to_evidence = 0),
          FOREIGN KEY(raw_payload_id) REFERENCES procore_endpoint_raw_payloads(raw_payload_id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS procore_ep_budget_detail_row_cells (
          cell_key TEXT PRIMARY KEY,
          record_key TEXT NOT NULL,
          raw_payload_id TEXT,
          endpoint_key TEXT NOT NULL,
          endpoint_family TEXT,
          project_key TEXT,
          project_id TEXT,
          project_id_hash TEXT,
          company_id TEXT,
          company_id_hash TEXT,
          budget_view_id TEXT,
          budget_row_id TEXT,
          row_id TEXT,
          column_id TEXT,
          column_key TEXT,
          column_name TEXT,
          column_label TEXT,
          field_path TEXT,
          value_text TEXT,
          value_decimal_text TEXT,
          currency_iso_code TEXT,
          value_json TEXT,
          payload_hash TEXT,
          source_quality TEXT NOT NULL,
          is_current INTEGER NOT NULL DEFAULT 1 CHECK(is_current IN (0, 1)),
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          raw_payload_emitted_to_read_model INTEGER NOT NULL DEFAULT 0 CHECK(raw_payload_emitted_to_read_model = 0),
          raw_payload_emitted_to_evidence INTEGER NOT NULL DEFAULT 0 CHECK(raw_payload_emitted_to_evidence = 0),
          FOREIGN KEY(record_key) REFERENCES procore_ep_budget_detail_rows(record_key),
          FOREIGN KEY(raw_payload_id) REFERENCES procore_endpoint_raw_payloads(raw_payload_id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS procore_ep_budget_detail_columns (
          record_key TEXT PRIMARY KEY,
          raw_payload_id TEXT,
          endpoint_key TEXT NOT NULL,
          endpoint_family TEXT,
          project_key TEXT,
          project_id TEXT,
          project_id_hash TEXT,
          company_id TEXT,
          company_id_hash TEXT,
          record_id TEXT NOT NULL,
          record_id_hash TEXT,
          parent_record_id TEXT,
          parent_record_id_hash TEXT,
          budget_view_id TEXT,
          column_id TEXT,
          column_key TEXT,
          name TEXT,
          label TEXT,
          data_type TEXT,
          field_path TEXT,
          position TEXT,
          visible TEXT,
          payload_sidecar_json TEXT,
          payload_hash TEXT,
          source_quality TEXT NOT NULL,
          payload_seen_first_utc TEXT,
          payload_seen_last_utc TEXT,
          is_current INTEGER NOT NULL DEFAULT 1 CHECK(is_current IN (0, 1)),
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          raw_payload_emitted_to_read_model INTEGER NOT NULL DEFAULT 0 CHECK(raw_payload_emitted_to_read_model = 0),
          raw_payload_emitted_to_evidence INTEGER NOT NULL DEFAULT 0 CHECK(raw_payload_emitted_to_evidence = 0),
          FOREIGN KEY(raw_payload_id) REFERENCES procore_endpoint_raw_payloads(raw_payload_id)
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_procore_ep_budget_detail_rows_project_key ON procore_ep_budget_detail_rows(project_key);",
        "CREATE INDEX IF NOT EXISTS idx_procore_ep_budget_detail_rows_endpoint_key ON procore_ep_budget_detail_rows(endpoint_key);",
        "CREATE INDEX IF NOT EXISTS idx_procore_ep_budget_detail_rows_raw_payload_id ON procore_ep_budget_detail_rows(raw_payload_id);",
        "CREATE INDEX IF NOT EXISTS idx_procore_ep_budget_detail_rows_record_id ON procore_ep_budget_detail_rows(record_id);",
        "CREATE INDEX IF NOT EXISTS idx_procore_ep_budget_detail_rows_parent_record_id ON procore_ep_budget_detail_rows(parent_record_id);",
        "CREATE INDEX IF NOT EXISTS idx_procore_ep_budget_detail_rows_budget_view_id ON procore_ep_budget_detail_rows(budget_view_id);",
        "CREATE INDEX IF NOT EXISTS idx_procore_ep_budget_detail_rows_wbs_flat_code ON procore_ep_budget_detail_rows(wbs_flat_code);",
        "CREATE INDEX IF NOT EXISTS idx_procore_ep_budget_detail_rows_canonical_key ON procore_ep_budget_detail_rows(canonical_budget_code_key);",
        "CREATE INDEX IF NOT EXISTS idx_procore_ep_budget_detail_rows_cost_code_id ON procore_ep_budget_detail_rows(cost_code_id);",
        "CREATE INDEX IF NOT EXISTS idx_procore_ep_budget_detail_rows_current_quality ON procore_ep_budget_detail_rows(is_current, source_quality);",
        "CREATE INDEX IF NOT EXISTS idx_procore_ep_budget_detail_row_cells_record_key ON procore_ep_budget_detail_row_cells(record_key);",
        "CREATE INDEX IF NOT EXISTS idx_procore_ep_budget_detail_row_cells_project_key ON procore_ep_budget_detail_row_cells(project_key);",
        "CREATE INDEX IF NOT EXISTS idx_procore_ep_budget_detail_row_cells_budget_view_id ON procore_ep_budget_detail_row_cells(budget_view_id);",
        "CREATE INDEX IF NOT EXISTS idx_procore_ep_budget_detail_row_cells_column_name ON procore_ep_budget_detail_row_cells(column_name);",
        "CREATE INDEX IF NOT EXISTS idx_procore_ep_budget_detail_row_cells_field_path ON procore_ep_budget_detail_row_cells(field_path);",
        "CREATE INDEX IF NOT EXISTS idx_procore_ep_budget_detail_row_cells_current_quality ON procore_ep_budget_detail_row_cells(is_current, source_quality);",
        "CREATE INDEX IF NOT EXISTS idx_procore_ep_budget_detail_columns_project_key ON procore_ep_budget_detail_columns(project_key);",
        "CREATE INDEX IF NOT EXISTS idx_procore_ep_budget_detail_columns_endpoint_key ON procore_ep_budget_detail_columns(endpoint_key);",
        "CREATE INDEX IF NOT EXISTS idx_procore_ep_budget_detail_columns_raw_payload_id ON procore_ep_budget_detail_columns(raw_payload_id);",
        "CREATE INDEX IF NOT EXISTS idx_procore_ep_budget_detail_columns_record_id ON procore_ep_budget_detail_columns(record_id);",
        "CREATE INDEX IF NOT EXISTS idx_procore_ep_budget_detail_columns_parent_record_id ON procore_ep_budget_detail_columns(parent_record_id);",
        "CREATE INDEX IF NOT EXISTS idx_procore_ep_budget_detail_columns_budget_view_id ON procore_ep_budget_detail_columns(budget_view_id);",
        "CREATE INDEX IF NOT EXISTS idx_procore_ep_budget_detail_columns_name ON procore_ep_budget_detail_columns(name);",
        "CREATE INDEX IF NOT EXISTS idx_procore_ep_budget_detail_columns_field_path ON procore_ep_budget_detail_columns(field_path);",
        "CREATE INDEX IF NOT EXISTS idx_procore_ep_budget_detail_columns_current_quality ON procore_ep_budget_detail_columns(is_current, source_quality);",
    ]

    # v56 Add explicit ERP-direct and JTD amount columns for Budget Detail Rows.
    # Values are promoted only from deterministic numeric payload/cell values by
    # the read-model projector; raw dynamic cells remain preserved separately.
    V56_STATEMENTS: list[str] = [
        "ALTER TABLE procore_ep_budget_detail_rows ADD COLUMN erp_direct_costs TEXT;",
        "ALTER TABLE procore_ep_budget_detail_rows ADD COLUMN job_to_date_costs TEXT;",
    ]

    # v57 Add newly observed Change Event budget-modification impact fields.
    # Projection tables store raw projected payload scalars as nullable TEXT,
    # including neighboring amount fields in procore_ep_change_events_change_items.
    V57_STATEMENTS: list[str] = [
        "ALTER TABLE procore_ep_change_events_change_items ADD COLUMN budget_impact_budget_modification_amount TEXT;",
        "ALTER TABLE procore_ep_change_events_change_items ADD COLUMN budget_impact_budget_modification_budget_modification_id TEXT;",
        "ALTER TABLE procore_ep_change_events_change_items ADD COLUMN budget_impact_budget_modification_notes TEXT;",
        "ALTER TABLE procore_ep_change_events_change_items ADD COLUMN budget_impact_budget_modification_transfer_from_id TEXT;",
        "ALTER TABLE procore_ep_change_events_change_items ADD COLUMN budget_impact_budget_modification_transfer_from_name TEXT;",
        "ALTER TABLE procore_ep_change_events_change_items ADD COLUMN budget_impact_budget_modification_transfer_to_id TEXT;",
        "ALTER TABLE procore_ep_change_events_change_items ADD COLUMN budget_impact_budget_modification_transfer_to_name TEXT;",
    ]

    # v58 Forecast DB-transition FOUNDATION schema (construction-financial-review).
    # Additive, local-only, body-free. This first transition migration intentionally
    # lands ONLY the five lineage/foundation tables — project identity, run registry,
    # source-file ingestions, package/run manifests, and validation events. Downstream
    # forecast-domain tables (budget/cost/owner/controls/schedule/staffing/stage outputs/
    # final-CSV source) are deferred to later additive migrations (v59+) once projection
    # and read-repository requirements are concrete. Common lineage columns
    # (project_key, source_package, source_sha256, run_id, created_utc) recur by design
    # so every later domain row can be traced to a run and a hashed source.
    V58_STATEMENTS: list[str] = [
        # Project identity / registry.
        """
        CREATE TABLE IF NOT EXISTS forecast_projects (
          project_key TEXT PRIMARY KEY,
          project_name TEXT,
          job_number TEXT,
          enabled INTEGER NOT NULL DEFAULT 1,
          created_utc TEXT NOT NULL,
          updated_utc TEXT
        );
        """,
        # Run registry: one row per full-fresh forecast run; the single source that
        # later replaces latest-glob / config-pin context resolution.
        """
        CREATE TABLE IF NOT EXISTS forecast_runs (
          run_id TEXT PRIMARY KEY,
          project_key TEXT NOT NULL,
          context_package TEXT,
          status TEXT NOT NULL DEFAULT 'pending',
          notes TEXT,
          created_utc TEXT NOT NULL
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_forecast_runs_project_created ON forecast_runs(project_key, created_utc);",
        # One row per landed upstream source file (TWN / owner extracts, etc.).
        """
        CREATE TABLE IF NOT EXISTS forecast_source_ingestions (
          ingestion_id TEXT PRIMARY KEY,
          project_key TEXT NOT NULL,
          run_id TEXT,
          source_kind TEXT NOT NULL,
          source_package TEXT,
          source_path TEXT,
          source_sha256 TEXT,
          row_count INTEGER,
          created_utc TEXT NOT NULL,
          UNIQUE (project_key, source_package, source_sha256)
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_forecast_source_ingestions_project_kind ON forecast_source_ingestions(project_key, source_kind);",
        "CREATE INDEX IF NOT EXISTS idx_forecast_source_ingestions_run ON forecast_source_ingestions(run_id);",
        # Package / run manifests: DB analog of manifest.json + input_inventory.json.
        """
        CREATE TABLE IF NOT EXISTS forecast_package_manifests (
          package_id TEXT PRIMARY KEY,
          project_key TEXT NOT NULL,
          run_id TEXT,
          package_type TEXT NOT NULL,
          package_name TEXT NOT NULL,
          package_stamp TEXT,
          upstream_packages TEXT,
          source_data_hashes TEXT,
          row_counts TEXT,
          validation_passed INTEGER,
          validation_conclusion TEXT,
          file_path TEXT,
          created_utc TEXT NOT NULL,
          UNIQUE (package_name)
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_forecast_package_manifests_project_type ON forecast_package_manifests(project_key, package_type);",
        "CREATE INDEX IF NOT EXISTS idx_forecast_package_manifests_run ON forecast_package_manifests(run_id);",
        # Per-run validation / audit events (append-only gate results).
        """
        CREATE TABLE IF NOT EXISTS forecast_validation_events (
          run_id TEXT NOT NULL,
          event_seq INTEGER NOT NULL,
          project_key TEXT NOT NULL,
          gate_name TEXT NOT NULL,
          status TEXT NOT NULL,
          detail TEXT,
          created_utc TEXT NOT NULL,
          PRIMARY KEY (run_id, event_seq)
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_forecast_validation_events_project ON forecast_validation_events(project_key, gate_name);",
    ]

    # v59 Forecast DB-transition SOURCE-DOMAIN slice (Phase 3). Three additive tables
    # projecting the TWN cost-forecast JSONL source rows (BudgetDetails, CostEntries,
    # monthly actuals by budget code) so selected source data can be read back from
    # SQLite in the same shape as the JSONL rows (DB read-parity proof). Each table keeps
    # the exact original row in ``raw_json`` (authoritative for parity) plus extracted
    # key/lineage columns for indexing. The same lineage columns recur (project_key,
    # source_package, source_path, source_sha256, source_row_number, run_id) so every
    # source-domain row traces to a run and a hashed source. Forecast reads stay
    # file-backed; these tables are intentionally empty until projection is applied.
    V59_STATEMENTS: list[str] = [
        # BudgetDetails canonical source rows (one per budget_code_key per package).
        """
        CREATE TABLE IF NOT EXISTS forecast_budget_details (
          project_key TEXT NOT NULL,
          budget_code_key TEXT NOT NULL,
          source_package TEXT NOT NULL,
          cost_code TEXT,
          category TEXT,
          source_path TEXT,
          source_sha256 TEXT,
          source_row_number INTEGER,
          run_id TEXT,
          raw_json TEXT NOT NULL,
          created_utc TEXT NOT NULL,
          updated_utc TEXT,
          PRIMARY KEY (project_key, budget_code_key, source_package)
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_forecast_budget_details_project ON forecast_budget_details(project_key);",
        "CREATE INDEX IF NOT EXISTS idx_forecast_budget_details_code ON forecast_budget_details(budget_code_key);",
        "CREATE INDEX IF NOT EXISTS idx_forecast_budget_details_package ON forecast_budget_details(source_package);",
        # CostEntries source rows — no business key, so a deterministic cost_entry_id is
        # derived from (project_key|source_package|source_row_number); UNIQUE on the same
        # triple keeps re-projection idempotent without collapsing distinct rows.
        """
        CREATE TABLE IF NOT EXISTS forecast_cost_entries (
          cost_entry_id TEXT PRIMARY KEY,
          project_key TEXT NOT NULL,
          source_package TEXT NOT NULL,
          source_row_number INTEGER NOT NULL,
          budget_code_key TEXT,
          accounting_month TEXT,
          source_path TEXT,
          source_sha256 TEXT,
          run_id TEXT,
          raw_json TEXT NOT NULL,
          created_utc TEXT NOT NULL,
          updated_utc TEXT,
          UNIQUE (project_key, source_package, source_row_number)
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_forecast_cost_entries_project ON forecast_cost_entries(project_key);",
        "CREATE INDEX IF NOT EXISTS idx_forecast_cost_entries_code ON forecast_cost_entries(budget_code_key);",
        "CREATE INDEX IF NOT EXISTS idx_forecast_cost_entries_package ON forecast_cost_entries(source_package);",
        # Monthly actuals by budget code. ``type`` is part of the natural key (repo-truth
        # correction over the 4-tuple) so a budget_code_key/month carrying more than one
        # row-type cannot collapse.
        """
        CREATE TABLE IF NOT EXISTS forecast_monthly_actuals_by_budget_code (
          project_key TEXT NOT NULL,
          budget_code_key TEXT NOT NULL,
          month TEXT NOT NULL,
          type TEXT NOT NULL,
          source_package TEXT NOT NULL,
          amount REAL,
          entry_count INTEGER,
          source_path TEXT,
          source_sha256 TEXT,
          source_row_number INTEGER,
          run_id TEXT,
          raw_json TEXT NOT NULL,
          created_utc TEXT NOT NULL,
          updated_utc TEXT,
          PRIMARY KEY (project_key, budget_code_key, month, type, source_package)
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_forecast_monthly_actuals_project ON forecast_monthly_actuals_by_budget_code(project_key);",
        "CREATE INDEX IF NOT EXISTS idx_forecast_monthly_actuals_code ON forecast_monthly_actuals_by_budget_code(budget_code_key);",
        "CREATE INDEX IF NOT EXISTS idx_forecast_monthly_actuals_package ON forecast_monthly_actuals_by_budget_code(source_package);",
        "CREATE INDEX IF NOT EXISTS idx_forecast_monthly_actuals_month ON forecast_monthly_actuals_by_budget_code(month);",
    ]

    # v60 Forecast CONFIG REGISTRY slice (Phase 16): four additive governed-config
    # tables (sources, items, snapshots, snapshot_items) holding the operator-approved
    # forecast config (project / controls / model_controls / staffing / crosswalk) as
    # raw+canonical JSON with effective/status metadata, immutable run-usable snapshots,
    # and snapshot membership. Additive CREATE TABLE IF NOT EXISTS only; intentionally
    # empty until config is imported; existing forecast behavior remains file-backed.
    V60_STATEMENTS: list[str] = [
        # One row per imported config source file / logical config source.
        """
        CREATE TABLE IF NOT EXISTS forecast_config_sources (
          config_source_id TEXT PRIMARY KEY,
          project_key TEXT NOT NULL,
          config_domain TEXT NOT NULL,
          config_name TEXT NOT NULL,
          source_path TEXT NOT NULL,
          source_format TEXT NOT NULL,
          source_sha256 TEXT NOT NULL,
          content_sha256 TEXT NOT NULL,
          row_count INTEGER NOT NULL,
          imported_at_utc TEXT NOT NULL,
          import_run_id TEXT NOT NULL,
          is_active INTEGER NOT NULL DEFAULT 1,
          created_utc TEXT NOT NULL,
          updated_utc TEXT NOT NULL,
          UNIQUE (project_key, config_domain, config_name, content_sha256)
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_forecast_config_sources_project ON forecast_config_sources(project_key);",
        "CREATE INDEX IF NOT EXISTS idx_forecast_config_sources_domain ON forecast_config_sources(config_domain);",
        "CREATE INDEX IF NOT EXISTS idx_forecast_config_sources_name ON forecast_config_sources(config_name);",
        # One row per config item/record (JSON object, JSONL line, or CSV row).
        """
        CREATE TABLE IF NOT EXISTS forecast_config_items (
          config_item_id TEXT PRIMARY KEY,
          config_source_id TEXT NOT NULL,
          project_key TEXT NOT NULL,
          config_domain TEXT NOT NULL,
          config_name TEXT NOT NULL,
          item_key TEXT NOT NULL,
          item_order INTEGER NOT NULL,
          effective_from TEXT,
          effective_to TEXT,
          status TEXT NOT NULL DEFAULT 'active',
          raw_json TEXT NOT NULL,
          canonical_json_sha256 TEXT NOT NULL,
          created_utc TEXT NOT NULL,
          updated_utc TEXT NOT NULL,
          FOREIGN KEY (config_source_id) REFERENCES forecast_config_sources(config_source_id),
          UNIQUE (project_key, config_domain, config_name, item_key, canonical_json_sha256)
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_forecast_config_items_source ON forecast_config_items(config_source_id);",
        "CREATE INDEX IF NOT EXISTS idx_forecast_config_items_project ON forecast_config_items(project_key);",
        "CREATE INDEX IF NOT EXISTS idx_forecast_config_items_domain ON forecast_config_items(config_domain);",
        "CREATE INDEX IF NOT EXISTS idx_forecast_config_items_name ON forecast_config_items(config_name);",
        "CREATE INDEX IF NOT EXISTS idx_forecast_config_items_status ON forecast_config_items(status);",
        # Immutable run-usable config snapshot header.
        """
        CREATE TABLE IF NOT EXISTS forecast_config_snapshots (
          config_snapshot_id TEXT PRIMARY KEY,
          project_key TEXT NOT NULL,
          snapshot_name TEXT NOT NULL,
          snapshot_created_utc TEXT NOT NULL,
          snapshot_reason TEXT NOT NULL,
          source_mode TEXT NOT NULL,
          item_count INTEGER NOT NULL,
          snapshot_sha256 TEXT NOT NULL,
          created_by TEXT,
          created_utc TEXT NOT NULL,
          UNIQUE (project_key, snapshot_name, snapshot_sha256)
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_forecast_config_snapshots_project ON forecast_config_snapshots(project_key);",
        "CREATE INDEX IF NOT EXISTS idx_forecast_config_snapshots_name ON forecast_config_snapshots(snapshot_name);",
        # Immutable list of items included in a snapshot.
        """
        CREATE TABLE IF NOT EXISTS forecast_config_snapshot_items (
          config_snapshot_id TEXT NOT NULL,
          config_item_id TEXT NOT NULL,
          project_key TEXT NOT NULL,
          config_domain TEXT NOT NULL,
          config_name TEXT NOT NULL,
          item_key TEXT NOT NULL,
          item_order INTEGER NOT NULL,
          raw_json TEXT NOT NULL,
          canonical_json_sha256 TEXT NOT NULL,
          PRIMARY KEY (config_snapshot_id, config_item_id),
          FOREIGN KEY (config_snapshot_id) REFERENCES forecast_config_snapshots(config_snapshot_id),
          FOREIGN KEY (config_item_id) REFERENCES forecast_config_items(config_item_id)
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_forecast_config_snapshot_items_snapshot ON forecast_config_snapshot_items(config_snapshot_id);",
        "CREATE INDEX IF NOT EXISTS idx_forecast_config_snapshot_items_project ON forecast_config_snapshot_items(project_key);",
        "CREATE INDEX IF NOT EXISTS idx_forecast_config_snapshot_items_domain ON forecast_config_snapshot_items(config_domain);",
    ]

    # v61 Forecast EXTERNAL-FORECAST EVALUATION slice (Phase 4): eight additive tables
    # giving the forecasting product a first-class representation of operator-supplied
    # external forecasts (Excel/CSV upload) and their evaluation against baselines —
    # never silently mixed with backend model forecasts (forecast_origin discriminator:
    # external rows are 'external', backend rows are 'model'). Additive CREATE TABLE IF
    # NOT EXISTS only; intentionally empty on the live DB until an external forecast is
    # imported (real rows are written only to an isolated per-run eval SQLite under the
    # eval-root, never the live DB). Forecast model reads remain file-backed.
    V61_STATEMENTS: list[str] = [
        # One row per uploaded/imported external forecast (header + file fingerprint).
        """
        CREATE TABLE IF NOT EXISTS forecast_external_forecasts (
          external_forecast_id TEXT PRIMARY KEY,
          project_key TEXT NOT NULL,
          source_system TEXT NOT NULL,
          forecast_origin TEXT NOT NULL DEFAULT 'external',
          period TEXT NOT NULL,
          source_filename TEXT NOT NULL,
          file_sha256 TEXT NOT NULL,
          content_sha256 TEXT NOT NULL,
          byte_count INTEGER NOT NULL,
          row_count INTEGER NOT NULL,
          import_run_id TEXT NOT NULL,
          imported_at_utc TEXT NOT NULL,
          created_utc TEXT NOT NULL,
          UNIQUE (project_key, period, content_sha256)
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_forecast_external_forecasts_project ON forecast_external_forecasts(project_key);",
        "CREATE INDEX IF NOT EXISTS idx_forecast_external_forecasts_period ON forecast_external_forecasts(period);",
        "CREATE INDEX IF NOT EXISTS idx_forecast_external_forecasts_source ON forecast_external_forecasts(source_system);",
        # One row per external-forecast line item (cost code x month value/EAC/remaining).
        """
        CREATE TABLE IF NOT EXISTS forecast_external_forecast_rows (
          external_forecast_row_id TEXT PRIMARY KEY,
          external_forecast_id TEXT NOT NULL,
          project_key TEXT NOT NULL,
          budget_code_key TEXT NOT NULL,
          month TEXT,
          value TEXT,
          eac TEXT,
          remaining TEXT,
          confidence TEXT,
          notes TEXT,
          row_order INTEGER NOT NULL,
          created_utc TEXT NOT NULL,
          FOREIGN KEY (external_forecast_id) REFERENCES forecast_external_forecasts(external_forecast_id)
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_forecast_external_rows_forecast ON forecast_external_forecast_rows(external_forecast_id);",
        "CREATE INDEX IF NOT EXISTS idx_forecast_external_rows_project ON forecast_external_forecast_rows(project_key);",
        "CREATE INDEX IF NOT EXISTS idx_forecast_external_rows_code ON forecast_external_forecast_rows(budget_code_key);",
        # Raw label -> canonical budget-code/month mapping with confidence + status.
        """
        CREATE TABLE IF NOT EXISTS forecast_external_forecast_mappings (
          external_forecast_mapping_id TEXT PRIMARY KEY,
          external_forecast_id TEXT NOT NULL,
          project_key TEXT NOT NULL,
          raw_label TEXT NOT NULL,
          canonical_budget_code_key TEXT,
          canonical_month TEXT,
          mapping_confidence TEXT,
          mapping_status TEXT NOT NULL DEFAULT 'unmapped',
          created_utc TEXT NOT NULL,
          FOREIGN KEY (external_forecast_id) REFERENCES forecast_external_forecasts(external_forecast_id)
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_forecast_external_mappings_forecast ON forecast_external_forecast_mappings(external_forecast_id);",
        "CREATE INDEX IF NOT EXISTS idx_forecast_external_mappings_project ON forecast_external_forecast_mappings(project_key);",
        "CREATE INDEX IF NOT EXISTS idx_forecast_external_mappings_status ON forecast_external_forecast_mappings(mapping_status);",
        # Accuracy metric per (external forecast x baseline x metric).
        """
        CREATE TABLE IF NOT EXISTS forecast_accuracy_results (
          accuracy_result_id TEXT PRIMARY KEY,
          external_forecast_id TEXT NOT NULL,
          project_key TEXT NOT NULL,
          baseline TEXT NOT NULL,
          metric TEXT NOT NULL,
          metric_value TEXT NOT NULL,
          sample_n INTEGER NOT NULL,
          created_utc TEXT NOT NULL,
          FOREIGN KEY (external_forecast_id) REFERENCES forecast_external_forecasts(external_forecast_id)
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_forecast_accuracy_results_forecast ON forecast_accuracy_results(external_forecast_id);",
        "CREATE INDEX IF NOT EXISTS idx_forecast_accuracy_results_project ON forecast_accuracy_results(project_key);",
        "CREATE INDEX IF NOT EXISTS idx_forecast_accuracy_results_baseline ON forecast_accuracy_results(baseline);",
        # Per code x baseline comparison (external vs baseline gap, absolute + percent).
        """
        CREATE TABLE IF NOT EXISTS forecast_comparison_results (
          comparison_result_id TEXT PRIMARY KEY,
          external_forecast_id TEXT NOT NULL,
          project_key TEXT NOT NULL,
          budget_code_key TEXT NOT NULL,
          baseline TEXT NOT NULL,
          external_value TEXT,
          baseline_value TEXT,
          gap_absolute TEXT,
          gap_percent TEXT,
          created_utc TEXT NOT NULL,
          FOREIGN KEY (external_forecast_id) REFERENCES forecast_external_forecasts(external_forecast_id)
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_forecast_comparison_results_forecast ON forecast_comparison_results(external_forecast_id);",
        "CREATE INDEX IF NOT EXISTS idx_forecast_comparison_results_project ON forecast_comparison_results(project_key);",
        "CREATE INDEX IF NOT EXISTS idx_forecast_comparison_results_code ON forecast_comparison_results(budget_code_key);",
        "CREATE INDEX IF NOT EXISTS idx_forecast_comparison_results_baseline ON forecast_comparison_results(baseline);",
        # Deterministic anomaly findings with severity + evidence.
        """
        CREATE TABLE IF NOT EXISTS forecast_anomaly_findings (
          anomaly_finding_id TEXT PRIMARY KEY,
          external_forecast_id TEXT NOT NULL,
          project_key TEXT NOT NULL,
          budget_code_key TEXT,
          flag_code TEXT NOT NULL,
          severity TEXT NOT NULL,
          evidence_json TEXT NOT NULL,
          created_utc TEXT NOT NULL,
          FOREIGN KEY (external_forecast_id) REFERENCES forecast_external_forecasts(external_forecast_id)
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_forecast_anomaly_findings_forecast ON forecast_anomaly_findings(external_forecast_id);",
        "CREATE INDEX IF NOT EXISTS idx_forecast_anomaly_findings_project ON forecast_anomaly_findings(project_key);",
        "CREATE INDEX IF NOT EXISTS idx_forecast_anomaly_findings_severity ON forecast_anomaly_findings(severity);",
        # Human-review queue items derived from anomalies / material gaps.
        """
        CREATE TABLE IF NOT EXISTS forecast_review_items (
          review_item_id TEXT PRIMARY KEY,
          external_forecast_id TEXT NOT NULL,
          project_key TEXT NOT NULL,
          budget_code_key TEXT,
          reason_code TEXT NOT NULL,
          severity TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'open',
          detail TEXT,
          created_utc TEXT NOT NULL,
          FOREIGN KEY (external_forecast_id) REFERENCES forecast_external_forecasts(external_forecast_id)
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_forecast_review_items_forecast ON forecast_review_items(external_forecast_id);",
        "CREATE INDEX IF NOT EXISTS idx_forecast_review_items_project ON forecast_review_items(project_key);",
        "CREATE INDEX IF NOT EXISTS idx_forecast_review_items_status ON forecast_review_items(status);",
        # Evidence-package ledger (one row per emitted evaluation package).
        """
        CREATE TABLE IF NOT EXISTS forecast_evidence_packages (
          evidence_package_id TEXT PRIMARY KEY,
          external_forecast_id TEXT NOT NULL,
          project_key TEXT NOT NULL,
          package_kind TEXT NOT NULL,
          manifest_sha256 TEXT NOT NULL,
          file_count INTEGER NOT NULL,
          created_utc TEXT NOT NULL,
          FOREIGN KEY (external_forecast_id) REFERENCES forecast_external_forecasts(external_forecast_id),
          UNIQUE (project_key, manifest_sha256)
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_forecast_evidence_packages_forecast ON forecast_evidence_packages(external_forecast_id);",
        "CREATE INDEX IF NOT EXISTS idx_forecast_evidence_packages_project ON forecast_evidence_packages(project_key);",
    ]

    # v62 Schedule Intelligence substrate: canonical schedule activities, file imports,
    # relationships/WBS/calendars/codes/UDFs, quality/diff, and operator-controlled cost
    # mapping. Additive CREATE TABLE IF NOT EXISTS only; intentionally empty until import
    # or Procore sync projection. SQLite is the source of truth after operator commit.
    @staticmethod
    def _v62_statements() -> list[str]:
        from hb_assistant.store.schedule_tables import V62_STATEMENTS

        return V62_STATEMENTS

    # v63 Forecast run-output family: the model run's own results (header + per-code
    # recommendations, risks, monthly/probability/changes/exposure/staffing/phasing/
    # narratives). Additive CREATE TABLE IF NOT EXISTS only; ships empty and is populated
    # only by the read-only output projector into a temp DB, never the live DB. Distinct
    # from the v61 external-forecast-evaluation tables.
    @staticmethod
    def _v63_statements() -> list[str]:
        from hb_assistant.store.forecast_output_tables import V63_STATEMENTS

        return V63_STATEMENTS

    @staticmethod
    def _v64_statements() -> list[str]:
        from hb_assistant.store.schedule_quality_tables import V64_STATEMENTS

        return V64_STATEMENTS

    # v66 Forecast decision-support family: per-run maturity snapshot, data-availability
    # profiles, method eligibility, confidence scorecards + factors, operator/required
    # assumptions. Additive CREATE TABLE IF NOT EXISTS only; populated only by the read-only
    # decision-support engine into a temp DB, never the live DB. (v65 is the schedule
    # derived-finish-float migration; decision-support follows it as v66.)
    @staticmethod
    def _v66_statements() -> list[str]:
        from hb_assistant.store.forecast_decision_support_tables import V66_STATEMENTS

        return V66_STATEMENTS

    # v72 Forecast model-registry (remediation P6, Gap 6): per-run model-version provenance —
    # estimator order / reliability weights / thresholds / backtest-cohort (forecast_model_versions),
    # the per-run methodology in effect (forecast_run_model_versions), and per-method calibration
    # provenance (forecast_calibration_weights). Additive CREATE TABLE IF NOT EXISTS only; populated
    # only by the read-only governance path into a temp DB, never the live DB.
    @staticmethod
    def _v72_statements() -> list[str]:
        from hb_assistant.store.forecast_model_registry_tables import V72_STATEMENTS

        return V72_STATEMENTS

    # v73 Forecast generation-request contract (Phase P-C): durable per-attempt request ledger —
    # selected project, optional forecast start/cut-off dates (+ cut-off basis), generation mode +
    # generator kind, readiness snapshot, request-contract validation state, and run linkage.
    # Additive CREATE TABLE IF NOT EXISTS only; populated at runtime by the generation routes.
    @staticmethod
    def _v73_statements() -> list[str]:
        from hb_assistant.store.forecast_generation_requests_tables import V73_STATEMENTS

        return V73_STATEMENTS

    # v74 Forecast monthly-matrix: operator month-window fields on the request ledger + immutable
    # output header, value_type/source_status classification on the sparse monthly cells, and the
    # table-ready per-row matrix + dense per-month total row. Column adds are applied only when absent
    # (idempotent under the schedule self-heal re-apply, which can leave columns present while the v74
    # row is missing); the backfill + CREATEs are idempotent. Populated at runtime by the DB-native
    # generation/persistence path.
    def _apply_v74_forecast_monthly_matrix(self, conn: sqlite3.Connection) -> None:
        from hb_assistant.store.forecast_output_matrix_tables import (
            V74_BACKFILL_STATEMENTS,
            V74_COLUMN_ADDITIONS,
            V74_CREATE_STATEMENTS,
        )

        for table, columns in V74_COLUMN_ADDITIONS:
            try:
                existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            except sqlite3.OperationalError:
                continue
            if not existing:
                continue
            for name, decl in columns:
                if name not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")
        for stmt in V74_BACKFILL_STATEMENTS:
            conn.execute(stmt)
        for stmt in V74_CREATE_STATEMENTS:
            conn.execute(stmt)

    # v75 Schedule import health foundation: additive package manifest, source capability,
    # baseline entity/evidence, crosswalk, baseline fact, and persisted diff-fact tables.
    @staticmethod
    def _v75_statements() -> list[str]:
        from hb_assistant.store.schedule_import_health_tables import V75_STATEMENTS

        return V75_STATEMENTS

    # v76 Project Staffing foundation (Phase 1, schema + seed only): holiday calendar family,
    # per-project staffing config/assumptions/absences, global templates + versions,
    # forecast-only staffing cost codes, attribution rules/review, normalized staffing-actuals
    # projection, and per-run staffing snapshots; plus additive staffing metadata columns on the
    # v74 matrix-row table. The default company holiday calendar (2026-2040) is seeded. All
    # CREATEs / column adds are idempotent (column-existence-guarded) and the holiday seed uses
    # INSERT OR IGNORE, so the whole apply is self-heal safe; only the schema_migrations row is
    # guarded. Repositories/services/API/UI and forecast-generation wiring land in later phases.
    def _apply_v76_project_staffing(self, conn: sqlite3.Connection, now: str) -> None:
        from hb_assistant.construction.analytics.staffing_holiday_calendar import (
            ensure_default_company_holiday_calendar,
        )
        from hb_assistant.store.forecast_staffing_tables import (
            V76_COLUMN_ADDITIONS,
            V76_CREATE_STATEMENTS,
        )

        for stmt in V76_CREATE_STATEMENTS:
            conn.execute(stmt)
        for table, columns in V76_COLUMN_ADDITIONS:
            try:
                existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            except sqlite3.OperationalError:
                continue
            if not existing:
                continue
            for name, decl in columns:
                if name not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")
        ensure_default_company_holiday_calendar(conn, now=now)

    # v77 Schedule identity foundation: additive canonical schedule identity
    # and committed-version identity match evidence.
    @staticmethod
    def _v77_statements() -> list[str]:
        from hb_assistant.store.schedule_identity_tables import V77_STATEMENTS

        return V77_STATEMENTS

    # v78 Schedule identity manual review/action audit foundation.
    @staticmethod
    def _v78_statements() -> list[str]:
        from hb_assistant.store.schedule_identity_tables import V78_STATEMENTS

        return V78_STATEMENTS

    # v79 Detailed schedule version diff facts.
    @staticmethod
    def _v79_statements() -> list[str]:
        from hb_assistant.store.schedule_diff_detail_tables import V79_STATEMENTS

        return V79_STATEMENTS

    # v80 Schedule impact intelligence: rollups derived from V79 detail facts.
    @staticmethod
    def _v80_statements() -> list[str]:
        from hb_assistant.store.schedule_diff_impact_tables import V80_STATEMENTS

        return V80_STATEMENTS

    # v81 Project Staffing attribution reshape: the V76 attribution_rules / review_items tables
    # were person-centric (employee_name_* NOT NULL), but real cost-entry data has no per-person
    # identity, so attribution keys on cost_code + category. Both tables ship empty -> drop+recreate
    # to the new shape. Destructive + count-neutral, so this is guarded to run ONCE (only when the
    # v81 row is absent) and ABORTS if either table somehow holds rows (no silent data loss).
    def _apply_v81_attribution_reshape(self, conn: sqlite3.Connection) -> None:
        from hb_assistant.store.forecast_staffing_tables import (
            V81_CREATE_STATEMENTS,
            V81_DROP_STATEMENTS,
            V81_RESHAPE_TABLES,
        )

        for table in V81_RESHAPE_TABLES:
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except sqlite3.OperationalError:
                count = 0  # table absent on a partial DB; CREATE below establishes the new shape
            if count:
                raise StaffingMigrationError(
                    f"refusing to reshape non-empty {table} ({count} rows); "
                    "an explicit data migration is required"
                )
        for stmt in V81_DROP_STATEMENTS:
            conn.execute(stmt)
        for stmt in V81_CREATE_STATEMENTS:
            conn.execute(stmt)

    # v82 Unified schedule package assembly: field lineage + equivalence facts.
    @staticmethod
    def _v82_statements() -> list[str]:
        from hb_assistant.store.schedule_import_health_tables import V80_STATEMENTS

        return V80_STATEMENTS

    # v83 CPM graph diagnostics foundation: additive run + diagnostic tables.
    @staticmethod
    def _v83_statements() -> list[str]:
        from hb_assistant.store.schedule_cpm_tables import V83_STATEMENTS

        return V83_STATEMENTS

    # v84 CPM forward pass foundation: additive result tables + run-metadata columns.
    @staticmethod
    def _v84_statements() -> list[str]:
        from hb_assistant.store.schedule_cpm_tables import V84_STATEMENTS

        return V84_STATEMENTS

    @staticmethod
    def _reconcile_v84_schedule_cpm_run_columns(conn: sqlite3.Connection) -> None:
        """Additively add forward-pass metadata columns to schedule_cpm_runs.

        ALTER TABLE ADD COLUMN is not IF NOT EXISTS in SQLite, so guard on PRAGMA
        table_info and add only the missing columns. Safe to re-run / self-heal.
        """
        from hb_assistant.store.schedule_cpm_tables import V84_RUNS_ADDITIVE_COLUMNS

        try:
            existing = {row[1] for row in conn.execute("PRAGMA table_info(schedule_cpm_runs)")}
        except sqlite3.OperationalError:
            return
        if not existing:
            return
        for column, decl in V84_RUNS_ADDITIVE_COLUMNS.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE schedule_cpm_runs ADD COLUMN {column} {decl}")

    @staticmethod
    def _reconcile_v85_schedule_cpm_backward_columns(conn: sqlite3.Connection) -> None:
        """Additively add backward-pass columns to the shared CPM result/run tables.

        Column-existence-guarded (ALTER ADD COLUMN is not IF NOT EXISTS in SQLite) so this
        is safe to re-run / self-heal. No new tables; table_count is unchanged.
        """
        from hb_assistant.store.schedule_cpm_tables import (
            V85_ACTIVITY_RESULTS_COLUMNS,
            V85_RELATIONSHIP_RESULTS_COLUMNS,
            V85_RUNS_COLUMNS,
        )

        for table, columns in (
            ("schedule_cpm_activity_results", V85_ACTIVITY_RESULTS_COLUMNS),
            ("schedule_cpm_relationship_results", V85_RELATIONSHIP_RESULTS_COLUMNS),
            ("schedule_cpm_runs", V85_RUNS_COLUMNS),
        ):
            try:
                existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            except sqlite3.OperationalError:
                continue
            if not existing:
                continue
            for column, decl in columns.items():
                if column not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")

    @staticmethod
    def _reconcile_v86_schedule_cpm_float_columns(conn: sqlite3.Connection) -> None:
        """Additively add float columns to the shared CPM result/run tables.

        Column-existence-guarded so it is safe to re-run / self-heal. No new tables;
        table_count is unchanged.
        """
        from hb_assistant.store.schedule_cpm_tables import (
            V86_ACTIVITY_RESULTS_COLUMNS,
            V86_RELATIONSHIP_RESULTS_COLUMNS,
            V86_RUNS_COLUMNS,
        )

        for table, columns in (
            ("schedule_cpm_activity_results", V86_ACTIVITY_RESULTS_COLUMNS),
            ("schedule_cpm_relationship_results", V86_RELATIONSHIP_RESULTS_COLUMNS),
            ("schedule_cpm_runs", V86_RUNS_COLUMNS),
        ):
            try:
                existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            except sqlite3.OperationalError:
                continue
            if not existing:
                continue
            for column, decl in columns.items():
                if column not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")

    # v87 CPM longest path foundation: TWO new path tables + run-summary columns.
    @staticmethod
    def _v87_statements() -> list[str]:
        from hb_assistant.store.schedule_cpm_tables import V87_STATEMENTS

        return V87_STATEMENTS

    @staticmethod
    def _reconcile_v87_schedule_cpm_path_run_columns(conn: sqlite3.Connection) -> None:
        """Additively add longest-path summary columns to schedule_cpm_runs.

        Column-existence-guarded so it is safe to re-run / self-heal.
        """
        from hb_assistant.store.schedule_cpm_tables import V87_RUNS_COLUMNS

        try:
            existing = {row[1] for row in conn.execute("PRAGMA table_info(schedule_cpm_runs)")}
        except sqlite3.OperationalError:
            return
        if not existing:
            return
        for column, decl in V87_RUNS_COLUMNS.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE schedule_cpm_runs ADD COLUMN {column} {decl}")

    # v44 Phase 10 Graph drive-item modified-by raw operational metadata.
    # Additive ADD COLUMN only on construction_drive_items; raw identity JSON is
    # local SQLite operational metadata and must not be emitted in committed evidence.
    V44_STATEMENTS: list[str] = [
        "ALTER TABLE construction_drive_items ADD COLUMN parent_folder_name TEXT",
        "ALTER TABLE construction_drive_items ADD COLUMN last_modified_by_display_name TEXT",
        "ALTER TABLE construction_drive_items ADD COLUMN last_modified_by_user_id TEXT",
        "ALTER TABLE construction_drive_items ADD COLUMN last_modified_by_email TEXT",
        "ALTER TABLE construction_drive_items ADD COLUMN last_modified_by_application_display_name TEXT",
        "ALTER TABLE construction_drive_items ADD COLUMN last_modified_by_raw_json TEXT",
    ]

    # v45 Phase 10 Email Follow-Up Raw Enrichment — additive, review-safe enrichment table.
    # Persists ONLY structured/redacted model-enriched follow-up fields + hashes + source refs
    # derived from a bounded, sanitized, NON-persisted local raw email window. Carries the full
    # 13 Phase-10 guard columns (CHECK = 0): no raw body, prompt, response, HTML, URL, token, or
    # secret ever lands here. ``raw_excerpt_hash`` / ``input_context_hash`` / ``output_hash`` /
    # ``email_thread_ref_hash`` are SHA-256[:12] hashes only. ``prompt_template_version`` mirrors the
    # existing task_candidates/local_model_run_receipts metadata column (template version string only,
    # never a raw prompt). V1-V44 untouched.
    V45_STATEMENTS: list[str] = [
        f"""
        CREATE TABLE IF NOT EXISTS email_followup_enrichments (
          enrichment_id TEXT PRIMARY KEY,
          idempotency_key TEXT NOT NULL UNIQUE,
          source_candidate_id TEXT NOT NULL,
          source_candidate_type TEXT NOT NULL,
          watch_item_id TEXT,
          email_thread_ref_hash TEXT,
          email_message_ref_hashes_json TEXT NOT NULL DEFAULT '[]',
          raw_excerpt_hash TEXT NOT NULL,
          enriched_title TEXT NOT NULL,
          waiting_state TEXT NOT NULL,
          assignee_type TEXT NOT NULL,
          assignee_display TEXT,
          suggested_next_action TEXT,
          due_at_utc TEXT,
          confidence REAL NOT NULL,
          confidence_band TEXT,
          reason_codes_json TEXT NOT NULL DEFAULT '[]',
          source_refs_json TEXT NOT NULL DEFAULT '[]',
          review_status TEXT NOT NULL DEFAULT 'pending',
          model_task TEXT NOT NULL DEFAULT 'email_followup_raw_enrichment',
          model_profile_id TEXT,
          prompt_template_version TEXT NOT NULL,
          input_context_hash TEXT NOT NULL,
          output_hash TEXT NOT NULL,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP{_P10_GUARDS}
        );
        """,
        "CREATE INDEX IF NOT EXISTS ix_email_followup_enrichments_candidate "
        "ON email_followup_enrichments(source_candidate_id);",
        "CREATE INDEX IF NOT EXISTS ix_email_followup_enrichments_watch_item "
        "ON email_followup_enrichments(watch_item_id);",
        "CREATE INDEX IF NOT EXISTS ix_email_followup_enrichments_review_status "
        "ON email_followup_enrichments(review_status);",
        "CREATE INDEX IF NOT EXISTS ix_email_followup_enrichments_waiting_state "
        "ON email_followup_enrichments(waiting_state);",
        "CREATE INDEX IF NOT EXISTS ix_email_followup_enrichments_created_utc "
        "ON email_followup_enrichments(created_utc);",
    ]

    # v46 Procore structured analytics foundation. Additive only. Raw landing
    # enables replay, while endpoint-family procore_raw_* bronze tables are the
    # acceptance gate for future analytics.
    _V46_STRUCTURED_TABLES: tuple[str, ...] = (
        "procore_raw_rfis",
        "procore_raw_rfi_responses",
        "procore_raw_submittals",
        "procore_raw_submittal_responses",
        "procore_raw_submittal_packages",
        "procore_raw_observations",
        "procore_raw_punch_items",
        "procore_raw_meetings",
        "procore_raw_meeting_details",
        "procore_raw_meeting_topics",
        "procore_raw_daily_logs",
        "procore_raw_inspections",
        "procore_raw_inspection_sections",
        "procore_raw_inspection_items",
        "procore_raw_schedules",
        "procore_raw_schedule_activities",
        "procore_raw_contracts",
        "procore_raw_contract_line_items",
        "procore_raw_change_orders",
        "procore_raw_change_order_line_items",
        "procore_raw_billing_periods",
        "procore_raw_invoices",
        "procore_raw_invoice_items",
        "procore_raw_payment_applications",
        "procore_raw_rfqs",
        "procore_raw_rfq_responses",
        "procore_raw_change_events",
        "procore_raw_change_event_comments",
        "procore_raw_budget_views",
        "procore_raw_budget_columns",
        "procore_raw_budget_rows",
        "procore_raw_budget_changes",
        "procore_raw_budget_change_line_items",
        "procore_raw_budget_modifications",
        "procore_raw_attachments",
        "procore_raw_project_dimensions",
        "procore_raw_company_dimensions",
        "procore_raw_person_dimensions",
        "procore_raw_cost_code_dimensions",
        "procore_raw_location_dimensions",
        "procore_raw_status_dimensions",
        "procore_raw_date_dimensions",
    )

    _V46_STRUCTURED_TABLE_DDL = [
        f"""
        CREATE TABLE IF NOT EXISTS {table} (
          record_key TEXT PRIMARY KEY,
          raw_payload_id TEXT,
          source_ref_hash TEXT NOT NULL,
          endpoint_key TEXT NOT NULL,
          endpoint_family TEXT NOT NULL,
          company_id TEXT,
          company_id_hash TEXT,
          project_id TEXT,
          project_id_hash TEXT,
          project_key TEXT,
          record_id TEXT NOT NULL,
          record_id_hash TEXT NOT NULL,
          parent_record_id TEXT,
          parent_record_id_hash TEXT,
          record_number TEXT,
          title_redacted TEXT,
          status TEXT,
          current_state TEXT,
          owner_name TEXT,
          assignee_name TEXT,
          responsible_party_name TEXT,
          due_at_utc TEXT,
          start_at_utc TEXT,
          finish_at_utc TEXT,
          business_date TEXT,
          cost_code TEXT,
          cost_type TEXT,
          amount TEXT,
          currency TEXT,
          quantity TEXT,
          unit_of_measure TEXT,
          source_updated_at_utc TEXT,
          payload_captured_at_utc TEXT,
          payload_seen_first_utc TEXT,
          payload_seen_last_utc TEXT,
          payload_hash TEXT NOT NULL,
          raw_payload_linked INTEGER NOT NULL DEFAULT 0 CHECK(raw_payload_linked IN (0, 1)),
          is_current INTEGER NOT NULL DEFAULT 1 CHECK(is_current IN (0, 1)),
          source_quality TEXT NOT NULL,
          analytics_eligible INTEGER NOT NULL DEFAULT 1 CHECK(analytics_eligible IN (0, 1)),
          daily_brief_eligible INTEGER NOT NULL DEFAULT 0 CHECK(daily_brief_eligible IN (0, 1)),
          security_scrub_status TEXT NOT NULL DEFAULT 'scrubbed',
          retention_class TEXT NOT NULL DEFAULT 'local_analytics',
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          raw_payload_emitted_to_read_model INTEGER NOT NULL DEFAULT 0 CHECK(raw_payload_emitted_to_read_model = 0),
          raw_payload_emitted_to_evidence INTEGER NOT NULL DEFAULT 0 CHECK(raw_payload_emitted_to_evidence = 0),
          FOREIGN KEY(raw_payload_id) REFERENCES procore_endpoint_raw_payloads(raw_payload_id)
        );
        """
        for table in _V46_STRUCTURED_TABLES
    ]

    _V46_STRUCTURED_INDEX_DDL = [
        stmt
        for table in _V46_STRUCTURED_TABLES
        for stmt in (
            f"CREATE INDEX IF NOT EXISTS ix_{table}_endpoint_project ON {table}(endpoint_key, project_key);",
            f"CREATE INDEX IF NOT EXISTS ix_{table}_project_status ON {table}(project_key, status);",
            f"CREATE INDEX IF NOT EXISTS ix_{table}_project_date ON {table}(project_key, business_date);",
            f"CREATE INDEX IF NOT EXISTS ix_{table}_source_ref ON {table}(source_ref_hash);",
            f"CREATE INDEX IF NOT EXISTS ix_{table}_raw_payload ON {table}(raw_payload_id);",
        )
    ]

    V46_STATEMENTS: list[str] = [
        """
        CREATE TABLE IF NOT EXISTS procore_endpoint_contracts (
          endpoint_key TEXT PRIMARY KEY,
          endpoint_family TEXT NOT NULL,
          endpoint_version TEXT NOT NULL DEFAULT 'legacy_v1',
          path_template TEXT NOT NULL,
          response_envelope TEXT NOT NULL,
          record_id_field TEXT NOT NULL,
          parent_record_id_field TEXT,
          required_path_params_json TEXT NOT NULL DEFAULT '[]',
          raw_landing_table TEXT NOT NULL DEFAULT 'procore_endpoint_raw_payloads',
          structured_table TEXT,
          live_verified INTEGER NOT NULL DEFAULT 0 CHECK(live_verified IN (0, 1)),
          analytics_eligible INTEGER NOT NULL DEFAULT 0 CHECK(analytics_eligible IN (0, 1)),
          daily_brief_eligible INTEGER NOT NULL DEFAULT 0 CHECK(daily_brief_eligible IN (0, 1)),
          sensitivity TEXT NOT NULL,
          retention_class TEXT NOT NULL DEFAULT 'local_analytics',
          no_writeback_posture TEXT NOT NULL DEFAULT 'local_read_only',
          defer_reason TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS procore_endpoint_capture_runs (
          capture_run_id TEXT PRIMARY KEY,
          mode TEXT NOT NULL,
          source_kind TEXT NOT NULL,
          started_at_utc TEXT NOT NULL,
          completed_at_utc TEXT,
          status TEXT NOT NULL,
          project_key TEXT,
          endpoint_key TEXT,
          endpoint_family TEXT,
          row_cap INTEGER,
          inspected_rows INTEGER NOT NULL DEFAULT 0,
          raw_landing_rows INTEGER NOT NULL DEFAULT 0,
          structured_rows INTEGER NOT NULL DEFAULT 0,
          gap_count INTEGER NOT NULL DEFAULT 0,
          fail_closed_reason TEXT,
          live_procore_calls INTEGER NOT NULL DEFAULT 0 CHECK(live_procore_calls = 0),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS procore_endpoint_capture_pages (
          capture_page_id TEXT PRIMARY KEY,
          capture_run_id TEXT NOT NULL REFERENCES procore_endpoint_capture_runs(capture_run_id),
          endpoint_key TEXT NOT NULL,
          endpoint_family TEXT NOT NULL,
          project_key TEXT,
          request_fingerprint_hash TEXT NOT NULL,
          page_number INTEGER,
          page_cursor_hash TEXT,
          rows_seen INTEGER NOT NULL DEFAULT 0,
          payload_hash TEXT,
          status TEXT NOT NULL,
          fail_closed_reason TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS procore_endpoint_capture_errors (
          capture_error_id TEXT PRIMARY KEY,
          capture_run_id TEXT,
          endpoint_key TEXT,
          endpoint_family TEXT,
          project_key TEXT,
          error_kind TEXT NOT NULL,
          error_message_redacted TEXT,
          fail_closed_reason TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS procore_endpoint_raw_payloads (
          raw_payload_id TEXT PRIMARY KEY,
          capture_run_id TEXT,
          endpoint_key TEXT NOT NULL,
          endpoint_family TEXT NOT NULL,
          endpoint_version TEXT NOT NULL,
          company_id TEXT,
          company_id_hash TEXT,
          project_id TEXT,
          project_id_hash TEXT,
          project_key TEXT,
          record_type TEXT NOT NULL,
          record_id TEXT NOT NULL,
          record_id_hash TEXT NOT NULL,
          parent_record_id TEXT,
          parent_record_id_hash TEXT,
          source_ref_hash TEXT NOT NULL,
          request_fingerprint_hash TEXT NOT NULL,
          payload_hash TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          payload_size_bytes INTEGER NOT NULL DEFAULT 0,
          payload_captured_at_utc TEXT,
          payload_seen_first_utc TEXT,
          payload_seen_last_utc TEXT,
          is_current INTEGER NOT NULL DEFAULT 1 CHECK(is_current IN (0, 1)),
          redaction_status TEXT NOT NULL,
          security_scrub_status TEXT NOT NULL,
          contains_personal_data INTEGER NOT NULL DEFAULT 0 CHECK(contains_personal_data IN (0, 1)),
          contains_signed_url INTEGER NOT NULL DEFAULT 0 CHECK(contains_signed_url IN (0, 1)),
          contains_secret_like_value INTEGER NOT NULL DEFAULT 0 CHECK(contains_secret_like_value IN (0, 1)),
          retention_class TEXT NOT NULL DEFAULT 'local_analytics',
          analytics_eligible INTEGER NOT NULL DEFAULT 1 CHECK(analytics_eligible IN (0, 1)),
          source_quality TEXT NOT NULL,
          raw_procore_payload_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_procore_payload_persisted IN (0, 1)),
          external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0),
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(endpoint_key, project_key, parent_record_id, record_id, payload_hash)
        );
        """,
        "CREATE INDEX IF NOT EXISTS ix_procore_endpoint_contracts_family ON procore_endpoint_contracts(endpoint_family, analytics_eligible);",
        "CREATE INDEX IF NOT EXISTS ix_procore_endpoint_capture_runs_status ON procore_endpoint_capture_runs(status, endpoint_family);",
        "CREATE INDEX IF NOT EXISTS ix_procore_endpoint_capture_pages_run ON procore_endpoint_capture_pages(capture_run_id, endpoint_key);",
        "CREATE INDEX IF NOT EXISTS ix_procore_endpoint_raw_payloads_endpoint_project ON procore_endpoint_raw_payloads(endpoint_key, project_key);",
        "CREATE INDEX IF NOT EXISTS ix_procore_endpoint_raw_payloads_source_ref ON procore_endpoint_raw_payloads(source_ref_hash);",
        "CREATE INDEX IF NOT EXISTS ix_procore_endpoint_raw_payloads_current ON procore_endpoint_raw_payloads(endpoint_key, is_current);",
        *_V46_STRUCTURED_TABLE_DDL,
        *_V46_STRUCTURED_INDEX_DDL,
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

            # v6 Phase 04A Procore live sync tables (additive only).
            for stmt in self.V6_STATEMENTS:
                conn.execute(stmt)

            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 6")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (6, 'v6_procore_live_sync', ?)",
                    (now,),
                )

            # v7 Phase 04B historical-memory + enrichment + inspection tables
            # (additive only; does not touch V1-V6 tables).
            for stmt in self.V7_STATEMENTS:
                conn.execute(stmt)

            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 7")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (7, 'v7_procore_history_and_enrichment', ?)",
                    (now,),
                )

            # v8 Phase 05 Procore contracts & financials projection tables
            # (additive only; does not touch V1-V7 tables).
            for stmt in self.V8_STATEMENTS:
                conn.execute(stmt)

            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 8")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (8, 'v8_procore_financials', ?)",
                    (now,),
                )

            # v9 Phase 05 subcontractor billing surface: billing periods +
            # subcontractor invoice headers (additive only; does not touch V1-V8).
            for stmt in self.V9_STATEMENTS:
                conn.execute(stmt)

            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 9")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (9, 'v9_procore_billing_and_subcontractor_invoices', ?)",
                    (now,),
                )

            # v10 Phase 06 active email-intelligence policy + mailbox source
            # registry (additive only; does not touch V1-V9, preserves the V5
            # deferred-state row).
            for stmt in self.V10_STATEMENTS:
                conn.execute(stmt)

            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 10")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (10, 'v10_email_intelligence_active_policy_and_mailbox_source_registry', ?)",
                    (now,),
                )

            # v11 Phase 06 operational email-intelligence data schema (additive
            # only; does not touch V1-V10, references the V10 email_source_locations).
            for stmt in self.V11_STATEMENTS:
                conn.execute(stmt)

            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 11")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (11, 'v11_email_operational_intelligence_schema', ?)",
                    (now,),
                )

            # v12 Phase 06 Prompt 08A encrypted full-body vault refs (additive
            # only; does not touch V1-V11, preserves email_messages CHECKs).
            for stmt in self.V12_STATEMENTS:
                conn.execute(stmt)

            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 12")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (12, 'v12_email_encrypted_body_vault_refs', ?)",
                    (now,),
                )

            # v13 Phase 06 Prompt 10 review-routing decision metadata (additive
            # ADD COLUMN only). Unlike CREATE TABLE IF NOT EXISTS, ALTER TABLE ADD
            # COLUMN is not idempotent, so it is gated behind the version row.
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 13")
            if cur.fetchone() is None:
                for stmt in self.V13_STATEMENTS:
                    conn.execute(stmt)
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (13, 'v13_email_review_body_capture_decision', ?)",
                    (now,),
                )

            # v14 Phase 06 Prompt 11 advisory Ollama email-classification read model
            # (additive CREATE TABLE only; does not touch V1-V13).
            for stmt in self.V14_STATEMENTS:
                conn.execute(stmt)

            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 14")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (14, 'v14_email_model_classifications', ?)",
                    (now,),
                )

            # v15 Phase 06 (Files) Prompt 06 rich driveItem metadata columns on
            # construction_drive_items (additive ADD COLUMN only; gated like v13
            # because ALTER TABLE ADD COLUMN is not idempotent). V1-V14 untouched.
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 15")
            if cur.fetchone() is None:
                for stmt in self.V15_STATEMENTS:
                    conn.execute(stmt)
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (15, 'v15_construction_drive_items_rich_metadata', ?)",
                    (now,),
                )

            # v16 Phase 06A user-provided link → ID resolution (additive CREATE
            # TABLE only; raw tokenized URL never persisted). V1-V15 untouched.
            for stmt in self.V16_STATEMENTS:
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 16")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (16, 'v16_construction_graph_link_resolution', ?)",
                    (now,),
                )

            # v17 Phase 06A Prompt 09 per-file project-match columns on
            # construction_drive_items (additive ADD COLUMN only; gated like v15/v17
            # because ALTER TABLE ADD COLUMN is not idempotent). V1-V16 untouched.
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 17")
            if cur.fetchone() is None:
                for stmt in self.V17_STATEMENTS:
                    conn.execute(stmt)
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (17, 'v17_construction_drive_items_project_matching', ?)",
                    (now,),
                )

            # v18 Phase 06A Prompt 10 file ingestion eligibility decisions
            # (additive CREATE TABLE only; CHECK enforces no extraction for
            # review-required files). V1-V17 untouched.
            for stmt in self.V18_STATEMENTS:
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 18")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (18, 'v18_construction_file_ingestion_decisions', ?)",
                    (now,),
                )

            # v19 Phase 06A Prompt 11 controlled download + extraction receipts
            # (additive CREATE TABLE only; CHECKs forbid raw download URL / vault
            # copy / full-text persistence). V1-V18 untouched.
            for stmt in self.V19_STATEMENTS:
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 19")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (19, 'v19_construction_download_and_extraction_receipts', ?)",
                    (now,),
                )

            # v20 Phase 07A Prompt 01 data-quality + source-record-map tables
            # (additive CREATE TABLE + INDEX only; CHECK guardrails; V1-V19 untouched).
            for stmt in self.V20_STATEMENTS:
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 20")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (20, 'v20_data_quality_and_source_record_map', ?)",
                    (now,),
                )

            # v21 Phase 07A Prompt 05 — agent-ready query marts (additive only).
            # Three new materialised read models + indexes. V1-V20 untouched.
            for stmt in self.V21_STATEMENTS:
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 21")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (21, 'v21_agent_ready_query_marts', ?)",
                    (now,),
                )

            # v22 Phase 07B Prompt 01 — additive raw-body guardrail on the five V21
            # marts. Idempotent: only ALTER a table that is missing the column. The
            # marts exist by now (V21 CREATE IF NOT EXISTS ran above). V1-V21 untouched.
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 22")
            if cur.fetchone() is None:
                for table in self.V22_MART_TABLES:
                    cols = {
                        row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
                    }
                    if "raw_body_persisted" not in cols:
                        conn.execute(
                            f"ALTER TABLE {table} ADD COLUMN raw_body_persisted "
                            "INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_persisted = 0)"
                        )
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (22, 'v22_mart_raw_body_guardrail', ?)",
                    (now,),
                )

            # v23 Phase 07B Prompt 02 — calendar + email-thread intelligence schema
            # (additive CREATE TABLE/INDEX only; CHECK guardrails; V1-V22 untouched).
            for stmt in self.V23_STATEMENTS:
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 23")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (23, 'v23_calendar_email_thread_intelligence', ?)",
                    (now,),
                )

            # v24 Phase 07C Prompt 02 — document intelligence schema additions. Additive:
            # extend the existing (empty) V5 construction_document_cards via idempotent
            # ALTER ADD COLUMN (per-column PRAGMA table_info guard, like V22), then create
            # the five document satellite tables + indexes (CREATE IF NOT EXISTS). The V5
            # card table exists by now (V5 CREATE IF NOT EXISTS ran above). V1-V23 untouched.
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 24")
            if cur.fetchone() is None:
                card_cols = {
                    row[1]
                    for row in conn.execute(
                        "PRAGMA table_info(construction_document_cards)"
                    ).fetchall()
                }
                for col_name, col_ddl in self.V24_CARD_COLUMNS:
                    if col_name not in card_cols:
                        conn.execute(
                            f"ALTER TABLE construction_document_cards ADD COLUMN {col_ddl}"
                        )
                for stmt in self.V24_STATEMENTS:
                    conn.execute(stmt)
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (24, 'v24_document_intelligence_schema', ?)",
                    (now,),
                )

            # v25 Phase 07D Prompt 02 — cross-source relationship + meeting-prep schema
            # additions (additive CREATE TABLE/INDEX only; no-raw/no-writeback CHECK
            # guardrails; deterministic-hash PKs + UNIQUE edges for idempotency). Tables
            # ship empty for later 07D prompts to populate. V1-V24 untouched.
            for stmt in self.V25_STATEMENTS:
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 25")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (25, 'v25_cross_source_relationship_meeting_prep_schema', ?)",
                    (now,),
                )

            # v26 Phase 08A Prompt 02 — local-first second-brain runtime substrate
            # (additive CREATE TABLE/INDEX only; per-table no-raw/no-writeback CHECK
            # guardrails; deterministic-hash PKs for idempotency). 21 tables ship empty
            # for later 08A prompts to populate. V1-V25 untouched.
            for stmt in self.V26_STATEMENTS:
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 26")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (26, 'v26_second_brain_phase_08a_schema', ?)",
                    (now,),
                )

            # v27 Phase 08B Prompt 01 — durable delivery-handoff recovery: one additive
            # daily_brief_handoff_lines table (per-row no-raw/no-writeback CHECK guardrails)
            # so the structured handoff sections survive process exit and can be
            # reconstructed. Ships empty. V1-V26 untouched.
            for stmt in self.V27_STATEMENTS:
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 27")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (27, 'v27_daily_brief_handoff_lines', ?)",
                    (now,),
                )

            # v28 Phase 08B Prompt 02 — persisted agent receipts (model-call + agent-run),
            # metadata-only with per-row no-raw/no-writeback CHECK guardrails. Replaces the
            # prior in-memory-only / V27-deferred receipts. Ships empty. V1-V27 untouched.
            for stmt in self.V28_STATEMENTS:
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 28")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (28, 'v28_agent_receipts', ?)",
                    (now,),
                )

            # v29 Phase 08B Prompt 05 — run registry + run-step ledger (no-overlap run accounting),
            # metadata-only with per-row no-raw/no-writeback CHECK guardrails. The lock itself is an
            # atomic file outside the repo; these tables are the audit trail. Ships empty. V1-V28
            # untouched.
            for stmt in self.V29_STATEMENTS:
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 29")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (29, 'v29_run_registry_and_steps', ?)",
                    (now,),
                )

            # v30 Phase 08B Prompt 06 — retry/backoff receipts (metadata-only, per-row no-raw/
            # no-writeback CHECK guardrails). The Run Recovery Agent reuses the V28 agent-run
            # receipts table. Ships empty. V1-V29 untouched.
            for stmt in self.V30_STATEMENTS:
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 30")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (30, 'v30_retry_receipts', ?)",
                    (now,),
                )

            # v31 Phase 08B Prompt 09 — daily-brief delivery receipts (metadata-only, per-row
            # no-raw/no-writeback CHECK guardrails; delivery_channel pinned to obsidian_vault). The
            # Daily Brief Delivery Agent records one row per local-only delivery for idempotency +
            # audit. Ships empty; V1-V30 untouched.
            for stmt in self.V31_STATEMENTS:
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 31")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (31, 'v31_daily_brief_delivery_receipts', ?)",
                    (now,),
                )

            # v32 Phase 08B Prompt 10 — local HTML brief render receipts (metadata-only, per-row
            # no-raw/no-writeback CHECK guardrails + a fail-closed no_external_assets = 1 invariant;
            # raw HTML never persisted). The renderer records one row per self-contained HTML
            # rendering written outside the repo. Ships empty; V1-V31 untouched.
            for stmt in self.V32_STATEMENTS:
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 32")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (32, 'v32_daily_brief_html_render_receipts', ?)",
                    (now,),
                )

            # v33 Phase 08B Prompt 11 — local macOS notification receipts (metadata-only, per-row
            # no-raw/no-writeback CHECK guardrails; channel pinned to local_macos; raw notification
            # text never persisted). The renderer records one row per notification preview/emit; the
            # osascript emission is real-but-policy-gated. Ships empty; V1-V32 untouched.
            for stmt in self.V33_STATEMENTS:
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 33")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (33, 'v33_daily_brief_notification_receipts', ?)",
                    (now,),
                )

            # v34 Phase 08B Prompt 12 — local brief-open receipts (metadata-only, per-row no-raw/
            # no-writeback CHECK guardrails; open_target pinned to vault|html; raw content never
            # persisted). The brief-open agent records one row per open preview/launch; the macOS
            # ``open`` is real-but-policy-gated. Ships empty; V1-V33 untouched.
            for stmt in self.V34_STATEMENTS:
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 34")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (34, 'v34_daily_brief_open_receipts', ?)",
                    (now,),
                )

            # v35 Phase 08C Prompt 01 — financial fact normalization + readiness substrate (additive only; V1-V34 untouched). 10 tables for normalization runs, normalized amount facts (decimal TEXT + minor units), currency/WBS/cost-code/source coverage snapshots, exposure summary, forecast readiness, review items, agent runs, validation runs. All with full no-raw/no-writeback/financial-determination guards + advisory_only=1.
            for stmt in self.V35_STATEMENTS:
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 35")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (35, 'v35_phase_08c_financial_fact_normalization_and_readiness', ?)",
                    (now,),
                )

            # v36 Phase 08C — review-required routing confidence label (additive
            # column on second_brain_financial_review_required_items). ALTER ADD
            # COLUMN is not idempotent, so it is gated on the migration row.
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 36")
            if cur.fetchone() is None:
                for stmt in self.V36_STATEMENTS:
                    conn.execute(stmt)
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (36, 'v36_phase_08c_review_required_confidence_label', ?)",
                    (now,),
                )

            # v37 Phase 08D Prompt 02 — local MCP bridge metadata substrate (additive only;
            # V1-V36 untouched). 10 metadata-only tables (server/tool/resource/prompt registry
            # snapshots, tool-call + denial receipts, permission-audit + policy-gate runs,
            # Claude Desktop config preview, phase-08D validation runs), each with the full
            # twenty no-raw / no-writeback / no-direct-api / no-determination guards. Ships
            # empty; no server or runtime dispatch is wired here.
            for stmt in self.V37_STATEMENTS:
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 37")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (37, 'v37_phase_08d_mcp_bridge_schema', ?)",
                    (now,),
                )

            # v38 Phase 09 Prompt 12 — retrieval / memory / agent metadata substrate (additive
            # only; V1-V37 untouched). Nineteen metadata-only tables, each with the full twenty-
            # three guard columns CHECK(... = 0) (the twenty no-raw / no-writeback / no-direct-api
            # / no-determination guards plus the three Phase 09 guards). Ships empty; no
            # LlamaIndex / embeddings / vector / semantic retrieval runtime is wired here.
            for stmt in self.V38_STATEMENTS:
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 38")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (38, 'v38_phase_09_retrieval_memory_agent_schema', ?)",
                    (now,),
                )

            # v39 Phase 09 review burden reduction (additive; two-step policy marts).
            # All 23 guard columns present with CHECK=0. Ships empty.
            for stmt in self.V39_STATEMENTS:
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 39")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (39, 'v39_phase_09_review_burden_reduction', ?)",
                    (now,),
                )

            # v40 Phase UI-05 / Prompt 05 — project keyword training registry (additive only).
            for stmt in self.V40_STATEMENTS:
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 40")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (40, 'v40_construction_project_keyword_registry', ?)",
                    (now,),
                )

            # v41 Phase 10 Local Action Intelligence — additive substrate (additive only).
            for stmt in self.V41_STATEMENTS:
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 41")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (41, 'v41_phase_10_local_action_intelligence', ?)",
                    (now,),
                )

            # v42 Phase 10A raw content tables (Prompt 03/04). Additive only; designated
            # plaintext holders when raw policy active. V1-V41 untouched.
            for stmt in self.V42_STATEMENTS:
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 42")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (42, 'v42_phase_10a_raw_content_tables', ?)",
                    (now,),
                )

            # v43 Phase 10A candidate review lifecycle (snooze/edit/audit). Additive
            # ADD COLUMN only; gated like v13/v15 because ALTER TABLE ADD COLUMN is not
            # idempotent. V1-V42 untouched.
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 43")
            if cur.fetchone() is None:
                for stmt in self.V43_STATEMENTS:
                    conn.execute(stmt)
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (43, 'v43_phase_10a_candidate_review', ?)",
                    (now,),
                )

            # v44 Graph drive-item modified-by metadata and explicit parent folder
            # name. Additive ADD COLUMN only; existing rows remain valid with NULLs.
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 44")
            if cur.fetchone() is None:
                for stmt in self.V44_STATEMENTS:
                    conn.execute(stmt)
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (44, 'v44_graph_drive_item_modified_by_metadata', ?)",
                    (now,),
                )

            # v45 Phase 10 email follow-up raw enrichment table (review-safe). Additive
            # CREATE TABLE/INDEX IF NOT EXISTS; the table carries the 13 guard columns and
            # holds only structured/redacted enriched fields + hashes. V1-V44 untouched.
            for stmt in self.V45_STATEMENTS:
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 45")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (45, 'v45_email_followup_enrichments', ?)",
                    (now,),
                )

            # v46 Procore structured analytics foundation. Additive local-only
            # capture/control, raw landing, and endpoint-family structured bronze
            # tables. Raw landing alone is not the analytics acceptance gate.
            for stmt in self.V46_STATEMENTS:
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 46")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (46, 'v46_procore_structured_analytics_foundation', ?)",
                    (now,),
                )

            # v47 Procore endpoint-specific structured projection tables. Additive,
            # local-only: one primary table per in-scope endpoint family + child/detail
            # tables for nested business-object arrays, derived deterministically from the
            # committed projection registry (single source of truth). Every table carries
            # the standard identity columns, a lossless ``payload_sidecar_json``, and the
            # zero-CHECK no-writeback / no-raw-emission guards. V1-V46 tables untouched.
            for stmt in self._v47_statements():
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 47")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (47, 'v47_procore_endpoint_specific_structured_projections', ?)",
                    (now,),
                )

            # v48 Procore projection column reconciliation. The V47 endpoint-specific tables
            # are registry-derived; when the committed projection registry is regenerated
            # (e.g. wider payload coverage, or the object|null container fix) it can require
            # curated columns that pre-existing physical tables lack — and CREATE TABLE IF
            # NOT EXISTS cannot add columns. This reconciliation runs UNCONDITIONALLY (outside
            # the version-48 gate) so it self-heals column drift on every apply, even on a DB
            # already at head. Additive only: ALTER TABLE ADD COLUMN for missing registry
            # columns; never drops or alters existing columns.
            self._reconcile_v48_columns(conn)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 48")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (48, 'v48_procore_projection_column_reconciliation', ?)",
                    (now,),
                )

            # v49 Email + calendar full raw content provenance + final structured
            # projection layer. Additive only: (a) guarded ADD COLUMN on the three V42
            # raw tables (source-quality/provenance + a lossless raw_sidecar_json holder),
            # (b) registry-derived structured parent/child projection tables + ingestion/
            # projection/coverage receipts (CREATE IF NOT EXISTS), and (c) an unconditional
            # column reconcile that self-heals structured curated-column drift on every
            # apply (mirrors V48). V1-V48 tables untouched.
            for stmt in self._v49_create_statements():
                conn.execute(stmt)
            for stmt in self._v49_raw_column_alters(conn):
                conn.execute(stmt)
            self._reconcile_v49_columns(conn)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 49")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (49, 'v49_email_calendar_full_raw_content_and_projections', ?)",
                    (now,),
                )

            # v50 Phase 10 candidate cross-family lifecycle overlay (review queue /
            # disposition / merge / suppression). Additive, append-only; CREATE IF NOT
            # EXISTS so re-apply is a no-op. Extends V41/V43 per-family review status
            # without creating dual truth. V1-V49 untouched.
            for stmt in self.V50_STATEMENTS:
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 50")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (50, 'v50_phase_10_candidate_lifecycle_overlay', ?)",
                    (now,),
                )

            # v51 Phase 10 Ollama-assisted candidate ranking + daily-brief assembly
            # overlay. Additive, append-only; CREATE IF NOT EXISTS so re-apply is a no-op.
            # Layers ranking/assembly read-models on the V41 candidate projection and V50
            # lifecycle overlay without altering either. V1-V50 untouched.
            for stmt in self.V51_STATEMENTS:
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 51")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (51, 'v51_phase_10_candidate_ranking_and_daily_brief_assembly', ?)",
                    (now,),
                )

            # v52 Phase 10 daily-brief effectiveness / ranking-policy telemetry. Additive,
            # append-only; CREATE IF NOT EXISTS so re-apply is a no-op. Observational telemetry
            # over the V41/V50/V51 read models — reads them, mutates none. V1-V51 untouched.
            for stmt in self.V52_STATEMENTS:
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 52")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (52, 'v52_phase_10_daily_brief_effectiveness_telemetry', ?)",
                    (now,),
                )

            # v53 reconcile: add ranking_run_id (+ composite PK) to ranking_policy_eval_items so a
            # candidate surfaced in two ranking runs keeps a distinct fact per run. Changing a PK
            # needs a table rebuild; this guarded, idempotent reconcile is a no-op once the column
            # exists, and preserves any existing rows (backfilling ranking_run_id='unknown'). Needed
            # because an editable-install runner could migrate a DB to the original V52 shape.
            self._reconcile_v53_eval_items(conn)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 53")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (53, 'v53_reconcile_ranking_policy_eval_items_ranking_run_id', ?)",
                    (now,),
                )

            # v54 Phase 10 (252) New Today overnight change digest. Additive, append-only; CREATE IF
            # NOT EXISTS so re-apply is a no-op. Source-linked business-event read model + hash-only
            # source-ref child, both carrying the full 13 Phase-10 guards. V1-V53 untouched.
            for stmt in self.V54_STATEMENTS:
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 54")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (54, 'v54_phase_10_daily_brief_new_today_change_events', ?)",
                    (now,),
                )

            # v55 Procore Budget Detail Rows endpoint-specific forecasting read model.
            # Additive, local-only, and body-free outside SQLite raw landing.
            for stmt in self.V55_STATEMENTS:
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 55")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (55, 'v55_procore_budget_detail_rows_read_model', ?)",
                    (now,),
                )

            # v56 Procore Budget Detail Rows dynamic-cell amount promotion columns.
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 56")
            if cur.fetchone() is None:
                existing_cols = {
                    row[1]
                    for row in conn.execute("PRAGMA table_info(procore_ep_budget_detail_rows)")
                }
                for stmt in self.V56_STATEMENTS:
                    column_name = stmt.split(" ADD COLUMN ", 1)[1].split()[0]
                    if column_name not in existing_cols:
                        conn.execute(stmt)
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (56, 'v56_procore_budget_detail_row_amount_columns', ?)",
                    (now,),
                )

            # v57 Procore Change Event budget-modification projection columns.
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 57")
            if cur.fetchone() is None:
                existing_cols = {
                    row[1]
                    for row in conn.execute(
                        "PRAGMA table_info(procore_ep_change_events_change_items)"
                    )
                }
                for stmt in self.V57_STATEMENTS:
                    column_name = stmt.split(" ADD COLUMN ", 1)[1].split()[0]
                    if column_name not in existing_cols:
                        conn.execute(stmt)
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (57, 'v57_procore_change_event_budget_modification_columns', ?)",
                    (now,),
                )

            # v58 Forecast DB-transition FOUNDATION tables (project identity, run
            # registry, source ingestions, package manifests, validation events).
            # Additive CREATE TABLE IF NOT EXISTS only; domain tables deferred to v59+.
            for stmt in self.V58_STATEMENTS:
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 58")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (58, 'v58_forecast_db_transition_foundation', ?)",
                    (now,),
                )

            # v59 Forecast DB-transition SOURCE-DOMAIN slice (Phase 3): three additive
            # source-row tables (budget details, cost entries, monthly actuals) projecting
            # TWN cost-forecast JSONL for DB read-parity. Additive CREATE TABLE IF NOT
            # EXISTS only; forecast model reads remain file-backed.
            for stmt in self.V59_STATEMENTS:
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 59")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (59, 'v59_forecast_source_domain', ?)",
                    (now,),
                )

            # v60 Forecast DB-transition CONFIG-REGISTRY slice (Phase 16): four additive
            # governed-config tables (sources, items, snapshots, snapshot_items) for the
            # operator-approved forecast config. Additive CREATE TABLE IF NOT EXISTS only;
            # intentionally empty until config is imported; forecast reads remain file-backed.
            for stmt in self.V60_STATEMENTS:
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 60")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (60, 'v60_forecast_config_registry', ?)",
                    (now,),
                )

            # v61 Forecast EXTERNAL-FORECAST EVALUATION slice (Phase 4): eight additive
            # tables representing operator-supplied external forecasts (Excel/CSV) and
            # their evaluation against baselines (actuals/budget/ERP-JTD/model/prior),
            # kept distinct from backend model forecasts via forecast_origin. Additive
            # CREATE TABLE IF NOT EXISTS only; intentionally empty on the live DB (real
            # rows are written to an isolated per-run eval SQLite, never the live DB);
            # forecast reads remain file-backed.
            for stmt in self.V61_STATEMENTS:
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 61")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (61, 'v61_forecast_external_forecasts', ?)",
                    (now,),
                )

            # v62 Schedule Intelligence: canonical schedule activity substrate for Procore
            # API and uploaded XML/XER/CSV schedules plus operator-controlled cost mapping.
            for stmt in self._v62_statements():
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 62")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (62, 'v62_schedule_intelligence', ?)",
                    (now,),
                )

            # v63 Forecast run-output family: model-run results header + detail tables.
            # Additive only; intentionally empty until the read-only output projector
            # populates a temp DB. Forecast reads remain file-backed.
            for stmt in self._v63_statements():
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 63")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (63, 'v63_forecast_run_outputs', ?)",
                    (now,),
                )

            for stmt in self._v64_statements():
                conn.execute(stmt)
            self._reconcile_v64_schedule_quality_findings(conn)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 64")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (64, 'v64_schedule_quality_evaluation', ?)",
                    (now,),
                )

            self._reconcile_v65_schedule_float_columns(conn)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 65")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (65, 'v65_schedule_derived_finish_float', ?)",
                    (now,),
                )

            # v66 Forecast decision-support family: maturity/availability/confidence
            # persistence keyed to a forecast run. Additive only; intentionally empty until
            # the read-only decision-support engine populates a temp DB.
            for stmt in self._v66_statements():
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 66")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (66, 'v66_forecast_decision_support', ?)",
                    (now,),
                )

            self._reconcile_v67_schedule_critical_path_columns(conn)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 67")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (67, 'v67_schedule_critical_path_source_formats', ?)",
                    (now,),
                )

            self._reconcile_v68_procore_ep_projects_one_per_key(conn)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 68")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (68, 'v68_procore_ep_projects_one_per_key', ?)",
                    (now,),
                )

            self._reconcile_v69_schedule_import_fk_repair(conn)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 69")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (69, 'v69_schedule_import_fk_repair', ?)",
                    (now,),
                )

            self._reconcile_v70_schedule_quality_supplemental(conn)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 70")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (70, 'v70_schedule_quality_supplemental', ?)",
                    (now,),
                )

            self._reconcile_v71_schedule_quality_source_export(conn)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 71")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (71, 'v71_schedule_quality_source_export', ?)",
                    (now,),
                )

            # v72 Forecast model-registry: additive provenance tables, empty until the
            # read-only governance path populates a temp DB. Never the live DB.
            for stmt in self._v72_statements():
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 72")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (72, 'v72_forecast_model_registry', ?)",
                    (now,),
                )

            # v73 Forecast generation-request contract: additive request-ledger table, empty until
            # the generation routes persist requests into the app-managed DB.
            for stmt in self._v73_statements():
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 73")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (73, 'v73_forecast_generation_requests', ?)",
                    (now,),
                )

            # v74 Forecast monthly-matrix: operator month-window columns (+ basis/warnings),
            # value_type/source_status on the sparse monthly cells (with a one-time is_actual
            # backfill), and the matrix row + dense total tables. The column adds/backfill/CREATEs are
            # idempotent (column-existence-guarded), so they run on every apply (self-heal safe); only
            # the schema_migrations row insert is guarded.
            self._apply_v74_forecast_monthly_matrix(conn)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 74")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (74, 'v74_forecast_monthly_matrix', ?)",
                    (now,),
                )

            # v75 Schedule import health foundation: additive package/baseline/capability tables.
            for stmt in self._v75_statements():
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 75")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (75, 'v75_schedule_import_health_foundation', ?)",
                    (now,),
                )

            # v76 Project Staffing foundation: staffing table family + additive matrix-row
            # staffing metadata columns + seeded default company holiday calendar (2026-2040).
            # CREATEs/column-adds/seed are idempotent; only the schema_migrations row is guarded.
            self._apply_v76_project_staffing(conn, now)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 76")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (76, 'v76_project_staffing_foundation', ?)",
                    (now,),
                )

            # v77 Schedule identity foundation: additive identity/match tables.
            for stmt in self._v77_statements():
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 77")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (77, 'v77_schedule_identity_foundation', ?)",
                    (now,),
                )

            # v78 Schedule identity manual action audit table.
            for stmt in self._v78_statements():
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 78")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (78, 'v78_schedule_identity_manual_actions', ?)",
                    (now,),
                )

            # v79 Schedule diff intelligence foundation: detailed diff fact rows.
            for stmt in self._v79_statements():
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 79")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (79, 'v79_schedule_diff_detail_facts', ?)",
                    (now,),
                )

            # v80 Schedule impact intelligence: durable rollups over detailed facts.
            for stmt in self._v80_statements():
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 80")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (80, 'v80_schedule_diff_impact_rollups', ?)",
                    (now,),
                )

            # v81 Project Staffing attribution reshape (cost_code + category model). DESTRUCTIVE
            # drop+recreate of the two empty V76 attribution tables, so it runs ONCE (guarded by
            # the v81 row) and aborts if either table holds rows. Count-neutral (same table names).
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 81")
            if cur.fetchone() is None:
                self._apply_v81_attribution_reshape(conn)
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (81, 'v81_staffing_attribution_cost_code_category', ?)",
                    (now,),
                )

            # v82 Unified schedule package assembly evidence. This landed after main had already
            # assigned V80/V81, so preserve the package tables as the next additive migration.
            for stmt in self._v82_statements():
                conn.execute(stmt)
            self._reconcile_v82_schedule_package_equivalence_facts(conn)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 82")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (82, 'v82_schedule_package_assembly_evidence', ?)",
                    (now,),
                )

            # v83 CPM graph diagnostics foundation: additive structural-diagnostics tables.
            # Graph diagnostics only — no CPM dates/float/critical path are computed.
            for stmt in self._v83_statements():
                conn.execute(stmt)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 83")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (83, 'v83_schedule_cpm_graph_diagnostics_foundation', ?)",
                    (now,),
                )

            # v84 CPM forward pass foundation: additive forward-pass result tables plus
            # column-existence-guarded forward-pass metadata columns on schedule_cpm_runs.
            # Forward pass only — no backward pass/float/critical path; no source-field writes.
            for stmt in self._v84_statements():
                conn.execute(stmt)
            self._reconcile_v84_schedule_cpm_run_columns(conn)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 84")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (84, 'v84_schedule_cpm_forward_pass_foundation', ?)",
                    (now,),
                )

            # v85 CPM backward pass foundation: additive backward-pass columns on the shared
            # CPM result/run tables (no new tables; table_count unchanged). Backward pass only
            # — no float/longest/critical path; no source-field writes.
            self._reconcile_v85_schedule_cpm_backward_columns(conn)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 85")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (85, 'v85_schedule_cpm_backward_pass_foundation', ?)",
                    (now,),
                )

            # v86 CPM float foundation: additive float columns on the shared CPM result/run
            # tables (no new tables; table_count unchanged). Float only — derived from the
            # application-owned Phase 2/3 offsets; no critical/longest path; nothing marked
            # critical; no source-field writes.
            self._reconcile_v86_schedule_cpm_float_columns(conn)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 86")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (86, 'v86_schedule_cpm_float_foundation', ?)",
                    (now,),
                )

            # v87 CPM longest path foundation: two additive path tables + longest-path
            # summary columns on schedule_cpm_runs (table_count +2). Longest path only — a
            # path BASIS, not a critical-path declaration; nothing marked critical; no
            # source-field writes.
            for stmt in self._v87_statements():
                conn.execute(stmt)
            self._reconcile_v87_schedule_cpm_path_run_columns(conn)
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 87")
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (87, 'v87_schedule_cpm_longest_path_foundation', ?)",
                    (now,),
                )

        # Return latest version, then release the migration connection. get_connection's
        # contract is that the caller closes it; left open, this WAL connection is only
        # checkpointed when Python GC finalizes it, which non-deterministically flushes the
        # -wal into the main DB file and perturbs read-only callers that byte-compare the file.
        cur = conn.execute("SELECT MAX(version) FROM schema_migrations")
        row = cur.fetchone()
        version = int(row[0]) if row and row[0] is not None else 0
        conn.close()
        return version

    @staticmethod
    def _reconcile_v68_procore_ep_projects_one_per_key(conn: sqlite3.Connection) -> None:
        from hb_assistant.procore.projects_projection import dedupe_procore_ep_projects

        conn.execute("PRAGMA foreign_keys=OFF")
        dedupe_procore_ep_projects(conn)
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_procore_ep_projects_project_key_unique
            ON procore_ep_projects(project_key)
            """
        )

    @staticmethod
    def _reconcile_v69_schedule_import_fk_repair(conn: sqlite3.Connection) -> None:
        from hb_assistant.store.schedule_import_fk_repair import reconcile_schedule_import_fk_drift
        from hb_assistant.store.schedule_schema_verify import assert_schedule_import_fk_targets

        reconcile_schedule_import_fk_drift(conn)
        assert_schedule_import_fk_targets(conn)

    @staticmethod
    def _reconcile_v82_schedule_package_equivalence_facts(conn: sqlite3.Connection) -> None:
        from hb_assistant.store.schedule_import_health_tables import (
            V80_PACKAGE_EQUIVALENCE_FACT_ADDITIVE_REPAIR_COLUMNS,
            V80_PACKAGE_EQUIVALENCE_FACT_INSERT_COLUMNS,
        )

        try:
            existing = {
                row[1]
                for row in conn.execute("PRAGMA table_info(schedule_package_equivalence_facts)")
            }
        except sqlite3.OperationalError:
            return
        if not existing:
            return
        missing = set(V80_PACKAGE_EQUIVALENCE_FACT_INSERT_COLUMNS) - existing
        unrepairable = missing - set(V80_PACKAGE_EQUIVALENCE_FACT_ADDITIVE_REPAIR_COLUMNS)
        if unrepairable:
            raise sqlite3.OperationalError(
                "schedule_package_equivalence_facts is missing non-repairable V82 columns: "
                + ", ".join(sorted(unrepairable))
            )
        for column in V80_PACKAGE_EQUIVALENCE_FACT_INSERT_COLUMNS:
            if column in missing:
                conn.execute(
                    "ALTER TABLE schedule_package_equivalence_facts "
                    f"ADD COLUMN {column} "
                    f"{V80_PACKAGE_EQUIVALENCE_FACT_ADDITIVE_REPAIR_COLUMNS[column]}"
                )

    @staticmethod
    def _reconcile_v64_schedule_quality_findings(conn: sqlite3.Connection) -> None:
        from hb_assistant.store.schedule_quality_tables import V64_FINDING_ALTER_COLUMNS

        try:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(schedule_quality_findings)")}
        except sqlite3.OperationalError:
            return
        if not cols:
            return
        for col in V64_FINDING_ALTER_COLUMNS:
            if col not in cols:
                conn.execute(f"ALTER TABLE schedule_quality_findings ADD COLUMN {col} TEXT")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_schedule_quality_run "
            "ON schedule_quality_findings(schedule_version_key, evaluation_run_id)"
        )

    @staticmethod
    def _reconcile_v65_schedule_float_columns(conn: sqlite3.Connection) -> None:
        from hb_assistant.store.schedule_float_tables import (
            V65_ACTIVITY_ALTER_COLUMNS,
            V65_IMPORT_ALTER_COLUMNS,
        )

        def _add_cols(table: str, cols: tuple[str, ...], ddl: dict[str, str]) -> None:
            try:
                existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            except sqlite3.OperationalError:
                return
            if not existing:
                return
            for col in cols:
                if col not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl[col]}")

        import_ddl = {
            "compute_total_float_type": "TEXT",
            "critical_activity_path_type": "TEXT",
            "critical_activity_float_threshold": "TEXT",
            "calculate_float_based_on_finish_date": "INTEGER",
        }
        activity_ddl = {
            "remaining_early_start": "TEXT",
            "remaining_early_finish": "TEXT",
            "remaining_late_start": "TEXT",
            "remaining_late_finish": "TEXT",
            "derived_total_float_hours": "TEXT",
            "derived_total_float_days": "TEXT",
            "derived_float_basis": "TEXT",
            "derived_is_critical_by_float_threshold": "INTEGER",
        }
        _add_cols("schedule_file_imports", V65_IMPORT_ALTER_COLUMNS, import_ddl)
        _add_cols("procore_ep_schedule_activities", V65_ACTIVITY_ALTER_COLUMNS, activity_ddl)
        SQLiteMigrator._reconcile_v65_metric_status_check(conn)
        import_cols = {
            row[1] for row in conn.execute("PRAGMA table_info(schedule_file_imports)")
        }
        activity_cols = {
            row[1] for row in conn.execute("PRAGMA table_info(procore_ep_schedule_activities)")
        }
        if import_cols or activity_cols:
            from hb_assistant.store.schedule_schema_verify import assert_v65_schedule_float_schema

            assert_v65_schedule_float_schema(conn)

    @staticmethod
    def _reconcile_v67_schedule_critical_path_columns(conn: sqlite3.Connection) -> None:
        from hb_assistant.store.schedule_critical_path_tables import (
            V67_ACTIVITY_ALTER_COLUMNS,
            V67_IMPORT_ALTER_COLUMNS,
        )
        from hb_assistant.store.schedule_float_tables import V65_IMPORT_ALTER_COLUMNS

        SQLiteMigrator._reconcile_v67_source_format_check(conn)

        def _add_cols(table: str, cols: tuple[str, ...], ddl: dict[str, str]) -> None:
            try:
                existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            except sqlite3.OperationalError:
                return
            if not existing:
                return
            for col in cols:
                if col not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl[col]}")

        import_ddl = {
            "critical_path_type": "TEXT",
            "critical_float_threshold": "TEXT",
            "schedule_options_json": "TEXT",
            "baseline_source": "TEXT",
        }
        activity_ddl = {
            "explicit_total_float_hours": "TEXT",
            "explicit_total_float_days": "TEXT",
            "explicit_free_float_hours": "TEXT",
            "explicit_free_float_days": "TEXT",
            "float_source": "TEXT",
            "source_critical_flag": "INTEGER",
            "source_driving_path_flag": "INTEGER",
            "source_longest_path_flag": "INTEGER",
            "float_path": "TEXT",
            "float_path_order": "TEXT",
            "critical_path_number": "TEXT",
            "critical_path_source": "TEXT",
            "target_start": "TEXT",
            "target_finish": "TEXT",
            "target_duration": "TEXT",
            "baseline_start": "TEXT",
            "baseline_finish": "TEXT",
            "baseline_duration": "TEXT",
        }
        v65_import_ddl = {
            "compute_total_float_type": "TEXT",
            "critical_activity_path_type": "TEXT",
            "critical_activity_float_threshold": "TEXT",
            "calculate_float_based_on_finish_date": "INTEGER",
        }
        _add_cols("schedule_file_imports", V65_IMPORT_ALTER_COLUMNS, v65_import_ddl)
        _add_cols("schedule_file_imports", V67_IMPORT_ALTER_COLUMNS, import_ddl)
        _add_cols("procore_ep_schedule_activities", V67_ACTIVITY_ALTER_COLUMNS, activity_ddl)
        SQLiteMigrator._reconcile_v67_metric_status_check(conn)

    @staticmethod
    def _reconcile_v70_schedule_quality_supplemental(conn: sqlite3.Connection) -> None:
        from hb_assistant.store.schedule_float_tables import (
            METRIC_FAMILY_CHECK_VALUES,
            METRIC_STATUS_CHECK_VALUES,
        )

        cur = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='schedule_quality_metric_results'"
        )
        row = cur.fetchone()
        if not row or not row[0]:
            return
        ddl = str(row[0])
        if "supplemental" in ddl and "measured_from_source_export_proxy" in ddl:
            return
        families = ", ".join(f"'{f}'" for f in METRIC_FAMILY_CHECK_VALUES)
        statuses = ", ".join(f"'{s}'" for s in METRIC_STATUS_CHECK_VALUES)
        conn.execute(
            "ALTER TABLE schedule_quality_metric_results RENAME TO schedule_quality_metric_results_v70"
        )
        conn.execute(
            f"""
            CREATE TABLE schedule_quality_metric_results (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              evaluation_run_id TEXT NOT NULL,
              project_key TEXT NOT NULL,
              schedule_version_key TEXT NOT NULL,
              metric_code TEXT NOT NULL,
              metric_name TEXT NOT NULL,
              metric_family TEXT NOT NULL CHECK(metric_family IN ({families})),
              numerator TEXT,
              denominator TEXT,
              value TEXT,
              unit TEXT,
              threshold_warning TEXT,
              threshold_fail TEXT,
              status TEXT NOT NULL CHECK(status IN ({statuses})),
              not_measurable_reason TEXT,
              evidence_json TEXT,
              related_finding_codes_json TEXT,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY (evaluation_run_id) REFERENCES schedule_quality_evaluation_runs(evaluation_run_id)
            );
            """
        )
        conn.execute(
            """
            INSERT INTO schedule_quality_metric_results (
              evaluation_run_id, project_key, schedule_version_key, metric_code, metric_name,
              metric_family, numerator, denominator, value, unit, threshold_warning,
              threshold_fail, status, not_measurable_reason, evidence_json,
              related_finding_codes_json, created_at
            )
            SELECT
              evaluation_run_id, project_key, schedule_version_key, metric_code, metric_name,
              metric_family, numerator, denominator, value, unit, threshold_warning,
              threshold_fail, status, not_measurable_reason, evidence_json,
              related_finding_codes_json, created_at
            FROM schedule_quality_metric_results_v70
            """
        )
        conn.execute("DROP TABLE schedule_quality_metric_results_v70")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sq_metrics_run ON schedule_quality_metric_results(evaluation_run_id)"
        )

    @staticmethod
    def _reconcile_v71_schedule_quality_source_export(conn: sqlite3.Connection) -> None:
        from hb_assistant.store.schedule_float_tables import (
            METRIC_FAMILY_CHECK_VALUES,
            METRIC_STATUS_CHECK_VALUES,
        )

        cur = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='schedule_quality_metric_results'"
        )
        row = cur.fetchone()
        if not row or not row[0]:
            return
        ddl = str(row[0])
        if "source_export" in ddl and "available_xer_driving_path" in ddl:
            return
        families = ", ".join(f"'{f}'" for f in METRIC_FAMILY_CHECK_VALUES)
        statuses = ", ".join(f"'{s}'" for s in METRIC_STATUS_CHECK_VALUES)
        conn.execute(
            "ALTER TABLE schedule_quality_metric_results RENAME TO schedule_quality_metric_results_v71"
        )
        conn.execute(
            f"""
            CREATE TABLE schedule_quality_metric_results (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              evaluation_run_id TEXT NOT NULL,
              project_key TEXT NOT NULL,
              schedule_version_key TEXT NOT NULL,
              metric_code TEXT NOT NULL,
              metric_name TEXT NOT NULL,
              metric_family TEXT NOT NULL CHECK(metric_family IN ({families})),
              numerator TEXT,
              denominator TEXT,
              value TEXT,
              unit TEXT,
              threshold_warning TEXT,
              threshold_fail TEXT,
              status TEXT NOT NULL CHECK(status IN ({statuses})),
              not_measurable_reason TEXT,
              evidence_json TEXT,
              related_finding_codes_json TEXT,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY (evaluation_run_id) REFERENCES schedule_quality_evaluation_runs(evaluation_run_id)
            );
            """
        )
        conn.execute(
            """
            INSERT INTO schedule_quality_metric_results (
              evaluation_run_id, project_key, schedule_version_key, metric_code, metric_name,
              metric_family, numerator, denominator, value, unit, threshold_warning,
              threshold_fail, status, not_measurable_reason, evidence_json,
              related_finding_codes_json, created_at
            )
            SELECT
              evaluation_run_id, project_key, schedule_version_key, metric_code, metric_name,
              metric_family, numerator, denominator, value, unit, threshold_warning,
              threshold_fail, status, not_measurable_reason, evidence_json,
              related_finding_codes_json, created_at
            FROM schedule_quality_metric_results_v71
            """
        )
        conn.execute("DROP TABLE schedule_quality_metric_results_v71")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sq_metrics_run ON schedule_quality_metric_results(evaluation_run_id)"
        )

    @staticmethod
    def _reconcile_v67_metric_status_check(conn: sqlite3.Connection) -> None:
        from hb_assistant.store.schedule_float_tables import METRIC_STATUS_CHECK_VALUES

        cur = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='schedule_quality_metric_results'"
        )
        row = cur.fetchone()
        if not row or not row[0]:
            return
        if "measured_from_xer_driving_path" in str(row[0]):
            return
        statuses = ", ".join(f"'{s}'" for s in METRIC_STATUS_CHECK_VALUES)
        conn.execute("ALTER TABLE schedule_quality_metric_results RENAME TO schedule_quality_metric_results_v66")
        conn.execute(
            f"""
            CREATE TABLE schedule_quality_metric_results (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              evaluation_run_id TEXT NOT NULL,
              project_key TEXT NOT NULL,
              schedule_version_key TEXT NOT NULL,
              metric_code TEXT NOT NULL,
              metric_name TEXT NOT NULL,
              metric_family TEXT NOT NULL CHECK(metric_family IN ('dcma', 'gao', 'aace')),
              numerator TEXT,
              denominator TEXT,
              value TEXT,
              unit TEXT,
              threshold_warning TEXT,
              threshold_fail TEXT,
              status TEXT NOT NULL CHECK(status IN ({statuses})),
              not_measurable_reason TEXT,
              evidence_json TEXT,
              related_finding_codes_json TEXT,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY (evaluation_run_id) REFERENCES schedule_quality_evaluation_runs(evaluation_run_id)
            );
            """
        )
        conn.execute(
            """
            INSERT INTO schedule_quality_metric_results (
              evaluation_run_id, project_key, schedule_version_key, metric_code, metric_name,
              metric_family, numerator, denominator, value, unit, threshold_warning,
              threshold_fail, status, not_measurable_reason, evidence_json,
              related_finding_codes_json, created_at
            )
            SELECT
              evaluation_run_id, project_key, schedule_version_key, metric_code, metric_name,
              metric_family, numerator, denominator, value, unit, threshold_warning,
              threshold_fail, status, not_measurable_reason, evidence_json,
              related_finding_codes_json, created_at
            FROM schedule_quality_metric_results_v66
            """
        )
        conn.execute("DROP TABLE schedule_quality_metric_results_v66")

    @staticmethod
    def _reconcile_v67_source_format_check(conn: sqlite3.Connection) -> None:
        cur = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='schedule_file_imports'"
        )
        row = cur.fetchone()
        if not row or not row[0] or "ms_project_xml" in str(row[0]):
            return
        old_info = list(conn.execute("PRAGMA table_info(schedule_file_imports)"))
        if not old_info:
            return
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute(
            """
            CREATE TABLE schedule_file_imports_v67 (
              import_id TEXT PRIMARY KEY,
              project_key TEXT NOT NULL,
              procore_project_id TEXT,
              source_type TEXT NOT NULL CHECK(source_type IN ('procore_api', 'xml', 'xer', 'csv')),
              source_format TEXT NOT NULL CHECK(source_format IN (
                'procore_json', 'primavera_pmxml', 'primavera_xer', 'ms_project_xml', 'csv'
              )),
              source_filename_redacted TEXT,
              source_file_sha256 TEXT,
              source_payload_sha256 TEXT,
              parser_name TEXT,
              parser_version TEXT,
              import_status TEXT NOT NULL DEFAULT 'previewed' CHECK(import_status IN (
                'previewed', 'committed', 'failed', 'superseded'
              )),
              validation_status TEXT,
              activity_count INTEGER NOT NULL DEFAULT 0,
              relationship_count INTEGER NOT NULL DEFAULT 0,
              wbs_count INTEGER NOT NULL DEFAULT 0,
              calendar_count INTEGER NOT NULL DEFAULT 0,
              code_count INTEGER NOT NULL DEFAULT 0,
              udf_count INTEGER NOT NULL DEFAULT 0,
              cost_loaded_status TEXT NOT NULL DEFAULT 'not_cost_loaded' CHECK(cost_loaded_status IN (
                'not_cost_loaded', 'possible', 'verified', 'unreconciled'
              )),
              schedule_version_key TEXT,
              evidence_package_id TEXT,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              created_by_operator TEXT
            );
            """
        )
        base_cols = {r[1] for r in conn.execute("PRAGMA table_info(schedule_file_imports_v67)")}
        for col_name, col_type in ((r[1], r[2]) for r in old_info):
            if col_name not in base_cols:
                conn.execute(
                    f"ALTER TABLE schedule_file_imports_v67 ADD COLUMN {col_name} {col_type}"
                )
        all_cols = [r[1] for r in conn.execute("PRAGMA table_info(schedule_file_imports)")]
        new_cols = {r[1] for r in conn.execute("PRAGMA table_info(schedule_file_imports_v67)")}
        present = [c for c in all_cols if c in new_cols]
        if present:
            cols_sql = ", ".join(present)
            conn.execute(
                f"INSERT INTO schedule_file_imports_v67 ({cols_sql}) "
                f"SELECT {cols_sql} FROM schedule_file_imports"
            )
        conn.execute("DROP TABLE schedule_file_imports")
        conn.execute("ALTER TABLE schedule_file_imports_v67 RENAME TO schedule_file_imports")
        conn.execute("PRAGMA foreign_keys=ON")

    @staticmethod
    def _reconcile_v65_metric_status_check(conn: sqlite3.Connection) -> None:
        from hb_assistant.store.schedule_float_tables import METRIC_STATUS_CHECK_VALUES

        cur = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='schedule_quality_metric_results'"
        )
        row = cur.fetchone()
        if not row or not row[0]:
            return
        if "measured_from_derived_finish_float" in str(row[0]):
            return
        statuses = ", ".join(f"'{s}'" for s in METRIC_STATUS_CHECK_VALUES)
        conn.execute("ALTER TABLE schedule_quality_metric_results RENAME TO schedule_quality_metric_results_v64")
        conn.execute(
            f"""
            CREATE TABLE schedule_quality_metric_results (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              evaluation_run_id TEXT NOT NULL,
              project_key TEXT NOT NULL,
              schedule_version_key TEXT NOT NULL,
              metric_code TEXT NOT NULL,
              metric_name TEXT NOT NULL,
              metric_family TEXT NOT NULL CHECK(metric_family IN ('dcma', 'gao', 'aace')),
              numerator TEXT,
              denominator TEXT,
              value TEXT,
              unit TEXT,
              threshold_warning TEXT,
              threshold_fail TEXT,
              status TEXT NOT NULL CHECK(status IN ({statuses})),
              not_measurable_reason TEXT,
              evidence_json TEXT,
              related_finding_codes_json TEXT,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY (evaluation_run_id) REFERENCES schedule_quality_evaluation_runs(evaluation_run_id)
            );
            """
        )
        conn.execute(
            """
            INSERT INTO schedule_quality_metric_results (
              id, evaluation_run_id, project_key, schedule_version_key, metric_code, metric_name,
              metric_family, numerator, denominator, value, unit, threshold_warning, threshold_fail,
              status, not_measurable_reason, evidence_json, related_finding_codes_json, created_at
            )
            SELECT
              id, evaluation_run_id, project_key, schedule_version_key, metric_code, metric_name,
              metric_family, numerator, denominator, value, unit, threshold_warning, threshold_fail,
              status, not_measurable_reason, evidence_json, related_finding_codes_json, created_at
            FROM schedule_quality_metric_results_v64
            """
        )
        conn.execute("DROP TABLE schedule_quality_metric_results_v64")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sq_metrics_run ON schedule_quality_metric_results(evaluation_run_id)"
        )

    @staticmethod
    def _v47_statements() -> list[str]:
        """Endpoint-specific structured projection DDL, generated from the committed
        Procore projection registry. Imported lazily so the migrator carries no
        import-time dependency on the procore package."""
        from hb_assistant.procore.projection_registry import build_v47_ddl

        return build_v47_ddl()

    @classmethod
    def _reconcile_v53_eval_items(cls, conn: sqlite3.Connection) -> None:
        """Rebuild ``ranking_policy_eval_items`` to add ``ranking_run_id`` + the composite PK.

        Idempotent and guarded: a no-op once ``ranking_run_id`` exists (fresh DBs created by the new
        V53-aware migrator already have it; here V52 creates the original shape and this rebuilds it).
        Non-destructive — existing rows are copied into the rebuilt table (legacy rows, which carry no
        run id, are backfilled with ``ranking_run_id='unknown'``). The table holds only derived,
        regenerable telemetry; in practice it is empty wherever this reconcile runs.
        """
        cols = {row[1] for row in conn.execute("PRAGMA table_info(ranking_policy_eval_items)")}
        if not cols or "ranking_run_id" in cols:
            return  # table absent (pre-V52) or already reconciled
        new_ddl = f"""
        CREATE TABLE ranking_policy_eval_items__v53 (
          eval_run_id TEXT NOT NULL,
          ranking_run_id TEXT NOT NULL,
          daily_brief_action_candidate_id TEXT NOT NULL,
          rank_position INTEGER,
          section_key TEXT,
          candidate_family TEXT,
          source_family TEXT,
          project_key TEXT,
          deterministic_score REAL,
          feedback_score REAL,
          model_advisory_score REAL,
          final_score REAL,
          model_advisory_used INTEGER NOT NULL DEFAULT 0,
          outcome_type TEXT,
          outcome_weight REAL,
          outcome_lag_hours REAL,
          source_ref_count INTEGER NOT NULL DEFAULT 0,
          eval_notes_json TEXT,
          created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP{cls._P10_GUARDS},
          PRIMARY KEY (eval_run_id, ranking_run_id, daily_brief_action_candidate_id)
        );
        """
        conn.execute("DROP TABLE IF EXISTS ranking_policy_eval_items__v53")
        conn.execute(new_ddl)
        conn.execute(
            """
            INSERT INTO ranking_policy_eval_items__v53 (
              eval_run_id, ranking_run_id, daily_brief_action_candidate_id, rank_position, section_key,
              candidate_family, source_family, project_key, deterministic_score, feedback_score,
              model_advisory_score, final_score, model_advisory_used, outcome_type, outcome_weight,
              outcome_lag_hours, source_ref_count, eval_notes_json, created_utc
            )
            SELECT
              eval_run_id, 'unknown', daily_brief_action_candidate_id, rank_position, section_key,
              candidate_family, source_family, project_key, deterministic_score, feedback_score,
              model_advisory_score, final_score, model_advisory_used, outcome_type, outcome_weight,
              outcome_lag_hours, source_ref_count, eval_notes_json, created_utc
            FROM ranking_policy_eval_items
            """
        )
        conn.execute("DROP TABLE ranking_policy_eval_items")
        conn.execute("ALTER TABLE ranking_policy_eval_items__v53 RENAME TO ranking_policy_eval_items")
        for stmt in (
            "CREATE INDEX IF NOT EXISTS ix_ranking_policy_eval_items_run ON ranking_policy_eval_items(eval_run_id);",
            "CREATE INDEX IF NOT EXISTS ix_ranking_policy_eval_items_ranking_run ON ranking_policy_eval_items(ranking_run_id);",
            "CREATE INDEX IF NOT EXISTS ix_ranking_policy_eval_items_candidate ON ranking_policy_eval_items(daily_brief_action_candidate_id);",
            "CREATE INDEX IF NOT EXISTS ix_ranking_policy_eval_items_family ON ranking_policy_eval_items(candidate_family);",
        ):
            conn.execute(stmt)

    @staticmethod
    def _reconcile_v48_columns(conn: sqlite3.Connection) -> None:
        """Add registry-required curated columns missing from existing ``procore_ep_*``
        tables (additive ``ALTER TABLE ADD COLUMN``). Idempotent; introspects physical
        columns and only adds the missing ones. Imported lazily."""
        from hb_assistant.procore.projection_registry import reconcile_column_alters

        existing: dict[str, set[str]] = {}
        for (name,) in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'procore_ep_%'"
        ).fetchall():
            existing[name] = {row[1] for row in conn.execute(f"PRAGMA table_info({name})")}
        for stmt in reconcile_column_alters(existing):
            conn.execute(stmt)

    @staticmethod
    def _v49_create_statements() -> list[str]:
        """Structured email/calendar projection + receipt DDL, generated from the committed
        email/calendar projection registry. Imported lazily so the migrator carries no
        import-time dependency on the construction package."""
        from hb_assistant.construction.email_calendar.schema import build_v49_ddl

        return build_v49_ddl()

    @staticmethod
    def _v49_raw_column_alters(conn: sqlite3.Connection) -> list[str]:
        """Guarded ADD COLUMN statements for missing source-quality/provenance columns on the
        three V42 raw tables (returns only columns absent from the physical table)."""
        from hb_assistant.construction.email_calendar.schema import raw_table_column_alters

        return raw_table_column_alters(conn)

    @staticmethod
    def _reconcile_v49_columns(conn: sqlite3.Connection) -> None:
        """Add registry-required curated columns missing from the structured projection
        tables (additive ALTER TABLE ADD COLUMN; idempotent). Mirrors V48 reconciliation."""
        from hb_assistant.construction.email_calendar.schema import reconcile_structured_columns

        reconcile_structured_columns(conn)

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
