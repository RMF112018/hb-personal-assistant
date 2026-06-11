You are the local code agent working in Bobby's `RMF112018/hb-personal-assistant` repository.

Package: `docs/planning/phase-10-email-followup-candidate-projection-package/`

Before doing anything else:

```bash
cd /Users/bobbyfetting/hb-personal-assistant
git status --short
git branch --show-current
git rev-parse HEAD
```

Stop if you are on `main` or if unexplained dirty files are present.

Hard safety constraints:

- Do not mutate the production DB.
- Do not send/draft/reply/forward email.
- Do not mutate calendar, Graph, Procore, SharePoint, OneDrive, Obsidian, or any external system.
- Use `/tmp` DB copies for apply validation.
- Do not expose raw bodies, HTML, private URLs, tokens, secrets, full recipient arrays, unbounded subjects, model prompts, or model responses.

# 11 — Final Handoff

## Objective

Produce the final implementation handoff and do not overclaim.

## Required Commands

```bash
git status --short
git branch --show-current
git rev-parse HEAD
git diff --name-only main...HEAD
git log --oneline --decorate -12
```

If Bobby requested commits:

```bash
git status --short
git add <intentional files only>
git commit -m "feat(second-brain): project email follow-up candidates into daily brief"
git status --short
git rev-parse HEAD
```

Do not commit unless Bobby asked for commits.

## Required Handoff

Use:

`docs/planning/phase-10-email-followup-candidate-projection-package/FINAL_HANDOFF_TEMPLATE.md`

Write final evidence to:

`docs/evidence/phase-10-email-followup-candidate-projection/14-final-handoff.md`

Include:

- branch
- commit SHA, if any
- changed files
- tests run
- DB copy validation
- candidate counts
- source-ref coverage
- project-key coverage
- guard-column result
- no-raw-leak result
- known failures/quarantines
- production safety statement
- merge readiness statement

Be explicit if anything is incomplete or not merge-ready.
