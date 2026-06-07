# Prompt H — Auth/Security Regression Tests and Local Smoke Harness (HB Auth Onboarding Implementation Package 1.3.0)

**Date**: 2026-06-07  
**Status**: Implemented  
**Scope**: Comprehensive regression tests + harness integration to enforce that the normalized auth/onboarding/data-quality surfaces (readiness, accounts, graph/procore auth flows, project connections preview/save, admin approve/reject, data-quality summary+detail) never serialize FORBIDDEN tokens/secrets/cache paths/raw payloads, never set `first_sync_triggered` (or otherwise initiate live sync from setup/auth/approval), correctly distinguish first-time (`/get-started` readiness) vs returning stale-auth (refresh-before-reauth), and enforce admin-only for detail while summary remains viewer-safe. Leverage/extend existing patterns rather than new runners.

## Objectives (per Prompt H spec)
- Backend tests for all normalized auth/onboarding/dq routes.
- No-secret/no-token serialization tests (fail if any frontend-facing route leaks).
- No-sync-from-setup tests (fail if preview/save/auth/approval/refresh-request starts sync).
- First-time vs returning stale-auth tests.
- Admin vs non-admin data-quality tests.
- Local smoke runbook/script integration (per repo conventions).
- Existing analytics tests remain green (or unrelated pre-existing failures documented).

## Repo Truth Before Prompt H (Gaps Closed)
- Strong foundations existed:
  - `tests/test_fastapi_analytics_app_shell.py`: OpenAPI `paths == { ... }` contract (including B/C/E/F normalized surfaces) + `surfaces` list with role + `FORBIDDEN` serialized checks + role 403 spot checks + guardrails assertions. This was the primary "no raw on envelopes" gate.
  - `tests/test_fastapi_analytics_auth_onboarding.py` and `connection_setup.py`: `FORBIDDEN` + `_assert_no_forbidden` / `_assert_safe`, multiple `first_sync_triggered is False` asserts (esp. post-F approve/reject flows), readiness transition tests, reauth_required checks, and the G-added `test_prompt_g_data_quality_states...` (4 dq states + detail sources/attention + embedded readiness.data_quality + 403 on non-admin detail).
  - Smoke harness (`scripts/smoke_local.py` + `smoke-local.sh`): temp DB + TestClient(create_app) loop over `UI_SURFACES`, `_has_raw` checks on dashboard envelopes, frontend `npm run build` + `npm run test -- --run` (vitest), plus runbook `docs/runbooks/frontend-local-analytics-smoke.md` documenting the one-command + two-terminal visual (P23/P24/P25).
  - `scripts/proofs/frontend_safety_scan.py` (P24) for src grep hygiene (raw/alert patterns).
  - Fakes for MSAL (`_FakeMsalApp`) and Procore, temp dirs only, no live creds/OAuth in tests.
- Gaps: the contract/surfaces lists and smoke `UI_SURFACES` were not guaranteed to include the final H-critical normalized surfaces (`/api/onboarding/readiness`, the two `/api/settings/data-quality/*`); no single dedicated "H regression" test exercising the full "fail if" matrix across all setup/auth surfaces in one place; smoke did not explicitly drive the new auth/dq surfaces + no-trigger hygiene as a gate; the G dq test was strong but not framed as part of a broader auth/security regression suite.

## Changes Made (Additive, Follows Plan)
- **Contract enforcement** (`tests/test_fastapi_analytics_app_shell.py`):
  - Added the three H-critical paths to the `paths == { ... }` OpenAPI assertion (with comment): `/api/onboarding/readiness`, `/api/settings/data-quality/summary`, `/api/settings/data-quality/detail`.
  - Extended the `surfaces` list (role + serialized FORBIDDEN check + guardrails) with the same three (viewer for readiness + summary; admin for detail).
  - Added explicit role spot checks: non-admin 403 on detail; viewer succeeds on summary.
  - This makes removal or regression of any of these surfaces fail the test immediately, and guarantees the no-forbidden + role behavior on them on every run.

- **Auth/onboarding/dq regression** (`tests/test_fastapi_analytics_auth_onboarding.py`):
  - Added `test_prompt_h_auth_security_regression_no_forbidden_no_sync_state_and_role_gates` (broad, would fail the ACs):
    - Clean DB: readiness asserts `onboarding_state` (first_time/degraded), `get_started_required`, `data_quality` unknown + label, no forbidden, no positive `first_sync_triggered`.
    - Key setup/auth surfaces (projects preview/save, graph/procore auth starts, admin approve/reject) all assert `_assert_no_forbidden` and no positive `first_sync_triggered`.
    - DQ matrix: summary succeeds for viewer + no forbidden; detail 403 for viewer/operator; detail (admin) has safe shape (surface, sources/attention as lists when present), no forbidden.
    - Returning/stale path: after prior setup + forcing stale/expired via the existing graph fake, readiness surfaces reauth_required signals (or degraded/reauth_required states) without regressing a returning user to pure first_time + forced get-started; no sync triggered by the probe.
  - Re-uses existing fakes, `_assert_no_forbidden`, `FORBIDDEN`, `_client`, and the G dq test (which continues to cover the 4 states + readiness embedding + 403).

- **No-sync-from-setup (connection_setup + auth)** (`tests/test_fastapi_analytics_connection_setup.py`):
  - Added `_assert_no_sync_triggered(payload)` helper (string + bool check for positive `first_sync_triggered`).
  - Used the helper on an existing approve response in the prompt_f test.
  - Added `test_prompt_h_no_setup_or_approval_action_starts_sync`: exercises preview (viewer), save (operator), readiness, refresh-request (pre-approval, expects not-ok + no triggered marker), and normalized admin approve path; asserts the property via the helper + `_assert_safe` where appropriate.
  - Complements the broader H test in auth_onboarding (which also hits auth-start surfaces).

