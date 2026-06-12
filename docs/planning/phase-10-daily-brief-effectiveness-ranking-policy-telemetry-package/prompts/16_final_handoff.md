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

# 16 — Final Handoff

## Objective

Prepare the final implementation handoff after validation.

## Required Steps

1. Confirm `git status --short`.
2. Confirm branch and HEAD.
3. Summarize changed files.
4. Summarize evidence files.
5. Summarize validation results.
6. State any known limitations.
7. Use `FINAL_HANDOFF_TEMPLATE.md` exactly.

## Prohibited Claims

Do not claim merge readiness unless every gate in `templates/merge_readiness_checklist.md` passes.

Do not include raw evidence content in the handoff.
