# Phase 8 Repo-Truth Audit — Named Baseline Workbench Parity

**Audit date:** 2026-06-30  
**Base commit (origin/main):** `e2acc41d07ddba52773c6a96890e3c89a653b00d`  
**Worktree branch:** `feature/schedule-named-baseline-workbench-phase8-20260630T233345Z`  
**Schema version:** 96 (no migration required for Phase 8)

## Phase 7 prerequisite: PRESENT

| Artifact | Location |
|---|---|
| `GET/PUT /schedule/baselines` | `api.py` |
| `project_schedule_named_baseline_slots` (v96) | `project_schedule_named_baseline_tables.py` |
| `ProjectScheduleNamedBaselineService` | `project_schedule_named_baseline_service.py` |
| Vocabulary + named controls basis | `project_schedule_baseline_vocabulary.py` |
| `build_schedule_hub_context_with_named_baseline` | `project_schedule_summary_service.py` |
| Controls omit named workbench links | `project_schedule_controls_service.py` (`include_workbench_links=False` for named) |
| `controlsComparisonBasis` vs `workbenchComparisonBasis` | `ProjectSchedulePage.tsx` |

## Current comparison_basis vocabulary by route (pre-Phase 8)

| Route | Accepted today | Unknown handling |
|---|---|---|
| `GET /schedule/controls` | `prior_update`, named slots, legacy `baseline` (BC) | Coerced to `prior_update` via `normalize_controls_comparison_basis` only for unknown — **Phase 8 amendment: workbench routes must reject unknown** |
| `GET /schedule/review-items` | `prior_update`, `baseline` | Coerced to `prior_update` |
| `POST /schedule/review-items` | `prior_update`, `baseline` | Coerced to `prior_update`; only `prior_update` syncs queue |
| `GET /schedule/drivers/{id}/detail` | `prior_update`, `baseline` | Coerced to `prior_update` |
| Workbench page UI | `prior_update`, `baseline` | N/A |
| Driver detail page | `basis=prior_update\|baseline` | N/A |

## Legacy V90 vs named slot boundaries

See [`legacy-vs-named-baseline-boundary.md`](legacy-vs-named-baseline-boundary.md).

- **legacy_v90:** `project_schedule_baseline_selections`, `/schedule/baseline`, `ProjectScheduleSelectedBaselineService`, workbench `comparison_basis=baseline`
- **named_slot:** v96 `project_schedule_named_baseline_slots`, `/schedule/baselines`, `ProjectScheduleNamedBaselineService`
- **No cross-read:** named resolution must not read V90; legacy baseline must not read named slots

## Review Workbench persistence model

- `sync_and_list`: `sync_queue` only when `basis == "prior_update"`
- Generic `baseline` workbench: live preview (`use_persisted=False`, `synced=False`)
- Named baseline Phase 8: same read-only/live-preview rules; POST named → `400 named_baseline_sync_not_supported`

## Schema migration

**Not required.** Phase 8 is read-path parity only.

## Implementation plan

1. Add `project_schedule_comparison_basis_resolver.py` with `source_model` boundaries
2. Reject unknown `comparison_basis` with `invalid_comparison_basis` (no coercion)
3. Wire resolver into `build_review_items`, `build_driver_detail`, API routes
4. Extend `build_preview` with `response_comparison_basis` for named outward identity
5. Reinstate controls links for valid named baselines (after route tests pass)
6. Frontend: Workbench + DriverDetail named basis support; hide sync for named; no generic baseline in primary UI

## Files expected to change

- `project_schedule_comparison_basis_resolver.py` (new)
- `project_schedule_baseline_vocabulary.py`
- `project_schedule_summary_service.py`
- `project_schedule_review_service.py`
- `project_schedule_controls_service.py`
- `project_schedule_narrative_qa.py`
- `api.py`
- `frontend/src/lib/api.ts`, `ProjectScheduleWorkbenchPage.tsx`, `ProjectScheduleDriverDetailPage.tsx`, tests
- `tests/test_project_schedule_named_baseline_workbench.py` (new)

## Out of scope

- Schema/migrator, V90 changes, named disposition persistence, parser/CPM/import/trends

## Risks

1. URL param mismatch (`basis` vs `comparison_basis`) on driver detail — accept both, reject conflicts with 400
2. Workbench auto-sync on operator load — must skip for named basis
3. Unknown basis coercion removal may surface new 400s — intentional per amendment

## Test plan

- 20+ cases in `test_project_schedule_named_baseline_workbench.py`
- No-silent-fallback tests for unknown and missing named baselines
- source_model boundary proofs (named ≠ V90, legacy ≠ named slots)
- Controls link reinstatement only after workbench/driver route proofs
