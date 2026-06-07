-- Phase 10A raw-content schema addendum draft.
-- Additive only. Translate into the current SQLiteMigrator head + 1.

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
  updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(message_id_hash)
);

CREATE INDEX IF NOT EXISTS idx_email_message_raw_content_conversation
ON email_message_raw_content(conversation_id_hash);

CREATE INDEX IF NOT EXISTS idx_email_message_raw_content_received
ON email_message_raw_content(received_at_utc);

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
  updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(graph_event_id_hash)
);

CREATE INDEX IF NOT EXISTS idx_calendar_event_raw_content_start
ON calendar_event_raw_content(start_datetime_utc);

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

CREATE TABLE IF NOT EXISTS raw_content_access_events (
  access_event_id TEXT PRIMARY KEY,
  source_family TEXT NOT NULL,
  source_ref_hash TEXT,
  endpoint_or_command TEXT NOT NULL,
  raw_content_included INTEGER NOT NULL DEFAULT 1,
  purpose TEXT,
  created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
