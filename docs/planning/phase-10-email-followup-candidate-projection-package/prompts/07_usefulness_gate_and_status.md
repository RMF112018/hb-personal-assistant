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

# 07 — Usefulness Gate and Status

## Objective

Extend or verify the usefulness gate and operator status so email/follow-up contradictions fail/degrade honestly.

## Required Contradictions

The gate must detect:

1. Email raw/structured rows exist but follow-up candidates are empty and no data-gap card is present.
2. Follow-up candidates exist but source refs are missing.
3. Email-derived candidates exist but project-key coverage is unexpectedly low without review-required status.
4. Model/intelligence sections claim follow-ups while source-linked candidate substrate is empty.
5. Extractor stage fails/degrades but daily-run result claims success.
6. Raw access occurs without audit events.

## Status Block

The operator-facing status block must report:

- email raw available
- structured email available
- eligible messages/threads considered
- candidates generated/persisted
- domain rows persisted by type
- daily-brief rows persisted by section
- source-ref coverage
- project-key coverage
- review-required count
- data-gap card/status
- degraded/failure reasons

## Tests

Add/extend tests for:

- all contradiction paths
- backward compatibility when stage context is absent
- successful path with 100% source refs
- failure when refs missing
- degrade when project coverage low but no review-required reason exists
- model bullet/drop behavior where applicable

## Evidence

Write:

`docs/evidence/phase-10-email-followup-candidate-projection/07-usefulness-gate-status.md`
