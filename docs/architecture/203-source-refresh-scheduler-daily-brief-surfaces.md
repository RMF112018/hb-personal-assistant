# 203 — Source Refresh, Scheduler, and Daily Brief Status Surfaces

Status: Active · Package: `graph-procore-dev-ui-connections-implementation-package` (P04) · App version 1.3.0

## Context

P01–P03 added the read-only environment/source/Graph/Procore status + auth bridges. P04 adds the
UI-facing **action + status** surfaces — refresh (dry-run / local / live), scheduler status, and
daily-brief status — **without weakening gates**. All refresh modes reuse the in-process
`SourceRefreshOrchestrator`; the daily-brief surface reuses the existing `/api/daily-brief/status`.

## Contracts

| Route | Method | Role | Purpose |
|---|---|---|---|
| `/api/sources/refresh/dry-run` | POST | operator+ | Plan only — **no DB write**, no network |
| `/api/sources/refresh/local` | POST | operator+ | Rebuild local SQLite — **no live client** |
| `/api/sources/refresh/live` | POST | operator+ | Gated live refresh — **fails closed** by default |
| `/api/scheduler/daily-source-refresh/status` | GET | viewer+ | Scheduler schedule/freshness status |
| `/api/daily-brief/status` | GET | viewer+ | (Pre-existing) daily-brief status — reused, unchanged |

### Refresh gate matrix
| Mode | RefreshOptions | DB write | Live client | Notes |
|---|---|---|---|---|
| dry-run | `apply=False, allow_*_live=False` | no | no | `dry_run:true`, zero upserts |
| local | `apply=True, confirm=True, mock_data=True, allow_*_live=False` | local only | no | `live_mode:"local_only"` |
| live | `apply=True, confirm=True, mock_data=False, allow_*_live=<config>` | local only | gated | see fail-closed |

All three set `all_=True, skip_vector=True, skip_daily_brief_proof=True` so the action is scoped to
source data (procore+graph+sqlite) with **no vault/vector side effects**. The orchestrator's `db_path` is
threaded from `create_app(db_path=…)` so the refresh targets the active environment DB (and the temp DB
under test).

### Live fail-closed rule
`live(confirm)` returns `{status:"blocked", live_read_performed:false, reason}` **without running any
live read** unless ALL of: `environment == "production"`, `config.automation.scheduler.enable_live_reads`,
and `confirm == true`. Reasons: `dev_live_disabled`, `live_reads_disabled_by_config`,
`confirmation_required`. When permitted, the run is wrapped in a `HB_PROCORE_LIVE` set/restore
contextmanager and the orchestrator still independently fails closed on auth-not-ready. Dev and the
default production config both fail closed.

### Scheduler status shape
`{surface:"analytics.scheduler.daily_source_refresh.status", job_id, environment, enabled,
schedule_time_local, timezone, catch_up_on_wake, current_local_date, next_expected_run,
next_expected_run_from_state, last_status, last_successful_schedule_date, last_attempted_schedule_date,
consecutive_failures, live_reads_enabled, state_health, guardrails}`.

## Implementation

- New service `src/hb_assistant/construction/analytics/source_refresh_control.py`
  (`SourceRefreshControlService`) — db_path-aware wrapper over `SourceRefreshOrchestrator` with the three
  modes + the live fail-closed gate. Returns the orchestrator's metadata-only summary (it writes nothing
  to disk — `write_evidence()` is not called).
- `EnvironmentStatusService.build_scheduler_status()` (`environment_status.py`) — built from
  `config.automation.scheduler` + `SchedulerState.load(...)` + `scheduler.due.compute_next_run` /
  `current_local_date`. No native-backend subprocess and **no `resolve_profile`** (avoids the dev
  double-`(Dev)` path bug); environment is derived from the `PathPolicy` root name.
- Routes added in `api.py` (next to the P01–P03 `/api/sources/*` routes) + `RefreshLiveRequest{confirm}`.
- `/api/daily-brief/status` already existed (`DailyBriefService.get_status()`, metadata-only, offline) and
  satisfies the daily-brief requirement — reused as-is.

## Safety posture

- **Dry-run writes no DB** (test counts temp-DB rows before/after → unchanged; `inserted/updated == 0`).
- **Local/mock constructs no live client** (test makes `GraphHttpClient`/`ProcoreHTTPClient` raise; mode
  reports `live_reads_enabled:false`, `live_mode:"local_only"`).
- **Live fails closed** (blocked, `live_read_performed:false`, no client built) for both `confirm:true`
  and `confirm:false` in non-permitting environments.
- **No raw payloads in receipts**: the orchestrator summary is metadata-only (`_GUARDRAILS_BASE` has
  `no_raw_*`, `local_sqlite_only`, `fail_closed`); tests grep a FORBIDDEN substring list.

## Tests

`tests/test_fastapi_analytics_source_refresh_surfaces.py`: dry-run no-write, local no-live, live
fail-closed (×2 confirm values), scheduler status safe, daily-brief reuse, and role gating (viewer 403
on refresh POSTs, 200 on status). `tests/test_fastapi_analytics_app_shell.py` openapi allowlist extended
with the four new routes.

## Verification (P04)

Live against the dev backend: `POST :8000/api/sources/refresh/dry-run` (operator) → 200 `dry_run:true`,
zero upserts; `…/refresh/local` → 200 `live_mode:"local_only"`; `…/refresh/live` `{confirm:true}` → 200
`status:"blocked"` reason `dev_live_disabled`; `GET …/scheduler/daily-source-refresh/status` → 200 with
schedule/next-run/last-status; viewer → 403 on refresh POSTs. Response grep for
`access_token|refresh_token|client_secret|BEGIN PRIVATE|Bearer ` → none. Full `-k fastapi_analytics`
suite green.
