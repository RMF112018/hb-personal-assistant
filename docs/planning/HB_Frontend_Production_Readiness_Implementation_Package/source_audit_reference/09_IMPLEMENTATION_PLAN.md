# 09 Implementation Plan

Generated: 2026-06-07T07:17:24.406486+00:00

Audit scope: `hb-personal-assistant` FastAPI / Vite React frontend analytics dashboard. Repository truth reviewed through the GitHub connector because the sandbox could not access `/Users/bobbyfetting/hb-personal-assistant` and network clone failed. No production source changes were made.


## Prompt 16 — Route/API contract hardening and launch blockers

**Objective:** Eliminate browser-breaking API/shape mismatches before UX polish.

**Scope**
- Project tab object/array adapter or backend items arrays
- My Items subroute alignment
- Remove or implement /api/today/important export
- Fix BrowserRouter hash links
- Admin 403 baseline state

**Non-scope**
- Visual redesign
- new source integrations

**Files likely touched**
- `frontend/src/lib/api.ts`
- `frontend/src/pages/Project*.tsx`
- `frontend/src/pages/MyItemsPage.tsx`
- `frontend/src/pages/TodayPage.tsx`
- `frontend/src/pages/AdminDataConfidencePage.tsx`
- `src/hb_assistant/construction/analytics/api.py`
- `src/hb_assistant/construction/analytics/service.py`
- `tests/test_fastapi_analytics_app_shell.py`
- `tests/test_fastapi_analytics_dashboard_read_models.py`

**Acceptance criteria**
- No expected frontend API call returns 404
- Project subroutes render without TypeError from backend envelopes
- Admin non-admin shows clear role state
- No #/ links remain

**Validation commands**
- `python -m pytest tests/test_fastapi_analytics_app_shell.py tests/test_fastapi_analytics_dashboard_read_models.py`
- `python -m ruff check src/hb_assistant/construction/analytics tests/test_fastapi_analytics_app_shell.py tests/test_fastapi_analytics_dashboard_read_models.py`
- `python -m mypy src/hb_assistant/construction/analytics`
- `cd frontend && npm run typecheck && npm run build`

**Risk notes**
- Changing route inventory requires updating app-shell OpenAPI path assertion.

**Dependency:** None

## Prompt 17 — Today dashboard UX/content completion

**Objective:** Make Today the construction-first landing page that clearly shows what matters now.

**Scope**
- Add explicit required sections
- Refine empty/loading/error states
- Keep data confidence compact
- Ensure Daily Brief Settings link works

**Non-scope**
- Projects detailed tabs
- Settings persistence

**Files likely touched**
- `frontend/src/pages/TodayPage.tsx`
- `frontend/src/components/dashboard/*`
- `frontend/src/components/ui/*`
- `src/hb_assistant/construction/analytics/service.py`
- `tests/test_fastapi_analytics_today.py`

**Acceptance criteria**
- Today shows Header/day context, Important Today, What Changed, Today meetings, Action Items, Cost/Change/Time Signals, Documents/Correspondence, Daily Brief, compact Data Confidence
- No raw JSON fallback copy
- No raw calendar body or join URL

**Validation commands**
- `python -m pytest tests/test_fastapi_analytics_today.py`
- `cd frontend && npm run typecheck && npm run build`

**Risk notes**
- Add new test file because current tree lacks test_fastapi_analytics_today.py.

**Dependency:** Prompt 16

## Prompt 18 — Projects portfolio and project dashboards

**Objective:** Turn Projects into a usable All Projects / project-specific command center.

**Scope**
- Portfolio project selector from project_keys/projects array
- Overview section rendering from metric cards/attention
- Meetings/Field Operations/Cost & Time contextual tabs
- Backend/frontend contract for project labels/freshness

**Non-scope**
- Full Procore drilldowns
- writeback

**Files likely touched**
- `frontend/src/pages/ProjectsPage.tsx`
- `frontend/src/pages/ProjectDashboardPage.tsx`
- `frontend/src/pages/ProjectMeetingsPage.tsx`
- `frontend/src/pages/ProjectFieldOperationsPage.tsx`
- `frontend/src/pages/ProjectCostTimePage.tsx`
- `frontend/src/components/projects/*`
- `src/hb_assistant/construction/analytics/service.py`

**Acceptance criteria**
- All Projects appears and individual projects appear when project_keys exist
- Tabs render metric cards and attention items
- Field Operations includes startup/closeout/daily log/observations/punch language
- Cost & Time includes cost/change/billing/cash/schedule language

**Validation commands**
- `python -m pytest tests/test_fastapi_analytics_dashboard_read_models.py`
- `cd frontend && npm run typecheck && npm run build`

**Risk notes**
- Avoid adding top-level domain nav.

**Dependency:** Prompt 16

## Prompt 19 — My Items dashboard

**Objective:** Make My Items a user-specific filtered work queue instead of a raw data browser.

**Scope**
- Backend subroutes or aggregate adapters
- Action items/meetings/correspondence/files/followed projects
- Useful empty states
- No email client/calendar/file browser behavior

**Non-scope**
- Mailbox mutation
- full OneDrive browser

**Files likely touched**
- `frontend/src/pages/MyItemsPage.tsx`
- `frontend/src/components/my-items/*`
- `src/hb_assistant/construction/analytics/api.py`
- `src/hb_assistant/construction/analytics/service.py`
- `tests/test_fastapi_analytics_dashboard_read_models.py`

**Acceptance criteria**
- No My Items 404s
- Each required My Items section renders
- No raw email body/file text/calendar body

**Validation commands**
- `python -m pytest tests/test_fastapi_analytics_dashboard_read_models.py`
- `cd frontend && npm run typecheck && npm run build`

**Risk notes**
- Keep source confidence secondary.

