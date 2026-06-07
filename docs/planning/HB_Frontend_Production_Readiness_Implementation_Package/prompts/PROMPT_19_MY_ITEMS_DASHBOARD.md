# Prompt 19 — My Items dashboard

Repository: `RMF112018/hb-personal-assistant`  
Working path: `/Users/bobbyfetting/hb-personal-assistant`  
Prompt dependency: Prompt 18 should be closed or explicitly waived with evidence.

## Objective

Make My Items a user-specific work queue that surfaces attention items without becoming a raw email, calendar, or file browser.

## Repo-Truth First Step

Before changing files, run the preflight commands in `02_REPO_TRUTH_PREFLIGHT.md` or update the existing preflight evidence if it has already been run in this implementation sequence. Repository truth is authoritative over this package.

## Gaps Addressed

### FPR-002 — My Items page calls unimplemented backend subroutes

- Severity: P1
- Affected area: My Items / API alignment
- Recommended fix: Either add backend compatibility section endpoints derived from build_my_items() or refactor frontend to use the aggregate /api/my-items only.
- Validation: pytest app shell openapi path assertion; new pytest my-items section routes or updated frontend no-call test; browser smoke /my-items no 404s


## Scope

- Finalize the My Items backend/frontend contract after Prompt 16.
- Render user-specific action items, meetings, correspondence worth reviewing, OneDrive/files worth reviewing, followed/pinned projects, and review-required items.
- Use useful empty states that explain what will appear after connections/syncs.
- Keep confidence/freshness secondary.
- Ensure no expected My Items route or API call returns 404.

## Non-Scope

- Mailbox client behavior.
- Calendar clone behavior.
- File browser behavior.
- Mutating emails/files/calendar events.

## Files Likely Touched

- `frontend/src/pages/MyItemsPage.tsx`
- `frontend/src/components/my-items/*`
- `frontend/src/components/dashboard/*`
- `frontend/src/lib/api.ts`
- `src/hb_assistant/construction/analytics/api.py`
- `src/hb_assistant/construction/analytics/service.py`
- `tests/test_fastapi_analytics_dashboard_read_models.py`
- `tests/test_fastapi_analytics_app_shell.py`

## Implementation Guidance

- Prefer typed adapters and explicit view-model normalization over permissive `any` fallbacks.
- Preserve the current safety boundaries: no source-system writeback, no active chat, no raw/secrets serialization, no setup-triggered live sync.
- Keep the UI construction-management-first and avoid backend-console labels.
- Update tests and evidence in the same prompt; do not defer validation to a later session unless blocked by environment.
- When a gap is already fixed in current repo truth, document the evidence and do not rework the code unnecessarily.

## Acceptance Criteria

- My Items loads with no expected API 404s.
- Each required user-specific section renders.
- Empty states are helpful and not raw/debug.
- No raw email body, file text, calendar body, or meeting join URL appears.
- Operator role can use the page normally.

## Validation Commands

- `python -m pytest tests/test_fastapi_analytics_app_shell.py tests/test_fastapi_analytics_dashboard_read_models.py`
- `cd frontend && npm run lint && npm run typecheck && npm run build`
- `Browser smoke: /my-items as operator/viewer/admin`

## Evidence Required

Create or update:

```text
docs/evidence/frontend-production-readiness-implementation/prompt-19-my-items-dashboard-closeout.md
```

Include branch, HEAD, files changed, gaps closed/deferred, validation command output summary, browser smoke notes, and guardrail confirmation.

## Risk Notes

- Avoid adding raw inbox/file lists.
- Keep source matching and relevance advisory.
