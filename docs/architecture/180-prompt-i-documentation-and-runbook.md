# 180 — Prompt I — Documentation and Runbook (HB Auth Onboarding Implementation Package)

**Date:** 2026-06-07  
**Package:** HB Auth Onboarding Implementation Package (manifest 1.3.0)  
**Repository:** `/Users/bobbyfetting/hb-personal-assistant`  
**Status:** Complete (Prompts A–I executed and validated against repo truth)

## Objective

Update documentation and operator runbooks after implementation and validation are complete for the auth/onboarding surfaces that enable first-time and returning local operators to connect Microsoft Graph and Procore accounts, preview and save project/source connections, obtain admin first-sync approval, and observe safe data-quality/readiness signals — all while preserving the local-first, read-only, no-writeback, admin-approval, and strict non-exposure posture.

## Scope (as executed)

- Document first-time Get Started flow.
- Document Microsoft 365 device-code auth.
- Document Procore OAuth callback and manual fallback.
- Document stale-auth automated refresh and reauth behavior.
- Document Project Connections preview/save/admin approval flow.
- Document Data Quality indicator meanings (non-admin vs admin).
- Document security guardrails and no-writeback posture.
- Document local smoke testing (harness + manual).

Non-scope items observed and respected:
- No claims that external API sync is newly production-ready beyond what prior phases and tests already established.
- No tokens, screenshots with codes, cache paths, or secrets in any doc.
- No documentation of unsupported deployment assumptions.

## Implemented Normalized Route Contract (Prompt A baseline, extended by B–G)

The authoritative frontend-facing contract (coexists with legacy root-level surfaces for compatibility only; UI and typed clients use the `/api/...` family):

- `GET /api/onboarding/readiness` → `OnboardingReadinessResponse` (onboarding_state: first_time | ready | degraded | reauth_required | blocked; get_started_required; data_quality: DataQualitySummary; safe messages; first_sync_triggered=false; guardrails).
- `GET /api/settings/connections/accounts` → `ConnectionsAccountsResponse` (graph + procore AccountStatus with 7-state auth_status, safe hints only, timestamps, no tokens/secrets/cache_path).
- `POST /api/settings/connections/auth/refresh` → `AuthRefreshResponse` (per-source results with ok/reason_code; no sync side-effect).
- Graph family:
  - `POST /api/settings/connections/graph/auth/start`
  - `GET /api/settings/connections/graph/auth/status?flow_id=...`
  - `POST /api/settings/connections/graph/disconnect-local`
- Procore family:
  - `POST /api/settings/connections/procore/auth/start`
  - `GET /api/settings/connections/procore/auth/callback` (localhost; state-validated)
  - `GET /api/settings/connections/procore/auth/status?flow_id=...`
  - `POST /api/settings/connections/procore/auth/exchange-code` (manual fallback only)
  - `POST /api/settings/connections/procore/disconnect-local`
- Project connections (auth-aware):
  - `POST /api/settings/connections/projects/preview` → `ProjectConnectionPreviewResponse` (status ready_to_save, first_sync_status pending_admin_approval, admin_approval_required, warnings, message; explicit "Preview complete. No sync has started.")
  - `POST /api/settings/connections/projects/save` → `ProjectConnectionSaveResponse` (ok, first_sync_status pending_admin_approval, message; no sync started)
- Admin approval (admin role only):
  - `POST /api/settings/connections/admin/{connection_id}/approve-first-sync` → `AdminApprovalResponse`
  - `POST /api/settings/connections/admin/{connection_id}/reject-first-sync` → `AdminApprovalResponse` (includes reason_code)
- Data Quality:
  - `GET /api/settings/data-quality/summary` (safe for viewer/operator/admin) → `DataQualitySummary` (status: unknown | poor | degraded | good; label; last_updated_at)
  - `GET /api/settings/data-quality/detail` (admin-only) → `DataQualityDetail` (per-source readiness/freshness/approval/failures/attention_items; no raw payloads)

Legacy root surfaces (`/onboarding/auth/status`, `/auth/graph/...`, `/auth/procore/...`, `/connections/...`, `/admin/...`) remain for compatibility but are not the primary contract for the current frontend.

Response models and all envelopes enforce: no access/refresh/id tokens, no client secrets, no PEMs, no signed_url/download_url, no msal/procore cache paths, no raw bodies, no raw prompts/responses, no full external payloads.

## First-Time Get Started Flow (Prompt D)

