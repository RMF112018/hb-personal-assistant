# Phase 18A fix summary

## Root cause

1. **Disposition vocabulary drift:** Tests filtered/asserted legacy `open`/`reviewed` after Phase 17 canonical dispositions.
2. **Controls named-baseline routing:** `build_controls` used prior-update review preview for named baseline bases instead of `ProjectScheduleNamedBaselineReviewService`.
3. **Controls test contract drift:** Test expected `activity_id` on PM `top_controls` after `_pm_top_control()` redaction; activity-backed controls are linked via `driver_detail` URLs.

## Changes

### Service

- [project_schedule_controls_service.py](../../../src/hb_assistant/construction/analytics/project_schedule_controls_service.py)
  - Lazy-init `ProjectScheduleNamedBaselineReviewService`
  - For `is_named_baseline_basis(basis)`, build workbench preview via named scope + `build_preview`
  - Prior-update/legacy paths unchanged

### Tests

- [test_project_schedule_named_baseline_comparison_accuracy.py](../../../tests/test_project_schedule_named_baseline_comparison_accuracy.py)
  - Use `is_open_disposition`, `DISPOSITION_NEEDS_REVIEW`, `DISPOSITION_ACCEPTED_FOR_FOLLOW_UP`

- [test_project_schedule_multi_baseline_controls.py](../../../tests/test_project_schedule_multi_baseline_controls.py)
  - `_seed_named_baseline_controls_fixture()` wraps driver-chain seed
  - Assert activity-backed controls via `links.driver_detail` + `links.review_item`

## Files changed

- `src/hb_assistant/construction/analytics/project_schedule_controls_service.py`
- `tests/test_project_schedule_named_baseline_comparison_accuracy.py`
- `tests/test_project_schedule_multi_baseline_controls.py`
