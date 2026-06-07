# 172 — Prompt A: Auth Route Contract and Safe Status Models

**Objective:** Establish the canonical, frontend-facing backend contract for onboarding readiness, account connection status, auth refresh, project connection setup, admin first-sync approval, and data-quality summary/detail. Introduce shared safe Pydantic response models and the explicit 7-state source auth model + 5-state onboarding model. All surfaces are read-only with respect to external systems and sync; no tokens, secrets, raw payloads, cache paths, or signed/download URLs are ever emitted.

## Route Families (Additive)

All new routes live under the normalized prefixes. Every pre-existing route (including root-level `/onboarding/auth/status`, `/auth/*`, `/connections/*`, `/admin/connections/*`, `/api/settings/*`, dashboard `/api/*`, etc.) remains exactly as before so that existing tests and any direct callers continue to function without modification.

- `GET /api/onboarding/readiness` — safe startup/decision surface. Returns `OnboardingReadinessResponse` shape (or equivalent dict). Computes `onboarding_state`, `required_actions`, `reauth_required`, coarse `data_quality`, and booleans for `main_app_allowed` / `get_started_required`. May consult local caches and pending approval state; never initiates device flows, OAuth, or sync.
- `GET /api/settings/connections/accounts` — safe per-source account summaries (`ConnectionsAccountsResponse`).
- `POST /api/settings/connections/auth/refresh` — safe refresh attempt for stale-but-refreshable sources. Current implementation is a status-preserving stub (reports before/after); future increments may wire silent refresh where providers support it. Never escalates to interactive login or starts sync.
- Project connections (preview/save/list) under `/api/settings/connections/projects/*` — thin delegates to the same `ConnectionSetupService` used by the legacy `/connections/*` paths, guaranteeing identical guardrails and "first_sync_triggered": false behavior.
- Admin approval under `/api/settings/connections/admin/*` — thin delegate for `approve_first_sync`; still requires admin role and still returns `first_sync_triggered: false`.
- Data quality: `GET /api/settings/data-quality/summary` (viewer-safe compact indicator) and `GET /api/settings/data-quality/detail` (admin-only richer advisory metadata, no raw content). Implemented as safe projections over existing admin confidence / gate evaluators.

## Shared Safe Models (Prompt A)

Defined in `src/hb_assistant/construction/analytics/api.py` (colocated with other request/response models for the optional FastAPI shell; also realized as plain dicts returned by services for flexibility).

Enums / literals:

- `AuthSource`: `graph | procore`
- `AuthStatus`: `never_connected | connected_valid | connected_refreshing | connected_stale_refreshable | connected_stale_reauth_required | connected_error | disconnected_by_user`
- `OnboardingState`: `first_time | ready | degraded | reauth_required | blocked`
- `DataQualityStatus`: `good | degraded | poor | unknown`
- `ApprovalStatus`: `not_requested | pending | approved | rejected | not_required`

Key response shapes (see `04_BACKEND_ROUTE_CONTRACTS.md` and `auth_route_contracts.json` in the implementation package for the authoritative examples):

- `OnboardingReadinessResponse`
- `ConnectionsAccountsResponse` (graph + procore `AccountStatus`)
- `AuthRefreshResponse` (array of per-source before/after items)
- Project preview/save and admin approval envelopes (safe metadata + `guardrails`; `first_sync_triggered` always false except where explicitly documented as not triggered).
- `DataQualitySummary` / `DataQualityDetail`

All models and service outputs carry a `guardrails` object declaring `tokens_returned: false`, `secrets_returned: false`, `no_live_endpoint_calls`, etc.

## State Machines (Implemented in AuthOnboardingService)

`AuthOnboardingService` (extended for Prompt A) owns the pure mapping from internal status dicts (`graph_status()`, `procore_status()`, `build_combined_status()`) plus lightweight local signals (cache presence, pending approvals) to the 7 `AuthStatus` values per source.

- `never_connected`: no usable cache/token type for the source.
- `connected_valid`: cache present and the service reports ready_for_live_calls / delegated+cache_present.
- `connected_stale_refreshable`, `connected_stale_reauth_required`, `connected_error`, `connected_refreshing`, `disconnected_by_user`: conservative fallbacks or future promotions from refresh/approval flows (the mapping starts with valid vs. never; refresh stub can simulate a transition for contract completeness).

