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

# 01 — Ranking / Assembly Prerequisite Audit

## Objective

Confirm whether the prerequisite ranking/assembly slice exists locally and define the repo-true contract this telemetry slice will consume.

## Required Findings

Document exact names/locations for:

- ranking run table/read model;
- ranked candidate table/read model;
- assembly run table/read model;
- assembly section table/read model;
- similarity/duplicate edge table/read model;
- model ranking receipt table/read model;
- policy version fields;
- feedback calibration version fields;
- deterministic/model/final score fields;
- candidate set hash fields;
- model degradation/withheld/fallback fields.

## Stop Condition

If these do not exist, stop implementation. Write `01-ranking-assembly-prerequisite.md` with status `missing_ranking_assembly_prerequisite` and do not change source code.

## Evidence

Write:

`docs/evidence/phase-10-daily-brief-effectiveness-ranking-policy-telemetry/01-ranking-assembly-prerequisite.md`
