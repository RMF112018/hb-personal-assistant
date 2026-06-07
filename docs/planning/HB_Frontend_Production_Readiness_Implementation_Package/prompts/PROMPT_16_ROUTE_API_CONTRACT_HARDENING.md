# Prompt 16 — Route/API contract hardening and launch blockers

Repository: `RMF112018/hb-personal-assistant`  
Working path: `/Users/bobbyfetting/hb-personal-assistant`  
Prompt dependency: None

## Objective

Eliminate launch-blocking route/API contract mismatches and browser-breaking shape errors before UX polish.

## Repo-Truth First Step

Before changing files, run the preflight commands in `02_REPO_TRUTH_PREFLIGHT.md` or update the existing preflight evidence if it has already been run in this implementation sequence. Repository truth is authoritative over this package.

## Gaps Addressed

### FPR-001 — Project tab pages can crash because frontend treats object read models as arrays

- Severity: P0
- Affected area: Projects
- Recommended fix: Normalize project tab responses in a shared adapter; render metric_cards and attention_items; or add backend items arrays. Add tests that each route renders when backend returns object envelopes.
- Validation: npm run typecheck; npm run build; browser smoke /projects/all/meetings /field-operations /cost-time; pytest dashboard read models

### FPR-002 — My Items page calls unimplemented backend subroutes

- Severity: P1
- Affected area: My Items / API alignment
- Recommended fix: Either add backend compatibility section endpoints derived from build_my_items() or refactor frontend to use the aggregate /api/my-items only.
- Validation: pytest app shell openapi path assertion; new pytest my-items section routes or updated frontend no-call test; browser smoke /my-items no 404s

### FPR-006 — BrowserRouter pages contain hash-style links

- Severity: P1
- Affected area: Navigation
- Recommended fix: Replace with <Link to="/settings"> and <Link to="/today">.
- Validation: npm run typecheck; browser smoke clicking Today/Settings links


## Scope

- Run repo-truth preflight and confirm current route/API inventory.
- Fix project tab object/array mismatch for Meetings, Field Operations, and Cost & Time.
- Resolve My Items subroute mismatch by either adding backend section endpoints or refactoring frontend to consume the aggregate `/api/my-items` contract. Prefer the smallest stable contract that avoids expected 404s.
- Replace BrowserRouter-incompatible `#/` links with router-aware `<Link>` or navigation helpers.
- Add a baseline Admin 403 UI state if needed to prevent endless loading while leaving backend role guards intact.
- Update route/OpenAPI assertions and frontend API types/adapters.

## Non-Scope

- Visual redesign beyond states required to avoid broken UX.
- New external integrations.
- Starting live syncs or writeback.
- Chat UI or chat endpoint work.

## Files Likely Touched

- `frontend/src/lib/api.ts`
- `frontend/src/pages/ProjectDashboardPage.tsx`
- `frontend/src/pages/ProjectMeetingsPage.tsx`
- `frontend/src/pages/ProjectFieldOperationsPage.tsx`
- `frontend/src/pages/ProjectCostTimePage.tsx`
- `frontend/src/pages/MyItemsPage.tsx`
- `frontend/src/pages/TodayPage.tsx`
- `frontend/src/pages/SettingsPage.tsx`
- `frontend/src/pages/AdminDataConfidencePage.tsx`
- `src/hb_assistant/construction/analytics/api.py`
- `src/hb_assistant/construction/analytics/service.py`
- `tests/test_fastapi_analytics_app_shell.py`
- `tests/test_fastapi_analytics_dashboard_read_models.py`

## Implementation Guidance

- Prefer typed adapters and explicit view-model normalization over permissive `any` fallbacks.
- Preserve the current safety boundaries: no source-system writeback, no active chat, no raw/secrets serialization, no setup-triggered live sync.
- Keep the UI construction-management-first and avoid backend-console labels.
- Update tests and evidence in the same prompt; do not defer validation to a later session unless blocked by environment.
- When a gap is already fixed in current repo truth, document the evidence and do not rework the code unnecessarily.

## Acceptance Criteria

- No project subroute crashes from `.slice()` or array methods applied to object envelopes.
- No expected My Items API call returns 404, or the frontend no longer calls unimplemented subroutes.
- No `#/settings`, `#/today`, or other hash-router links remain in a BrowserRouter app.
- Admin route as operator shows a clear role-required state if admin calls are made.
- Backend role guards remain fail-closed.
- `/chat` remains unavailable and `/chat/status` remains disabled/future-only.

## Validation Commands

- `python -m pytest tests/test_fastapi_analytics_app_shell.py tests/test_fastapi_analytics_dashboard_read_models.py`
- `python -m ruff check src/hb_assistant/construction/analytics tests/test_fastapi_analytics_app_shell.py tests/test_fastapi_analytics_dashboard_read_models.py`
- `python -m mypy src/hb_assistant/construction/analytics`
- `cd frontend && npm run lint && npm run typecheck && npm run build`
- `Browser smoke: /today, /projects, /projects/all/overview, /projects/all/meetings, /projects/all/field-operations, /projects/all/cost-time, /my-items, /admin, /settings`

## Evidence Required

Create or update:

```text
docs/evidence/frontend-production-readiness-implementation/prompt-16-route-api-contract-hardening-closeout.md
```

Include branch, HEAD, files changed, gaps closed/deferred, validation command output summary, browser smoke notes, and guardrail confirmation.

## Risk Notes

- If backend compatibility routes are added, update app-shell/OpenAPI tests.
- Do not weaken admin dependency enforcement to improve the UI.
- If choosing aggregate `/api/my-items`, ensure the page still renders all required My Items sections from the aggregate shape.
