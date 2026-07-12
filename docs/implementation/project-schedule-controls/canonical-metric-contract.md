# Project Schedule Controls Canonical Metric Contract

## Purpose

Phase 1 centralizes Project Schedule Hub metric definitions in
`ProjectScheduleCanonicalMetricService` so backend read models, drilldowns,
exports, evidence collectors, and tests can use the same basis.

The contract is read-only. It does not import schedules, recompute CPM, mutate
diff facts, update baselines, or sync review items.

## Canonical Acceptance Metrics

For `project_key=tropical`, `current=TWNU19`, and `prior=TWNU18`, the canonical
contract is expected to produce:

| Metric | Expected | Basis |
| --- | ---: | --- |
| Remaining work | 712 | persisted DB fact |
| Remaining later | 461 | diff-derived |
| Remaining earlier | 76 | diff-derived |
| Finish changed | 537 | diff-derived |
| New remaining | 98 | diff-derived |
| Worsened float | 378 | diff-derived |
| Improved float | 122 | diff-derived |
| Moved remaining milestones | 6 | diff-derived |
| Source/export negative float | 711 | source/exported |
| Computed CPM critical remaining | 613 | CPM-computed |
| Computed CPM near-critical remaining | 0 | CPM-computed |
| Forecast finish | 2026-11-03 | service-derived |

## Metric Bases

`remaining_work`

- Basis: persisted DB fact.
- Source: `procore_ep_schedule_activities.actual_finish`.
- Definition: count current-version activities whose actual finish is null or blank.

`remaining_later`, `remaining_earlier`, `finish_changed`, `new_remaining`,
`worsened_float`, `improved_float`, `moved_remaining_milestones`

- Basis: diff-derived.
- Source: `ProjectScheduleComparisonService.compare_versions`.
- Definition: compare remaining current-version activities to the comparison
  version by `activity_id`.
- Finish basis: `remaining_finish`, fallback `finish_date`, fallback
  `remaining_early_finish`.
- Float basis: `total_float`, fallback `derived_total_float_days`, fallback
  `explicit_total_float_days`, fallback `computed_total_float`.

`source_export_negative_float`

- Basis: source/exported.
- Source: current-version `procore_ep_schedule_activities`.
- Definition: count remaining activities with negative
  `total_float`/`derived_total_float_days`/`explicit_total_float_days`.

`computed_cpm_critical_remaining`, `computed_cpm_near_critical_remaining`

- Basis: CPM-computed.
- Source: selected persisted `schedule_cpm_runs` plus
  `schedule_cpm_activity_results`.
- Definition: count remaining current-version activities in the selected
  application-computed CPM run where `computed_critical_flag=1` or
  `computed_near_critical_flag=1`.

`forecast_finish`

- Basis: service-derived.
- Source: current-version `procore_ep_schedule_activities`.
- Definition: maximum resolved finish date across remaining current-version
  activities.

## Existing Logic Now Used

- Remaining-work counts delegate to
  `ProjectScheduleCanonicalMetricService.activity_summary`.
- Computed CPM summary counts delegate to
  `ProjectScheduleCanonicalMetricService.computed_cpm_summary`.
- Forecast finish delegates to
  `ProjectScheduleCanonicalMetricService.forecast_finish`.
- Version-over-version movement continues to use
  `ProjectScheduleComparisonService.compare_versions`, which is the existing
  resolved-finish comparison implementation used by hub drilldowns.

## Why Earlier Direct DB Evidence Diverged

The earlier direct DB collector diverged from API values because it duplicated
only part of the service logic:

- It treated raw SQL as authoritative instead of using the hub's service-layer
  current/previous version resolution, schedule identity checks, future-date
  filtering, and comparison eligibility.
- It compared blank `remaining_finish` values directly in places where the hub
  uses resolved finish dates: `remaining_finish`, then `finish_date`, then
  `remaining_early_finish`.
- It did not consistently scope CPM counts to the selected persisted CPM run and
  remaining current-version activities.
- It could mix source/export float and app-computed CPM float, even though the
  hub intentionally exposes those as separate evidence classes.

Evidence collectors should call `ProjectScheduleCanonicalMetricService` or mark
their SQL-only output as heuristic/non-authoritative.
