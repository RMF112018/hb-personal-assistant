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

# 03 — Telemetry Join Contract

## Objective

Implement a repo-true join map connecting ranked/assembled brief items to lifecycle outcomes, source refs, model receipts, and duplicate/similarity advice.

## Tasks

1. Create a small join-map module or documented constants inside the packet builder.
2. Map ranking rows to `daily_brief_action_candidate_id`.
3. Map assembly sections to section keys/groups.
4. Map candidate IDs to `candidate_source_refs` counts.
5. Map candidates to V50 lifecycle states and lifecycle events.
6. Map model-assisted rows to model receipt/profile metadata.
7. Map duplicate/similarity advisory edges to cluster-level evaluation facts.

## Required Behavior

- Missing ranked briefs -> `no_ranked_briefs`.
- Missing outcomes -> `insufficient_outcome_data`.
- Missing model receipts -> deterministic-only evaluation.
- Missing source refs for surfaced actionable candidates -> fail/degrade honestly.

## Evidence

Write `07-outcome-join-proof.json` and `14-source-ref-coverage-proof.json`.
