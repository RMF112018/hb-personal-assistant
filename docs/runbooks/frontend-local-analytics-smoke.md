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

## Related

- `frontend/README.md` (exact routes, navigation contract, data posture, verification commands).
- Prompt 24 closeout (FPR-014/016 hardening, ErrorBoundary, safety scan, fixtures + mutation proof).
- Prompt 23 closeout (harness + vitest + two-terminal baseline).
- `docs/evidence/frontend-production-readiness-implementation/00_PREFLIGHT.md` (Prompt 25 run section).
- `docs/evidence/frontend-production-readiness-implementation/INDEX.md` (or FINAL_EVIDENCE_INDEX.md).
- Architecture 176 (UI kit + testing + harness), 177 (screens), 170 (app shell), 178 (Daily Brief external), 179 (Admin).
- Planning package 06_VALIDATION_MATRIX, 07_BROWSER_SMOKE_TEST_PLAN, 08_ACCEPTANCE_EVIDENCE_TEMPLATE for the exact command matrix and checklist.

After any change that affects launch or smoke paths, re-run the scripted harness + the two-terminal visual checklist and update the relevant closeout/evidence.

(End of runbook. Repo truth authoritative.)