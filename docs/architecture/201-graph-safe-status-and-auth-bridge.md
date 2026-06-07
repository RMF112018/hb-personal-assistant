# 201 — Microsoft Graph Safe Status and Auth Bridge

Status: Active · Package: `graph-procore-dev-ui-connections-implementation-package` (P02) · App version 1.3.0

## Context

P01 added the aggregate `/api/environment` + `/api/sources/status`. P02 adds a dedicated, browser-safe
Microsoft Graph namespace `/api/sources/graph/*` so the Dev/Production UI (P06/P07) can render Microsoft
365 status and drive backend-controlled auth — without ever reading mail/calendar/files or starting
sync, and without leaking tokens/secrets/cache paths.

## Contracts

| Route | Method | Role | Purpose |
|---|---|---|---|
| `/api/sources/graph/status` | GET | viewer+ (all-roles) | Normalized Graph status (metadata-only) |
| `/api/sources/graph/auth/start` | POST | operator+ | Start device-code flow (backend-controlled) |
| `/api/sources/graph/auth/status?flow_id=` | GET | operator+ | Poll the device-code flow |
| `/api/sources/graph/auth/refresh` | POST | operator+ | Safe silent refresh (no content read, no sync) |

Naming split (mirrors existing code): `/status` = source status (viewer-safe); `/auth/status` =
device-flow poll (operator).

### `GET /api/sources/graph/status` shape
`{surface:"analytics.sources.graph.status", system:"microsoft_365_graph", state, token_type,
classification, account, tenant, scopes, expires_in_seconds_if_known, scope_presence{expected, missing,
all_present}, scope_diagnostics, next_step, message, guardrails}`.

`state` is derived from `graph_status()`:
- `connected_valid` — token_type delegated + classification `delegated_verified`
- `reauth_required` — classification `stale_reauth_required`
- `cache_present_unverified` — classification `delegated_cache_present`
- `not_connected` — otherwise

`scope_presence.missing` = `EXPECTED_GRAPH_SCOPES` (`user.read, mail.read, calendars.read,
files.read.all`) minus the union of configured + granted scopes.

## Implementation

- New method `AuthOnboardingService.graph_source_status()`
  (`src/hb_assistant/construction/analytics/auth_onboarding.py`) reuses the existing offline
  `graph_status()` and adds the normalized `state` + `scope_presence`. No new auth logic.
- Routes added in `src/hb_assistant/construction/analytics/api.py` (next to the P01 `/api/sources/*`).
  Auth routes reuse the existing `start_graph_device_auth()`, `poll_graph_device_auth_status()`, and the
  safe `attempt_auth_refresh(["graph"])`.

## Safety posture

- **No content (mail/calendar/files) API call**: status uses `graph_status()` → silent MSAL
  verification (`acquire_token_silent`, network only to login.microsoftonline.com); no `GraphHttpClient`
  is constructed (test asserts it raises if built). Refresh uses `provider.get_token(force_refresh=False)`
  (silent MSAL), never a Graph data API, never starts sync.
- **No tokens / secrets / cache paths**: responses carry `_auth_guardrails()` with `tokens_returned:False`,
  `secrets_returned:False`, `graph_data_api_called:False`, `cli_shellout:False`; only safe account/tenant
  hints are surfaced. Tests grep a FORBIDDEN substring list (incl. the synthetic token).
- **Correct stale / missing-scope states**: `reauth_required` from stale classification;
  `scope_presence.missing` flags insufficient scopes.

## Tests

`tests/test_fastapi_analytics_graph_source_bridge.py` (mirrors the auth-onboarding harness):
metadata-only + safe, no Graph data client constructed, not-connected / connected_valid / stale /
missing-scope states, device start→poll (pending→complete), safe refresh, and role gating (viewer 403 on
auth routes, 200 on `/status`). `tests/test_fastapi_analytics_app_shell.py` openapi allowlist extended
with the four routes.

## Verification (P02)

Live against the dev backend: `GET :8000/api/sources/graph/status` → 200 with `state` + `scope_presence`,
no secrets; operator `POST /api/sources/graph/auth/refresh` → 200 graph result; viewer → 403 on auth
routes / 200 on `/status`. Response grep for `access_token|refresh_token|client_secret|BEGIN PRIVATE` →
none. Full `-k fastapi_analytics` suite green.
