# Repo-truth audit (verified against the committed Phase 7 worktree)

## Backend API
FastAPI app `construction/analytics/api.py::create_app(*, db_path)`; inline `@app.get`/`@app.post` routes; `app.state.db_path`; service factories (`_schedule_db_path()`, `_schedule_quality_service()`); role dep `X-HB-UI-Role`; GET routes `del role` (viewer-ok), POST gated by `require_operator_role`; schedule routes at `/api/schedules/versions/{schedule_version_key}/...`; plain-dict responses; 404 via HTTPException for unknown version (`_enforce_version_project_scope`).

## Frontend (exists — root CLAUDE.md "no frontend" is stale)
React 19 + TS + Vite at `frontend/`. Pages `frontend/src/pages/Schedule*.tsx`; chrome/nav `components/schedule/SchedulePageChrome.tsx` (NAV array; re-exports ScheduleShell/Table/Th/Td/Panel from forecast primitives); routes `app/routes.tsx`; API client `lib/api.ts` (`fetchJson<T>`, role header injected, `api` object); UI `components/ui/{Badge,EmptyState}.tsx`; project/version via `useScheduleProjectParam` + `?project=&version=` query params + `ScheduleProjectPicker`/`ScheduleVersionPicker`. Tests vitest + RTL (mock `../lib/api`, QueryClient+memory router). Commands: `npm run typecheck` (tsc -b), `npm run lint`, `npm run test` (vitest).

## CPM dependency fields used (read-only, app-owned)
runs (calculation_type/cpm_recalculation_status/source_run_id/created_at/counts), activity_results (computed early/late/float/criticality + membership), paths + path_activities, diagnostics. Phase 7 `evaluate_dcma_critical_path(svk)` for DCMA evidence.

## Source fields AVOIDED
The computed activity view uses an explicit app-owned whitelist; source critical/driving-path/float/is_critical/imported early-late are not in these tables and are never surfaced. Source-export evidence stays on the Schedule Health page, separate and unchanged.

## Tests added
tests/test_schedule_cpm_api.py (backend), frontend/src/pages/ScheduleCpmPage.test.tsx.
