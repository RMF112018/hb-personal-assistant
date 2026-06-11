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

# 06 — Daily Brief Integration

## Objective

Integrate email-derived candidates into the daily-brief pipeline and operator output.

## Required Behavior

Wire the extractor/persistence into the local-agent daily run.

Default stage placement:

```text
email_calendar_projection
email_followup_projection
follow_up_watch
procore_digest
calendar_prep
daily_brief_synthesis
daily_brief_render
```

If repo truth shows `follow_up_watch` is the correct existing stage, extend that stage rather than creating a redundant stage. Document the decision.

## Stage Receipt

The email follow-up stage receipt must be raw-free and include:

- stage name
- mode: dry-run/apply
- raw email available
- structured email available
- eligible messages considered
- eligible threads considered
- generated candidate count
- persisted domain count
- persisted daily-brief count
- source-ref coverage
- project-key coverage
- unresolved review-required count
- raw access count
- data-gap status
- reason codes
- degraded reason, if any

## Daily Brief Behavior

- When eligible candidates exist, render them in `follow_up`, `waiting`, and/or `actions`.
- When raw/structured email rows exist but no follow-up candidates are generated, preserve the email/follow-up data-gap card.
- When the stage fails, status must degrade/fail honestly.
- Do not let synthesis claim follow-ups unsupported by source-linked candidates.
- Browser/status output must remain raw-free.

## Tests

Add/extend tests for:

- stage ordering
- dry-run writes nothing
- apply writes to `/tmp` DB copy only
- stage receipt raw-free
- data-gap card replaced when candidates exist
- data-gap card preserved when no candidates exist
- daily brief sections include only source-linked candidates
- no model success without source-linked substrate

## Evidence

Write:

`docs/evidence/phase-10-email-followup-candidate-projection/06-daily-brief-integration.md`
