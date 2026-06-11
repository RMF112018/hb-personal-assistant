# Expected DB Invariants

All validation uses `/tmp` DB copies.

## Schema / Substrate

Expected tables, subject to repo-truth confirmation:

- `email_message_raw_content`
- `email_thread_raw_context`
- `email_raw_message_structured`
- `email_raw_thread_structured`
- `email_raw_thread_messages_structured`
- `email_raw_message_recipients_structured`
- `email_raw_message_attachments_structured`
- `raw_content_access_events`
- `email_calendar_projection_runs`
- `email_calendar_projection_coverage`
- `follow_up_watch_items`
- `email_followup_enrichments`
- `task_candidates`
- `commitment_candidates`
- `accepted_tasks`
- `accepted_commitments`
- `daily_brief_action_candidates`
- `candidate_source_refs`
- `daily_brief_source_refs`
- `construction_project_identity`
- `construction_project_keyword_registry`
- `construction_project_source_matches`

## Required Invariants

- Email/calendar structured projection coverage is complete before extraction.
- Total unmapped business fields is zero.
- Email-derived daily-brief candidates have at least one `candidate_source_refs` row.
- Email-derived daily-brief source-ref coverage is 1.0.
- Executive source-ref coverage remains 1.0.
- Idempotency replay does not increase candidate counts on the second run.
- Guard/leak columns remain zero.
- Raw access events only increase when explicit `load_body(...)` access occurs.
- No external writeback receipts appear.
- Project-key coverage is reported, not guessed.
- Unresolved project-like items are marked review-required.

## Safe Count Queries

See `templates/raw_safe_sql_checks.sql`.
