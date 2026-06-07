# 202 — Procore Safe Status and Auth Bridge

Status: Active · Package: `graph-procore-dev-ui-connections-implementation-package` (P03) · App version 1.3.0

## Context

Procore analog of arch-doc 201 (Graph). P03 adds a browser-safe Procore namespace
`/api/sources/procore/*` so the Dev/Production UI (P06/P07) can render Procore status and drive safe
OAuth — without calling Procore project-list/sync/live-content APIs, starting sync, or leaking
tokens/secrets/cache paths. Status additionally reports correct **missing-config** and
**missing-mapping** states.

## Contracts

| Route | Method | Role | Purpose |
|---|---|---|---|
| `/api/sources/procore/status` | GET | viewer+ (all-roles) | Normalized Procore status (metadata-only) |
| `/api/sources/procore/auth/start` | POST | operator+ | Start OAuth flow (authorization URL + flow_id) |
| `/api/sources/procore/auth/callback?code&state` | GET | none (CSRF state + one-time code) | Browser callback; safe HTML |
| `/api/sources/procore/auth/status?flow_id=` | GET | operator+ | Poll the OAuth flow |
| `/api/sources/procore/auth/refresh` | POST | operator+ | Safe silent token refresh (no sync, no data API) |

### `GET /api/sources/procore/status` shape
`{surface:"analytics.sources.procore.status", system:"procore", state, auth_status, ready_for_live_calls,
token_cache_present, keychain_secret_present, env_keys_present, env_keys_missing,
expires_in_seconds_if_known, missing_config, missing_mapping, mapping{status, ok, company_id, total,
by_status, pending_projects}, live_reads_enabled, hint, guardrails}`.

`state` derivation:
- `not_configured` — no OAuth credentials reachable (status `env_absent` and no keychain secret).
- `configured_not_connected` — credentials present but no local token cache (needs OAuth).
- `connected` — local token cache present.

`missing_config` = not config-present. `missing_mapping` = mapping `ok is False` (any `pending` project);
an unreadable mapping yields `ok: None` and is **not** treated as missing.

## Implementation

- New methods `AuthOnboardingService.procore_source_status()` + `_procore_mapping_summary()`
  (`src/hb_assistant/construction/analytics/auth_onboarding.py`). The first reuses the existing offline
  `procore_status()`; the second runs the offline `EndpointAuditor(load_endpoint_contract(),
  load_procore_projects()).validate_mapping()` (pure YAML projection). No new auth logic.
- Routes added in `src/hb_assistant/construction/analytics/api.py` (next to the P02 `/api/sources/graph/*`).
  Auth routes reuse `start_procore_auth_flow()`, `handle_procore_oauth_callback()`,
  `poll_procore_auth_status()`, and the safe `attempt_auth_refresh(["procore"])`. The callback returns
  `Response(content=html, media_type="text/html")`, mirroring the existing connections callback.

## Safety posture

- **No live Procore client / no projects-list / no sync**: status uses `check_auth_status()` (env-var +
  token-cache-file + macOS-keychain presence) and the offline mapping validator; neither constructs
  `ProcoreHTTPClient` (test asserts it raises if built). Refresh uses the token-provider chain
  `get_access_token()` (silent OAuth refresh only if near expiry); never a data API, never sync.
- **No tokens / secrets / cache paths**: responses carry `_auth_guardrails()` with `tokens_returned:False`,
  `secrets_returned:False`, `procore_data_api_called:False`, `cli_shellout:False`; callback emits safe
  static HTML only. Tests grep a FORBIDDEN substring list (incl. synthetic tokens).
- **Correct missing-config / missing-mapping states** surfaced explicitly.

## Tests

`tests/test_fastapi_analytics_procore_source_bridge.py` (mirrors the auth-onboarding harness with
`_FakeProcoreClient`): metadata-only + safe, no live Procore client constructed, missing-config /
connected / missing-mapping / complete-mapping states, OAuth start→poll, callback safe HTML, safe
refresh, and role gating (viewer 403 on auth routes, 200 on `/status`, callback reachable without role).
`tests/test_fastapi_analytics_app_shell.py` openapi allowlist extended with the five routes.

## Verification (P03)

Live against the dev backend: `GET :8000/api/sources/procore/status` → 200 with `state`,
`missing_config`, `missing_mapping`, `mapping`, no secrets; operator `POST /api/sources/procore/auth/refresh`
→ 200 procore result; viewer → 403 on auth routes / 200 on `/status`. Response grep for
`access_token|refresh_token|client_secret|BEGIN PRIVATE` → none. Full `-k fastapi_analytics` suite green.
