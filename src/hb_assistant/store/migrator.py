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
