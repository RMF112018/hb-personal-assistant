# Usefulness Scorecard

A lifecycle-aware run is useful only if:

- There is at least one useful deterministic section, accepted action, watch item, or review-required item.
- Surfaced executive/actionable rows have source-ref coverage = 100%.
- Rejected/suppressed/merged rows are not surfaced as new.
- Snoozed rows respect return date.
- Duplicate groups do not inflate action counts.
- Project-review-required rows are visible or explicitly counted as a data gap.
- Lifecycle stage failures are reflected in status.
- No raw leak is present.

Fail/degrade reasons should include:

- `lifecycle_read_model_empty_with_candidates`
- `accepted_actions_missing_source_refs`
- `rejected_visible_as_new`
- `suppressed_visible_as_new`
- `merged_visible_as_new`
- `snoozed_visible_before_return`
- `duplicate_inflation`
- `lifecycle_stage_failed`
- `project_review_required_hidden`
- `lifecycle_source_ref_coverage_below_100`

