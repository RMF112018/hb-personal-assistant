# Prompt 07 DASHBOARD READ MODELS

Implement the first set of read models/endpoints for the simplified CM-first dashboard hierarchy.

Do not implement separate top-level domain dashboards. Compose domain analytics into:

- Today;
- Projects Portfolio / All Projects;
- Individual Project Overview;
- Project Meetings;
- Project Field Operations;
- Project Cost & Time;
- My Items;
- Admin / Data Confidence.

## Required endpoints

- `GET /api/today`
- `GET /api/projects/portfolio`
- `GET /api/projects/all/overview`
- `GET /api/projects/{project_key}/overview`
- `GET /api/projects/{project_key}/meetings`
- `GET /api/projects/{project_key}/field-operations`
- `GET /api/projects/{project_key}/cost-time`
- `GET /api/my-items`

## Requirements

- Keep user-facing language construction-native and advisory-only.
- Include freshness/confidence badges as supporting context.
- Do not expose dry-run/apply/execute terminology.
- Do not serialize raw bodies, raw document text, prompts/responses, tokens, signed URLs, or secrets.
- Use the revised 135-metric catalog for metric IDs and MVP priorities, but route the metrics through the simplified dashboard structure.