- Fully unauthenticated (or no usable prior setup) sessions receive `onboarding_state: first_time` (plus `get_started_required: true`) from readiness.
- App routing (StartupRedirect in `frontend/src/app/routes.tsx`) redirects to `/get-started`.
- `GetStartedPage` explains the sequence: connect Microsoft 365 → connect Procore → Project Connections (preview then save) → admin first-sync approval.
- Explicit copy in UI and docs: "connecting an account, previewing a source, or saving a setup does not start live sync."
- After connections are established and at least one source saved with pending approval, readiness transitions away from pure first_time for returning contexts (see stale-auth below).
- Main app shell (with sidebar) is not presented as fully ready until after the above.

## Microsoft 365 Device-Code Auth (Prompt B)

- Card: `GraphConnectionCard` (in Account Connections).
- Start: `POST .../graph/auth/start` returns safe device-code metadata only (`user_code`, `verification_uri`, `expires_in`, flow_id; short-lived).
- Operator visits verification link (or copies code) in a separate browser/profile; completes consent.
- Frontend polls `.../graph/auth/status?flow_id=...` until terminal state.
- States surfaced: `never_connected`, `connected_valid` (after silent MSAL verification where possible), `connected_refreshing`, `connected_stale_refreshable`, `connected_stale_reauth_required`, `connected_error`, `disconnected_by_user`.
- On success: safe account hints (display/account/tenant), scopes, timestamps; no tokens or cache path.
- Disconnect: local-cache only (`/disconnect-local`); does not affect external accounts.
- Readiness uses the verified status (silent refresh attempted for returning users before surfacing reauth).

## Procore OAuth (Prompt C)

- Card: `ProcoreConnectionCard`.
- Primary path: `POST .../procore/auth/start` returns safe authorization URL + opaque flow_id (state is server-side, short-lived).
- Browser is directed to the authorization URL; after consent, Procore redirects to the registered localhost callback.
- `GET .../procore/auth/callback` validates state, completes token exchange server-side, and returns a minimal success page (no tokens or secrets in the HTML/response body visible to the app).
- Status polling (`.../procore/auth/status`) reports pending/complete/expired/failed/cancelled using safe account/company hints only.
- Manual fallback: `POST .../procore/auth/exchange-code` (explicitly labeled as fallback, not primary; for cases where localhost redirect is not registered or blocked).
- Refresh-token attempt occurs before reauth prompt for returning users.
- Disconnect clears only local Procore auth state.
- No raw Procore payloads, authorization codes, state tokens, or cache paths ever leave the backend.

## Stale-Auth Automated Refresh and Reauth (Prompts A/B/C/D/H)

- Returning users with prior setup/auth are **not** forced through first-time Get Started.
- Readiness (and the refresh endpoint) attempt silent refresh for Graph (MSAL) and/or Procore (refresh token) where a prior delegated cache exists.
- Success: user proceeds to main shell; `connected_valid` (or degraded if data is old but auth ok); no user prompt.
- Failure: source-specific `connected_stale_reauth_required` (or overall `reauth_required` in onboarding_state) with actionable card in Settings / Get Started panel for that source only.
- Refresh and reauth paths never set `first_sync_triggered` and never initiate source sync.
- Tests (H) and smoke harness explicitly assert the "refresh before reauth" ordering and the absence of first-time reset for returning stale-auth sessions that still have usable prior setup.

## Project Connections Auth-Aware Setup Flow (Prompts E/F)

- Panel: `ProjectConnectionsPanel` (Settings); child `ConnectionPreviewCard`.
- Inputs (auth-aware): Procore project homepage URL (required for Procore sources); SharePoint site/folder or OneDrive scope where backend supports; Outlook/Calendar project matching (checkboxes, default false and optional).
- Auth gating: Procore card disabled until a valid Procore account connection exists; Graph-dependent sources similarly gated.
- Preview (`.../projects/preview`): parses the URL client-side + backend (no fetch of content beyond governed metadata resolution); returns sanitized `detected_source_type`, `proposed_source`, `status: ready_to_save`, `first_sync_status: pending_admin_approval`, `admin_approval_required: true`, `warnings`, and message. UI explicitly renders: "Preview complete. No sync has started." and "First sync requires admin approval (pending_admin_approval)."
- Save (`.../projects/save`): persists the connection locally (SQLite `source_locations` / `construction_project_identity` with stage `setup_pending_admin_approval`); returns pending status; does not start sync.
- Saved items appear in Admin First-Sync Approval queue (`AdminFirstSyncApprovalPanel`).
- Admin actions (`approve-first-sync` / `reject-first-sync`) are the only paths that flip eligibility. Non-admin cannot approve. Rejection records reason_code.
- No preview or save action ever produces `first_sync_triggered: true` or flips a live-sync marker (enforced by H regression tests + smoke hygiene block).

