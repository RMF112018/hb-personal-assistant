# Frontend Local Analytics Smoke (Prompt 25 / FPR-018 final packaging)

**Audience:** New developer or operator (Bobby).  
**Posture:** Local-first, read-only, advisory, construction-management-first.  
**Hard rule:** This runbook documents how to launch and smoke the FastAPI + Vite analytics command center on localhost only. It never starts live source syncs from setup flows, never performs source-system writeback, and never exposes raw bodies, tokens, secrets, signed/download URLs, or PEM material.

The end-to-end local smoke harness and runbook were packaged in Prompt 25 (building on the P23 scripted harness + 07_BROWSER_SMOKE_TEST_PLAN visual checklist). All steps below are repeatable from a clean checkout with the documented prerequisites.

## Prerequisites

- Python 3.12+ virtualenv at repo root (`.venv`).
- Backend optional dependency group installed: `pip install -e ".[analytics-ui]"`.
- Node 22 + npm 10+ (frontend/ directory).
- The P23 harness is present: `scripts/smoke_local.py` and `scripts/smoke-local.sh` (executable).
- No real operator DB, auth cache, or Obsidian vault is touched by any command below (all fixtures are temp or committed synthetic).

## One-command scripted path (repeatable, evidence-friendly)

From repo root:

```bash
# 1. Backend contract + frontend build + vitest (P23 harness, uses tmp DB + TestClient)
python -m scripts.smoke_local
# or the thin wrapper:
./scripts/smoke-local.sh
```

This exercises the exact UI-facing surfaces the pages query, asserts envelope shapes and no raw on sensitive read models, drives `cd frontend && npm run build` and `npm run test -- --run`, and fails fast on 404s or bad shapes. Full labeled output is suitable for evidence capture.

Then (or in parallel for the matrix):

```bash
cd frontend
npm install                  # normal path — no --legacy-peer-deps required or used
npm run lint
npm run typecheck
npm run build
# Optional component/adapter smoke:
npm run test -- --run
```

Capture the full stdout/stderr + any receipt files (e.g. `docs/evidence/frontend-production-readiness-implementation/prompt-24-frontend-safety-scan-proof.json` from the companion scan script) into your prompt closeout or run log.

## Two-terminal visual smoke (per 07_BROWSER_SMOKE_TEST_PLAN + P24/P25 checklists)

**Terminal 1 (backend):**

```bash
source .venv/bin/activate
python -m uvicorn "hb_assistant.construction.analytics.api:create_app" --factory --port 8000
```

**Terminal 2 (frontend):**

```bash
cd frontend
npm run dev
```

Open http://localhost:5173 (Vite will print the URL). Root `/` redirects to `/today`.

### Exact checklist (12 steps + roles + expectations)

Use the local dev role selector (labeled "Local dev role — not production auth"). Default is `operator`.

1. `/` → redirects to `/today`.
2. `/today` loads with no blocking console errors (network shows the today family calls the page actually makes; Daily Brief section shows one of the 7 documented states with advisory text).
3. `/projects` shows All Projects + any project selector/cards from backend contract.
4. `/projects/all/overview` renders dashboard envelope without TypeError.
5. `/projects/all/meetings` renders meetings-prep view without TypeError.
6. `/projects/all/field-operations` renders field operations signals without TypeError.
7. `/projects/all/cost-time` renders cost/time advisory signals without TypeError.
8. `/my-items` loads with no expected API 404s (aggregate-only contract); sections render with useful CM-facing empty states.
9. `/admin` (default/operator role) shows a clear "Admin role required" / denied state (not perpetual loading).
10. Switch local dev role to `admin` → `/admin` loads the full 6 Data Confidence categories (source sync health, workflow jobs, evidence guardrails, retrieval/AI quality, permissions/governance, data completeness). 403s for non-admin are expected and drive the denied UI.
11. `/settings` loads the guided sections (Account Connections, Project Connections, Daily Brief, Preferences, Keywords). No raw JSON/debug panels. Preferences support real local JSON persist (patch a value such as theme, re-GET reflects it; note in response says "local-first").
12. `/chat` is inaccessible (no route or clearly disabled; `/chat/status` reports `chat_enabled: false`).

**Console / Network criteria (must hold):**
- No uncaught React errors.
- No TypeError from `.slice()` on object envelopes or similar contract mismatches.
- No expected API 404s on the surfaces the UI actually calls.
- Admin 403s are allowed only when they drive a clear role-denied UI state.
- No Tailwind/PostCSS/Vite compile errors.
- Network tab shows only expected `/api/*` calls with 200s (or expected 403s for role-gated admin surfaces when non-admin role selected).
- Role selector visibly says "local dev simulation only".
- Links between primary surfaces (Today/Projects/My Items) and Admin/Settings work.

