# Review Workbench Audit — After

## Backend

- POST review-items sync accepts `comparison_basis` and threads it through `sync_review_workbench` → `sync_and_list`.
- `sync_and_list` persists queue rows only for `prior_update`; baseline sync returns live baseline envelope without persistence.
- Cue evidence now carries distinct `as_of` (requested review context) and `schedule_data_date` (resolved update data date). `data_date` mirrors schedule data date for backward compatibility.
- `ProjectScheduleReviewEvidenceService` enriches cues with lineage (`ScheduleActivityRepository.get_activity_merge_lineage_batch`) and latest committed CPM observability.
- `project_schedule_review_cue_taxonomy.py` supplies PM-facing `cue_category`, `cue_label`, and `recommended_review_action`.
- `validate_review_cue_text()` added to `project_schedule_narrative_qa.py` with negated/disclaimer-aware forbidden-term scanning.
- `NON_CAUSATION_CUE` added to milestone, float, critical, window, quality, and compression cues.

## Frontend

- `syncProjectScheduleReviewItems` sends `comparison_basis`.
- Workbench sync passes selected basis; query invalidation includes full key tuple with `asOfDate`.
- `ReviewCueCard` / `ReviewCueTechnicalDetails` extracted under `frontend/src/components/project-schedule/`.
- Default cards hide raw IDs; technical evidence collapsed behind explicit toggle.
- Schedule hub driver table and driver detail header suppress raw `activity_id` in default labels.
- Driver/workbench back links preserve `?as_of=`.

## Tests

- Added `tests/test_project_schedule_review_alignment.py` covering basis threading, date semantics, lineage/CPM provenance, cue QA, export advisory language, and canonical XER/XML lineage proof.
- Extended `ProjectScheduleWorkbenchPage.test.tsx` and `ProjectSchedulePage.test.tsx`.

## Out of scope (unchanged)

Parser, CPM algorithm, and import UX foundations were not modified.
