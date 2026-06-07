# FastAPI Today, Projects, My Items Screens (Prompt 09 / UI-09)

## Objective and Scope
Implement the primary user-facing screens that make the app feel like a low-friction time-management and construction-intelligence platform on top of the Prompt 08 Vite/React/TypeScript/Tailwind/shadcn-style shell.

- `/today` (primary landing after `/` redirect) with the 6 required sections.
- `/projects` as Portfolio + project selector (All Projects + individual projects); `/projects/all` aggregated + per-project overviews and the 3 contextual tabs; identical tab routes for `/all/*`.
- Project overview surfaces use the exact 8 assistant-like sections.
- Project secondary tabs enforce the specified ownership.
- `/my-items` as a user-specific filtered work queue (5 sections), explicitly not a replacement email client, calendar, or file browser.
- All surfaces: compact freshness/confidence badges, construction-facing/business-language actions (no dry-run/apply/execute terminology), advisory notes, link detailed source/sync/evidence/retrieval diagnostics to Admin / Data Confidence, no chat activation.

This change is purely additive client-side. The Prompt 07 read-model endpoints (`/api/today*`, `/api/projects/portfolio`, `/api/projects/all/*`, `/api/projects/{project_key}/*`, `/api/my-items*`) and the FastAPI analytics shell are unchanged and provide the composed, advisory envelopes. The Python package, store, migrations, CLI, and automation are untouched.

Daily Brief remains external-MD only: the app detects, validates freshness, and presents/polishes a polished executive brief. It does not generate or materially rewrite content (presenter/formatter posture, repeated across 08_, 09_, 11_, 13_, backend design, and 176).

## Today (`/today`)
Primary landing page (root `/` redirects to `/today` per navigation contract and 11_).

Required sections (Prompt 09 + 11_ + navigation_model.json):
- Important Today (high-priority attention items across active/followed projects; aging decisions; cost/change exposure; schedule/procurement; field/closeout/billing; review-required operational items).
- Daily Brief (optional executive-style rendered from externally generated Markdown file; 7 states: Not configured, External AI setup required, Configured/waiting for next run, Brief available, Brief stale, Brief generation failed, Markdown parse warning; app presents/polishes only).
- Today's Meetings (meeting list, prep readiness, related emails/files/Procore context, source/context freshness badge, one-click drill to prep).
- What Changed (new/changed Procore records, document/file changes, correspondence highlights, meeting context changes, cost/change/schedule/field signals since last review window).
- Action Items (open user-facing items, aging, review-required, locally reviewed/unreviewed state, items assigned or relevant to the current user).
- Cost / Change / Time Signals (Prompt 17 split; budget vs actual, change exposure, schedule/procurement, closeout/billing — advisory only, not determinations).
- Documents and Correspondence Worth Reviewing (Prompt 17 split; documents changed/requiring review, correspondence worth attention, project-matched).
- Header/day context + compact Data Confidence badges/links (secondary; detailed source/sync/evidence hidden on primary Today; link to /admin). (Prompt 17 / FPR-008)

Implementation notes (frontend):
- Uses TanStack Query over the today family (`/api/today`, `/today/important|changes|meetings|action-items|portfolio-signals`, `/today/daily-brief`).
- Daily Brief section wires the enhanced `DailyBriefRenderer` (safe external-MD only) with status, content, path, generated time, and warnings; strong advisory text repeated in UI and component.
- Business language, low-friction links (e.g. "Review in Projects", "Open My Items"), compact badges at page + card level, link to `/admin` for diagnostics.
- Graceful empty/stale via `EmptyState` / `StaleDataBanner`.

## Projects (`/projects`)
Portfolio dashboard and project selection entry point (11_, Prompt 09, navigation_model.json).

Project selector must include:
- All Projects (special aggregated entry, routes to `/projects/all`).
- Individual active/followed projects (cards/links with key/name/status/freshness, route to `/projects/:projectKey`).

