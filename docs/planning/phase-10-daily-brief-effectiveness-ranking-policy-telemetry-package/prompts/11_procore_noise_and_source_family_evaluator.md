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

# 11 — Procore Noise and Source-Family Evaluator

## Objective

Implement `procore_noise_evaluator.py` and source/family grouping metrics.

## Tasks

1. Identify Procore-derived ranked/exposed candidates from safe metadata.
2. Group by source family, candidate family, signal type, section, project key.
3. Compute Procore noise score and top noisy groups.
4. Compute source-family usefulness scores.
5. Generate safe tuning recommendations.

## Requirements

- No automatic suppression or threshold changes.
- No Procore writeback.
- No raw Procore payload reads.
- Mark small samples insufficient.
