# Repo-Truth Audit

**STAMP:** 20260701T081419Z  
**origin/main:** `8799c0bb` (PR #243 Phase 11 merged)  
**Proof type:** repo truth

## Phase 11 gate

PASS — query-param driver detail route, `driverDetailHref` with `activity_id`, conflict rejection, Phase 11 evidence at `driver-route-encoding-phase11-20260701T075049Z/`.

## PM workflow map

1. Schedule Hub (`/projects/tropical/schedule`) — story, controls, baseline anchors, driver analysis
2. Select comparison basis in Schedule Controls (badges)
3. Baseline Anchors below controls — assign three named slots
4. Open Workbench — named basis = read-only preview
5. Driver detail via `driver-detail?activity_id=...` — movement + impacts
6. Back links preserve `comparison_basis` + `as_of`

**Page order:** `ScheduleControlsPanel` renders **before** `ScheduleBaselineSelector` in [`ProjectSchedulePage.tsx`](frontend/src/pages/ProjectSchedulePage.tsx) L727–740. Pre-fix walkthrough will assess whether this confuses PMs.

## Backend (read-only)

| Area | Behavior |
|------|----------|
| Named comparison | `project_schedule_controls_service.py` resolves named slots via comparison basis resolver |
| Missing baseline | Returns `available: false`, `reason: baseline_not_selected` / `baseline_invalid` with `baseline_context.slot_label` |
| Driver detail | `GET .../schedule/drivers/detail?activity_id=` shared handler; legacy path retained |
| PM copy in payloads | Headlines humanized; `reason` values are snake_case enums |

No backend changes planned unless walkthrough blocks UI.

## Frontend friction (code review hypotheses)

| Surface | Issue | Severity (hypothesis) |
|---------|-------|----------------------|
| Driver detail | H3 = "Driver Detail"; activity name in subtext | P1 |
| Driver detail | Error text mentions `comparison_basis` enum | P1 |
| Driver detail | Logic changes show raw activity IDs | P1 |
| Driver detail | No advisory footer | P2 |
| Controls (available) | No persistent "Comparing against" context | P1 |
| Controls (unavailable) | `reason.replace(/_/g,' ')` for non-missing cases | P1 |
| Baseline selector | Missing copy `No {label} selected.` — weak action | P1 |
| Workbench | Read-only note is small muted text, not banner | P1 |
| Hub focus link | `Open driver {focusDriver}` exposes raw ID | P2 |

## Tests — coverage gaps

- No dedicated `ScheduleBaselineSelector` / `ScheduleControlsPanel` unit tests
- Driver page does not assert activity name as primary heading
- Phase 11 slash ID tests exist in `scheduleBaselineLabels.test.ts` and driver page tests

## Files expected to change

- `frontend/src/lib/scheduleBaselineLabels.ts` (shared helpers only if reused ≥2 surfaces)
- `ScheduleBaselineSelector.tsx`, `ScheduleControlsPanel.tsx`
- `ProjectScheduleWorkbenchPage.tsx`, `ProjectScheduleDriverDetailPage.tsx`
- Possibly `ProjectSchedulePage.tsx` (focus link only — **not** section reorder unless P0/P1 finding)
- Corresponding `*.test.tsx`

## Out of scope

Schema, migrations, parser, CPM, import, trends, V90 sync, disposition persistence, analytics, driver route shape changes.

## Live proof plan

Real local DB tropical walkthrough + Playwright screenshots pre/post-fix. Missing-baseline screenshot via frontend test fixture, not DB mutation.

## Risks

- Section reorder deferred per amendment unless walkthrough proves P0/P1 confusion
- Screenshot sensitivity — redact committed captures
