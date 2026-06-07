# Prompt 24 — Local-first production hardening

Repository: `RMF112018/hb-personal-assistant`  
Working path: `/Users/bobbyfetting/hb-personal-assistant`  
Prompt dependency: Prompt 23 should be closed or explicitly waived with evidence.

## Objective

Close remaining safety, dependency, and packaging gaps required for local-first production readiness.

## Repo-Truth First Step

Before changing files, run the preflight commands in `02_REPO_TRUTH_PREFLIGHT.md` or update the existing preflight evidence if it has already been run in this implementation sequence. Repository truth is authoritative over this package.

## Gaps Addressed

### FPR-014 — Daily Brief latest endpoint returns bounded Markdown content; needs explicit no-source-raw fixture coverage

- Severity: P2
- Affected area: Daily Brief / Safety
- Recommended fix: Add fixtures for forbidden content, overly long files, parse warnings, stale files, and path display; keep original file unchanged.
- Validation: pytest daily brief expanded fixtures; no source file mutation proof

### FPR-016 — Preferences persistence is still an echo stub

- Severity: P3
- Affected area: Settings / Preferences
- Recommended fix: Persist preferences to local Application Support JSON with schema/version and safe validation.
- Validation: pytest preferences roundtrip; browser reload persistence


## Scope

- Capture dependency install/build proof with normal npm install.
- Add or strengthen no-raw/no-secrets/no-writeback scans for frontend evidence.
- Expand Daily Brief fixtures: forbidden markers, overly long files, parse warnings, stale files, missing files, path display, original-file preservation.
- Add app-level error boundary if absent.
- Document environment defaults and failure states.
- If preferences persistence was deferred in Prompt 20, either implement it or explicitly classify it as non-blocking with UI honesty.

## Non-Scope

- External deployment.
- Active chat.
- Live source sync changes beyond admin-gated governance already in repo.

## Files Likely Touched

- `frontend/package.json`
- `frontend/src/*`
- `frontend/src/components/*`
- `scripts/proofs/*`
- `tests/test_fastapi_analytics_daily_brief.py`
- `src/hb_assistant/construction/analytics/daily_brief.py`
- `docs/evidence/frontend-production-readiness-implementation/*`

## Implementation Guidance

- Prefer typed adapters and explicit view-model normalization over permissive `any` fallbacks.
- Preserve the current safety boundaries: no source-system writeback, no active chat, no raw/secrets serialization, no setup-triggered live sync.
- Keep the UI construction-management-first and avoid backend-console labels.
- Update tests and evidence in the same prompt; do not defer validation to a later session unless blocked by environment.
- When a gap is already fixed in current repo truth, document the evidence and do not rework the code unnecessarily.

## Acceptance Criteria

- npm install/lint/typecheck/build proof captured.
- No `--legacy-peer-deps` required, or documented as unresolved technical debt with a remediation path.
- Expanded Daily Brief tests pass and original Markdown fixture remains preserved.
- No raw/secrets/writeback scan violations.
- Chat remains inaccessible.

## Validation Commands

- `cd frontend && npm install && npm run lint && npm run typecheck && npm run build`
- `python -m pytest tests/test_fastapi_analytics_daily_brief.py`
- `python -m pytest targeted analytics tests`
- `Run no-raw/no-secrets/no-writeback scans and save evidence`

## Evidence Required

Create or update:

```text
docs/evidence/frontend-production-readiness-implementation/prompt-24-local-first-production-hardening-closeout.md
```

Include branch, HEAD, files changed, gaps closed/deferred, validation command output summary, browser smoke notes, and guardrail confirmation.

## Risk Notes

- Do not include real secrets or raw content in negative fixtures. Use synthetic markers only.
- Do not mutate user Obsidian vault during tests.
