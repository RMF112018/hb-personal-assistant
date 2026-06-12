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

# 05 — Exposure Event Tracking

## Objective

Add raw-free exposure event capture for brief/section/item render surfaces.

## Tasks

1. Implement exposure event builder/writer that records only metadata and hashes.
2. Capture event types such as `brief_rendered`, `section_rendered`, `item_rendered`, `cli_preview`, `browser_preview`, `markdown_export` when repo surfaces exist.
3. Use artifact/content hash only. Do not store artifact path or body.
4. Integrate with render/report paths only when safe; otherwise expose a separate explicit command path.

## Requirements

- Render remains read-only unless caller explicitly uses apply telemetry.
- Dry-run exposure tracking writes zero rows.
- Exposure events must never use `include_raw` output.
