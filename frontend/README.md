# HB Analytics Frontend (Prompt 08 / UI-08)

Vite + React + TypeScript + Tailwind + shadcn-style modular UI.

Primary dark theme with dark / light / system support (persisted locally, respects OS).

## Required navigation (implemented)
- Primary (top-level): Today, Projects, My Items
- Support: Admin / Data Confidence, Settings
- Disabled (no active route, page, widget, or nav item): Chat

Domain areas (Portfolio, Meetings, Action Items, Cost/Change, Documents, Correspondence, Vendors, Billing/Cash, Closeout, Field Operations) are **contextual sections/tabs only** inside Today, Projects, or My Items. No active top-level nav items for them.

## Routes (exact)
- `/` → redirects to `/today`
- `/today`
- `/projects`
- `/projects/all`
- `/projects/all/meetings`
- `/projects/all/field-operations`
- `/projects/all/cost-time`
- `/projects/:projectKey`
- `/projects/:projectKey/meetings`
- `/projects/:projectKey/field-operations`
- `/projects/:projectKey/cost-time`
- `/my-items`
- `/admin`
- `/settings`

No `/chat` route.

## Run (with the Python FastAPI backend)
1. In repo root, start the optional analytics shell (read-only):
   ```
   source .venv/bin/activate
   pip install -e ".[analytics-ui]"
   uvicorn hb_assistant.construction.analytics.api:create_app --factory --reload --port 8000
   ```
   (The backend serves the Prompt 07 read models at `/api/today`, `/api/projects/*`, `/api/my-items`, etc.)

2. In `frontend/`:
   ```
   npm install          # one-time (populates node_modules from package.json)
   npm run dev
   ```
   Vite proxies `/api` → `http://127.0.0.1:8000` (see vite.config.ts).  
   Override with `VITE_API_BASE=http://localhost:8000` in a `.env` (copied from `.env.example`).

3. Open http://localhost:5173 (or the printed URL). Root redirects to Today.

Theme cycles via the header button (dark primary default).

## Data posture (guardrails preserved)
- All data is advisory-only, construction-facing.
- Compact freshness + confidence badges on primary screens.
- Detailed source/sync/evidence/retrieval diagnostics are hidden from primary screens and linked to `/admin`.
- Daily Brief (if present) is an externally generated Markdown file that the app **presents/polishes only** — it does not generate or rewrite content.
- No dry-run/apply/execute language in primary screens.
- No raw bodies, tokens, secrets, signed URLs, or prompts ever surface in the UI.

## Verification note
Python FastAPI app must import and run without any frontend build artifacts present (`16_TESTING_VALIDATION_ACCEPTANCE.md`).
Frontend: `npm run typecheck`, `npm run lint`, `npm run build` must succeed after `npm install`.

## Structure (hierarchy preserved)
See the plan and `src/app/`, `src/layouts/`, `src/navigation/`, `src/pages/`, `src/components/{dashboard,daily-brief,projects,my-items,admin,ui}/`.

## Next (future prompts)
UI-09+ will flesh out richer panel content, real-time query usage in all pages, project selector, more charts, and full Daily Brief polished renderer while keeping the same nav + route + guardrail contract.
