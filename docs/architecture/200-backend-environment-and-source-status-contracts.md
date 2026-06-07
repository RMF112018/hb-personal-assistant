# 200 — Backend Environment and Source Status Contracts

Status: Active · Package: `graph-procore-dev-ui-connections-implementation-package` (P01) · App version 1.3.0

## Context

P00 classified gap **GPC-P0-001**: the Dev UI had no aggregate source-status surface — the backend
returned `404` for `GET /api/environment` and `GET /api/sources/status`, so the UI could not show
"running in Dev / local-mock mode" or a single Graph + Procore + scheduler/freshness summary. P01 adds
those two browser-safe, read-only, **offline** routes. Frontend wiring is deferred to P05/P06.

## Contracts

Both routes are `GET`, all-roles (viewer/operator/admin), and return user-safe JSON ending with the
standard `guardrails` block (`read_only`, `no_live_endpoint_calls`, `no_external_writeback`, …). They
return `200` even when a sub-section cannot be read (degraded sub-section → safe `{status:"unavailable"}`).

### `GET /api/environment`
`{surface:"analytics.environment", status, environment ("dev"|"production"), source_refresh_mode,
frontend_url, frontend_port, backend_port, app_support_root (home-redacted to ~), live_reads{…},
live_refresh{available,enabled,reason}, guardrails}`.

### `GET /api/sources/status`
Same environment/mode/live fields plus per-source summaries:
- `graph`: `{system, token_type, classification, account, expires_in_seconds_if_known}`
- `procore`: `{system, status, cache_present, ready_for_live_calls, expires_in_seconds_if_known}`
- `scheduler`: `{enabled, last_status, last_successful_schedule_date, last_attempted_schedule_date,
  consecutive_failures, next_expected_run, schedule_time_local, timezone, live_reads_enabled}`

## Implementation

- New service: `src/hb_assistant/construction/analytics/environment_status.py` →
  `EnvironmentStatusService` (db-free; mirrors the per-domain service pattern of `auth_onboarding.py`).
- Routes added in `src/hb_assistant/construction/analytics/api.py` (next to `/api/settings/sources`),
  exported from `analytics/__init__.py`.

### Environment resolution decision (important)

Environment is inferred from the resolved Application Support root name:
`"dev" if PathPolicy().get_app_support().name.endswith("(Dev)") else "production"`. `PathPolicy()` uses
`load_config()`, which honors the launcher's **`HB_PA_CONFIG`** signal (set to the dev config in dev,
unset in production).

We deliberately **do not** call `launcher.profiles.resolve_profile()` from inside the API process. In
the dev backend subprocess `load_config()` already returns the dev-rooted config, so `resolve_profile()`
would re-append `" (Dev)"` (`profiles.py:163` `_dev_root`) and produce a double-`(Dev)` path. The small
set of profile-derived constants we need (`source_refresh_mode`, ports) are replicated directly instead.

### Offline status sources reused (no live data client, no subprocess)

- `PathPolicy()` / `load_config()` — paths + `cfg.automation.scheduler` live flags + `cfg.launcher.*` ports.
- `hb_assistant.procore.live_gate.live_env_active()` — `HB_PROCORE_LIVE == "1"`.
- `AuthOnboardingService().build_combined_status()` — the SAME safe status aggregator `/api/settings/accounts`
  uses (reads local auth cache; never returns tokens; never calls a Graph/Procore **data** API).
- `SchedulerState.load(<root>/scheduler-state/daily-source-refresh.json, environment=…)` — pure file read.

## Safety posture

- No tokens / secrets / cache paths in responses (app-support root is home-redacted to `~`).
- No live Graph/Procore **data** client is constructed by the status path (test asserts `GraphHttpClient`
  / `ProcoreHTTPClient` are never built).
- Live-read flags default **OFF**; Dev `live_refresh.enabled` is always `False`
  (`reason: dev_local_mock_only`) — Dev live refresh disabled by default.
- Per-section try/except returns safe `unavailable` instead of leaking internals; endpoints stay `200`.

## Tests

`tests/test_fastapi_analytics_environment_status.py` — 200 + safe payload, live flags off by default,
all-roles access, aggregate summaries present, dev-mode local/mock inference, and no-live-data-client
construction. `tests/test_fastapi_analytics_app_shell.py` openapi allowlist updated with both routes.

## Verification (P01)

End-to-end against the running dev backend: `GET /api/environment` → `environment:"dev"`,
`source_refresh_mode:"mock_data"`, all live flags `false`; `GET /api/sources/status` → graph/procore/
scheduler summaries; both `200` via the `:5173` proxy and direct `:8000` (P00's `404` resolved); response
grep for `access_token|refresh_token|client_secret|BEGIN PRIVATE KEY` → none.
