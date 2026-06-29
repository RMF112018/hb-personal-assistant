# Project Schedule Hub Phase 4 Update-to-Update Comparison

Date: 2026-06-29

## Prior-Update Selection Policy

Current update selection uses the existing Project Schedule Hub eligibility rule:

1. Load committed schedule versions for the project.
2. Keep versions eligible under `ScheduleTrustService.is_hub_eligible`.
3. Keep versions whose schedule data date, as resolved by `ProjectScheduleSummaryService._data_date`, is on or before `as_of`.
4. Select the latest data date; use imported/created timestamp only as a tie-breaker.

The previous update is the latest earlier eligible version in the same accepted schedule identity. If no previous update exists, the comparison context is unavailable with `unavailable_reason=no_prior_update`.

## Comparison Context

Backend read paths expose one prior-update comparison context:

- `current_version_key`
- `previous_version_key`
- `diff_id`
- `comparison_basis=prior_update`
- `finish_movement_basis=resolved_finish_date`
- `schedule_identity_key`
- `as_of_date`
- `available`
- `unavailable_reason`

Raw version keys remain technical evidence and collector-facing context, not default PM copy.

## Diff / Comparison Source Map

- `schedule_version_diffs`: persisted diff header and default diff id for the current update.
- `schedule_version_diff_detail_facts`: detailed activity/relationship change facts used by driver logic-change analysis and upstream cues.
- `schedule_version_diff_impact_rollups`: persisted impact rollups for diff intelligence surfaces.
- `schedule_version_diff_facts`: persisted summary facts from import/diff health.
- `project_schedule_series_membership`: project schedule series review/acceptance state used by hub eligibility.
- `schedule_version_identity_matches`: schedule identity match, review requirement, and same-identity prior-update selection.
- `procore_ep_schedule_activities`: authoritative activity rows used for resolved-finish and float movement comparisons.

## Supported Project Drilldowns

Project update-to-update drilldowns:

- `remaining_later`
- `remaining_earlier`
- `finish_changed`
- `new_remaining`
- `worsened_float`
- `improved_float`
- `milestones_later`
- `negative_float`
- `critical_remaining`
- `near_critical_remaining`
- `upstream_cues`

Baseline-prefixed project drilldowns remain baseline-specific and do not affect prior-update counts.

## Driver-Only Drilldowns

Relationship-change and duration-change details are not project drilldown route types in Phase 4. They are available through existing driver drilldown types when supporting data exists:

- `logic_changes`
- `duration_changes`

Unsupported project drilldown types return `unsupported_drilldown_type`.

## TWNU18 to TWNU19 Mapping

Canonical update-to-update counts:

- Remaining later: `461`
- Remaining earlier: `76`
- Finish changed: `537`
- New remaining: `98`
- Worsened float: `378`
- Improved float: `122`
- Moved remaining milestones: `6`

Phase 3 CPM/float reconciliation remains unchanged:

- Computed CPM critical remaining: `613`
- Computed CPM near-critical remaining: `0`
- Source/export negative float remaining: `711`

## Test Count Note

The current checkout's requested backend bundle collects the tests present in:

- `tests/test_project_schedule_hub_api.py`: 18
- `tests/test_project_schedule_hub_drilldowns.py`: 7
- `tests/test_project_schedule_driver_analysis.py`: 4
- `tests/test_project_schedule_review_workbench.py`: 6
- `tests/test_project_schedule_baseline_selection.py`: 2

The current collection total is 37. Earlier Phase 2 output reported 39 passing tests from an intermediate state that included additional route-contract tests not present in this checkout. Phase 3 reported 32 passing tests from the current reduced collection before Phase 4 tests were added.