Routes implemented (exact from Prompt 09 + 11_):
- `/projects` → Portfolio + selector.
- `/projects/all` (aggregated All Projects overview) + `/projects/all/meetings|field-operations|cost-time`.
- `/projects/:projectKey` (individual overview) + `/projects/:projectKey/meetings|field-operations|cost-time`.

Project Overview sections (assistant-like, exactly 8; used for both All and per-key):
- Important Today
- What Changed
- Action Items
- Meetings Needing Prep
- Cost & Time Signals
- Field Operations Signals
- Documents / Correspondence Highlights
- Startup / Closeout / Billing Attention (where applicable)

Compact confidence/freshness badges on the overview surface.

Project-Level Secondary Navigation / Tabs (only these; contextual only):
1. Overview (the 8 sections above).
2. Meetings — uses calendar, Outlook, meeting action items, related files, related Procore context, and Daily Brief/meeting-prep context.
3. Field Operations — **must be the location for** startup, closeout, daily log, observations, punch-list, inspections, quality/safety, and superintendent-facing data.
4. Cost & Time — **must be the location for** cost/change, billing/cash/retention, schedule, procurement, and cost/time-impacting RFI/submittal/design-decision signals.

Documents, correspondence, vendors, closeout, billing, schedule, procurement, RFIs, submittals, and design decisions are not standalone top-level nav items; they appear inside these project dashboards and drilldowns.

Implementation: `ProjectsPage` drives the selector from `/api/projects/portfolio` (All special card + individuals with badges); `ProjectDashboardPage` renders the 8 sections for All and keyed (data from `/api/projects/all/overview` or per-key); the three tab pages (`Project*Page.tsx`) are wired to the tab-specific read models (`/all/*` and `/:key/*`) and contain explicit ownership language + content areas.

Prompt 18 (FPR-003/009): `ProjectsPage` now supports backend `project_keys` list (when present and no legacy projects/items array, maps keys to minimal {key, name: key} cards for the selector; "All Projects" card always present). Page header badges and the three tab page headers are bound to the envelope's `freshness` (overall + minutes_ago_max) and `confidence_summary` (overall) instead of hardcoded values. Field Operations and Cost & Time pages retain their construction-facing ownership language ("is the location for...") and advisory notes. No top-level domain nav added (contextual tabs only). FPR-015 (charts) deferred. See prompt-18-projects-portfolio-and-dashboards-closeout.md (and 00_PREFLIGHT.md update) + cross-refs in 176/169.

## My Items (`/my-items`)
User-specific dashboard / filtered work queue (Prompt 09 + 11_).

Sections (exactly 5):
- My Action Items (open, aging, review-required; locally reviewed/unreviewed state).
- My Meetings (today/upcoming; prep status; related files/emails/Procore context).
- My Correspondence (emails worth reviewing; stale threads; waiting-on/reply-needed candidates; project-matched and unclassified).
- My Files (OneDrive; recently changed; files needing classification/review; files tied to meetings/projects).
- My Followed Projects (pinned/followed project summaries; attention items from followed projects).

Explicit rule: "My Items should be a filtered work queue, not a replacement email client, calendar, or file browser."

Implementation: wired exclusively to the aggregate `/api/my-items` (Prompt 16 contract; backend implements no section subroutes — confirmed in app_shell OpenAPI tests and page/api client comments). Uses `MyActionItemCard` and simple lists derived from the envelope's explicit per-section arrays (my_action_items, my_meetings, ...) or attention_items with kinds (Prompt 19); badges + advisory to use Admin for full source evidence. Prompt 19: richer categorized attention (varied kinds) + explicit per-section arrays in the aggregate envelope; 5 distinct sections with CM-facing EmptyState hints (connections + "first sync approved (Admin)"); light TS interfaces on the page for the my-items surface; FPR-002 (subroute 404s) documented closed in Prompt 16 with 19 delivering UX/contract polish within the aggregate. See prompt-19-my-items-dashboard-closeout.md (and 00_PREFLIGHT.md update) + cross-refs in 176/169.

## Data Mapping to Prompt 07 Read Models
All screens are thin presenters over the existing Prompt 07 / 10_ read-model endpoints (no new backend, no duplication of logic). Freshness and confidence summaries are surfaced as compact badges on every surface (page, cards, selector, tabs). Advisory language and "hide detailed diagnostics from primary; link to /admin" are consistent.

