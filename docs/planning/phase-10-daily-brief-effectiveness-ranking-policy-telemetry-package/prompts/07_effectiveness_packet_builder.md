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

# 07 — Effectiveness Packet Builder

## Objective

Implement `daily_brief_effectiveness_packets.py` to build raw-free evaluation packets from repo-true structured data.

## Packet Fields

- window start/end;
- brief dates;
- ranking/assembly run ids;
- policy/model/calibration versions;
- candidate id, section, family, source family, project key;
- rank position and scores;
- source-ref count;
- lifecycle outcome type and lag;
- model status/degradation metadata;
- duplicate/similarity cluster metadata;
- data sufficiency flags.

## Requirements

- Pure/read-only by default.
- Scanner-clean.
- No raw title/reason unless bounded/redacted and scanner-clean by repo convention.
- Explicit degradation states for missing data.
