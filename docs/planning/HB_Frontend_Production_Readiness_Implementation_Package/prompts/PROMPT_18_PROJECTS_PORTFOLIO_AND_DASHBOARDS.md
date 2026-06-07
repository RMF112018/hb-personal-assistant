# Prompt 18 — Projects portfolio and project dashboards

Repository: `RMF112018/hb-personal-assistant`  
Working path: `/Users/bobbyfetting/hb-personal-assistant`  
Prompt dependency: Prompt 17 should be closed or explicitly waived with evidence.

## Objective

Turn Projects into a usable All Projects / individual project command center with contextual second-level navigation.

## Repo-Truth First Step

Before changing files, run the preflight commands in `02_REPO_TRUTH_PREFLIGHT.md` or update the existing preflight evidence if it has already been run in this implementation sequence. Repository truth is authoritative over this package.

## Gaps Addressed

### FPR-003 — Projects portfolio selector does not consume backend project_keys

- Severity: P1
- Affected area: Projects
- Recommended fix: Adapt ProjectsPage to build project cards from project_keys and metric_cards, or update backend to emit a projects array with key/name/freshness/status.
- Validation: component/unit test for project_keys response; browser smoke /projects with seeded project_keys

### FPR-009 — Hardcoded freshness/confidence values remain on project pages

- Severity: P2
- Affected area: Projects UX
- Recommended fix: Always bind badges to backend freshness/confidence_summary; default to unknown only when absent.
- Validation: component tests for freshness rendering; browser smoke with stale/fresh fixtures

### FPR-015 — Chart readiness dependency exists but chart UX is not implemented

- Severity: P3
- Affected area: UI kit / Future enhancement
- Recommended fix: Defer until route contracts are stable; add chart card only for validated metrics.
- Validation: visual smoke; data contract tests


## Scope

- Adapt ProjectsPage to consume backend `project_keys` and/or a normalized projects array.
- Keep All Projects as a valid selection.
- Render project cards/selectors with label, freshness, confidence, and attention status where available.
- Render Overview, Meetings, Field Operations, and Cost & Time tabs from backend read-model envelopes.
- Make Field Operations the home for Startup, Closeout, Daily Log, Observations, Punch List, and related field signals.
- Make Cost & Time the home for Cost / Change, Billing / Cash, and Schedule signals.
- Replace hardcoded freshness/confidence badges with backend-derived values.
- Leave chart implementation as future unless a simple non-blocking chart improves an existing signal without overbuilding.

## Non-Scope

- Full Procore drilldown UI.
- Source-system writeback.
- New top-level domain navigation.

## Files Likely Touched

- `frontend/src/pages/ProjectsPage.tsx`
- `frontend/src/pages/ProjectDashboardPage.tsx`
- `frontend/src/pages/ProjectMeetingsPage.tsx`
- `frontend/src/pages/ProjectFieldOperationsPage.tsx`
- `frontend/src/pages/ProjectCostTimePage.tsx`
- `frontend/src/components/projects/*`
- `frontend/src/components/dashboard/*`
- `frontend/src/lib/api.ts`
- `src/hb_assistant/construction/analytics/service.py`
- `tests/test_fastapi_analytics_dashboard_read_models.py`

## Implementation Guidance

- Prefer typed adapters and explicit view-model normalization over permissive `any` fallbacks.
- Preserve the current safety boundaries: no source-system writeback, no active chat, no raw/secrets serialization, no setup-triggered live sync.
- Keep the UI construction-management-first and avoid backend-console labels.
- Update tests and evidence in the same prompt; do not defer validation to a later session unless blocked by environment.
- When a gap is already fixed in current repo truth, document the evidence and do not rework the code unnecessarily.

## Acceptance Criteria

- Projects landing shows All Projects plus individual projects when backend `project_keys` exist.
- Overview renders high-level assistant-like sections.
- Meetings, Field Operations, and Cost & Time routes render without TypeError.
- Field Operations and Cost & Time use construction-facing labels.
- No hardcoded stale/fresh/source-backed values remain where backend values exist.

## Validation Commands

- `python -m pytest tests/test_fastapi_analytics_dashboard_read_models.py`
- `cd frontend && npm run lint && npm run typecheck && npm run build`
- `Browser smoke: /projects, /projects/all/overview, /projects/all/meetings, /projects/all/field-operations, /projects/all/cost-time, and at least one concrete project key if available`

## Evidence Required

Create or update:

```text
docs/evidence/frontend-production-readiness-implementation/prompt-18-projects-portfolio-and-dashboards-closeout.md
```

Include branch, HEAD, files changed, gaps closed/deferred, validation command output summary, browser smoke notes, and guardrail confirmation.

## Risk Notes

- Do not expose every data domain as top-level navigation.
- Do not imply financial determinations; keep cost/time signals advisory.
