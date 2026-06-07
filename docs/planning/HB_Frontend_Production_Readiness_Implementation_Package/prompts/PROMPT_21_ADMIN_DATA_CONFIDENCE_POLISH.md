# Prompt 21 — Admin / Data Confidence polish

Repository: `RMF112018/hb-personal-assistant`  
Working path: `/Users/bobbyfetting/hb-personal-assistant`  
Prompt dependency: Prompt 20 should be closed or explicitly waived with evidence.

## Objective

Keep Admin / Data Confidence supportive, role-aware, and useful without dominating normal operator workflows.

## Repo-Truth First Step

Before changing files, run the preflight commands in `02_REPO_TRUTH_PREFLIGHT.md` or update the existing preflight evidence if it has already been run in this implementation sequence. Repository truth is authoritative over this package.

## Gaps Addressed

### FPR-007 — Admin page does not present role-denied state clearly

- Severity: P1
- Affected area: Admin / Data Confidence
- Recommended fix: Detect 403 errors and render a clear “Admin role required” state with local role selector guidance.
- Validation: browser smoke admin as operator/admin; React Query error state test; pytest admin 403 remains


## Scope

- Render a clear admin-required state on 403 for operator/viewer roles.
- Render six categories for admin: Source / Sync Health, Workflow / Job Health, Evidence / Guardrail Health, Retrieval / AI Quality, Permissions / Governance, Data Completeness / Coverage.
- Keep local dev role selector visibly non-production auth.
- Make admin cards readable and compact.
- Ensure raw sensitive fields are redacted or not fetched/serialized.

## Non-Scope

- Weakening backend admin role requirements.
- Adding new diagnostics engines.
- Putting admin telemetry on top-level Today in a dominant way.

## Files Likely Touched

- `frontend/src/pages/AdminDataConfidencePage.tsx`
- `frontend/src/components/admin/*`
- `frontend/src/components/ui/*`
- `frontend/src/lib/api.ts`
- `tests/test_fastapi_analytics_app_shell.py`
- `src/hb_assistant/construction/analytics/api.py`

## Implementation Guidance

- Prefer typed adapters and explicit view-model normalization over permissive `any` fallbacks.
- Preserve the current safety boundaries: no source-system writeback, no active chat, no raw/secrets serialization, no setup-triggered live sync.
- Keep the UI construction-management-first and avoid backend-console labels.
- Update tests and evidence in the same prompt; do not defer validation to a later session unless blocked by environment.
- When a gap is already fixed in current repo truth, document the evidence and do not rework the code unnecessarily.

## Acceptance Criteria

- Operator/viewer see a clear admin-required state, not endless loading.
- Admin sees all six categories.
- 403 from admin endpoints remains enforced by backend.
- No raw/secrets appear in admin diagnostics.

## Validation Commands

- `python -m pytest tests/test_fastapi_analytics_app_shell.py`
- `cd frontend && npm run lint && npm run typecheck && npm run build`
- `Browser smoke: /admin as operator, viewer, admin`

## Evidence Required

Create or update:

```text
docs/evidence/frontend-production-readiness-implementation/prompt-21-admin-data-confidence-polish-closeout.md
```

Include branch, HEAD, files changed, gaps closed/deferred, validation command output summary, browser smoke notes, and guardrail confirmation.

## Risk Notes

- Do not turn local role selector into implied production auth.
- Avoid making Admin the perceived center of the product.