`build_readiness(...)` composes the two source states + `has_prior_setup` (any cached auth or any pending/approved construction sources) into one of the 5 `OnboardingState` values using the rules documented in `03_TARGET_ARCHITECTURE.md`:

- `first_time`: graph never_connected and no prior setup.
- `reauth_required`: any required source is in a reauth state.
- `ready`: at least one source valid (or stale-refreshable) and prior setup present.
- `degraded`: partial data or stale-but-not-blocked.
- `blocked`: no usable path forward without user action.

`build_account_summaries()` and `attempt_auth_refresh()` produce the exact contract shapes used by `/api/settings/connections/accounts` and the refresh POST. The refresh method is intentionally a safe stub for this prompt; it never calls live data APIs and never starts sync.

`ConnectionSetupService` continues to be the single source of truth for preview/save/approve/first-sync-status. The new normalized paths are thin adapters only.

Data-quality summary/detail are derived from the existing `AnalyticsService` admin confidence builders + phase gates (phase_09_gates, table inventory, etc.). They remain advisory, `readiness_overstated: false`, and contain no raw document text, prompts, or external payloads.

## Guardrails (Enforced)

- No Microsoft 365 / Procore writeback.
- No raw email bodies, document text, prompts/responses, tokens, PEMs, cache paths, signed or download URLs in any response (existing `FORBIDDEN` redaction sets in tests cover the new paths).
- Readiness, preview, save, list, and refresh never start live sync (`first_sync_triggered` remains false; admin approve still only flips local sync_status to `approved_first_sync_not_started`).
- Role model unchanged: viewer for read surfaces; operator for local writes (save, refresh trigger); admin for approvals and detailed admin data-quality.
- All new surfaces declare the standard guardrails (`local_first`, `no_cli_shellout`, `no_live_endpoint_calls`, `no_external_writeback`, `tokens_returned: false`, ...).
- Legacy root paths and their exact request/response bodies are untouched (the OpenAPI path set asserted by `tests/test_fastapi_analytics_app_shell.py` remains identical).

## Files Changed (This Prompt)

- `src/hb_assistant/construction/analytics/api.py` — new request/response models, new route handlers (additive), thin delegation to services, removal of transient duplicate mappers after moving logic to the service.
- `src/hb_assistant/construction/analytics/auth_onboarding.py` — added `build_readiness`, `build_account_summaries`, `attempt_auth_refresh`, and the internal `_map_internal_to_auth_status` (pure).
- `tests/test_fastapi_analytics_auth_onboarding.py` — new tests for the contract paths, state values (including the 7 auth states), onboarding transitions, redaction, and role behavior. Existing tests untouched.
- `tests/test_fastapi_analytics_settings.py` — light additional coverage asserting the new normalized paths are reachable with parity.
- `docs/architecture/172-prompt-a-auth-route-contracts-and-safe-models.md` — this document.

No changes to CLI, store schema, external auth providers, or any pre-existing route definitions.

## Validation

See the package-level `PROMPT_A_*` acceptance commands. After implementation the exact suite is:

```
python -m pytest tests/test_fastapi_analytics_auth_onboarding.py tests/test_fastapi_analytics_settings.py tests/test_fastapi_analytics_connection_setup.py
python -m ruff check src/hb_assistant/construction/analytics tests/test_fastapi_analytics_auth_onboarding.py
python -m mypy src/hb_assistant/construction/analytics
```

All must pass with no new forbidden leaks and the pre-existing OpenAPI path inventory test still green.

## References

- Planning package: `docs/planning/HB_Auth_Onboarding_Implementation_Package/`
  - `04_BACKEND_ROUTE_CONTRACTS.md`
  - `data/auth_route_contracts.json`
  - `03_TARGET_ARCHITECTURE.md`
  - `05_FRONTEND_UX_SPEC.md` (for how the frontend will call these)
- Prior surfaces: `docs/architecture/171-fastapi-auth-onboarding-surfaces.md`
- Safety / redaction precedent: Prompt 13 UI-13 proofs and the `FORBIDDEN` sets in the analytics FastAPI tests.

This prompt delivers only the contract + models + safe status surfaces. Full device-code / OAuth wiring beyond shells, and any frontend UI, are out of scope (per the prompt). Later prompts will consume these routes for Get Started, Settings → Connections, and Admin approval flows.