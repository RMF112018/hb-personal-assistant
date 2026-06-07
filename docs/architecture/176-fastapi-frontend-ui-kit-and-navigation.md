# FastAPI Frontend UI Kit and Navigation (Prompt 08 / UI-08)

## Objective
Deliver the first modular Vite/React/TypeScript/Tailwind/shadcn-style UI shell for the CM-first analytics dashboard.

- Primary dark theme with dark/light/system support.
- Simplified navigation: Today / Projects / My Items (primary); Admin / Data Confidence + Settings (support).
- Chat and all detailed construction domains (Meetings, Cost/Change, Documents, Correspondence, Vendors, Billing/Cash, Closeout, Field Operations, Portfolio as top-level) are disabled as top-level nav or routes. They appear only as contextual sections/tabs inside Today, Projects, or My Items.
- Exact route set with `/` redirect to `/today`; no `/chat`.
- Thin presentation layer only. All intelligence lives in the Prompt 07 read-model endpoints (`/api/today`, `/api/projects/*`, `/api/my-items`, admin surfaces). Frontend fetches and renders; never duplicates backend logic.
- Daily Brief is presented/polished from an externally generated Markdown file only (no generation or rewrite in-app).
- Compact freshness/confidence badges; construction-facing labels; advisory notes; hide detailed source/sync/evidence/retrieval diagnostics from primary screens (link to `/admin`).
- Structure and component hierarchy per the Prompt 08 spec (actual paths may vary slightly for repo conventions; intent preserved).

This change is purely additive client-side. The Python package, FastAPI analytics shell, store, migrations, and guardrails are untouched. The frontend is optional and has no impact on CLI, automation, or second-brain phases.

## Navigation Model
Source of truth: `frontend/src/navigation/navigationModel.ts` (PRIMARY_NAV, SUPPORT_NAV, DISABLED_NAV, CONTEXTUAL_ONLY list).

- Primary: Today (`/today`), Projects (`/projects`), My Items (`/my-items`).
- Support: Admin / Data Confidence (`/admin`), Settings (`/settings`).
- Disabled (no nav item, no route, no widget): Chat.
- Domain tabs (Meetings, Field Operations, Cost & Time, etc.) are rendered via `ProjectSubNav` only inside project or all-projects views.

AppShell (`layouts/AppShell.tsx`) + MainNavigation + SupportNavigation enforce the model at runtime. Active states and disabled presentation are declarative.

## Routes (implemented exactly)
- `/` → redirects to `/today` (via React Router index + Navigate).
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

No `/chat` (explicit 404 or absence; disabled nav item carries explanatory title).

Routing lives in `app/routes.tsx` using `createBrowserRouter` + a root layout that wraps `AppShell` + `Outlet`. Project sub-pages are handled by the same page components (they branch on `projectKey === 'all'` or render `ProjectSubNav`).

## Theme
- Primary: dark.
- Support: dark / light / system (persisted to localStorage key `hb-theme`).
- Implementation: `app/providers.tsx` `ThemeProvider` applies `.dark` class to `<html>`, reacts to `prefers-color-scheme` when system, exposes `useTheme()` + cycle toggle.
- Tailwind `darkMode: 'class'` + CSS variables in `src/index.css` drive the palette (hb-* tokens for calm, executive, operations-focused surfaces).

## Component Inventory & Placement (per 12 + Prompt 08 sketch)
- `app/`: App.tsx (thin), routes.tsx, providers.tsx (Theme + QueryClient).
- `layouts/`: AppShell.tsx (sidebar + header + footer + outlet), MainNavigation.tsx, SupportNavigation.tsx, PageHeader.tsx.
- `navigation/`: navigationModel.ts (single source of truth).
- `pages/`: TodayPage, ProjectsPage, ProjectDashboardPage, ProjectMeetingsPage, ProjectFieldOperationsPage, ProjectCostTimePage, MyItemsPage, AdminDataConfidencePage, SettingsPage (all nine present; thin skeletons with required sections from 11).
- `components/`:
  - `dashboard/`: MetricCard, AttentionItemCard (plus room for MetricChartCard, DashboardSection).
  - `daily-brief/`: DailyBriefRenderer (safe external-MD presenter + status states; present/polish only).
  - `projects/`: ProjectSubNav (contextual tabs only), ProjectSelector (room for later).
  - `my-items/`: MyActionItemCard (room for more filtered queue cards).
  - `admin/`: SourceSyncCard (and health cards per 12).
  - `ui/`: Badge (FreshnessBadge + ConfidenceBadge), EmptyState, StaleDataBanner (room for ErrorRecoveryPanel, DrilldownTable).
- Tech: React 19 + Vite, Tailwind 3, React Router 6, TanStack Query 5 (client ready), Lucide icons, Recharts (declared), cva/clsx/tailwind-merge for shadcn-style primitives (modular off-the-shelf; no rigid design system).

