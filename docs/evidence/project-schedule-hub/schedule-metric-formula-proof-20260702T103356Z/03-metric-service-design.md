# Metric service design

Service: `schedule_metric_formula_service.py`

## Near-critical change formula

```
near_critical_change_count =
  count of activities whose computed_criticality_class changed
  into OR out of computed_near_critical
  between comparison CPM run (prior update) and current CPM run
```

If prior CPM criticality run unavailable → `not_computable`, not 0.

## Baseline delay

Uses `ProjectScheduleSelectedBaselineService.get_state()` only. Outputs `comparison_basis`, `selected_baseline_schedule_version_key`, `baseline_finish_source`, `current_finish_source`.

## Denominator audit

All ratios emit `numerator`, `denominator`, `zero_denominator_policy`, `result`.

## Trend compatibility

Trend service unchanged in this phase. Formula service is primary path for `/schedule/metric-proof`.
