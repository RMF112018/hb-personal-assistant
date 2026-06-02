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
LATEST_SCHEMA_VERSION = 30


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