## Data Integration (Prompt 07 read models)
- Thin client: `src/lib/api.ts` (base URL via `VITE_API_BASE` or `/api` proxy; Prompt 16: materialized with `LocalUiRole` get/set, X-HB-UI-Role header injection on every call, and explicit normalization comments for object envelopes (`metric_cards`/`attention_items`/`sections`) on project tabs + `/api/my-items` vs. today-compat `items` arrays. All today/project/my-items/admin/daily-brief/settings surfaces covered via `api` object + named exports. any-tolerant to match page style; safety boundaries noted (read-only, no secrets/raw).).
- Endpoints targeted (from 10 and Prompt 07 implementation): `/api/today`, `/api/projects/portfolio`, `/api/projects/all/overview`, per-key `/overview|meetings|field-operations|cost-time`, `/api/my-items`, admin health surfaces.
- Pages now consume the real client (Prompt 09/16). Project tabs render `metric_cards` + `attention_items` via Metric/Attention cards (no `.slice` on object envelopes). My Items consumes aggregate only (no subroute calls). Hash links replaced with `<Link>`. Admin surfaces show role-denied state on 403 without weakening backend guards. Prompt 17: Today (primary landing) updated with header/day context, required sections split (Cost/Change/Time Signals + Documents & Correspondence Worth Reviewing), CM-facing states/empties, explicit advisory cost/time language, compact secondary Data Confidence; new dedicated test coverage; see Prompt 17 closeout + evidence.
Prompt 18: ProjectsPage selector now consumes `project_keys` from portfolio envelope (dual-shape, maps to cards when no legacy array); portfolio + tab page header badges bound to backend freshness/confidence (FPR-003/009 closed); Field/Cost ownership + contextual tabs only preserved; see 177 + prompt-18 closeout.
Prompt 19: My Items finalized on aggregate-only contract (no subs); page uses explicit per-section arrays + kinds from richer envelope, 5 distinct sections with CM empties, light TS interfaces (my-items surface only); FPR-002 closed in 16 (documented) + 19 polish; see 177 + prompt-19 closeout.
Prompt 20: Settings guided CM-first (no raw panels/alerts/"sent (stub)"); Daily Brief state precedence fixed + helper; real local prefs JSON persist; keyword management UI; preview/save only. See 177 + prompt-20 closeout.
- Daily Brief: status + external MD content only; no authoring path.
- All fetch errors / empty / stale states degrade to EmptyState + badges (no crashes, no raw leakage).
- Guardrails (advisory_only, no raw, no determinations, construction labels, hide admin details) are expressed in UI copy and links.

Dev proxy in `vite.config.ts`:
```ts
proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true } }
```
Backend run (for reference):
```
pip install -e ".[analytics-ui]"
uvicorn hb_assistant.construction.analytics.api:create_app --factory --reload --port 8000
```

## Guardrails & Posture (unchanged from prior prompts)
- read_only, local_first, no_cli_shellout, no_external_writeback, sensitive_field_values_excluded, makes_determination: false.
- No tokens, raw bodies, full documents, prompts/responses, signed URLs, or PEMs ever leave the backend or enter the UI.
- Primary screens use business language (Refresh, Review, Prepare, Open, Mark Reviewed). No dry-run/apply/execute.
- Admin / Data Confidence is secondary and more technical; primary screens link to it for diagnostics.
- Evidence bundles and architecture docs (this file) are the source of truth over planning notes.

## Dev / Prod Considerations
- `frontend/` is a peer to `src/`; Python package data does not include it.
- `package.json` declares exact runtime + dev deps for the stack (Tailwind, router, query, icons, charts, utilities). Real `npm install` required for node_modules / build.
- TypeScript strict-ish (verbatimModuleSyntax, noUnused*, etc.) inherited from Vite template + our code.
- ESLint flat config (react-hooks, react-refresh, TS) present.
- Build: `tsc -b && vite build` (produces dist/).
- No Python changes; FastAPI app imports and serves without the frontend tree present (see 16_TESTING_VALIDATION_ACCEPTANCE).

## Validation Evidence (this run)
- Zero pre-existing frontend/ or node/ files in repo (confirmed via Glob + ls before scaffold).
- Exact navigation list, route list, disabled rules, and component hierarchy implemented and matching Prompt_08_FRONTEND_UI_KIT.md + 11 + 12.
- Theme provider + toggle + persistence + system respect implemented and wired through AppShell header.
- All nine pages exist with documented sections (Important Today, Daily Brief external, Meetings, What Changed, Action Items, Portfolio Signals, etc.), construction labels, compact badges, advisory text, and /admin drill links.
- Project sub-pages use contextual subnav only; no forbidden top-level nav items or routes.
- Thin `lib/api.ts` + proxy + env support present (Prompt 16: client materialized with role header + object-envelope normalization; pages updated for contract; hash links removed; Admin 403 baseline UI added — see evidence/frontend-production-readiness-implementation/prompt-16-route-api-contract-hardening-closeout.md and 00_PREFLIGHT.md).
- `frontend/README.md` + `.env.example` document run + integration steps.
- Python surface (analytics + tests) untouched; will be re-verified in the prompt run (targeted analytics tests + safe -m subset + ruff + mypy on analytics only) to prove "imports without optional frontend build".
- Architecture cross-refs: Prompt 08, 11_FRONTEND_UI_STRUCTURE, 12_UI_KIT_THEME_AND_COMPONENTS, 17_IMPLEMENTATION_SEQUENCE, 09_FASTAPI_BACKEND_DESIGN, 10_ANALYTICS_READ_MODELS_AND_ENDPOINTS, 16_TESTING_VALIDATION_ACCEPTANCE, navigation_model.json, and prior 17x series (Prompts 05-07).

This completes UI-08 scope per the package manifest and sequence. Fuller panel content, live query integration across pages, and polish are deferred to UI-09+.

## Related
- Planning package: `docs/planning/fastapi-analytics-dashboard-implementation-package/`
- Previous: 173 (keywords), 174 (sync governance), 175 (read models).
- Next in sequence: UI-09 (Today/Projects/My Items screens), UI-10 (Daily Brief external workflow), etc.
