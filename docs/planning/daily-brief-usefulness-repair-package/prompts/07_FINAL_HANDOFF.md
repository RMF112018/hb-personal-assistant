# Prompt 07 — Final Handoff

## Objective

Prepare final evidence and handoff.

## Required Actions

1. Run final checks:
   - `git status --short`
   - `git log --oneline main..HEAD`
   - compileall
   - targeted pytest
   - changed-file lint/type
   - forbidden scan
   - production DB unchanged proof
2. Create `docs/evidence/daily-brief-usefulness-repair/07-final-handoff/`.
3. Use `templates/FINAL_HANDOFF_TEMPLATE.md`.
4. Add/update a durable architecture note if the implementation creates a durable contract change.

## Final Response Must Include

- branch and HEAD;
- base/main relationship;
- commit list;
- files changed;
- five-priority implementation summary;
- tests;
- DB-copy live proof;
- production DB unchanged proof;
- safety scan;
- known limitations;
- merge recommendation.

## Suggested Commit

`docs(second-brain): add daily brief usefulness repair handoff`
