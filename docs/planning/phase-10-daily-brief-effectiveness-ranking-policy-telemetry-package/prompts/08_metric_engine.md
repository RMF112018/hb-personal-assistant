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

# 08 — Metric Engine

## Objective

Implement `daily_brief_effectiveness_metrics.py` with deterministic metric functions from `references/metric_definitions.md`.

## Required Metrics

- accepted_rate
- rejected_rate
- snoozed_rate
- ignored_rate
- stale_accepted_recurrence
- rank_outcome_score
- source_family_usefulness_score
- procore_noise_score
- model_advice_validity_rate
- advisory_adoption_proxy
- model_degradation_rate
- duplicate_precision_proxy
- source_ref_coverage
- brief_usefulness_score
- deterministic_vs_model_delta
- feedback_calibration_lift

## Requirements

- Pure functions.
- Stable rounding.
- Small sample returns `insufficient_sample` metadata.
- Unit tests with fixed examples.
