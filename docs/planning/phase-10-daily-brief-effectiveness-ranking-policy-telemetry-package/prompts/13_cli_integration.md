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

# 13 — CLI Integration

## Objective

Add the repo-true CLI command for evaluating daily brief effectiveness.

## Target Command

```bash
hb-assistant second-brain daily-brief evaluate-effectiveness   --window-start YYYY-MM-DD   --window-end YYYY-MM-DD   --dry-run   --json
```

## Required Options

- `--db PATH`
- `--window-start YYYY-MM-DD`
- `--window-end YYYY-MM-DD`
- `--brief-date YYYY-MM-DD`
- `--policy-version TEXT`
- `--model-profile-id TEXT`
- `--eval-mode observed|deterministic-replay|model-assisted-observed|ablation`
- `--include-procore-noise/--no-procore-noise`
- `--include-model-profile/--no-model-profile`
- `--include-rollups/--no-rollups`
- `--max-persist N`
- `--apply/--dry-run`
- `--json/--no-json`

## Exit Codes

- `0`: evaluation completed or dry-run report produced.
- `2`: invalid usage/date/window/options.
- `3`: fail-closed safety/schema/raw-leak/authority contradiction.
- `1`: unexpected implementation error.

## Requirements

- Default dry-run.
- Apply requires `--max-persist`.
- JSON output raw-free.
- `/tmp` DB path redaction follows repo convention.