- Today: `/api/today` (+ `/today/important|changes|meetings|action-items|portfolio-signals`) and `/api/today/daily-brief` (special external-MD status + content).
- Projects Portfolio / selector: `/api/projects/portfolio`.
- All Projects + tabs: `/api/projects/all/overview|meetings|field-operations|cost-time`.
- Per-project + tabs: `/api/projects/{project_key}/overview|meetings|field-operations|cost-time`.
- My Items: `/api/my-items` only (aggregate envelope with sections + explicit per-section arrays + attention_items; no subroutes per Prompt 16 contract and app_shell assertions). Prompt 19 enriched the envelope data and UX (see 177 My Items section + prompt-19 closeout).
- Admin (linked from all primary surfaces): the admin health family (source-sync, workflow-job incl. Daily Brief receipts, evidence-guardrails, retrieval-ai-quality, permissions-governance, data-completeness).

Daily Brief dedicated management (status, latest, configure, setup instructions, validate folder, detect) lives behind the `/api/daily-brief/*` family (backend) and is consumed by Today + Settings; frontend only renders.

## Component Inventory (UI-09 additions on the Prompt 08 shell)
- Pages: TodayPage, ProjectsPage, ProjectDashboardPage, ProjectMeetingsPage, ProjectFieldOperationsPage, ProjectCostTimePage, MyItemsPage (all nine shell pages now have real section content and live queries).
- Layouts/Navigation: AppShell, MainNavigation, SupportNavigation, PageHeader, ProjectSubNav (contextual tabs only), navigationModel (unchanged contract).
- Components (enhanced or newly exercised):
  - `daily-brief/DailyBriefRenderer` (enhanced for 7 states, path, generatedAt, warnings, stronger "present/polish only" advisory).
  - `dashboard/MetricCard`, `AttentionItemCard` (used in Today and overviews).
  - `my-items/MyActionItemCard` (wired in My Items).
  - `ui/Badge` (FreshnessBadge + ConfidenceBadge, compact variants everywhere).
  - `ui/EmptyState`, `ui/StaleDataBanner` (graceful degradation across surfaces).
- `lib/api.ts` extended with the full today-family, projects tabs, and my-items subs (thin fetchers; `VITE_API_BASE` or `/api` proxy unchanged). Prompt 16: api.ts materialized as the canonical adapter (role header + envelope normalization docs); project tabs + My Items now consume object envelopes via aggregate only; see Prompt 16 closeout. Prompt 17: TodayPage updated for required sections + split (Cost/Change/Time + Documents/Correspondence), header/day context, CM-facing states/empties, compact confidence; new dedicated test; backend today sections list lightly aligned for contract; see Prompt 17 closeout.
- Providers: Theme (dark primary + system) + QueryClient remain the data backbone.

No new top-level routes or nav items. No `/chat` route, page, widget, or nav item.

## UX and Guardrails (Preserved and Reinforced)
- Primary theme dark with dark/light/system support (persisted, OS-respecting).
- Construction-facing labels and business-language actions (Refresh, Review, Prepare, Open, Mark Reviewed, etc.). No dry-run/apply/execute terminology in primary screens.
- Compact freshness/confidence badges on every primary surface and card; link to Admin / Data Confidence for detailed source/sync/evidence/retrieval diagnostics.
- Admin / Data Confidence is strictly secondary/support (not on primary nav for operator workflows). 6 categories implemented in service (build_admin_source_sync_health, workflow_job_health, evidence_guardrails, retrieval_ai_quality, permissions_governance, data_completeness) producing advisory metric cards + exact category advisory_notes. Role-denied state rendered clearly (Prompt 16 baseline: isRoleDenied + exact "Admin role required..." + selector guidance; confirmed in Prompt 21 via targeted grep + TestClient smoke). Local role selector is dev-only simulation; backend require_admin_role fail-closed. FPR-007 closed/documented (see prompt-21-admin-data-confidence-polish-closeout.md).
- Advisory-only posture repeated in footers, section notes, Daily Brief renderer, and empty states ("Advisory signal only. No legal, financial, schedule, safety or entitlement determinations.").
- Daily Brief: "Source: externally generated Markdown file. The app presents/polishes only and does not generate or materially rewrite content."
- My Items explicitly labeled as filtered work queue, not full clients.
- All domain detail (Meetings, Field Ops, Cost & Time, Documents, Correspondence, etc.) remains contextual inside Today/Projects/My Items via tabs or sections.
- Chat remains disabled (no nav item, no route, status-only if reserved).