**Evidence capture for this visual run:**
- Labeled terminal output (both terminals).
- Note any console warnings (non-blocking) and confirm they are not errors.
- Reference the P23 `scripts/smoke_local.py` harness output and the frontend build/vitest for the repeatable contract part.
- The scripted harness provides the "one command" repeatable evidence (API shapes the UI depends on + build + vitest + no raw on envelopes). The manual visual confirms real Vite dev server + browser console + HMR + full 07 checklist.

## Additional operator flows (documented for completeness)

**Settings (real persistence, guided sections):**
- The page is divided into guided CM-first sections.
- Preferences (`/api/settings/preferences`) are persisted to local Application Support JSON (schema_version present on disk after save; re-GET after PATCH reflects changes).
- Daily Brief section: configure output folder + pattern + stale threshold; status/detect surfaces return one of the 7 states (`not_configured`, `configured_waiting`, `brief_available`, `brief_stale`, `markdown_parse_warning`, `brief_generation_failed`, ...), `last_file.path` for display when present, `parse_warnings` (safe), bounded content, and strong "presenter only / external agent generated" advisory text. The app never authors or rewrites the Markdown.

**Daily Brief (external-agent Markdown workflow only):**
- The app detects a user-provided local folder + naming pattern, finds the latest matching `.md`, computes freshness/state, performs light heading-based section extraction when practical, and returns a polished executive view + metadata.
- It must not silently alter the original file (tests using the committed synthetic fixtures under `tests/fixtures/daily_brief_analytics/` copy to a per-test tmp dir and assert pre/post sha256 on the committed originals — "no source file mutation proof").
- 7 states + human labels are stable and already exercised in status/detect/Today surfaces and tests.
- Place a real external-agent Markdown in your configured folder for visual smoke; the synthetic fixtures are for deterministic negative/boundary testing only (forbidden-marker style, overly-long, parse-warn, path+stale).

**Admin / Data Confidence (role-gated governance):**
- Local dev role must be set to `admin` to see the six categories.
- Non-admin (default operator/viewer) receives 403 and a clear denied-state UI (implemented and verified in P21/P24).
- All six health/governance surfaces are read-only and advisory.

**Role selector:**
- Always labeled "Local dev role — not production auth".
- Default remains `operator` unless intentionally changed for a specific visual step.
- Affects the `X-HB-UI-Role` header sent by the frontend; backend `require_admin_role` is fail-closed.

## Auth Onboarding & Data Quality (HB Auth Package Prompts A–I)

**Posture (re-stated for A–I):** Local-first, read-only, advisory, construction-management-first. Hard rule: the auth/onboarding surfaces, Project Connections flows, Data Quality indicator, and the smoke harness **never** start live source syncs from setup/auth/preview/save/refresh/approval flows, never perform source-system writeback, and never expose raw bodies, tokens, secrets, signed/download URLs, PEM material, or local token cache paths to the frontend or into evidence.

The end-to-end normalized contract and operator UX for first-time Get Started, Microsoft 365 device-code, Procore OAuth (callback primary + manual fallback), stale-auth refresh-before-reauth, auth-aware Project Connections preview/save with admin approval gate, non-admin sidebar Data Quality indicator, and admin-only diagnostics were implemented and regression-hardened in Prompts A–I. The one-command harness (`python -m scripts.smoke_local`) and this runbook now cover those surfaces and invariants.

### Key implemented surfaces and labels (match repo truth)
- Startup: `GET /api/onboarding/readiness` drives `StartupRedirect`; first_time → `/get-started`; returning (even with stale auth) prefers main shell after refresh attempt.
- Get Started page: explains connect (M365 + Procore) → Project Connections (preview then save) → admin first-sync approval. Explicit copy: connecting accounts / preview / save does **not** start sync.
- Account Connections (Settings or Get Started panel):
  - Microsoft 365 card (`GraphConnectionCard`): "Connect Microsoft 365" → displays `user_code` (large, copyable) + `verification_uri`; polls status; shows connected state with safe account/tenant hints only; local disconnect.
  - Procore card (`ProcoreConnectionCard`): "Connect Procore" → opens authorization URL (primary) or offers manual code fallback (labeled as fallback, not primary); polls callback completion; connected state with safe account/company hints; local disconnect.
