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

# 05 — Project Resolution and Review Queue

## Objective

Reuse existing project identity/project-key resolution for email-derived candidates and surface unresolved project-like items honestly.

## Required Behavior

- Use existing project identity tables/functions:
  - `construction_project_identity`
  - `construction_project_keyword_registry`
  - `construction_project_source_matches`
  - any existing project alias/project promotion APIs
- Prefer explicit structured `project_key` when already present.
- If no `project_key` exists, run existing safe resolution against bounded/redacted subject/title/domain metadata only.
- Do not use raw body text for project resolution unless audited and justified.
- Do not invent project keys.
- If project-like but unresolved:
  - keep `project_key = None`
  - mark `project_resolution_status = review_required`
  - include a data-gap/review count in status
  - optionally persist a review queue/source match row if repo conventions support it

## Tests

Add tests for:

- explicit project key is preserved
- alias/keyword match resolves a project key
- ambiguous match becomes review-required
- no match becomes not-project-related or review-required based on signal
- no invented keys
- daily brief still source-links unresolved candidates
- project-key coverage is reported

## Evidence

Write:

`docs/evidence/phase-10-email-followup-candidate-projection/05-project-resolution-review.md`

Include counts only:

- candidates considered
- resolved
- review-required
- not-project-related
- project-key coverage
- invented keys found: must be zero