**Dependency:** Prompt 16

## Prompt 20 — Settings and onboarding polish

**Objective:** Replace backend-console controls with guided local-first setup flows.

**Scope**
- Account Connections
- Project Connections preview/save
- Daily Brief workflow bug fixes
- Preferences persistence plan/implementation
- Remove raw JSON/details and stub copy
- Inline error states

**Non-scope**
- Starting live sync from setup
- secret display

**Files likely touched**
- `frontend/src/pages/SettingsPage.tsx`
- `frontend/src/components/settings/*`
- `src/hb_assistant/construction/analytics/api.py`
- `src/hb_assistant/construction/analytics/daily_brief.py`
- `tests/test_fastapi_analytics_settings.py`
- `tests/test_fastapi_analytics_connection_setup.py`

**Acceptance criteria**
- No Raw response/stub/alert text
- Daily Brief state accurate
- Preview→save→admin approval boundary visible
- No setup interaction starts live sync

**Validation commands**
- `python -m pytest tests/test_fastapi_analytics_settings.py tests/test_fastapi_analytics_connection_setup.py tests/test_fastapi_analytics_daily_brief.py`
- `cd frontend && npm run typecheck && npm run build`

**Risk notes**
- Some auth setup routes legitimately start OAuth/device flows; keep dashboard read models free of live calls.

**Dependency:** Prompt 16

## Prompt 21 — Admin / Data Confidence polish

**Objective:** Keep Admin supportive, role-aware, and useful without dominating the app.

**Scope**
- 403/non-admin state
- Six admin sections
- Metric grouping and drilldown hygiene
- Permissions/governance copy

**Non-scope**
- New diagnostics engines

**Files likely touched**
- `frontend/src/pages/AdminDataConfidencePage.tsx`
- `frontend/src/components/admin/*`
- `tests/test_fastapi_analytics_app_shell.py`

**Acceptance criteria**
- Operator sees clear admin-required state
- Admin sees six sections
- No raw sensitive fields
- Primary nav remains unchanged

**Validation commands**
- `python -m pytest tests/test_fastapi_analytics_app_shell.py`
- `cd frontend && npm run typecheck && npm run build`

**Risk notes**
- Do not weaken backend role guards to improve UI convenience.

**Dependency:** Prompt 16

## Prompt 22 — UI kit, accessibility, responsiveness consolidation

**Objective:** Create a coherent lightweight component layer without overbuilding a custom design system.

**Scope**
- Shared cards/section/error/loading/empty components
- Responsive shell
- Keyboard/focus states for controls
- Remove duplicated badge/layout code

**Non-scope**
- Re-platforming UI library
- heavy design system

**Files likely touched**
- `frontend/src/components/ui/*`
- `frontend/src/components/dashboard/*`
- `frontend/src/layouts/*`
- `frontend/src/index.css`

**Acceptance criteria**
- Consistent spacing/typography/cards/badges
- Mobile/narrow viewport usable
- Keyboard navigation works across nav/forms
- No alert() calls

**Validation commands**
- `cd frontend && npm run lint && npm run typecheck && npm run build`
- `manual a11y smoke`

**Risk notes**
- Keep off-the-shelf Tailwind/Radix/shadcn-style primitives; do not create rigid system.

**Dependency:** Prompts 17-21

## Prompt 23 — End-to-end local smoke harness

**Objective:** Make local launch validation repeatable.

**Scope**
- Backend start check 8000
- Frontend start check 5173
- Route/API smoke
- Role switch smoke
- No 404 expected API calls
- No blocking console errors

**Non-scope**
- CI deployment
- cloud hosting

**Files likely touched**
- `frontend/package.json`
- `scripts/proofs/*`
- `docs/runbooks/*`
- `tests/*`

**Acceptance criteria**
- One documented smoke path from clean checkout
- Captures route/API results
- Fails on expected API 404 or build error

**Validation commands**
- `python -m pytest targeted analytics tests`
- `cd frontend && npm run build`
- `new smoke script`

**Risk notes**
- Use local-only test DB; do not touch operator DB/auth cache/Obsidian.

**Dependency:** Prompts 16-22

## Prompt 24 — Local-first production hardening

**Objective:** Close production-readiness safety, dependency, and packaging gaps.

**Scope**
- Dependency install/build proof
- No raw/no writeback scans for frontend evidence
- Daily Brief safety fixtures
- Environment defaults
- Error boundary

**Non-scope**
- External deployment
- active chat

**Files likely touched**
- `frontend/package.json`
- `frontend/src/*`
- `scripts/proofs/*`
- `docs/evidence/*`

**Acceptance criteria**
- npm install/build/typecheck/lint evidence captured
- No --legacy-peer-deps required or debt documented
- No secrets/raw content in evidence
- Chat inaccessible

**Validation commands**
- `npm install`
- `npm run lint`
- `npm run typecheck`
- `npm run build`
- `python safety proofs`

**Risk notes**
- Do not use --legacy-peer-deps as a silent permanent fix.

**Dependency:** Prompt 23

## Prompt 25 — Documentation and runbook packaging

**Objective:** Package the operational instructions for local-first use and future agents.

**Scope**
- README/runbook updates
- Install/launch/role testing
- Settings/Daily Brief setup instructions
- Admin governance notes
- Known limitations

**Non-scope**
- Code behavior changes except doc links

**Files likely touched**
- `README.md`
- `frontend/README.md`
- `docs/runbooks/*`
- `docs/evidence/*`

**Acceptance criteria**
- New user can launch backend/frontend and understand freshness/confidence
- No stale package claims
- Next prompt handoff generated

**Validation commands**
- `documentation link check`
- `fresh clone runbook smoke`

**Risk notes**
- Docs must distinguish current implementation from planned capabilities.

**Dependency:** Prompt 24
