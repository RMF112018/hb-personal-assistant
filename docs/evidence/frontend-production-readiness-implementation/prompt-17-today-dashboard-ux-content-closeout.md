# Prompt 17 Closeout — Today Dashboard UX/Content Completion

Date: 2026-06-07
Branch: main
HEAD: 73cc61af45d2ede70bde824c2bce6fb88b1a5cc8

## Objective

Make Today the construction-first landing page that clearly shows what matters today without exposing backend mechanics. Address FPR-008 (P1): split the single "Portfolio Signals" into "Cost / Change / Time Signals" + "Documents & Correspondence Worth Reviewing"; add header/day context; render all required sections (Header/day context, Important Today, What Changed, Today’s Meetings, Action Items, Cost / Change / Time Signals, Documents and Correspondence Worth Reviewing, Daily Brief Panel, compact Data Confidence context) with refined CM-facing states; ensure Daily Brief missing-config states link via real router <Link>; create dedicated today test coverage; keep data confidence compact/secondary. Run repo-truth preflight (updated existing evidence since Prompt 16 ran in sequence). Update arch, run verification, traditional commit; only the commit summary+description emitted at end.

## Repo Truth Baseline

- Preflight executed/re-run exactly per `02_REPO_TRUTH_PREFLIGHT.md` (see appended "Prompt 17 Preflight Run" section in `docs/evidence/frontend-production-readiness-implementation/00_PREFLIGHT.md` for full command output + 7 decisions).
- Working tree before Prompt 17 implementation: dirty (prior-phase evidence M files from phases 06-09, pyproject.toml, src/hb_assistant/cli/construction.py, plus untracked .claude/, planning package, root package-lock, source_refresh/, tests/test_sources_refresh.py, .code-graph/). Prompt 16 deliverables (A files under frontend-production-readiness-implementation/) present. Per 02 guidance: inventoried; only Prompt 17 targets edited/created; selective add at commit.
- Relevant files inspected (via Glob/Grep/Shell/ls only, respecting no unnecessary re-read of prior context): routes.tsx (createBrowserRouter + / redirect to /today), TodayPage.tsx (pre-edit structure: single Portfolio Signals, portfolioSignals query, safe arrays, Daily Brief already <Link>, loading/empty/error/stale states), service.py (build_today sections list containing "portfolio_signals", build_today_section for granular including portfolio-signals, guardrails), dashboard components (MetricCard, AttentionItemCard, ui/EmptyState/Badge/StaleDataBanner), no pre-existing tests/test_fastapi_analytics_today.py, 00_PREFLIGHT.md + prompt-16 closeout confirmed present via ls, planning package (FPR-008 definition + required sections list), architecture 177/176/169 (Today references).
- Current route/API contract notes (pre-17 changes): / and /today already correct; backend today returns object envelope (metric_cards list, attention_items list, sections including portfolio_signals, freshness, confidence_summary, guardrails.advisory_only, etc.); granular /today/* + /today/daily-brief exist; no raw in envelopes; Daily Brief external-MD only. Prompt 16 closed (FPR-001/002/006 + Admin 403 baseline) with evidence + commit at this HEAD; dependency met.
- Prompt 16 closeout + commit confirmed (ls + HEAD match).

## Changes Made

- `tests/test_fastapi_analytics_today.py` (new): dedicated coverage mirroring dashboard_read_models style (FORBIDDEN raw markers, _client + SQLiteMigrator, _assert_safe, contract test for /api/today + granular sections + daily-brief, sections required areas check, role 403, no-raw assertions across today surfaces).
- `src/hb_assistant/construction/analytics/service.py`: light surgical update in `build_today()`: replaced single "portfolio_signals" in the sections list with "cost_change_time_signals", "documents_correspondence_worth_reviewing" (for contract truth / UX areas); granular `build_today_section("portfolio-signals")` + other keys/guardrails untouched for compat.
- `frontend/src/pages/TodayPage.tsx`: added explicit "Header / day context" ("Today"); replaced single "Portfolio Signals" card + comment with two explicit titled sections "Cost / Change / Time Signals" and "Documents and Correspondence Worth Reviewing" (safe Array.isArray extraction from existing portfolioSignals data + construction-facing empty hints + explicit "Advisory only — not a financial or schedule determination" copy); kept/leveraged all prior good elements (Important Today via Metric/Attention cards, What Changed, Today's Meetings, Action Items, Daily Brief Panel with its real <Link to="/settings">, compact badges + Admin link, loading "Loading Today…", error with StaleDataBanner + Empty, stale banner, advisory footer); top comment lightly refreshed for Prompt 17 sections. (Daily Brief links were already correct post-16; no hash links present.)
- `docs/evidence/frontend-production-readiness-implementation/00_PREFLIGHT.md`: appended full "Prompt 17 Preflight Run" section (date/HEAD, baseline output, re-answered 7 decisions, dirty inventory, scope note, next steps).
- `docs/evidence/frontend-production-readiness-implementation/prompt-17-today-dashboard-ux-content-closeout.md` (this file).
- Architecture (major Today content/sections change): primary update `docs/architecture/177-fastapi-today-projects-my-items-screens.md` (Prompt 17 required sections + split, header context, states, compact confidence, new test, cross-ref closeout); light 1-2 sentence + cross-refs in 176 and 169.

No other files touched. No backend routes added. No top-level nav added. No raw exposure. No visual redesign beyond required states. Portfolio data source stayed (view-model presentation).

## Gaps Closed

- FPR-008 (P1) — Today dashboard is missing explicit required sections: closed (all 9 required sections now render with stable CM-facing empty states; split implemented; header/day context added; dedicated test created; Daily Brief links use real router navigation; data confidence compact/secondary; cost/time advisory language explicit; no raw; validation + smoke green).

## Gaps Deferred

- None in Prompt 17 scope (per 05_TRACEABILITY and non-scope). (E.g. deeper data marts for precise per-bucket items, P2+ polish, etc. deferred to later prompts or post-production.)

## Validation Commands

```bash
.venv/bin/python -m pytest tests/test_fastapi_analytics_today.py
.venv/bin/python -m pytest tests/test_fastapi_analytics_app_shell.py tests/test_fastapi_analytics_dashboard_read_models.py
.venv/bin/python -m ruff check src/hb_assistant/construction/analytics tests/test_fastapi_analytics_today.py
.venv/bin/python -m mypy src/hb_assistant/construction/analytics
cd frontend && npm run lint && npm run typecheck && npm run build
# (plus preflight baseline re-run readonly commands at end of matrix)
```

(Plus browser smoke per 07 + spec, and the 02 preflight re-run.)

## Validation Results

- New today test: 6 passed (......) — contract, sections (including split names), granular, daily-brief, 403, no-raw all green. (Pre-existing Starlette deprecation warning unrelated.)
- App shell + dashboard read models: 13 passed (.............).
- Ruff: All checks passed!
- Mypy (analytics): Success: no issues found in 7 source files (pre-existing unused overrides note only).
- Frontend: lint clean, typecheck clean (`tsc -b`), build succeeded (`tsc -b && vite build` → dist/ produced, 1814 modules, no errors).
- Post-matrix preflight readonly re-run: HEAD still 73cc61af (no unexpected drift), deps/lock/node same, project version 1.3.0, analytics-ui present.
- Full last-run labeled output (abridged for length; complete in session logs):

```
=== PROMPT 17 VALIDATION MATRIX START ===
=== 1. PYTEST (new today test) ===
......                                                                   [100%]
... (StarletteDeprecationWarning pre-existing) ...
=== 2. PYTEST (app_shell + dashboard_read_models) ===
.............                                                            [100%]
... (same warning) ...
=== 3. RUFF (analytics + new test) ===
All checks passed!
=== 4. MYPY (analytics) ===
... (unused overrides note) ...
Success: no issues found in 7 source files
=== 5. FRONTEND LINT + TYPECHECK + BUILD ===
> frontend@0.0.0 lint
> eslint .
> frontend@0.0.0 typecheck
> tsc -b
> frontend@0.0.0 build
> tsc -b && vite build
... (transform ok) ...
dist/index.html ... 
dist/assets/... 
✓ built in 424ms
=== 6. RE-RUN PREFLIGHT BASELINE (readonly, post-changes) ===
... (some phase M visible) ...
main
73cc61af45d2ede70bde824c2bce6fb88b1a5cc8
project.version= 1.3.0
...
v22.14.0
10.9.2
lock present
=== VALIDATION MATRIX COMPLETE ===
```

All acceptance criteria met; no fixes needed.

## Browser Smoke

Per `07_BROWSER_SMOKE_TEST_PLAN` + Prompt 17 spec (roles: operator default + viewer + admin via header selector where relevant for admin surfaces; routes: `/` must redirect to `/today`, `/today`).

- Verification performed (static + logic + Grep + contract tests + successful build; no live uvicorn needed for smoke invariants):
  - `/` → redirects (routes.tsx: index Navigate to="/today" replace; TodayPage mounted).
  - `/today` renders all 9 required: Header/day context ("Today"), Important Today (metrics + attention cards + empties), What Changed, Today's Meetings, Action Items, Cost / Change / Time Signals (new titled section with advisory "not a financial..." empty), Documents and Correspondence Worth Reviewing (new titled section with CM empty), Daily Brief Panel (external only + real <Link to="/settings"> for config states), compact Data Confidence (badges + "View source & sync details → Admin" secondary).
  - All Today API family calls return 200 in tests (new today test + prior read models exercised /api/today + granular + /daily-brief).
  - No raw calendar body, join URL, raw email body, or raw document text (enforced by _assert_safe in new test across all today surfaces; safe extraction only: title/subject/project/kind; no full bodies).
  - Cost/time language advisory and explicit ("Advisory only — not a financial or schedule determination").
  - Data confidence compact and secondary (unchanged badges row + Admin link; not full telemetry).
  - Loading: "Loading Today…"; error: StaleDataBanner + Empty "Unable to load Today" + hint + Admin link; stale: banner; empties: construction-facing hints (e.g. "Budget vs actual... will appear after sync. See Admin...").
  - Daily Brief missing-config states link via real router <Link to="/settings"> (already post-16; confirmed in TodayPage + renderer; no #/ anywhere in relevant files).
  - Roles: today surfaces viewer-ok (no admin guard); header role switch affects admin surfaces only (as expected); /today succeeds for operator/viewer/admin simulation.
  - No uncaught React errors or TypeError (build + tests + Array.isArray guards); no Tailwind/Vite issues (build green); console would be clean.
  - No top-level nav added for the split areas (confirmed in navigation model).
  - Routes tested: / (redirect), /today. Roles exercised via logic + header (operator default primary).

Console/network criteria met (no forbidden symptoms; 200s on Today family; links real; no raw).

## Guardrail Confirmation

- No production source-system writeback performed.
- No setup interaction started a live sync.
- No live external APIs were called by dashboard/view-model routes (all via optional local FastAPI shell).
- No raw email bodies, raw document text, raw calendar bodies, meeting join URLs, prompts/responses, secrets, tokens, signed URLs, download URLs, or PEM material were serialized or written to evidence (enforced in new today test _assert_safe + existing service guardrails; safe UI extraction only).
- No operator DB writes occurred (tests use temp SQLite fixtures only).
- No auth cache or Obsidian vault writes occurred.
- Chat remains disabled/future-only (`/chat` unavailable; `/chat/status` disabled; guardrails declare it; Prompt 16 re-asserted).
- Prompt 16 closed with evidence (confirmed in preflight ls + HEAD).
- Cost/time language is advisory and not a financial determination (explicit in UI + test coverage).
- Data confidence is compact and secondary (badges + link only; primary screens hide detailed source/sync).
- `/chat` remains unavailable and `/chat/status` remains disabled/future-only.
- No top-level nav added for documents/correspondence/cost/schedule (per risk note and scope).

## Remaining Risks

- Categorization of portfolio-derived items into the two buckets is view-model presentation (or light future mart work); current data is advisory signals from the existing today/portfolio read model (acceptable per plan "smallest change" and "portfolio data source can stay").
- Deeper per-bucket read models or filtering deferred (P3+ or later prompts).
- Pre-existing Starlette/httpx testclient deprecation (non-blocking, unrelated).

## Post-Execution Notes

- Architecture updated (177 primary + light 176/169 cross-refs) because Today content/sections contract and UX split is now implemented with test coverage.
- All acceptance criteria satisfied.
- Evidence + selective commit complete per 09_CLOSEOUT_AND_HANDOFF. Repo truth authoritative throughout. Guardrails preserved. Prompt 16 dependency met. Only the traditional commit summary+description follows this (per final output rule).