# Prompt 23 — End-to-end local smoke harness

Repository: `RMF112018/hb-personal-assistant`  
Working path: `/Users/bobbyfetting/hb-personal-assistant`  
Prompt dependency: Prompt 22 should be closed or explicitly waived with evidence.

## Objective

Make local backend/frontend launch validation repeatable and evidence-backed.

## Repo-Truth First Step

Before changing files, run the preflight commands in `02_REPO_TRUTH_PREFLIGHT.md` or update the existing preflight evidence if it has already been run in this implementation sequence. Repository truth is authoritative over this package.

## Gaps Addressed

### FPR-012 — No frontend test harness found

- Severity: P2
- Affected area: Testing / Validation
- Recommended fix: Add Vitest + React Testing Library for components/adapters and Playwright or scripted browser smoke for local routes.
- Validation: npm run test; npm run smoke:frontend; npm run build

### FPR-018 — End-to-end local smoke harness and runbook are not yet packaged

- Severity: P3
- Affected area: Documentation / Operations
- Recommended fix: Create one command/scripted runbook for install, backend start, frontend start, route smoke, no 404/console errors, and role switching.
- Validation: run documented smoke from clean checkout; capture evidence


## Scope

- Add a frontend test harness if absent: Vitest + React Testing Library for adapters/components and/or Playwright for route smoke.
- Add npm scripts for test/smoke without breaking existing scripts.
- Add a local smoke script or documented harness that starts/verifies backend 8000 and frontend 5173, checks expected routes/API calls, and captures failures.
- Ensure the harness can run against local test fixtures without touching operator DB/auth cache/Obsidian.
- Fail on expected API 404s, build errors, and blocking console errors.

## Non-Scope

- Cloud CI/CD deployment.
- External API integration tests.
- Operator production data tests.

## Files Likely Touched

- `frontend/package.json`
- `frontend/vitest.config.*`
- `frontend/src/**/*.test.*`
- `frontend/tests/*`
- `scripts/proofs/*`
- `docs/runbooks/*`
- `tests/*`
- `docs/evidence/frontend-production-readiness-implementation/*`

## Implementation Guidance

- Prefer typed adapters and explicit view-model normalization over permissive `any` fallbacks.
- Preserve the current safety boundaries: no source-system writeback, no active chat, no raw/secrets serialization, no setup-triggered live sync.
- Keep the UI construction-management-first and avoid backend-console labels.
- Update tests and evidence in the same prompt; do not defer validation to a later session unless blocked by environment.
- When a gap is already fixed in current repo truth, document the evidence and do not rework the code unnecessarily.

## Acceptance Criteria

- A documented repeatable smoke path exists.
- Frontend has at least adapter/component tests for route/API shape fixes.
- Smoke fails on expected API 404s or blocking console errors.
- Evidence captures backend/frontend startup and route results.

## Validation Commands

- `python -m pytest tests/test_fastapi_analytics_app_shell.py tests/test_fastapi_analytics_dashboard_read_models.py tests/test_fastapi_analytics_daily_brief.py tests/test_fastapi_analytics_settings.py tests/test_fastapi_analytics_connection_setup.py tests/test_fastapi_analytics_today.py`
- `cd frontend && npm run lint && npm run typecheck && npm run build`
- `cd frontend && npm run test -- --run`
- `Run new smoke command/script and save output evidence`

## Evidence Required

Create or update:

```text
docs/evidence/frontend-production-readiness-implementation/prompt-23-end-to-end-local-smoke-harness-closeout.md
```

Include branch, HEAD, files changed, gaps closed/deferred, validation command output summary, browser smoke notes, and guardrail confirmation.

## Risk Notes

- Keep smoke local-only.
- Do not use real credentials, auth cache, or operator DB.
- If Playwright is too heavy for this phase, implement a scripted API/route smoke and document Playwright as future.
