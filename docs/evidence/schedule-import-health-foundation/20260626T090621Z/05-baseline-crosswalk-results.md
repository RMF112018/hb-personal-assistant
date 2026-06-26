# Baseline Crosswalk Results

Implemented crosswalk hierarchy:

- exact activity ID: confidence `1.00`
- exact normalized activity name and WBS: confidence `0.90`
- fuzzy normalized name: confidence `0.75+`, review required

Persisted evidence:

- `schedule_baseline_activity_crosswalk`
- match method
- confidence
- review status
- evidence JSON

Baseline health facts are persisted to `schedule_baseline_health_facts`. Weak or missing matches do not produce false headline precision; they surface `requires_user_mapping`.
