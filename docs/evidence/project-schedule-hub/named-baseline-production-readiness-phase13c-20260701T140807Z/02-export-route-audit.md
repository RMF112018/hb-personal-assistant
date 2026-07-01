# Export route audit — Phase 13C

## Route

`GET /api/projects/{project_key}/schedule/export?format=&comparison_basis=&as_of=`

## Before (13B)

- `build_export` for named slots called `build_summary` (prior-update story) then patched comparison labels.
- Named bases `current_contract_baseline` / `secondary_progress_update_baseline` returned **422 `narrative_qa_failed`**.
- `previous_progress_update_baseline` returned 200 with prior-update-like movement counts.

## After (13C)

1. **`build_export` named path** uses `_build_named_export_summary()` built from `build_schedule_hub_context_with_named_baseline()` — movement, milestones, drivers, and comparison provenance are named-context-derived.
2. **`_export_comparison_context_complete()`** guard — deterministic fallback returns **200** only when slot label, version keys, and basis are present.
3. **`export_mode: deterministic_fallback`** + `export_warnings` when narrative QA fails but context is complete; does **not** mask `baseline_not_selected`, `baseline_invalid`, `unsupported_export_format`, or incomplete context (still 422).
4. **Memo body** prepends `## Comparison Context` for complete named exports.
5. **Frontend:** `ProjectScheduleWorkbenchPage` export mutation passes `{ asOf, comparisonBasis }` (hub page already did).

## Test coverage

- `tests/test_project_schedule_named_baseline_export.py` — per-slot label, version key, distinct movement counts, HTML, deterministic fallback, missing slot 422.
- `ProjectScheduleWorkbenchPage.test.tsx` — export spy for `prior_update` + 3 named bases.
- Tropical read-only: `13c-api-proof-export.json` — all four bases HTTP 200 with differential counts.