- Project Connections panel (`ProjectConnectionsPanel` + `ConnectionPreviewCard`): auth-aware (disabled until valid account connection); Procore project homepage URL (and SharePoint/OneDrive where supported); Outlook/Calendar matching optional and false by default. Preview result states "Preview complete. No sync has started.", `status: ready_to_save`, `first_sync_status: pending_admin_approval`, "First sync requires admin approval (pending_admin_approval)". Save queues pending approval; no live sync.
- Admin First-Sync Approval (Settings, admin role): `AdminFirstSyncApprovalPanel` lists pending items (from both Procore project identities and Microsoft sources); Approve/Reject buttons (non-admin 403); clear copy that approval is required before first sync eligibility.
- Sidebar (all normal users): `DataQualityIndicator` in `AppShell` footer after SupportNavigation — label "Data Quality" + status dot (green=good, yellow=degraded/attention, red=poor/no trusted data, neutral=unknown). Hover tooltip contains status, "Last updated:", and short message. No raw diagnostics.
- Admin Data Quality Diagnostics (Settings): load button calls admin-only `/api/settings/data-quality/detail`; shows per-source readiness/freshness/approval/attention_items. Non-admin receives 403 with denied UI.

### Scripted harness coverage (H + I)
`UI_SURFACES` includes the normalized H/I surfaces (`/api/onboarding/readiness`, `/api/settings/data-quality/summary` (viewer), `/api/settings/data-quality/detail` (admin)). After the main loop, a dedicated "[Prompt H auth/onboarding/dq hygiene]" block re-drives critical auth/setup/dq surfaces and fails the run (appends to `failures`) on any raw leak or positive `first_sync_triggered`. Role 200/403, no-forbidden, and no-sync assertions are part of the contract gate.

### Two-terminal visual smoke additions (A–I flows)
Perform these in addition to the pre-existing dashboard / Daily Brief / admin steps (use a clean or test-isolated profile; mocks or test-only credentials only):

1. Fresh launch (no prior auth/setup) → lands on `/get-started` (not the main shell). Get Started copy explains the full sequence and explicitly states that connect/preview/save do not start sync.
2. Microsoft 365 card: click Connect → device code + verification link render (large, copyable); no token or cache path appears in UI or network; complete or mock → connected badge + accounts summary updates; Data Quality dot appears in sidebar.
3. Procore card: click Connect → browser opens the returned auth URL (primary path); after callback, status reaches connected with safe hints; manual fallback entrypoint is visible and labeled as fallback only.
4. Project Connections: with accounts connected, enter a Procore homepage URL → Preview renders sanitized result with "ready_to_save", "pending_admin_approval", "No sync has started", and "First sync requires admin approval"; Save succeeds and item appears as pending; confirm no sync side-effect (readiness or admin surfaces do not report triggered).
5. Sidebar Data Quality: non-admin hover shows status + last updated + message; no per-source detail. Switch local dev role to admin → open Settings → "Data Quality Diagnostics" loads (source/attention counts); switch back to operator/viewer → detail load yields clear 403 denied state.
6. Admin approval: pending items from save appear in the admin approval panel; approve or reject; post-action refresh eligibility reflects the decision (may still surface read-model reasons until actual data exists). Non-admin cannot see or act on the panel.
7. Stale-auth returning user simulation (test profile with prior setup but forced stale Graph/Procore): readiness surfaces reauth_required (or degraded/reauth_required) for the affected source(s); main shell remains accessible if other auth is usable; automated refresh is attempted before any reauth prompt; no first-time Get Started reset; no sync is triggered by the readiness probe or refresh request.
8. Inspect all network responses for the above flows: only safe metadata; no FORBIDDEN strings (access_token, refresh_token, id_token, client_secret, Authorization, Bearer, -----BEGIN, signed_url, download_url, msal-token-cache, procore-token-cache, raw bodies, etc.); `first_sync_triggered` is absent or false.

Reference the planning package 07_BROWSER_SMOKE_TEST_PLAN and 10_ACCEPTANCE_CHECKLIST for the full manual checklist (first-time, returning valid, returning stale, project setup, security).

## Capture instructions (for evidence / closeout)

- Scripted harness output (`python -m scripts.smoke_local` or the .sh) — pass/fail summary + key surfaces exercised.
- Frontend matrix output (npm install / lint / typecheck / build / test) — "clean, dist produced, N tests passed".
- Frontend safety scan receipt (if re-run): `python -m scripts.proofs.frontend_safety_scan` → `docs/evidence/frontend-production-readiness-implementation/prompt-24-frontend-safety-scan-proof.json` (or equivalent for this run).
- Two-terminal visual: labeled terminal logs + "checklist complete, no blocking console, network only expected calls, role switch worked, /chat inaccessible".
- Reference the P24/P25 closeouts, 00_PREFLIGHT Prompt 25 section, and the evidence INDEX.

## Known limitations (explicit — do not claim otherwise)

