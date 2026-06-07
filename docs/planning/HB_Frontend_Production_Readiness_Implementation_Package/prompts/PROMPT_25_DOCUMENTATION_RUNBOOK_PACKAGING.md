# Prompt 25 — Documentation and runbook packaging

Repository: `RMF112018/hb-personal-assistant`  
Working path: `/Users/bobbyfetting/hb-personal-assistant`  
Prompt dependency: Prompt 24 should be closed or explicitly waived with evidence.

## Objective

Package final local-first operating instructions and next-session handoff without overstating implemented capabilities.

## Repo-Truth First Step

Before changing files, run the preflight commands in `02_REPO_TRUTH_PREFLIGHT.md` or update the existing preflight evidence if it has already been run in this implementation sequence. Repository truth is authoritative over this package.

## Gaps Addressed

### FPR-018 — End-to-end local smoke harness and runbook are not yet packaged

- Severity: P3
- Affected area: Documentation / Operations
- Recommended fix: Create one command/scripted runbook for install, backend start, frontend start, route smoke, no 404/console errors, and role switching.
- Validation: run documented smoke from clean checkout; capture evidence


## Scope

- Update README/frontend README/runbooks as appropriate.
- Document backend/frontend launch commands, role testing, Settings setup flows, Daily Brief external-agent workflow, Admin governance, and known limitations.
- Add final implementation evidence index.
- Generate a next-prompt handoff only for remaining deferred P2/P3 items, not for closed work.
- Ensure docs distinguish current behavior from planned/future behavior.

## Non-Scope

- Behavioral code changes except doc links or minor evidence index wiring.
- Marketing copy.
- Claims that are not supported by validation evidence.

## Files Likely Touched

- `README.md`
- `frontend/README.md`
- `docs/runbooks/*`
- `docs/evidence/frontend-production-readiness-implementation/*`
- `docs/architecture/*`

## Implementation Guidance

- Prefer typed adapters and explicit view-model normalization over permissive `any` fallbacks.
- Preserve the current safety boundaries: no source-system writeback, no active chat, no raw/secrets serialization, no setup-triggered live sync.
- Keep the UI construction-management-first and avoid backend-console labels.
- Update tests and evidence in the same prompt; do not defer validation to a later session unless blocked by environment.
- When a gap is already fixed in current repo truth, document the evidence and do not rework the code unnecessarily.

## Acceptance Criteria

- A new developer/user can launch the app locally from docs.
- Docs explain Today, Projects, My Items, Admin/Data Confidence, Settings, and Daily Brief workflow.
- Known limitations are explicit.
- Final closeout includes branch, HEAD, validation results, gap status, and guardrail confirmation.

## Validation Commands

- `Documentation link/path check`
- `Fresh-clone-style runbook smoke as far as local environment allows`
- `Final grep for stale claims such as active in-app chat or live sync from setup`

## Evidence Required

Create or update:

```text
docs/evidence/frontend-production-readiness-implementation/prompt-25-documentation-runbook-packaging-closeout.md
```

Include branch, HEAD, files changed, gaps closed/deferred, validation command output summary, browser smoke notes, and guardrail confirmation.

## Risk Notes

- Do not claim production readiness unless validation evidence supports it.
- Do not bury remaining blockers in narrative.
