# Defect 6 close-out — freshness reporting hardening + ingest writer fixes

Branch `fix/nas-mcp-freshness-defect6` off `origin/main` @ `7f869a9b`. Follows the deployed 10-defect
remediation (7 pass on the last connector retest; only Defect 6 open). No schema/migration; no tool
add/remove/rename; security posture unchanged (RO snapshot; brokered/idempotent writes; workspace DB
isolated).

## What the retest surfaced

The last connector retest read Defect 6 (freshness) as **not proven**: `email_sync` and `drive_sync`
reported a bare `unknown`, and `calendar_sync` reported `anomaly_future_timestamp`. Read-only
investigation of the live snapshot + the ingest code established the ground truth: the states are
**honest but under-informative**, and they trace to two ingest-side writer bugs plus one operational
condition.

- **email** (`email_sync_state`): `sync_status='completed'`, `last_attempted_sync_utc`≈2026-06-07, but
  `last_successful_sync_utc` was **always NULL** — the writer hard-coded `NULL` in that column. The
  reporter keys freshness off the success column, so a month-stale mailbox read as `unknown`.
- **calendar** (`calendar_sync_state`): `last_successful_sync_utc` was written as `window_end_utc`
  (the forward-looking `now + lookahead_days` window end) → a **future** timestamp, correctly flagged
  `anomaly_future_timestamp`.
- **drive** (`construction_source_sync_state`): genuinely `pending_admin_approval` (SharePoint admin
  consent), timestamps NULL → shown as `unknown`. Operational, not a code bug.

No subsystem is in `error/failed`, so `degraded_last_run_failed` cannot appear from current data — that
mapping is unit-proven and fires only on a real failed sync.

## Fixes

### Part 1 — MCP freshness reporting (`nas_mcp/freshness.py`) — reporting-only; makes stale data legible

1. **`_sync_domain`** gained an optional `attempted_col` fallback: when `MAX(last_successful_sync_utc)`
   is NULL but `MAX(last_attempted_sync_utc)` exists, age is computed from the attempt and the row is
   marked `never_succeeded: true` + `basis: "last_attempt"`; the latest-status read is ordered by
   `attempted_col or ts_col`. → email now reads `stale` (`never_succeeded`) instead of `unknown`.
2. **`_apply_last_status`** gained `_BLOCKED_STATUSES` (`pending_admin_approval`, `blocked`, `disabled`,
   `paused`) → new `STATUS_BLOCKED = "blocked_or_pending"`, applied when the headline is
   ok/stale/**unknown**. → drive now reads `blocked_or_pending` instead of `unknown`. The existing
   failure→`degraded_last_run_failed` and future→anomaly behavior are unchanged.
3. **`data_freshness`** passes `attempted_col="last_attempted_sync_utc"` to the email/drive/calendar
   `_sync_domain` calls. `last_successful_runs()` is left unchanged (it must show success only).

### Part 2 — ingest writer fixes (`construction/store/repositories.py`) — corrects future writes

1. **Email** — `apply_project_email_discover_batch`: the `last_successful_sync_utc` VALUES column was
   literal `NULL`; now bound to `now` (`_utc_now()`), and `last_successful_sync_utc =
   excluded.last_successful_sync_utc` added to the `ON CONFLICT DO UPDATE` clause. Runs only on the
   success path (inside the batch tx), mirroring the drive delta-sync ok-path.
2. **Calendar** — `apply_calendar_index_batch`: `last_successful_sync_utc` bind changed from
   `window_end_utc` to the already-computed completion time `now_done`, keeping the
   `(not chunked or is_final_chunk) else None` guard.

## Effect timing (not overclaimed)

Part 1 lands on the live surface via the **MCP redeploy** and immediately improves how the *current*
snapshot reads (email → `stale`/`never_succeeded`; drive → `blocked_or_pending`; calendar →
`anomaly_future_timestamp`). Part 2 corrects the *writers*, which run in the ingest pipeline (not the
internet-facing container); the live calendar/email values only become `ok` after the next ingest run
with the fixed code **and** a snapshot refresh. `degraded_last_run_failed` still requires an actual
`error/failed` sync — none exists today.

## Validation

- **Part 1 units** (`test_nas_mcp_client_readiness_10x.py`):
  `test_freshness_blocked_status_surfaced_from_unknown` (unknown + `pending_admin_approval` →
  `blocked_or_pending`); `test_freshness_sync_domain_falls_back_to_last_attempt` (success NULL +
  attempt present → `stale` + `never_succeeded` + `basis:last_attempt`).
- **Part 2 units**:
  `test_project_discovery.py::test_discover_records_last_successful_sync` — after a committing
  discover, `email_sync_state.last_successful_sync_utc` is set on INSERT and stays set (monotonic)
  through the ON CONFLICT re-sync.
  `test_calendar_event_indexing.py::test_sync_state_records_completion_time_not_future_window` —
  `calendar_sync_state.last_successful_sync_utc` is the completion time, `!=`/`<` `window_end_utc`,
  and not in the future.
- **Regression** (new tests + plan list): `test_calendar_event_indexing.py`,
  `test_project_discovery.py`, `test_nas_mcp_client_readiness_10x.py`,
  `test_freshness_observability_agent.py`, `test_email_operational_schema_v11.py`,
  `test_email_folder_discovery.py`, `test_fastapi_analytics_connection_setup.py`,
  `test_fastapi_analytics_sync_governance.py` → **108 passed, 1 failed**. The single failure,
  `test_raw_content_flag_produces_rows_and_counts` (`assert dry.raw_content_enabled is False`), is
  **pre-existing on `origin/main`** (raw-content policy artifact, unrelated to this change; the
  `or True` SIM222 line it lives near is also pre-existing) — verified via `git show
  origin/main:tests/test_calendar_event_indexing.py`.
- `scripts/test-schedule.sh` canary — see `schedule-bundle-output-defect6.txt` (repositories.py is a
  shared construction module).
- `ruff check` clean on all touched source + test files.

## Post-deploy live check (via connector)

`hb_data_freshness` (or `data_freshness`) should show: email → `stale` with `never_succeeded:true`
(last_attempt ≈ 2026-06-07); drive → `blocked_or_pending` (`last_status:pending_admin_approval`);
calendar → `anomaly_future_timestamp` (until a re-sync runs with the Part-2 writer + snapshot refresh).
No subsystem should read a bare `unknown` for a state that is actually stale or blocked.
