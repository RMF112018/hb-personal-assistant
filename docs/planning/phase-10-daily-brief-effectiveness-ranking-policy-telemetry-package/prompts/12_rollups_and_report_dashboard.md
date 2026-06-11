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

# 12 — Rollups and Report / Dashboard

## Objective

Implement raw-free rollup persistence and a CLI/report-first effectiveness dashboard.

## Tasks

1. Implement `effectiveness_rollups.py`.
2. Implement `daily_brief_effectiveness_report.py`.
3. Produce daily, weekly, monthly, project, candidate_family, source_family, and model_profile rollups.
4. Render raw-free Markdown and JSON reports.
5. Add browser/dashboard surface only if repo truth has a safe compatible local surface.

## Requirements

- Reports include window, sample size, confidence note.
- Reports include insufficiency banners when appropriate.
- Reports scan clean.
