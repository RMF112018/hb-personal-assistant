# Prompt 17 — Today dashboard UX/content completion

Repository: `RMF112018/hb-personal-assistant`  
Working path: `/Users/bobbyfetting/hb-personal-assistant`  
Prompt dependency: Prompt 16 should be closed or explicitly waived with evidence.

## Objective

Make Today the construction-first landing page that clearly shows what matters today without exposing backend mechanics.

## Repo-Truth First Step

Before changing files, run the preflight commands in `02_REPO_TRUTH_PREFLIGHT.md` or update the existing preflight evidence if it has already been run in this implementation sequence. Repository truth is authoritative over this package.

## Gaps Addressed

### FPR-008 — Today dashboard is missing explicit required sections

- Severity: P1
- Affected area: Today UX
- Recommended fix: Split Portfolio Signals into Cost / Change / Time Signals and Documents & Correspondence Worth Reviewing; keep data confidence compact.
- Validation: frontend route smoke /today; copy/label regression test; no raw calendar body/join URL scan


## Scope

- Create or update `tests/test_fastapi_analytics_today.py` unless equivalent coverage already exists.
- Ensure `/` lands on `/today`.
- Render the required Today sections: Header/day context, Important Today, What Changed, Today’s Meetings, Action Items, Cost / Change / Time Signals, Documents and Correspondence Worth Reviewing, Daily Brief Panel, compact Data Confidence context.
- Refine loading, empty, stale, and error states with construction-facing language.
- Ensure missing Daily Brief configuration/file states render cleanly and link to Settings using BrowserRouter navigation.
- Keep raw source coverage/evidence internals out of the normal Today user path.

## Non-Scope

- Project detail dashboards.
- Settings persistence.
- New source integrations.

## Files Likely Touched

- `frontend/src/pages/TodayPage.tsx`
- `frontend/src/components/dashboard/*`
- `frontend/src/components/ui/*`
- `frontend/src/lib/api.ts`
- `src/hb_assistant/construction/analytics/service.py`
- `src/hb_assistant/construction/analytics/api.py`
- `tests/test_fastapi_analytics_today.py`

## Implementation Guidance

- Prefer typed adapters and explicit view-model normalization over permissive `any` fallbacks.
- Preserve the current safety boundaries: no source-system writeback, no active chat, no raw/secrets serialization, no setup-triggered live sync.
- Keep the UI construction-management-first and avoid backend-console labels.
- Update tests and evidence in the same prompt; do not defer validation to a later session unless blocked by environment.
- When a gap is already fixed in current repo truth, document the evidence and do not rework the code unnecessarily.

## Acceptance Criteria

- Today renders all required sections with stable empty states.
- All Today API calls return 200 in local smoke.
- No raw calendar body, meeting join URL, raw email body, or raw document text appears.
- Cost/time language is advisory and not a financial determination.
- Data confidence is compact and secondary.

## Validation Commands

- `python -m pytest tests/test_fastapi_analytics_today.py`
- `python -m pytest tests/test_fastapi_analytics_app_shell.py tests/test_fastapi_analytics_dashboard_read_models.py`
- `cd frontend && npm run lint && npm run typecheck && npm run build`
- `Browser smoke: / and /today as operator, viewer, and admin where relevant`

## Evidence Required

Create or update:

```text
docs/evidence/frontend-production-readiness-implementation/prompt-17-today-dashboard-ux-content-closeout.md
```

Include branch, HEAD, files changed, gaps closed/deferred, validation command output summary, browser smoke notes, and guardrail confirmation.

## Risk Notes

- Do not add new top-level nav for documents/correspondence/cost/schedule.
- Do not turn Today into admin coverage telemetry.
