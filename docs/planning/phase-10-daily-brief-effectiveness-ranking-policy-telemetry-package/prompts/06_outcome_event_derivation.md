You are the local code agent working in Bobby's `RMF112018/hb-personal-assistant` repository.

Package: `docs/planning/phase-10-daily-brief-effectiveness-ranking-policy-telemetry-package/`

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
- Use `/tmp` DB copies for apply validation.
- Do not send/draft/reply/forward email.
- Do not mutate calendar, Graph, Procore, SharePoint, OneDrive, Obsidian, or any external system.
- Do not mutate lifecycle state or source refs from telemetry.
- Do not expose raw bodies, HTML, private URLs, tokens, secrets, local paths, raw Procore payloads, model prompts, or model responses.
- Telemetry is observational only.

# 06 — Outcome Event Derivation

## Objective

Derive raw-free outcome events from lifecycle/review/read-model data without creating lifecycle events.

## Tasks

1. Read V50 lifecycle overlay and computed review queue.
2. Derive outcomes: accepted, rejected, snoozed, merged, suppressed, closed, reopened, ignored, stale_no_action.
3. Calculate outcome lag hours from exposure/render time to lifecycle/review event time when available.
4. Use deterministic IDs for outcome event rows.
5. Persist only in telemetry apply mode.

## Requirements

- No lifecycle table inserts/updates.
- No review status changes.
- No inferred acceptance from high rank.
- Ignored means exposed and no movement after configured lag window.
