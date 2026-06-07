# 173 — Prompt B: Microsoft Graph Local Auth Flow

**Objective:** Implement the split MSAL device-code authentication flow (start + safe pollable status that drives completion), silent verification/refresh on cached credentials, and local-only disconnect behind the normalized `/api/settings/connections/graph/*` contract. Enhance `graph_status` and readiness/account summaries so that "connected" status is based on verified silent acquisition (not merely cache file presence), stale auth triggers a silent attempt before emitting `reauth_required`, and all 7 `AuthStatus` + 5 `OnboardingState` values are supported in the Prompt A contract shapes. Legacy root routes (`/auth/graph/*`, `/onboarding/auth/status`, etc.) and their exact behaviors are preserved.

## Routes (Additive, Contract-Normative)

All new surfaces live under the settings connections family (per the HB Auth Onboarding Implementation Package contracts). Every pre-existing route and response body remains unchanged.

- `POST /api/settings/connections/graph/auth/start` (operator/admin) — calls provider to `initiate_device_flow` with the configured (sanitized) delegated scopes. Returns the safe contract shape:
  ```json
  {
    "flow_id": "opaque-local-session-id",
    "verification_uri": "https://microsoft.com/devicelogin",
    "user_code": "ABCD-EFGH",
    "expires_at": "2026-...",
    "interval_seconds": 5,
    "message": "Sign in to Microsoft 365 using the displayed code. Connecting does not start sync.",
    "guardrails": { "tokens_returned": false, ... }
  }
  ```
- `GET /api/settings/connections/graph/auth/status?flow_id=...` (operator/admin) — fast path for in-memory flow expiry; otherwise drives `acquire_token_by_device_flow`. Returns one of:
  - `{ "status": "pending", "message": "Waiting for user..." }`
  - `{ "status": "complete", "account": { "display_name": null, "account_hint": "...", "tenant_hint": "...", "scopes": ["User.Read", ...] }, "message": "Microsoft 365 is connected." }`
  - `{ "status": "expired" | "failed" | "cancelled", ... }`
- `POST /api/settings/connections/graph/disconnect-local` (operator/admin) — calls `DelegatedAuthProvider.logout()` (clear delegated cache + `remove_account`). The returned cache paths are discarded (never serialized). Returns a safe confirmation envelope. Post-disconnect, subsequent status/readiness report `never_connected` (or equivalent) for Graph.

These coexist with the legacy `/auth/graph/status`, `/auth/graph/device-login/start|complete` surfaces (which continue to function for any direct callers or older tests).

## Service Implementation (AuthOnboardingService)

