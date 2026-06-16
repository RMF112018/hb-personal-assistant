# Workflow 08 — Forecast Intelligence (anticipated final cost + overrun detection)

Projects the real anticipated final cost per budget code and surfaces overruns. Additive over the
`forecast_accuracy` slice; nothing in the earlier pipeline changes.

## Inputs (latest packages under the Tropical 2026-June data root)

- `forecast_context_package_tropical_*` — canonical 127 budget codes, monthly actuals, owner/procore
  evidence, ERP `budget_amounts`.
- `forecast_analysis_package_tropical_crosswalk_v2_*` — rule-based `forecast_recommendations_*`
  (current projected cost, owner SOV scope assignment) — read only, reference only.
- `schedule_integrated_forecast_package_tropical_*` and `project_schedule_json_package` — schedule
  rollup + raw activities (data date 2026-05-26, finish 2026-11-03).
- Prior `forecast_accuracy_package_tropical_*` — for change explanation + backtest before/after.
- Local DB `~/Library/Application Support/HB Personal Assistant/db/...sqlite` — read-only inventory
  + project-level change-order aggregation only.

## Run

```bash
cd subrepos/construction-financial-review
# Deterministic mock (no model):
PYTHONPATH=src python3 -m construction_financial_review.cli forecast-intelligence \
  --project tropical --frozen-stamp 20260101_000000 --out-root /tmp/fi_a
# Delivered run with live local-Ollama advisory narratives:
PYTHONPATH=src python3 -m construction_financial_review.cli forecast-intelligence \
  --project tropical --with-llm
```

Determinism check: two `--frozen-stamp` mock runs into separate `--out-root` dirs, then
`diff -rq` (identical except `llm/`).

## Output package `forecast_accuracy_next_package_tropical_<stamp>/`

Per-code (127 rows): `forecast_recommendations_by_budget_code.jsonl`,
`forecast_accuracy_next_by_budget_code.jsonl`, `forecast_model_evidence_by_budget_code.jsonl`,
`schedule_forecast_evidence_by_budget_code.jsonl`, `trend_evidence_by_budget_code.jsonl`,
`remaining_work_evidence_by_budget_code.jsonl`, `forecast_confidence_by_budget_code.jsonl`,
`forecast_change_explanation.jsonl`.
Variable: `forecast_overrun_risk_register.jsonl`, `data_quality_warnings.jsonl`.
Rollups: `project_forecast_summary.json`, `top_overrun_risks.json`, `top_forecast_changes.json`,
`model_backtest_results.json`, `model_calibration_summary.json`.
Audit: `audit/{db_inventory,schedule_inventory,source_files_used,analysis_reconciliation,safety_scan_report}.json`.
Plus `README.md`, `SCHEMA.md`, `manifest.json`, `input_inventory.json`, `validation_report.json`,
and advisory `llm/{forecast_narratives,llm_receipts}.jsonl`.

## How a reviewer reads it

- **Start with `top_overrun_risks.json`** — the largest anticipated overruns vs current projected
  cost, with basis, severity, schedule association, and trend signal.
- `recommended_final_cost` is the balanced-central anticipated cost; `worst_credible_final_cost` is
  the evidence-supported exposure ceiling. **ERP projected cost is a reference, never a cap.**
- `forecast_direction` = increase / decrease / hold / review / insufficient_evidence. A `decrease`
  is only emitted when defensible (near-complete + stable + no commitment overrun).
- `insufficient_evidence` codes have no code-level evidence; recommended = actuals, low confidence,
  `requires_human_acceptance` — these are honest gaps, not ERP echoes.
- `model_backtest_results.json` shows method accuracy at 40/60/80% as-of points and the before/after
  vs the prior package; calibration weights re-rank methods by historical error.

## Guardrails

Actuals are truth and the only hard floor; never overwritten by pay-app values. No
source/Excel/SQLite/external mutation (DB read-only). LLM advisory only, never numeric, never fails
the quantitative package. Every recommendation requires human acceptance. No commit unless instructed.
