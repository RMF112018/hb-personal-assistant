# P03 — Today Masonry Dashboard and Copy Rewrite

## Objective

Refactor Today into a responsive masonry-style command-center dashboard and remove backend/read-model/Daily-Brief pipeline language from normal UI.

## Scope

Likely files:

- `frontend/src/pages/TodayPage.tsx`
- `frontend/src/components/today/*`
- `frontend/src/components/daily-brief/DailyBriefRenderer.tsx`
- shared primitives from P02
- `frontend/src/lib/statusCopy.ts`
- `frontend/src/lib/errorCopy.ts`

## Target layout

```text
Today
  Page header
  Dashboard grid:
    Important Today / Priority summary
    Daily Brief
    Meetings
    Action Items
    Recent Changes
    Correspondence
    Documents
    Cost / Change / Time signal card if already available
```

## Required copy remediation

Remove or hide from normal UI:

- `FastAPI`
- `uvicorn`
- `read model`
- `source/sync/evidence`
- raw JSON/`JSON.stringify` fallbacks
- Daily Brief state-machine or external Markdown/MCP details in primary view

Preferred copy examples:

- `This section could not be loaded. Restart the local app and try again.`
- `No items need attention right now.`
- `Brief not available yet. Check Daily Brief setup in Settings.`
- `Last updated ...`
- `Check Data Health`

## Non-scope

- Do not change daily brief generation.
- Do not change external agent/MCP workflow contracts.
- Do not modify backend route behavior.

## Acceptance criteria

- Today uses shared dashboard grid/card primitives.
- High-priority content appears first in DOM and visual order.
- Layout is scan-friendly at desktop and graceful at tablet/mobile widths.
- Normal Today UI contains no forbidden technical copy.
- Empty/error states point to Settings or Data Health as appropriate.

## Validation

```bash
cd frontend
npm run lint
npm run typecheck
npm run build
npm run test
cd ..
python -m pytest tests/test_fastapi_analytics_app_shell.py
```

Manual smoke:

- Today top/middle/bottom scroll.
- Empty data state.
- Error/disconnected backend state if feasible without modifying external systems.
- Keyboard focus through cards.
