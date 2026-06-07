# 04 Schema Plan

## Additive migration

Do not mutate existing tables destructively. Add new raw-content tables and/or columns.

## Preferred approach

Use separate raw-content tables keyed to existing read-model rows. This reduces risk to existing metadata-only behavior.

## Proposed tables

- `email_message_raw_content`
- `email_thread_raw_context`
- `calendar_event_raw_content`
- `raw_content_processing_receipts`
- `raw_content_model_context_packets`
- `raw_content_access_events`
- `raw_content_policy_state`

## Required fields

### `email_message_raw_content`

- `message_id_hash`
- `internet_message_id_hash`
- `conversation_id_hash`
- `subject`
- `body_preview`
- `body_text`
- `body_html`
- `from_name`
- `from_address`
- `to_recipients_json`
- `cc_recipients_json`
- `sent_at_utc`
- `received_at_utc`
- `has_attachments`
- `attachment_metadata_json`
- `source_ref_hash`
- `created_utc`
- `updated_utc`

### `calendar_event_raw_content`

- `event_index_id`
- `graph_event_id_hash`
- `subject`
- `body_preview`
- `body_text`
- `body_html`
- `location_display`
- `organizer_name`
- `organizer_email`
- `attendees_json`
- `online_meeting_provider`
- `join_url`
- `start_datetime_utc`
- `end_datetime_utc`
- `source_ref_hash`
- `created_utc`
- `updated_utc`

## Indexes

- source ref hash;
- message/event hash;
- received/sent/start date;
- project key if known;
- conversation/thread hash.

## Migration acceptance

- Existing metadata-only tables remain usable.
- Raw-content tables can be empty when disabled.
- Raw-content tables populate when enabled.
