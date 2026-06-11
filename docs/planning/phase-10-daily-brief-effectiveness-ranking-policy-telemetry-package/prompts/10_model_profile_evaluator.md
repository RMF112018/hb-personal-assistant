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

# 10 — Model Profile Evaluator

## Objective

Implement `model_profile_evaluator.py` to evaluate local model reliability and advisory utility from receipt metadata only.

## Required Outputs

- attempt count;
- success count;
- schema invalid count;
- safety withheld count;
- timeout count;
- unknown alias count;
- lifecycle excluded ref count;
- fallback count;
- average latency;
- p95 latency;
- advisory adoption proxy;
- degradation rate.

## Requirements

- Do not read raw prompt/response.
- Do not call local model.
- Do not store raw output.
- Use receipt IDs/hashes/status codes only.
