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

# 04 — Store / Repository Accessors

## Objective

Add focused, parameterized store/repository methods for telemetry tables. Business logic must not use arbitrary SQL strings except in migration/tests/helpers.

## Required Accessors

- `insert_daily_brief_exposure_event(...)`
- `list_daily_brief_exposure_events(...)`
- `insert_daily_brief_item_outcome_event(...)`
- `list_daily_brief_item_outcome_events(...)`
- `insert_ranking_policy_eval_run(...)`
- `insert_ranking_policy_eval_item(...)`
- `list_ranking_policy_eval_runs(...)`
- `list_ranking_policy_eval_items(...)`
- `insert_model_profile_eval_result(...)`
- `insert_brief_effectiveness_rollup(...)`
- `list_brief_effectiveness_rollups(...)`

## Requirements

- Idempotent inserts.
- No caller-supplied guard values.
- No lifecycle/source-ref mutation.
- No raw text/path/url columns.
- Unit tests for idempotency and parameter binding.
