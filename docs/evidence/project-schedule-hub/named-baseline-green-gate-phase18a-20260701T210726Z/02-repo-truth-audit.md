# Phase 18A repo-truth audit

Base: `ef00fc73` (Phase 18 merged on `origin/main`)

## Failure 1: `test_prior_update_disposition_does_not_join_named_workbench`

**Assertion:** `assert open_prior` where filter used `review_status == "open"`.

**Repo truth:** Phase 17 canonicalized dispositions in `project_schedule_review_disposition.py`. API payloads normalize legacy `open` → `needs_review` and `reviewed` → `accepted_for_follow_up` via `enrich_item_disposition_pm_fields`.

**Isolation behavior:** Named-baseline review uses separate table/repo (`project_schedule_named_baseline_review_items`) and `ProjectScheduleNamedBaselineReviewService`. No code path reads prior-update disposition when building named workbench preview.

**Verdict:** Test fixture assertion stale; **behavior correct**. Fix tests to use `is_open_disposition()` and canonical constants.

## Failure 2: `test_controls_named_includes_workbench_links`

**Assertion:** `pytest.fail("expected at least one activity-backed control")` when checking `control.get("activity_id")`.

**Repo truth (service):** `ProjectScheduleControlsService.build_controls` routed all comparison bases through `ProjectScheduleReviewService.build_preview`, while `ProjectScheduleSummaryService` routes named slots to `ProjectScheduleNamedBaselineReviewService.build_preview`. **Real routing defect.**

**Repo truth (test):** `_pm_top_control()` strips `activity_id` from PM `top_controls` payloads (PM redaction). Activity-backed controls are evidenced via `links.driver_detail` URLs, as in `test_controls_reinstates_named_workbench_and_driver_links`.

**Repo truth (fixture):** Named-baseline activity-backed controls require driver-chain schedule data (`_seed_driver_chain`), not milestone-only `_seed_comparable_versions`.

**Verdict:** **Service fix required** for named preview routing. Test assertion updated to link-based activity-backed check (not weakened). Fixture uses coherent driver-chain helper.

## Phase 17 / Phase 18 impact

- Phase 17 disposition semantics are authoritative; do not re-lock to legacy strings.
- Phase 18 portfolio dashboard unchanged; no edits to portfolio review service in this phase.

## Narrowest safe fix

1. Route named-baseline controls preview through `ProjectScheduleNamedBaselineReviewService` (mirror summary service).
2. Update comparison-accuracy test for canonical dispositions.
3. Align controls named-baseline test fixture + assertions with established workbench/controls contract.
