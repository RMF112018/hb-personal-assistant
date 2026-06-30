# Review Workbench Audit — Before

## Gaps identified at session start

- POST `/api/projects/{project_key}/schedule/review-items` accepted only `as_of`; `comparison_basis` was ignored.
- `ProjectScheduleSummaryService.sync_review_workbench` did not accept or forward `comparison_basis`.
- `ProjectScheduleReviewService.sync_and_list` hardcoded `comparison_basis="prior_update"` when building the active workbench envelope.
- Cue evidence overloaded `data_date` with the requested `as_of` review context instead of separating review context from schedule update data date.
- Review cue evidence lacked canonical lineage and CPM import observability provenance.
- PM-facing taxonomy fields (`cue_category`, `cue_label`, `recommended_review_action`) were absent from cue evidence.
- Several cue types (milestone, float, quality, etc.) omitted `NON_CAUSATION_CUE`.
- `validate_review_cue_text()` did not exist for workbench cue copy QA.
- Frontend `syncProjectScheduleReviewItems` did not send `comparison_basis`; workbench sync was gated to `prior_update` only.
- Workbench query invalidation omitted `asOfDate` from the key tuple.
- Default UI surfaces exposed raw `activity_id` in driver labels and omitted `as_of` on some navigation links.

## Scope note

Parser, CPM algorithm, and import UX were not modified in this phase unless proven necessary.