## Data Quality Readiness/Freshness Surfaces (Prompt G)

- Non-admin (viewer/operator): sidebar footer in `AppShell` renders `DataQualityIndicator` ("Data Quality" + colored dot).
  - Colors (deterministic from `build_data_quality_summary`):
    - green: good (approved sources with recent freshness)
    - yellow: degraded / attention (mixed or stale-but-present)
    - red: poor / no trusted data (all poor/unknown or no approved sources)
    - neutral/gray: unknown or loading/error
  - Hover tooltip: status label, "Last updated: <iso>", short plain-language message. No raw JSON, no per-source diagnostics, no tokens/secrets/paths.
- Admin-only (Settings → "Data Quality Diagnostics"): button loads `GET /api/settings/data-quality/detail` (403 for non-admin). Shows source-by-source readiness, freshness (last_seen_utc), approval stage, attention_items, failures. Still advisory metadata only; no raw content.
- `DataQualitySummary` is also embedded in the readiness response so startup can surface a high-level signal without extra calls.
- 4 states are exercised and asserted in tests (`test_prompt_g_data_quality_states_detail_readiness_consistency` and H regression); consistency between summary/detail/readiness.data_quality is verified.
- Summary is safe for all roles; detail is strictly admin-gated.

## Security Guardrails and No-Writeback Posture (enforced across A–I)

Hard invariants (repo truth; never weakened):

- No source-system writeback at any layer.
- No setup, auth, preview, save, refresh, or approval action may start live sync automatically (`first_sync_triggered` remains false; eligibility requires admin approval).
- No tokens (access/refresh/id), client secrets, PEM material, signed URLs, download URLs, local cache paths (`msal-token-cache*`, `procore-token-cache*`), raw source payloads, raw email bodies, raw document text, or raw prompts/responses are ever serialized to the frontend.
- Admin approval is the single gate for first live sync eligibility; both Procore project identities and Microsoft source locations participate in the same model.
- Outlook/Calendar project matching remains optional and false by default.
- Refresh updates only local auth state.
- Frontend does not use localStorage for tokens/secrets.
- All responses and rendered UI for normal users contain no raw/debug JSON panels (Prompt D/E polish).
- H regression + smoke harness (`_assert_no_forbidden`, `_assert_no_sync_triggered`, role 403 checks, UI_SURFACES drive of readiness + dq surfaces, hygiene block that fails on positive trigger or raw leaks) make these properties fail-fast on every run.

See also: planning package `06_SECURITY_GUARDRAILS.md`, `07_ONBOARDING_AND_DATA_QUALITY_SPEC.md`, and the no-writeback proofs from prior phases (re-run green).

## Local Smoke Testing (Prompt H + this runbook update)

### Scripted harness (repeatable, one-command contract + hygiene)
```bash
python -m scripts.smoke_local
# or
./scripts/smoke-local.sh
```
- Exercises `UI_SURFACES` including the H/I-critical normalized surfaces: `/api/onboarding/readiness`, `/api/settings/data-quality/summary`, `/api/settings/data-quality/detail`.
- Role headers (viewer/operator/admin simulation via `X-HB-UI-Role`); 200/403 assertions; raw-leak scan on 200 bodies (`_has_raw` against FORBIDDEN list).
- Dedicated "[Prompt H auth/onboarding/dq hygiene]" block after the main loop that re-drives key auth/setup/dq surfaces and explicitly fails on raw leaks or positive `first_sync_triggered`.
- Also runs: frontend `npm run lint && typecheck && build && test -- --run` (where present), backend ruff/mypy on analytics + auth tests.

### Two-terminal visual smoke (per planning package 07_BROWSER_SMOKE_TEST_PLAN + P23/P24/P25)
Terminal 1 (backend dev server on 8000).  
Terminal 2 (frontend `npm run dev` on 5173). Open `http://localhost:5173`.

Key auth/onboarding/dq steps (mocks or test-only credentials; never real tokens in evidence):
1. Fresh profile / clear auth → lands on `/get-started` (readiness first_time).
2. Get Started explains connect → preview/save → admin approval; copy states "does not start sync".
3. Microsoft 365 card: Connect → device code + verification link appear (large, copyable); no token; poll to connected_valid.
4. Procore card: Connect → opens auth URL (or shows manual fallback labeled "fallback"); callback completes; connected state with safe hints.
5. Project Connections: enter Procore URL (auth now present) → Preview shows "ready_to_save", "pending_admin_approval", "No sync has started", "First sync requires admin approval"; Save succeeds with pending status; no live sync.
6. Sidebar footer: "Data Quality" dot appears (color per state); hover shows status + "Last updated:" + message. No diagnostics for non-admin.
7. Switch local dev role to admin → Settings "Data Quality Diagnostics" loads detail (source counts, attention); non-admin role yields 403 with clear denied UI.
8. Admin approval panel (Settings): pending items visible; approve/reject buttons; post-approve refresh eligibility updates (may still show read-model reasons until data present).
9. Returning stale-auth simulation: readiness surfaces reauth_required for the stale source without regressing to pure first_time/get-started for a user who still has prior usable setup; refresh attempt precedes reauth prompt.
10. Inspect network: all envelopes contain only safe fields; no FORBIDDEN strings; `first_sync_triggered` never true on setup/auth/approval paths.

