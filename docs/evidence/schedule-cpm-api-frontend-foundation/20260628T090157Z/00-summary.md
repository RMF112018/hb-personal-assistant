# Schedule CPM API / Frontend Surfacing Foundation — Phase 8

Generated: 20260628T090157Z (UTC)
Branch: feat/schedule-cpm-api-frontend-foundation
Base commit: a7930b2d (Phase 7 `feat/schedule-cpm-dcma-critical-path-integration`, committed + pushed, NOT on origin/main → branched from the Phase 7 commit; stacked P1→…→8)
Schema: v89 → **v89 (NO migration)**; table_count unchanged at **477**

## Implemented (read-only surfacing)
- `construction/analytics/schedule_cpm_read_service.py` (new) — read-only `ScheduleCpmReadService` assembling run-chain summary, computed activities (app-owned whitelist), longest path, diagnostics, and the Phase 7 DCMA eligibility evidence. No computation, no writes.
- `construction/analytics/api.py` — 4 read-only GET endpoints + `_schedule_cpm_read_service()` factory (viewer-ok): `/cpm/summary`, `/cpm/activities`, `/cpm/longest-path`, `/cpm/diagnostics` under `/api/schedules/versions/{schedule_version_key}`.
- Frontend: `frontend/src/lib/api.ts` (4 typed client fns + types), `frontend/src/pages/ScheduleCpmPage.tsx` (new "Computed CPM" tab), route in `app/routes.tsx`, nav entry in `components/schedule/SchedulePageChrome.tsx`. Reuses existing chrome/pickers/primitives and the SAME project/version query-param semantics.
- Tests: `tests/test_schedule_cpm_api.py` (10) + `frontend/src/pages/ScheduleCpmPage.test.tsx` (7).

## Result
- Endpoints return `available: false` (200, not 500) for missing CPM; full chain → run-chain + DCMA basis `application_computed_cpm` + dependency run ids; activities use latest criticality→float→backward→forward run and exclude source fields; longest-path returns ordered membership; reads never create/mutate CPM runs (proven).
- Frontend "Computed CPM" tab: run-chain card, DCMA evidence card (computed vs source-export distinction), Longest Path panel (labelled "Longest Path", not "Critical Path"), computed activity table, source-export-separation note, empty/error states; project/version selection matches the rest of the schedule module.

## Explicitly NOT implemented
No new CPM algorithms; no recomputation in read paths; no writes to CPM tables; no automatic "run full CPM" from frontend/quality; no schema migration; no source-field reinterpretation; source-export/proxy evidence stays on Schedule Health (separate, unchanged); no PM-facing storytelling/narrative/root-cause; no DCMA certification claim. Root CLAUDE.md "no frontend" line is stale but left unchanged (out of scope).
