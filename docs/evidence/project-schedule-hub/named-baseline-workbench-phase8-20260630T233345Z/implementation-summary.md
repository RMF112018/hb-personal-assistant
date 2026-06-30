# Phase 8 Implementation Summary — Named Baseline Workbench Parity

**Branch:** `feature/schedule-named-baseline-workbench-phase8-20260630T233345Z`  
**Base:** `e2acc41d` (Phase 7 merged)

## Delivered

1. **`project_schedule_comparison_basis_resolver.py`** — explicit `source_model` boundaries (`prior_update`, `legacy_v90`, `named_slot`); rejects unknown with `invalid_comparison_basis`; driver param reconciliation with `conflicting_comparison_params`.
2. **Workbench GET** — named slots via `build_resolved_hub_context`; read-only preview (`synced=false`, no disposition carry-forward); outward `comparison_basis` preserves named slot identity.
3. **POST review-items** — sync only `prior_update`; named → `400 named_baseline_sync_not_supported`; legacy `baseline` POST unchanged (preview-only, zero sync).
4. **Driver detail** — named + legacy + prior_update; accepts `basis` and `comparison_basis`; conflicting → `400`.
5. **Controls links** — reinstated for valid named baselines with `comparison_basis` + `as_of` preserved on workbench/driver URLs.
6. **Frontend** — Workbench URL init from `comparison_basis`; named slot toggles from baselines API; no operator sync for named; Driver detail dual-param support; legacy `baseline` hidden from workbench primary UI.

## Amendment compliance

| Amendment | Status |
|---|---|
| Unknown basis → `invalid_comparison_basis` (no coercion) | ✅ |
| source_model boundaries + tests | ✅ |
| Named workbench read-only / no carry-forward / synced=false | ✅ |
| POST sync only prior_update; named → 400 | ✅ |
| Controls links after route proofs | ✅ |
| Driver dual params + conflict 400 | ✅ |
| No-silent-fallback tests | ✅ |
| Legacy baseline backend-only on workbench UI | ✅ |

## Files changed

- New: `project_schedule_comparison_basis_resolver.py`, `test_project_schedule_named_baseline_workbench.py`
- Backend: vocabulary, summary, review, controls, driver analysis, api
- Frontend: api.ts, WorkbenchPage, DriverDetailPage, ReviewCueCard, ProjectSchedulePage (types)