### Validation commands (exact, run after any change affecting these surfaces)
```bash
git diff --check
python -m ruff check src/hb_assistant/construction/analytics tests/test_fastapi_analytics_auth_onboarding.py tests/test_fastapi_analytics_connection_setup.py tests/test_fastapi_analytics_settings.py
cd frontend && npm run lint && npm run typecheck && npm run build
```

See also: `scripts/smoke_local.py` (UI_SURFACES + H hygiene block), updated runbook section below, H arch 179, planning package 08_TEST_AND_VALIDATION_PLAN + 10_ACCEPTANCE_CHECKLIST.

## References

- Planning package (authoritative intent): `docs/planning/HB_Auth_Onboarding_Implementation_Package/README.md` + 00_PACKAGE_MANIFEST through 11_GAP_REGISTER + prompts/PROMPT_A_... through PROMPT_I_....
- Architecture (this series):
  - 171-fastapi-auth-onboarding-surfaces.md (older Prompt 03 pre-normalization surfaces — superseded for the current UI contract)
  - 172-prompt-a-auth-route-contracts-and-safe-models.md
  - 173-prompt-b-microsoft-graph-local-auth-flow.md
  - 174-prompt-c-procore-local-oauth-flow.md
  - 175-prompt-d-get-started-and-account-connections-ux.md
  - 176-prompt-e-project-connections-auth-aware-setup-flow.md
  - 177-prompt-f-admin-first-sync-approval-integration.md
  - 178-prompt-g-data-quality-readiness-freshness-surfaces.md
  - 179-prompt-h-auth-security-regression-tests-and-smoke-harness.md
  - 180-prompt-i-documentation-and-runbook.md (this file)
- Smoke / operator: `docs/runbooks/frontend-local-analytics-smoke.md` (updated in I), `scripts/smoke_local.py`, `scripts/smoke-local.sh`.
- Frontend sources (labels, routing, components): `frontend/src/app/routes.tsx`, `frontend/src/lib/api.ts`, `GetStartedPage.tsx`, `GraphConnectionCard.tsx`, `ProcoreConnectionCard.tsx`, `ProjectConnectionsPanel.tsx`, `ConnectionPreviewCard.tsx`, `AdminFirstSyncApprovalPanel.tsx`, `DataQualityIndicator.tsx`, `AppShell.tsx`, `SettingsPage.tsx`, `useOnboardingReadiness.ts`, `useDataQualitySummary.ts`.
- Backend contract + services: `src/hb_assistant/construction/analytics/api.py`, `auth_onboarding.py`, `connection_setup.py`.
- Tests (invariants): `tests/test_fastapi_analytics_auth_onboarding.py`, `tests/test_fastapi_analytics_connection_setup.py`, `tests/test_fastapi_analytics_app_shell.py` (paths== + surfaces + role/FORBIDDEN), `tests/test_fastapi_analytics_settings.py`.
- Security / posture: planning `06_SECURITY_GUARDRAILS.md`, prior phase no-writeback proofs, H regression (no-forbidden + no-sync-from-setup + role gates).
- Gap register (pre-I): planning `11_GAP_REGISTER.md` (AUTH-P* items closed by A–H; I is the documentation closeout).

## Closeout

All A–I acceptance criteria are met per repo truth:
- Docs (this record + runbook + references) match implemented normalized routes and current UI labels.
- Docs explain that connect/preview/save/refresh/approval do not start sync.
- Docs explain first live sync requires admin approval.
- Docs explain non-admin (simple sidebar indicator + hover) vs admin (detailed diagnostics in Settings) Data Quality visibility.
- Validation commands and expected results are recorded.
- No secrets, tokens, codes, cache paths, or real auth artifacts appear in any produced document.

The HB Auth Onboarding Implementation Package (1.3.0) is complete. Future work may extend discovery, add richer optional metadata, or promote sync surfaces, but must continue to satisfy the guardrails above and update these docs accordingly.

(End of Prompt I architecture record. Repo truth authoritative.)