- Charts (FPR-015, P3) remain deferred (recharts is in package.json but unused in `frontend/src`; no implementation or UX added in the 16–25 sequence).
- No Playwright or heavier browser automation in this packaging (scripted API/contract smoke via TestClient + manual two-terminal visual per the 07 plan; Playwright noted as future per prior risk notes).
- Local dev role selector is dev simulation only (not production auth; clearly labeled as such).
- All data is advisory-only, construction-facing. No determinations, no dry-run/apply/execute language on primary screens, detailed diagnostics hidden behind /admin.
- Daily Brief is strictly an external-agent Markdown workflow (the app detects, validates freshness, parses headings when practical, and presents/polishes; it never generates or materially rewrites content).
- No active in-app chat (route and UI disabled/future-only; `/chat/status` reports disabled).
- No setup-triggered live syncs; no source-system writeback at any layer.
- The full visual experience requires two terminals + manual browser steps; the packaged harness provides the repeatable "one command" contract/build/vitest/scan evidence.
- Auth/onboarding flows (Get Started, Graph device-code, Procore OAuth start/callback/fallback, Project Connections preview/save, refresh, admin approve/reject) are exercised in the harness and never produce a positive `first_sync_triggered` or initiate live sync (H regression + smoke hygiene block).
- Data Quality summary (`/api/settings/data-quality/summary`) is safe for viewer/operator roles and contains only status, label, last_updated_at, and a short message; detail (`/api/settings/data-quality/detail`) is admin-only and returns 403 for non-admin.
- All frontend-facing auth/onboarding/account/project/dq responses and rendered cards for normal users are free of forbidden fields (no tokens, secrets, cache paths, raw payloads, signed/download URLs, PEMs, or raw bodies). The harness and tests fail on any leak.
- Procore manual code exchange (`/auth/exchange-code`) is documented and exposed only as a fallback; the primary path is the backend-generated authorization URL + localhost callback with state validation.

## Guardrails (re-stated for this runbook)

- No production source-system writeback performed by any documented step.
- No setup interaction starts a live sync.
- No live external APIs are called by dashboard/view-model routes in the smoke (TestClient against local temp fixtures for scripted part; localhost dev servers only for visual).
- No raw email bodies, raw document text, raw calendar bodies, meeting join URLs, prompts/responses, secrets, tokens, signed URLs, download URLs, or PEM material are serialized or written to evidence.
- No operator DB writes occur in the smoke (temp SQLite via migrator for TestClient; committed synthetic fixtures under tests/ are read-only copies in per-test tmp dirs with pre/post sha256 proof on the originals).
- No auth cache or Obsidian vault writes occur.
- Chat remains disabled/future-only.
- Local role = dev simulation only.
- All surfaces and docs remain construction-management-first with advisory language.
- The auth/onboarding surfaces (readiness, accounts, graph/procore auth start/status/callback/exchange/disconnect, projects preview/save, admin approve/reject, data-quality summary/detail) are driven by the harness UI_SURFACES + hygiene block with role, no-raw, and no-positive-trigger gates.
- First live sync eligibility requires explicit admin approval via the normalized `/api/settings/connections/admin/*` paths; preview/save/refresh never bypass this.
- Non-admin Data Quality visibility is intentionally limited to the sidebar indicator + hover; detailed source-by-source diagnostics are admin-only.

## Related

- `frontend/README.md` (exact routes, navigation contract, data posture, verification commands).
- Prompt 24 closeout (FPR-014/016 hardening, ErrorBoundary, safety scan, fixtures + mutation proof).
- Prompt 23 closeout (harness + vitest + two-terminal baseline).
- `docs/evidence/frontend-production-readiness-implementation/00_PREFLIGHT.md` (Prompt 25 run section).
- `docs/evidence/frontend-production-readiness-implementation/INDEX.md` (or FINAL_EVIDENCE_INDEX.md).
- Architecture 176 (UI kit + testing + harness), 177 (screens), 170 (app shell), 178 (Daily Brief external), 179 (Admin).
- Architecture 172–180 (HB Auth Onboarding Implementation Package: Prompt A route contracts + safe models through Prompt I documentation/runbook; normalized /api surfaces, Get Started, Graph device-code, Procore OAuth with callback + fallback, Project Connections, Data Quality indicator + diagnostics, regression tests, smoke integration).
- `docs/planning/HB_Auth_Onboarding_Implementation_Package/README.md` and prompts/PROMPT_A_... through PROMPT_I_... (package manifest 1.3.0, executive brief, security guardrails, onboarding/data-quality spec, test/validation plan, acceptance checklist, gap register).
- H hygiene block (in `scripts/smoke_local.py`) + this runbook section (auth/onboarding/dq surfaces and the no-sync / no-leak invariants are re-asserted on every harness run).
- Planning package 06_VALIDATION_MATRIX, 07_BROWSER_SMOKE_TEST_PLAN, 08_ACCEPTANCE_EVIDENCE_TEMPLATE for the exact command matrix and checklist.

After any change that affects launch or smoke paths, re-run the scripted harness + the two-terminal visual checklist and update the relevant closeout/evidence.

(End of runbook. Repo truth authoritative.)