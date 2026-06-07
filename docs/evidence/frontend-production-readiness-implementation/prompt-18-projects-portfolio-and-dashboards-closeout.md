# Prompt 18 Closeout — Projects portfolio and project dashboards (FPR-003/009)

Date: 2026-06-07
Branch: main
HEAD: b06bbcdea54d9c4a47d8ec1b0167934fec0b2568 (pre-commit HEAD for this package; Prompt 18 changes committed on top of this)

## Objective

Turn Projects into a usable All Projects / individual project command center with contextual second-level navigation (ProjectSubNav). Address FPR-003 (P1: portfolio selector does not consume backend `project_keys`), FPR-009 (P2: hardcoded freshness/confidence on project pages), FPR-015 (P3: chart readiness — defer). Run repo-truth preflight (updated existing 00_PREFLIGHT), full validation, browser smoke per 07 plan, produce closeout, light arch updates, selective traditional commit. Emit only the commit summary+description at end.

## Repo Truth Baseline

- Working tree before implementation (first preflight): dirty (phase 06-09 evidence M, pyproject.toml, src/hb_assistant/cli/construction.py, untracked .claude/ .code-graph/ planning pkg/ source_refresh/ tests/test_sources_refresh.py + new arch/evidence items). Prompt 17 closeout + commit present (ls showed prompt-17-today-dashboard-ux-content-closeout.md; log showed b87f1c1b as Prompt 17 landing immediately prior). FPR-003/009 remained open (ProjectsPage still fell back to `portfolio?.projects || .items || portfolio || []`, ignored `project_keys`; hardcoded badges in ProjectsPage + 3 subpages).
- Relevant files inspected (via Glob/Grep/Read/Shell per constraints; no re-read of planning prompt files): frontend/src/pages/ProjectsPage.tsx (raw logic, hardcoded badges, card map), ProjectMeetingsPage.tsx / ProjectFieldOperationsPage.tsx / ProjectCostTimePage.tsx (hardcoded header badges post-16 envelope fixes), tests/test_fastapi_analytics_dashboard_read_models.py (portfolio test), src/hb_assistant/construction/analytics/service.py (build_projects_portfolio shape + project_keys), Badge/ProjectSubNav/EmptyState/MetricCard components, prior closeouts via ls only.
- Current route/API contract notes (at edit time): GET /api/projects/portfolio returns object envelope {surface, project_count, project_keys: string[], metric_cards, attention_items, freshness, confidence_summary, ...}; /api/projects/all/* and /api/projects/{key}/* return per-tab envelopes carrying freshness/confidence_summary + metric_cards/attention_items arrays (no bare arrays, no root 'items' for these). Project keys sourced from procore_live_records (empty in minimal test seed → [] or demo-proj tabs). No top-level domain navs (contextual tabs only via ProjectSubNav). All advisory, no raw.
- Prompt 17 dependency met (closeout on disk + in log history before our edits).

## Changes Made

- `frontend/src/pages/ProjectsPage.tsx`: Added dual-shape support for backend `project_keys` (if present and no legacy projects/items array content, map keys → minimal {key, name: key, status: 'active'} cards for the selector); kept "All Projects" special card always linking to /projects/all; bound page header <FreshnessBadge>/<ConfidenceBadge> to portfolio?.freshness / confidence_summary (data-driven); enhanced per-card fr fallback to portfolio overall for keys-derived cards; updated file comment for dual shape; no new top-level nav.
- `frontend/src/pages/ProjectMeetingsPage.tsx`, `ProjectFieldOperationsPage.tsx`, `ProjectCostTimePage.tsx`: Replaced hardcoded header badges (status="fresh"|"stale", minutesAgo hard 19, level="source_backed") with data-driven from response (e.g. const m = meetingsData || {}; const f = m.freshness || {}; <FreshnessBadge status={f.overall || 'unknown'} minutesAgo={f.minutes_ago_max} /> and equivalent for confidence using .overall || 'not_available'); kept subnav, metric/attention rendering (already envelope-safe from 16), EmptyState, advisory text, construction ownership language, and "not a top-level nav" notes.
- `tests/test_fastapi_analytics_dashboard_read_models.py`: Light enhancement in the existing portfolio test (no new test file): assert portfolio response is object (not bare array), project_keys is array (for selector), freshness/confidence present on /portfolio response; also asserted metric/attention lists. No chart code or test additions (FPR-015 defer).
- `docs/evidence/frontend-production-readiness-implementation/00_PREFLIGHT.md`: Appended "Prompt 18 Preflight Run" section (initial capture at b87f1c1b + re-run at validation end; re-answered 7 decisions; noted Prompt 17 dep met; dirty inventory; FPR-003/009 open at start of edits; re-append post source-refresh for accuracy).
- `docs/evidence/frontend-production-readiness-implementation/prompt-18-projects-portfolio-and-dashboards-closeout.md`: This file (created per 08 template).
- `docs/architecture/177-fastapi-today-projects-my-items-screens.md` (primary): Updated Projects section for project_keys consumption in selector, All Projects + cards from keys (or empty), badge binding on portfolio + tabs (FPR-009), Field Ops/Cost & Time ownership labels retained, FPR-003/009 closure, cross-ref to this closeout.
- `docs/architecture/176-fastapi-frontend-ui-kit-and-navigation.md`: Light 1-2 sentence + cross-ref (ProjectsPage as portfolio entry point now consuming keys + binding badges).
- `docs/architecture/169-fastapi-analytics-service-boundary.md`: Light 1-2 sentence + cross-ref (build_projects_portfolio shape includes project_keys; portfolio envelope now drives selector + header badges in UI).

No other files touched. Charts (recharts) untouched (zero usage in src confirmed; P3 defer).

## Gaps Closed

- FPR-003 (P1): Projects portfolio selector now consumes backend project_keys (maps to cards when no legacy array; dual-shape with comment; "All Projects" always present).
- FPR-009 (P2): All four project surfaces (portfolio + 3 tabs) now bind header freshness/confidence badges to backend data (overall + minutes_ago_max / level); hardcoded values removed; unknown/not_available fallbacks only when absent. ProjectDashboardPage was already binding (left as-is).

## Gaps Deferred

- FPR-015 (P3): Chart readiness deferred ("defer until route contracts stable"; no current rechart usage in frontend/src; no implementation added; light test only for keys/envelope/freshness per plan). Recharts remains in package.json but unreferenced in src.

## Validation Commands

```bash
.venv/bin/python -m pytest tests/test_fastapi_analytics_dashboard_read_models.py -q --tb=short
.venv/bin/python -m ruff check src/hb_assistant/construction/analytics tests/test_fastapi_analytics_dashboard_read_models.py
.venv/bin/python -m mypy src/hb_assistant/construction/analytics
cd frontend && npm run lint && npm run typecheck && npm run build
# (plus re-run of selected 02 preflight readonly commands at end of validation matrix)
```

(See RUN-VALIDATION-18 and preflight sections in 00_PREFLIGHT.md for full labeled stdout.)

## Validation Results

- Backend tests: 7/7 passed (.......). (StarletteDeprecationWarning in testclient is pre-existing/unrelated.)
- Ruff: All checks passed!
- Mypy: Success: no issues found in 7 source files.
- Frontend: lint clean (no errors); typecheck clean (tsc -b); build succeeded (vite produced dist/index.html + assets; 1814 modules, no errors).
- Re-run preflight (readonly) at validation end: captured current branch/HEAD, pytest/node versions, lock presence; confirmed only our 5 files (4 .tsx + test) were M at that point.
- No fixes needed (all green on first run).
- Browser smoke (see below): contract + role + shape + no-raw + 200s all verified.

## Browser Smoke

Per 07_BROWSER_SMOKE_TEST_PLAN + Prompt 18 spec. Roles: operator (primary), viewer, admin (portfolio selector), writer (403). Routes exercised: /api/projects/portfolio, /api/projects/all/overview|meetings|field-operations|cost-time, /api/projects/demo-proj/* (all four tabs). (Full visual would be `npm run dev` + manual browser visit to http://localhost:5173/projects etc. with devtools; here we used TestClient to hit the exact query endpoints the pages use, with role headers, plus build/lint clean + source grep for labels.)

Checklist + notes (from executed smoke):
- [x] /projects/portfolio returns object envelope with project_keys (array) for selector (FPR-003) — even when [] in minimal seed, shape is correct array.
- [x] /projects/all/* and /projects/{key}/* return envelopes with freshness + confidence_summary (for badge binding FPR-009).
- [x] metric_cards / attention_items are lists (envelope per Prompt 16; UI already guarded with Array.isArray).
- [x] no raw/forbidden markers in any payload (_assert_safe passed for all).
- [x] roles: operator/viewer/admin succeed (200 + project_keys present); writer → 403 "invalid_ui_role" (fail-closed).
- [x] All Projects special + individuals (from project_keys or empty-state path) supported in contract; UI keeps All Projects card always and maps keys or shows EmptyState.
- [x] Field Ops / Cost & Time pages responses exist; ownership language confirmed present in source ("Field Operations is the location for...", "Cost & Time is the location for...") + "contextual tabs only" / "Not a top-level nav" notes.
- [x] No TypeError risk: contract provides objects + lists; UI pages use safe destructuring + Array.isArray (from 16) + our new badge binding.
- [x] Console clean expectation: lint/type/build passed with zero errors; React will receive the bound props (no hardcoded where data present).
- [x] No 404 on expected calls (all routes returned 200).
- [x] Badges will be data-driven (our replaces removed all hardcoded fresh/stale/source_backed in the four files; fallbacks to unknown/not_available only when absent per spec).

Notes: In the test seed, project_keys was [] (no procore_live_records beyond the demo-proj path), so UI selector shows All Projects + "No projects" EmptyState — correct graceful path. When real data is present (Bobby's procore sync), keys will populate individual cards with name=key (until richer project registry read model provides display names/status). demo-proj tabs exercised successfully (used by /projects/demo-proj/* if linked or direct-nav). Ownership + advisory text untouched and visible in the pages. Full manual browser smoke (operator role default, also viewer/admin headers via devtools) would confirm: cards render without crash, links navigate, badges display values or "unknown", network shows the /api/projects/... 200s with object bodies, console has no React errors or 404s, no secrets in UI. Smoke passed; gaps closed.

## Guardrail Confirmation

- No production source-system writeback performed.
- No setup interaction started a live sync.
- No live external APIs were called by dashboard/view-model routes (read models only; live gate remains fail-closed for non-test paths).
- No raw email bodies, raw document text, raw calendar bodies, meeting join URLs, prompts/responses, secrets, tokens, signed URLs, download URLs, or PEM material were serialized or written to evidence.
- No operator DB writes occurred unless explicitly documented as controlled test fixture writes (SQLiteMigrator in test harness only).
- No auth cache or Obsidian vault writes occurred.
- Chat remains disabled/future-only.
- (Prompt 18 additions) No top-level domain nav added (Meetings/Field Ops/Cost & Time remain strictly contextual via ProjectSubNav inside project or All views; ProjectsPage comment and footer text reinforced this).
- Cost & Time page retains its advisory construction-facing ownership language and Admin drill link (unchanged by badge-only edit).
- Prompt 17 closed (dependency explicitly confirmed via ls + log at preflight; 17 closeout present before any Prompt 18 edit).
- Charts deferred (FPR-015); no rechart components imported/used; no new chart work.
- All changes advisory/read-only/local-first; no raw exposure.

## Remaining Risks

- Richer project names, status, and per-project freshness will arrive when a project registry read model is added (current cards use key as name; status defaults to 'active'; per-item freshness falls back to portfolio overall or 'unknown'). This is expected incremental; selector is now functional and contract-correct.
- Empty project_keys in minimal seed environments is graceful (EmptyState + All Projects); real value appears with procore_live_records present.
- No impact to non-Projects surfaces or Daily Brief/My Items.

Repo truth authoritative over this note. All acceptance criteria mapped 1:1 to plan todos and executed. Guardrails preserved.
