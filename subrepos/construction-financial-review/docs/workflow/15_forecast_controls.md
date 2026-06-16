# 15 — Forecast Controls (operator stop-date / closeout constraints)

Operator-controlled, human-accepted layer that sets per-code forecast stop dates / closeout windows and
accepted remaining/final-cost allowances before monthly and comprehensive generation. See
`docs/architecture/forecast_controls.md` for the full design.

## When to use

A cost code is substantially complete and should stop carrying model forecast through the final month
(e.g. Roofing `15-07-590` — punchlist only). Add a control; the model will zero post-stop months and
redistribute the allowed remaining cost into the closeout window.

## Edit the control file

`config/forecast_controls/tropical/code_forecast_controls.jsonl` — one JSON object per line. Minimum for
a stop date:

```json
{"project_key":"tropical","control_id":"tropical-roofing-15-07-590-closeout-2026-06","budget_code_key":"1000.15-07-590.SUB","cost_code":"15-07-590","control_type":"closeout_stop_date","forecast_stop_date":"2026-07-31","acceptance_status":"pending","requires_human_acceptance":true,"accepted_by":null,"accepted_at":null,"acceptance_notes":null,"source":"operator_decision","reason":"Roofing substantially complete; punchlist only"}
```

- Leave `acceptance_status: "pending"` to queue without changing the forecast.
- Set `acceptance_status: "accepted"` and `accepted_by` to apply the stop date. With no
  `accepted_remaining_cost` / `accepted_final_cost`, this is **timing only** — the dollar total stays
  model-derived (a warning is emitted).
- To also fix the dollars, set `accepted_remaining_cost` (remaining) or `accepted_final_cost` (total).
  Neither may push final cost below actual cost to date.
- A `cost_code`-only control resolves only when the cost code is unique in the canonical universe; else
  provide `budget_code_key`.

## Run

```bash
PY="../../.venv/bin/python"; export PYTHONPATH=src
$PY -m construction_financial_review.cli forecast-controls --project tropical
```

Review `forecast_controls_package_tropical_<stamp>/`:
- `project_forecast_controls_summary.json` — counts + controlled budget codes.
- `forecast_controls_application_by_budget_code.jsonl` — per-control disposition.
- `forecast_controls_monthly_adjustments_by_budget_code.jsonl` — before/after monthly preview + months zeroed.
- `forecast_controls_review_queue.jsonl` — pending / superseded / unmapped controls.
- `forecast_controls_warnings.jsonl` — model-derived-dollars + mapping/floor warnings.
- `validation_report.json` — fail-closed gates.

## Effect on downstream forecasts

```bash
$PY -m construction_financial_review.cli forecast-monthly --project tropical
$PY -m construction_financial_review.cli forecast-comprehensive --project tropical
```

- **Monthly**: controlled codes show `monthly_forecast_basis = operator_controlled_*`; months after the
  stop are `0.00`; sums still reconcile to cost-to-complete and final cost. See
  `audit/forecast_controls_applied.json`.
- **Comprehensive**: an `operator_forecast_control` evidence item per controlled code; integrated monthly
  rows carry `operator_controlled` + `operator_stop_month`; the conflict register adds
  `operator_control_conflicts_with_model_forecast`,
  `operator_stop_date_conflicts_with_schedule_remaining_work`,
  `operator_remaining_allowance_below_actuals`, `operator_control_pending_not_applied`,
  `operator_control_ambiguous_mapping`.

## Guardrails

CostEntries are truth; actual cost to date is the only floor; no hidden caps. Pending controls never
change the forecast. Accepted dollar controls can never go below actuals. Nothing mutates source Excel,
accepted packages, or SQLite; no live external calls.

## Next step

`forecast-model-controls` (doc: `17_forecast_model_controls.md`) is the next pipeline step. It adds
per-code forecast **window**, **model shape**, **value-constraint**, and **manual-value** controls and
runs before forecast-monthly. Use it when you need to set a code's final to a reference, reshape its
monthly curve, or enter manual monthly values — not just stop its forecast.
