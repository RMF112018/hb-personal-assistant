You are working with Bobby on repository `RMF112018/hb-personal-assistant` at local path `/Users/bobbyfetting/hb-personal-assistant`.

This is an implementation prompt within `docs/planning/email_calendar_full_raw_content_ingestion_package/`.

Hard rules:
- Do not mutate the production DB during audit or validation; use `/tmp` copies.
- Do not run Microsoft Graph writes.
- Do not store OAuth access tokens, refresh tokens, auth headers, client secrets, signed URLs outside explicitly approved local DB policy, or credential-cache contents.
- Do not emit raw email/calendar bodies to stdout, logs, repo evidence, browser/status JSON, Obsidian, committed fixtures, or test snapshots.
- Use synthetic fixtures for tests that need body text.
- Stop and ask Bobby if a destructive migration or new tenant/admin Graph consent becomes necessary.

# 01 — Schema and Policy Strategy

## Objective

Implement or finalize the additive schema/policy substrate that makes full raw email/calendar local DB storage explicit, bounded, source-quality-classified, auditable, and safe at outbound boundaries.

## Required repo-truth starting point

Expected current schema head is V46. Reconfirm before editing. If head has advanced, use the next available migration number and update all tests/docs accordingly.

Existing raw tables should be preserved:

```text
raw_content_policy_state
email_message_raw_content
email_thread_raw_context
calendar_event_raw_content
raw_content_model_context_packets
raw_content_access_events
```

## Implementation requirements

Additive-only migration. No DROP, destructive ALTER, or data rewrite required.

Implement the next migration, expected V47, to add missing columns/tables needed for production-quality source-quality precedence.

Recommended additions:

### `email_message_raw_content`

Add if absent:

```text
source_quality TEXT NOT NULL DEFAULT 'metadata_only'
raw_capture_run_id TEXT
source_record_ref TEXT
source_record_id INTEGER
source_updated_at_utc TEXT
payload_hash TEXT
raw_content_schema_version TEXT NOT NULL DEFAULT 'email_raw_v1'
```

Allowed `source_quality` values:

```text
graph_full_body
graph_body_preview_only
redacted_legacy_projection
metadata_only
```

### `email_thread_raw_context`

Add if absent:

```text
source_quality TEXT NOT NULL DEFAULT 'metadata_only'
raw_capture_run_id TEXT
payload_hash TEXT
raw_content_schema_version TEXT NOT NULL DEFAULT 'email_thread_raw_v1'
```

### `calendar_event_raw_content`

Add if absent:

```text
source_quality TEXT NOT NULL DEFAULT 'metadata_only'
raw_capture_run_id TEXT
source_record_ref TEXT
source_record_id INTEGER
source_updated_at_utc TEXT
payload_hash TEXT
raw_content_schema_version TEXT NOT NULL DEFAULT 'calendar_raw_v1'
join_url_policy TEXT NOT NULL DEFAULT 'local_db_only'
```

Allowed `source_quality` values:

```text
graph_full_event_body
graph_body_preview_only
redacted_legacy_projection
metadata_only
```

### Optional run receipt

Create if useful:

```text
email_calendar_raw_ingestion_runs
```

Minimum columns:

```text
run_id TEXT PRIMARY KEY
source_family TEXT NOT NULL CHECK(source_family IN ('email','calendar'))
mode TEXT NOT NULL CHECK(mode IN ('dry_run','apply'))
started_utc TEXT NOT NULL
completed_utc TEXT
items_seen INTEGER NOT NULL DEFAULT 0
items_attempted_raw INTEGER NOT NULL DEFAULT 0
items_raw_persisted INTEGER NOT NULL DEFAULT 0
source_quality_distribution_json TEXT NOT NULL DEFAULT '{}'
status TEXT NOT NULL
error_redacted TEXT
raw_body_emitted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_emitted = 0)
external_writeback_performed INTEGER NOT NULL DEFAULT 0 CHECK(external_writeback_performed = 0)
```

## Policy semantics

Update config/policy models so these are unambiguous:

- DB-local raw storage: explicit opt-in; can persist raw business content locally.
- Outbound surfaces: redacted by default.
- Model context: explicit raw inclusion, bounded, logged.
- Access audit: raw reads write `raw_content_access_events`.
- Explicit CLI `--include-raw-content` must not silently bypass a disabled policy unless the command is a dry-run diagnostic designed to show what would happen.

## Tests

Add fixture tests for:

- migration applies from old schema and is idempotent;
- source-quality defaults exist;
- allowed source-quality values are validated in application code;
- legacy lower-quality row cannot overwrite higher-quality raw row;
- policy defaults are disabled/fail-closed for outbound raw emission.

## Evidence

Create:

```text
docs/evidence/email-calendar-full-raw-content-ingestion/01_schema_and_policy_strategy.md
```

Include schema version before/after, added columns/tables, and test results only.
