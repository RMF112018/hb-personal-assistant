# Execution Guide for Local Code Agent

## Objective

Implement the frontend shell/layout, masonry dashboard, and end-user copy remediation required to move the current local frontend from a technical/demo shell toward a production-ready construction-management command center.

## Recommended branch

Create a dedicated branch before edits:

```bash
cd /Users/bobbyfetting/hb-personal-assistant
git checkout main
git pull --ff-only
git checkout -b frontend-uiux-shell-copy-readiness
```

If the local branch or HEAD differs from the package baseline, continue only after documenting the delta in your preflight notes.

## Execution protocol

For each prompt:

1. Read the prompt fully.
2. Inspect current repo truth for all listed files before editing.
3. Make the smallest coherent set of changes that satisfies the acceptance criteria.
4. Run the prompt-level validation commands.
5. Record changed files, validation results, screenshots/manual smoke notes, and any unresolved items.
6. Do not proceed to dependent prompts if a P0 acceptance criterion fails.

## Implementation posture

- Prefer small, reusable components over one-off page-specific layout fixes.
- Prefer CSS Grid with explicit responsive spans over JS masonry or CSS columns.
- Keep DOM reading order accessible; do not use visual reorder tricks that break keyboard/screen-reader logic.
- Treat copy cleanup as required production-readiness work, not as polish.
- Move technical detail behind admin-only or explicit disclosure controls.
- Avoid changing backend behavior unless frontend type definitions must align with already-existing backend route contracts.

## Commit posture

Recommended commits:

1. `Fix frontend shell overflow and production chrome`
2. `Add shared dashboard layout and copy primitives`
3. `Refactor Today Projects and My Items dashboards`
4. `Rewrite Settings and Data Health user-facing copy`
5. `Add frontend copy regression and layout documentation`

Do not squash away validation evidence in the final report.
