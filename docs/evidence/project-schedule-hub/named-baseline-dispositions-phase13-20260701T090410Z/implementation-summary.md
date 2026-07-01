# Phase 13 Implementation Summary

**Proof type:** hybrid (repo truth + fixture DB + real local DB)

## Persistence design

- **Separate tables (V97):** `project_schedule_named_baseline_review_items`, `project_schedule_named_baseline_review_item_events`
- **Rationale:** `project_schedule_review_items` unique key is a droppable named index, but extending it would touch all prior_update upsert/carry-forward paths; separate table maximizes isolation per amendments.
- **Identity:** project + current schedule version + comparison_basis + baseline schedule version + source_stable_key + source_metric_key + source_signal_type + source_activity_id

## Backend

- `project_schedule_named_baseline_review_repository.py` — scoped upsert/list/PATCH only
- `project_schedule_named_baseline_review_service.py` — named sync/list/merge
- `project_schedule_summary_service.py` — routes named_slot sync/GET; legacy baseline preview unchanged
- `project_schedule_review_service.py` — dispatches `psnbri-*` PATCH/events
- `api.py` — named sync errors `baseline_not_selected` / `baseline_invalid` → 400

## Frontend

- `ProjectScheduleWorkbenchPage.tsx` — enables named sync when slot selected; named baseline review banner; legacy baseline stays read-only

## Tests

- New: `tests/test_project_schedule_named_baseline_dispositions.py` (17 cases incl. PATCH isolation)
- Updated: named workbench + WorkbenchPage frontend tests

## Out of scope (unchanged)

- prior_update table/behavior, legacy V90 baseline, parser/CPM/import, named slot selection semantics