- `start_graph_device_auth()` / `poll_graph_device_auth_status(flow_id)` / `disconnect_graph_local()` share the module-level `_GRAPH_FLOWS` in-memory registry with the legacy `start_graph_device_login` / `complete...` methods. Slots store `flow`, `provider`, `raw_scopes`, plus `started_at` + `expires_in` for time-based expiry on poll without blocking.
- Poll logic:
  - Missing slot → "failed".
  - Expiry (started + expires_in) → pop + "expired".
  - `acquire_token_by_device_flow` returns access_token → save cache via provider, pop, return "complete" + safe `account` envelope derived from `id_token_claims` (or backfilled via the provider's `_ensure_delegated_id_token_claims` path) + scopes from diagnostics. Never returns the access/refresh/id tokens.
  - `authorization_pending` / `slow_down` → "pending" (slot retained for next poll).
  - Other terminal (expired/denied/...) → pop + "expired" or "failed".
- `disconnect_graph_local()` calls provider logout (best-effort), returns `{ok, kind: "graph_disconnected_local", message, guardrails}`. No cache paths are included.
- Guardrails reused from `_auth_guardrails()` (tokens_returned: false, no data APIs called, no cli shellout, local_cache_only, etc.).

## Verified Status + Silent Refresh (Core Enhancement)

`graph_status()` (used by legacy `/auth/graph/status`, `build_combined_status`, `build_account_summaries`, and the Prompt A normalized readiness/accounts) now:

- If a delegated cache file is present on disk, instantiates `DelegatedAuthProvider` and calls `status_info()` (which internally does `get_token()` → `acquire_token_silent` + claims backfill via `_ensure...` + scope diagnostics).
- On success: `token_type: "delegated"`, `classification: "delegated_verified"`, `account`/`tenant`/`scopes`/`expires_in_seconds_if_known` populated from the verified result/claims (safe values only).
- On `NoTokenError` or any exception during the silent attempt: `classification: "stale_reauth_required"` (or error variant) with a safe message. Cache file presence alone no longer implies "valid".
- `build_readiness(...)` and `build_account_summaries()` (and the 7-state `_map_internal_to_auth_status`) now see honest states. An explicit silent attempt block is also present at the start of `build_readiness` (re-samples `graph_status` after) to guarantee "startup readiness attempts silent refresh before prompting reauth".
- The 7 `AuthStatus` values are produced by the updated mapper:
  - `connected_valid` (verified silent success)
  - `connected_stale_reauth_required` (cache present but silent failed)
  - `never_connected` (no cache)
  - `connected_error` (other verification failure)
  - `connected_stale_refreshable` / `disconnected_by_user` / `connected_refreshing` supported in the type system and in refresh surface/decision paths (refresh action now performs a real `get_token` attempt for stale* cases and reports before/after).
- `attempt_auth_refresh(...)` for Graph now performs an actual silent `get_token(force_refresh=False)` when the mapped state is stale*, promoting to `connected_valid` on success (still safe; never starts sync or interactive login).

Result: `/api/settings/connections/accounts`, `/api/onboarding/readiness`, and the legacy graph status surfaces all reflect verified state and avoid premature "ready" or missing reauth prompts.

## Guardrails & Safety (Non-Negotiable)

- No access/refresh/id/bearer tokens, no `msal-token-cache.bin` path (or its directory), no raw claims, no signed/download URLs, no PEMs, no raw external payloads ever appear in any response (existing `FORBIDDEN` sets + new tests cover the new paths).
- The only "live" token endpoint calls are the explicit device start (`initiate_device_flow`) and the silent acquire paths inside `get_token`/`status_info` (explicitly allowed for refresh-before-reauth). No Graph data APIs are invoked.
- No setup/auth/preview/save/refresh/approval action starts live sync (`first_sync_triggered` remains false).
- Role model: viewer may read accounts/readiness; operator+ required for start/poll/disconnect (consistent with prior device-login surfaces).
- Legacy root paths and their request/response bodies are byte-for-byte unchanged (the sole test update in `app_shell` is the minimal addition of the three new paths to the OpenAPI `paths == {...}` literal so the equality continues to hold).
- Scopes: runtime uses the configured `delegated_scopes` from `IdentityConfig` (sanitized only for MSAL-reserved by `scope_policy`). Broad consented scopes (e.g. `Files.ReadWrite.All`) are preserved for compatibility; no-writeback is enforced at policy/client/store layers (not by scope narrowing here).
- After explicit disconnect, the delegated cache is cleared; subsequent status/readiness correctly reflect the unauthenticated state for Graph.

## Files Changed (Minimal Set)

- `src/hb_assistant/construction/analytics/api.py` — three new route handlers under `/api/settings/connections/graph/auth/*` (after the legacy graph routes), role wiring, delegation to service, guardrails.
- `src/hb_assistant/construction/analytics/auth_onboarding.py` — new contract methods (`start_graph_device_auth`, `poll_...`, `disconnect...`); enhanced `graph_status` (silent verify), `build_readiness` (explicit attempt + re-sample), `build_account_summaries`, `attempt_auth_refresh` (real silent), and `_map_internal_to_auth_status` (7-state support + verified classification). Top-level datetime import.
- `tests/test_fastapi_analytics_auth_onboarding.py` — extended `_FakeMsalApp` (controllable `acquire_mode` for pending/expired/fail), updated `_install_graph_fake` (mode reset + comment), new tests for start/poll 5-states, verified transition, readiness silent-before-reauth, disconnect safety/redaction, role gates. All prior tests (including legacy complete + readiness transition) remain green.
- `tests/test_fastapi_analytics_settings.py` — light reachability/safety test for the new graph auth contract paths.
- `tests/test_fastapi_analytics_app_shell.py` — one-line addition of the three new paths to the `paths == {...}` set (only addition; no legacy paths removed).
- `docs/architecture/173-prompt-b-microsoft-graph-local-auth-flow.md` — this document (contract, flow, verified status integration, state machine, guardrails, mermaid, references).

No changes to `providers.py` (existing `status_info` / `get_token` / `_ensure...` / `logout` / `safe_redact_claims` were sufficient), Procore paths, data clients, sync, CLI, schema, or scope configuration.

## Mermaid Diagrams

Split device flow + poll (high level):

```mermaid
sequenceDiagram
    participant UI as Frontend (operator)
    participant R as FastAPI (/api/settings/connections/graph/auth/*)
    participant S as AuthOnboardingService
    participant P as DelegatedAuthProvider + MSAL
    UI->>R: POST /start (operator)
    R->>S: start_graph_device_auth()
    S->>P: _get_app().initiate_device_flow(sanitized_configured_scopes)
    P-->>S: flow (user_code, uri, expires_in, interval)
    S-->>R: {flow_id, verification_uri, user_code, expires_at, interval_seconds, message, guardrails}
    R-->>UI: ...
    Note over UI: User completes in browser (no tokens ever returned to UI)
    loop poll
        UI->>R: GET /status?flow_id=...
        R->>S: poll_graph_device_auth_status(flow_id)
        alt pending (authorization_pending from acquire)
            S-->>R: {status:"pending", ...}   ;; slot retained
        else success
            S->>P: acquire + save_cache (delegated)
            S-->>R: {status:"complete", account:{account_hint, tenant_hint, scopes}, message}
            Note over S: slot popped
        else expired/failed/cancelled
            S-->>R: {status: "..."} ;; slot popped
        end
        R-->>UI: ...
    end
    UI->>R: POST /disconnect-local (operator)
    R->>S: disconnect_graph_local()
    S->>P: logout()  ;; clear delegated cache + remove_account (paths discarded, never serialized)
    S-->>R: {ok, kind:"graph_disconnected_local", message, guardrails}
    R-->>UI: ...
```

Readiness + silent verify (startup / accounts path):

```mermaid
flowchart TD
  Readiness[GET /api/onboarding/readiness<br/>or /api/settings/connections/accounts] --> S[AuthOnboardingService.build_readiness / build_account_summaries]
  S --> GS[graph_status (enhanced)]
  GS --> HasCache{cache file present?}
  HasCache -->|no| Never[never_connected]
  HasCache -->|yes| Silent[prov.status_info()<br/>== get_token() → acquire_token_silent + claims backfill]
  Silent -->|success + claims| Valid[connected_valid<br/>+ safe account/tenant/scopes/expires]
  Silent -->|NoTokenError / exception| Stale[connected_stale_reauth_required or connected_error]
  Valid --> Map[_map_internal_to_auth_status<br/>produces one of 7 AuthStatus]
  Stale --> Map
  Never --> Map
  Map --> Reauth{graph in reauth_required states?}
  Reauth -->|yes| ReauthList[include in reauth_required + required_actions]
  Reauth -->|no| Decide[decide overall OnboardingState<br/>first_time / ready / degraded / reauth_required / blocked]
  Decide --> Out[return OnboardingReadinessResponse or Accounts<br/>with 7-state values + data_quality + guardrails<br/>(no tokens/paths/raw)]
```

The explicit silent attempt in `build_readiness` (plus the one inside `graph_status`) ensures a refreshable token is promoted before the reauth list and state are finalized.

## References

- Planning package (authoritative contracts): `docs/planning/HB_Auth_Onboarding_Implementation_Package/04_BACKEND_ROUTE_CONTRACTS.md`, `data/auth_route_contracts.json`, `03_TARGET_ARCHITECTURE.md`, `05_FRONTEND_UX_SPEC.md`, `PROMPT_B_MICROSOFT_GRAPH_LOCAL_AUTH_FLOW.md`.
- Prior architecture: `171-fastapi-auth-onboarding-surfaces.md`, `172-prompt-a-auth-route-contracts-and-safe-models.md`.
- Core primitives reused: `src/hb_assistant/auth/providers.py` (`DelegatedAuthProvider`, `get_token`/`status_info`/`logout`, `_ensure_delegated_id_token_claims`, `safe_redact_claims`), `token_cache_manager.py`, `scope_policy.py`; `src/hb_assistant/construction/analytics/auth_onboarding.py` (service) and `api.py` (shell).
- Safety precedent: Prompt 13 UI-13 redaction proofs and the `FORBIDDEN` sets in analytics FastAPI tests.

This prompt delivers the local-first Graph auth contract and verified status behavior. No data sync, no writeback, no secret leakage, and no change to pre-existing surfaces. Later prompts (e.g. Procore Prompt C, frontend Get Started/Settings) consume these surfaces.