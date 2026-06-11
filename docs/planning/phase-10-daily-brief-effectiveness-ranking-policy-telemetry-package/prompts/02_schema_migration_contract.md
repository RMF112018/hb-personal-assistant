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

# 02 — Schema Migration Contract

## Objective

Add the next schema version after repo truth for raw-safe effectiveness telemetry tables.

## Tasks

1. Bump `LATEST_SCHEMA_VERSION` by exactly one.
2. Add additive migration statements for:
   - `daily_brief_exposure_events`
   - `daily_brief_item_outcome_events`
   - `ranking_policy_eval_runs`
   - `ranking_policy_eval_items`
   - `model_profile_eval_results`
   - `brief_effectiveness_rollups`
3. Add indexes for window, brief date, run ids, candidate ids, policy/model, source/family/project, and created timestamps.
4. Add full Phase 10 guard columns with `DEFAULT 0 CHECK(... = 0)` to every table.
5. Add schema/migration tests.

## Guardrails

No DROP. No destructive ALTER. No raw-content exempt telemetry table. No raw body/title/path/artifact body columns.

## Evidence

Write `03-schema-migration-proof.json` after tests/SQL proof.
