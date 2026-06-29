# Project Schedule Hub Phase 3 CPM / Float Reconciliation

Date: 2026-06-29

## Source Map

- `schedule_cpm_runs`: application-computed CPM run metadata, calculation type, status, thresholds, counts, source run chain, and `created_at`.
- `schedule_cpm_activity_results`: per-activity application-computed dates, float, critical flags, near-critical flags, and criticality basis.
- `schedule_cpm_relationship_results`: per-relationship application-computed constraint and float evidence.
- `schedule_cpm_diagnostics`: graph/CPM diagnostic findings by run.
- `schedule_cpm_paths`: persisted application-computed longest-path summary.
- `schedule_cpm_path_activities`: ordered application-computed longest-path membership and computed float/date fields.
- `procore_ep_schedule_activities`: source/export schedule activity fields, including `total_float`, `derived_total_float_days`, and `explicit_total_float_days`.

## Selected CPM Run Policy

Project Schedule Hub canonical CPM criticality uses one selected application-computed CPM run per schedule version.

Selection order:

1. Latest eligible `criticality` run.
2. Latest eligible `float` run.
3. Latest eligible `backward_pass` run.
4. Latest eligible `forward_pass` run.

If status exists, successful/completed-style statuses are preferred over failed/partial runs. Ties are deterministic: newest `created_at`, then stable `cpm_run_id` descending.

Runs not selected are still exposed as `all_cpm_runs` / `excluded_cpm_runs` provenance. They are not counted in `computed_cpm_critical_remaining` or `computed_cpm_near_critical_remaining`.

## Float Separation

Source/export float is strictly activity-export evidence:

`procore_ep_schedule_activities.total_float -> derived_total_float_days -> explicit_total_float_days`

Application-computed CPM float and criticality are strictly selected CPM-run evidence:

`schedule_cpm_activity_results` rows for `source_cpm_run_id`

The hub payload exposes this separation in `source_float_summary` and `computed_cpm_summary`.

## Near-Critical Threshold

The near-critical threshold comes from the selected CPM run when present, then selected activity-result rows. If neither carries a threshold, the default is `10.0` days from `schedule_cpm_criticality.DEFAULT_NEAR_CRITICAL_THRESHOLD`.

## Critical Path Versus Critical Remaining

The critical path list is longest-path preview evidence from `schedule_cpm_paths` and `schedule_cpm_path_activities`. Its length is not the computed critical remaining count.

Computed critical remaining is the count of unfinished activities with `computed_critical_flag=1` in the selected CPM run.

## Evidence Collector Discrepancy

The prior direct DB collector could report `computed critical remaining = 0` and `computed near-critical remaining = 2` when it read a failed/stale/non-authoritative CPM run or all CPM activity rows without deterministic run selection.

The authoritative path is now `ProjectScheduleCanonicalMetricService.computed_cpm_summary()` and `cpm_flags_by_activity()`. Evidence collectors should call that contract rather than reimplementing CPM SQL.
