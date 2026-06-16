# 17 — Forecast Model Controls (per-code window / shape / value / manual)

Operator-controlled, human-accepted layer that configures the forecast model for a single canonical
`budget_code_key`: its forecast window, model shape, an optional value constraint against a selected
reference, and optional manual total/monthly values — before monthly and comprehensive generation. See
`docs/architecture/forecast_model_controls.md` for the full design. This is broader than
`forecast_controls` (timing/stop-date only): final-value pinning is one subsection here.

## When to use

- Pin a code's final forecast to a reference (e.g. final = projected cost, revised budget, committed cost,
  accepted intelligence final, or an explicit amount).
- Cap/floor a code against a reference (disclosed operator constraint, never a silent cap).
- Reshape a code's monthly distribution (linear, ascending/descending, front/back-loaded S-curve, bell).
- Constrain or extend the forecast window (start/end by date or schedule).
- Enter manual monthly values or a manual total for a code.

## Edit the control file

`config/forecast_model_controls/tropical/code_forecast_model_controls.jsonl` — one JSON object per line.
The committed file ships **pending examples only** (dormant). Examples:

```json
{"project_key":"tropical","control_id":"twn-15-08-250-equal-projected","budget_code_key":"1000.15-08-250.SUB","control_type":"forecast_model_control","effective_month":"2026-06","value_constraint_policy":"equal_to_reference","reference_source":"projected_cost","model_type":"existing_model","acceptance_status":"accepted","requires_human_acceptance":true,"accepted_by":"Bobby Fetting","accepted_at":"2026-06-16","reason":"final equals projected cost"}
{"project_key":"tropical","control_id":"twn-15-09-600-manual-monthly","budget_code_key":"1000.15-09-600.SUB","control_type":"forecast_model_control","effective_month":"2026-06","model_type":"manual_monthly","manual_monthly_values":{"2026-06":"10000.00","2026-07":"12000.00"},"acceptance_status":"accepted","requires_human_acceptance":true,"accepted_by":"Bobby Fetting","accepted_at":"2026-06-16","reason":"operator-entered monthly values"}
```

- `acceptance_status:"pending"` queues a control without changing the forecast (dormant).
- `acceptance_status:"accepted"` + `accepted_by`/`accepted_at` applies it. A controlled final may never be
  below actual cost to date (floor). Two accepted controls that disagree for one code fail closed.
- Defaults: `forecast_start_policy=current_month_start`, `forecast_end_policy=latest_project_schedule_date`,
  `value_constraint_policy=none`, `model_type=existing_model`.
- A `cost_code`-only control resolves only when the cost code is unique; else provide `budget_code_key`.

## Run

```bash
PY="../../.venv/bin/python"; export PYTHONPATH=src
$PY -m construction_financial_review.cli forecast-model-controls --project tropical
# validation / dry-run a candidate file without touching the committed config:
$PY -m construction_financial_review.cli forecast-model-controls --project tropical \
    --forecast-model-control-file /path/to/candidate.jsonl --out-root /tmp/check
```

Review `forecast_model_controls_package_tropical_<stamp>/`:
- `project_forecast_model_controls_summary.json` — counts + controlled budget codes.
- `model_control_applications_by_budget_code.jsonl` — per-control disposition.
- `model_control_resolved_targets_by_budget_code.jsonl` — resolved reference, controlled final/remaining,
  window basis, floor status.
- `model_control_monthly_preview_by_budget_code.jsonl` — monthly allocation reconciling to the controlled
  final.
- `model_control_probability_assessment_by_budget_code.jsonl` — anchor vs provisional plausibility.
- `model_control_review_queue.jsonl` / `model_control_conflicts.jsonl` / `model_control_warnings.jsonl`.
- `validation_report.json` — all fail-closed gates; `passed:true` required.

## Notes

- Probability is degraded-not-fatal: a value-changing code with a prior accepted probability row anchors to
  the controlled final; without one it gets a deterministic provisional plausibility assessment (numeric
  probabilities null) and the run still completes.
- `forecast-monthly` and `forecast-comprehensive` consume accepted model controls so the integrated final,
  monthly distribution, probability, and combined actuals+forecast CSV reconcile to the controlled result.
