# 11 — Data Freshness Contract

`freshness.py` reads status straight from SQLite read-only (`file:{db}?mode=ro` +
`PRAGMA query_only`, reusing `db_tools._ro_uri`'s storage guard). The obsidian
source-intelligence Python API is NAS-blocked, so nothing is read via that service.

## Aggregate-only, redaction-safe
Every query is `COUNT` / `MAX(timestamp)` / latest-status-enum over a **hardcoded** table set —
never `SELECT *`, never row content, never raw paths. This does NOT widen the generic
`hb_db_select` allowlist. Free-text error fields are passed through `redact_text`.

## Explicit state, no false confidence
Each query is guarded by a `sqlite_master` existence check:
`not_configured` (table absent) vs `unknown` (present but empty) vs `ok` (recent) vs `stale`
(present but older than ~25h). Absent/unavailable data is reported explicitly, never fabricated.

## Domains (from the real schema)
schema_version (`schema_migrations`), source-intelligence index + queue
(`source_intelligence_metadata`/`_events`), daily brief (`daily_brief_runs`), email/drive/calendar
sync (`*_sync_state.last_successful_sync_utc`), Procore (`procore_live_sync_runs`), AI-Outputs
mutations (`mutations.jsonl` tail), and the **watcher = `unknown` / not_available_on_nas**
(in-memory only). The broken allowlist entry `schema_version`→`schema_migrations` was fixed.

## Tools (Tier 0, origin-auth-required, safe-mode-available)
`hb_data_freshness`, `hb_queue_status`, `hb_recent_failures`, `hb_last_successful_runs`,
`hb_capability_mode`.
