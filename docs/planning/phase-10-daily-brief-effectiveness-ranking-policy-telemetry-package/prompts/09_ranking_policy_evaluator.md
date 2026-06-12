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

# 09 — Ranking Policy Evaluator

## Objective

Implement `ranking_policy_evaluator.py` to evaluate observed and replay/baseline ranking policies.

## Modes

- `observed`
- `deterministic-replay`
- `model-assisted-observed`
- `ablation`

## Requirements

- Deterministic-only evaluation works without model telemetry.
- Model-assisted evaluation uses model metadata only when present.
- No model call is required for evaluation.
- Metrics include sample-size caveats.
- Apply persists eval run/items only, capped by `--max-persist`.
