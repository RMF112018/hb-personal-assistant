# Runbook — Obsidian Source-Intelligence Runtime (single-owner watcher)

How the external-source watcher runs safely, and what to check before/while it runs.

## Single-owner watcher lease
Only one backend may run the watcher drain loop against a given DB/source-root context. The lease
lives in two `source_intelligence_state` rows (no DB migration): `watcher_owner` (JSON owner_info)
and `watcher_heartbeat_at`.

- On `SourceWatcher.start()` the instance tries to acquire the lease. A **live different owner**
  (fresh heartbeat) → this instance serves the API but stays **degraded** (no drain thread, no
  observer); `status.degraded = true`, `last_error_code = "watcher_not_owner"`, `mode = "degraded"`.
- A **stale** lease (heartbeat older than the TTL, `WATCHER_LEASE_TTL_SECONDS = 900s`, e.g. a
  crashed owner) is reclaimable: the new owner takes over and `requeue_stuck` recovers any
  in-flight events.
- The worker refreshes its heartbeat each drain pass; `stop()` releases the lease only if this
  instance owns it. A lease-check DB error fails **open** (a healthy single backend is never blocked).

### Reading watcher state
`GET /api/settings/obsidian-mcp/source-watch/status` (viewer-readable) and the nested `watcher`
block of `GET /api/settings/obsidian-mcp/source-index/status` include:
`running`, `mode`, `degraded`, `is_owner`, and `owner` (redacted: `pid`, `cwd`, `db_path`,
`roots_hash`, `started_at`, `heartbeat_at`, `heartbeat_age_seconds`, `stale` — the internal
`owner_token` nonce is NOT exposed; no bearer token is ever included).

## Clean-runtime preflight
- Confirm exactly one intended backend: `lsof -nP -iTCP:8000`.
- If two backends share the DB, the second reports `degraded: true` with the live owner's `pid`/`cwd`
  — stop the unintended one rather than forcing it.
- Skip codes: a skipped queue event is a clean terminal state, not an error. New skips carry a named
  `error_code`; a code-less new skip is stamped `unspecified_skip` (a regression signal), distinct
  from the legacy NULL→`unspecified` read-time bucket. Watch `skipped_by_code` in source-index status.
- Generated `Source Notes/` cards never re-enter indexing: the self-index guard is scoped to the
  vault root + configured `source_notes_folder` (an external root that merely contains a folder
  named "Source Notes" is indexed normally).

## Caps (unchanged by this work)
`source_card_auto_max_per_drain`, `source_summary_auto_max_per_drain`,
`external_source_scan_max_files` bound each drain/scan. The watcher never indexes on the request loop.
