# 15 — Final Integration Audit and Residual-Work Elimination

## Objective

Perform a final repo-truth audit after implementation and eliminate residual work inside this slice.

## Required checks

1. `git status --short`
2. `git diff --stat main...HEAD`
3. `git diff --name-only main...HEAD`
4. Confirm no unintended files/raw artifacts are staged.
5. Confirm evidence file inventory is complete.
6. Confirm validation matrix is satisfied.
7. Confirm final docs match implemented behavior.
8. Run forbidden string/no-raw scan over evidence and changed docs.
9. Inspect any TODO/FIXME added by this package and resolve or document as known limitation.
10. Prepare final handoff using `FINAL_HANDOFF_TEMPLATE.md`.

## Evidence

Create:

- `26-known-limitations.md`
- `27-final-handoff.md`
- `28-residual-work-audit.md`

## Commit

Commit the implementation on the feature branch with a clear message such as:

```text
feat(second-brain): activate source-linked daily brief projection slice
```

Do not merge to main unless explicitly instructed by the operator.

## Acceptance

- No residual first-slice work remains unless blocked by a documented stop condition.
- Branch is ready for review.


## Safety constraints for this prompt

- Use DB copies for validation.
- Do not print raw private values.
- Do not mutate external systems.
- Do not mutate production DB during validation.
- Commit only code/docs/tests/evidence that are raw-free.
- Stop if any stop condition is triggered.