## Dev / Prod Notes
- `frontend/` is a peer to `src/`; Python package data does not include it.
- Dev: Vite proxies `/api` to local FastAPI (default 127.0.0.1:8000) or honors `VITE_API_BASE`. Run backend with the `analytics-ui` extra.
- Build: `npm run build` (tsc -b && vite build). The screens are thin consumers; the intelligence and guardrails (no raw, read-only, advisory) live in the backend read models.
- Verification (this run): Python FastAPI analytics imports cleanly with no frontend present; targeted analytics tests + safe `-m` subset (tolerating only known unrelated Phase 09); ruff + mypy on the analytics surface only; frontend npm (legacy peer for env), lint (with disables for advisory `any` in thin client code and pre-existing rules), typecheck (clean after React import cleanup for modern JSX + noUnused), build (tsc clean; bundler note in some envs), manual smoke of routes, badges, Daily Brief states, selector, 8 sections, tab ownership, and "filtered queue" posture.

## Validation Evidence (this run)
- Requirements traced directly (via search-only grounding) to Prompt_09_TODAY_VIEW.md, 11_FRONTEND_UI_STRUCTURE.md, 10_ANALYTICS_READ_MODELS_AND_ENDPOINTS.md, 08_DAILY_BRIEF_EXTERNAL_AGENT_WORKFLOW.md, 17_IMPLEMENTATION_SEQUENCE.md, navigation_model.json, 09_FASTAPI_BACKEND_DESIGN.md, 12_UI_KIT..., and metrics catalog evidence.
- Current frontend shell (post Prompt 08) confirmed via Glob/Grep on `frontend/src` (full routes, AppShell+navs+subnav, badges, providers with QueryClient, api stubs, DailyBriefRenderer defined but unintegrated, pages as mocks/skeletons, no top-level domain navs, Chat disabled in model).
- All new code uses the exact endpoint families from 10_/09_; Daily Brief renderer and UI text repeat the external-only + 7 states + "presents/polishes only" contract.
- Tab ownership language ("must be the location for...") is present in the Field Operations and Cost & Time pages.
- My Items explicitly documents the filtered-work-queue rule and does not replicate full clients.
- No Python changes; git delta limited to `frontend/` + this 177 doc.
- Architecture cross-refs: Prompt 09, 11_, 10_, 08_, 17_, 176 (UI kit), navigation_model.json, prior 17x series.

This completes UI-09 scope per the package manifest and sequence. Fuller polish, additional charts, or settings flows are for later prompts.

## Related
- Planning package: `docs/planning/fastapi-analytics-dashboard-implementation-package/`
- Previous: 176 (frontend UI kit and navigation), 175 (read models), 174/173 (governance/keywords).
- Next in sequence: UI-10 (Daily Brief external workflow details), UI-11+, etc.

Prompt 20 (FPR-004/005/010/016/017): Settings guided CM-first sections (no raw/alert/"stub" panels); Daily Brief state precedence fixed with helper + test coverage; real local prefs JSON persist (Application Support, schema + safe); keyword management UI (per-project + explain over existing safe backend). Preview/save only. See prompt-20 closeout + 00_PREFLIGHT + cross-refs in 176/169. (Light addition to primary 177 per plan.)
See Prompt 25 runbook (docs/runbooks/frontend-local-analytics-smoke.md) and INDEX for the packaged local smoke (FPR-018 final) and final evidence summary. Cite prompt-25-documentation-runbook-packaging-closeout.md.