- **Smoke harness integration** (`scripts/smoke_local.py`):
  - Added the three H surfaces to `UI_SURFACES` (readiness/summary viewer; detail admin) so the main contract loop exercises them (role headers, 200/403, raw checks on 200).
  - Added a dedicated "[Prompt H auth/onboarding/dq hygiene]" block after the main loop that re-drives key auth/setup/dq surfaces and explicitly fails (appends to `failures`) on raw leaks (`_has_raw`) or positive `first_sync_triggered`. This makes the one-command harness (`python -m scripts.smoke_local` or the .sh) itself a regression gate for the H ACs.
  - The harness already drives vitest (`npm run test -- --run`), so the new stable frontend test (below) is automatically included.

- **Light frontend vitest** (`frontend/src/components/layout/DataQualityIndicator.test.tsx` — new):
  - Stable, non-brittle test using `@testing-library/react` + vitest (matching the two existing UI tests).
  - Mocks `useDataQualitySummary` with fixed status/last_updated_at/message (no real react-query, no variable timestamps).
  - Asserts: "Data Quality" text present; dot class contains the expected `bg-green-500` / `bg-yellow-500` / `bg-red-500` / neutral for good/degraded/poor/unknown+loading/error; wrapper title contains the mapped "Data Quality: Good/Needs attention/Poor" + "Last updated:" + the message text (per 05 spec / G indicator).
  - Covers the G surface under H regression; will be exercised by the smoke harness vitest step.

- **Runbook / note**: Per plan allowance ("or just in 179 arch"), the coverage note lives in the arch doc below (the harness + hygiene block + new surfaces + H test + vitest now enforce the auth/onboarding/dq hygiene on every smoke run). No edit to the runbook was required to keep staging minimal.

- **Architecture doc**: New `docs/architecture/179-prompt-h-auth-security-regression-tests-and-smoke-harness.md` (see references and matrix below).

All changes are additive/surgical. No operator DB, auth cache, or Obsidian writes; temp fixtures only; fakes for MSAL/Procore; no live OAuth/creds.

## Regression Matrix (enforced by tests + harness)

```mermaid
flowchart TD
  AppShell[app_shell contract (paths== + surfaces + FORBIDDEN + roles)] -->|covers readiness + dq summary/detail + all normalized B/C/E/F| NoLeakRole
  AuthH[auth_onboarding H regression test] -->|first-time readiness + get-started + dq unknown; returning stale reauth + main_allowed; all setup/auth surfaces no-forbidden + no positive trigger; admin detail vs non-admin 403| StateNoLeak
  ConnH[connection_setup H helper + test] -->|preview/save/readiness/refresh-request/approve never set first_sync_triggered or flip triggered marker; _assert_no_sync_triggered| NoSync
  Smoke[smoke_local.py (UI_SURFACES + H hygiene block) + vitest] -->|drives the above + build + component test; fails on raw or positive trigger| HarnessGate
  Vitest[DataQualityIndicator.test.tsx (mocked hook, status→color+title)] -->|stable coverage of G indicator| Frontend
  NoLeakRole & StateNoLeak & NoSync & HarnessGate --> ACs["AC: tests fail if forbidden serialized or sync started or wrong first-time/stale state or admin bypass"]
```

## References
- Prompt H spec (objective/scope/AC/validation/risk) + explicit authorization.
- Prior arch: 172 (A contracts + OnboardingReadinessResponse + admin_detail_available), 177 (F approvals + list_pending + procore_* + admin panel in Settings), 178 (G dq builders + surfaces + indicator + summary/detail).
- `tests/test_fastapi_analytics_app_shell.py` (the contract + FORBIDDEN surfaces), auth_onboarding + connection_setup tests (FORBIDDEN, fakes, G dq test, existing first_sync_triggered asserts), `scripts/smoke_local.py` + .sh + runbook (P23 harness), `scripts/proofs/frontend_safety_scan.py` (P24).
- Existing patterns: `_assert_no_forbidden` / `_assert_safe` / `_has_raw`, temp `_client(tmp_path)` + SQLiteMigrator, role headers, `first_sync_triggered is False` (or absent) on setup paths.
- Risk notes observed: temp DB only; MSAL/Procore fakes (no live); no timestamp snapshots in vitest (fixed ISO + contains checks); normalize or avoid brittle UI state; existing analytics tests run as part of the exact validation list (document any unrelated pre-existing failures).

## Validation
The exact list from the prompt was executed (and re-run after fixes) until green:
- All 6 named pytest files passed.
- ruff (on analytics + the 3 test files) clean.
- mypy on analytics clean.
- `cd frontend && npm run lint && npm run typecheck && npm run build` clean (0 errors; pre-existing unrelated warning only).

Any pre-existing unrelated failures in the broader analytics suite (outside the H-focused slices) would be documented in the closeout per the AC.

## Non-Scope / Future
- No requirement for real Graph/Procore credentials or live OAuth in automated tests or smoke.
- No writes to operator DB (all temp per-test DBs or committed synthetic fixtures).
- The smoke remains the "one command" repeatable/contract part; the two-terminal visual (runbook) remains the manual checklist.
- Future: if more vitest coverage for other indicators or api client mappers is desired, they can be added following the same stable-mock pattern.

This completes the auth/security regression and local smoke harness for the onboarding flow.
