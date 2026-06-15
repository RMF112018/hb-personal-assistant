# Workflow 12 — Forecast Cost-Frequency / Billing-Cadence

Additive, deterministic cadence evidence layer + its integration into the monthly forecast model. Run
it after the accepted forecast-intelligence (accuracy-next) package exists; the monthly model then phases
staffing costs by weekday cadence.

## Run

```bash
cd subrepos/construction-financial-review
# 1) the standalone evidence package
PYTHONPATH=src python3 -m construction_financial_review.cli forecast-cost-frequency \
    --project tropical --frozen-stamp 20260101_000000 --out-root /tmp/fcf
# 2) a fresh monthly run now consumes the same cadence logic (integration enabled)
PYTHONPATH=src python3 -m construction_financial_review.cli forecast-monthly \
    --project tropical --forecast-start-month 2026-06 --frozen-stamp 20260101_000000 --out-root /tmp/fm
```

`--with-llm` adds advisory (non-numeric) narratives for staffing / cadence-change codes. Omit
`--frozen-stamp` for a live timestamped package under the data root.

## What it produces

Package `forecast_cost_frequency_package_tropical_<stamp>/`:

- `cost_frequency_by_budget_code.jsonl` — per canonical code: staffing flag, configured override,
  observed + effective cadence class, `cadence_source` (configured/observed/inferred), confidence,
  months/recent-months observed, per-month entry counts, `transaction_level_costentries_available`,
  `monthly_aggregate_fallback_used`, latest-complete-month + weekday-normalized daily rate (staffing),
  `cadence_change_detected`/basis, `cadence_materially_changed_monthly_phasing`,
  `staffing_projection_scaled_to_ctc`, recommended phasing basis.
- `internal_staffing_daily_rate_by_budget_code.jsonl`, `weekday_calendar_by_forecast_month.jsonl`,
  `cost_entry_cadence_observations_by_budget_code.jsonl`, `frequency_revalidation_by_budget_code.jsonl`.
- `frequency_adjusted_monthly_phasing_by_budget_code.jsonl` — advisory normalized monthly weights +
  staffing raw vs scaled-to-CTC projection. `frequency_adjusted_monthly_project_forecast.jsonl` —
  project-level staffing scaled projection by month.
- `cadence_change_warnings.jsonl`, `forecast_cost_frequency_recommendations.jsonl`,
  `project_cost_frequency_summary.json` (carries the consumable `package_contract`).
- `audit/*` (frequency_detection, staffing_code_policy, source_hashes_before_after, source_files_used,
  db_inventory, safety_scan), `README.md`, `SCHEMA.md`, `manifest.json`, `input_inventory.json`,
  `validation_report.json`, `llm/*` (advisory, excluded from determinism).

The monthly package gains `source_shares.frequency_weight`, a
`frequency_monthly_phasing_by_budget_code.jsonl` evidence file, and
`audit/cadence_reconciliation_proof.json`.

## How a reviewer reads it

- **`project_cost_frequency_summary.json`** — counts by observed/effective class, staffing codes
  recognized, cadence-change count, staffing daily-rate summary, weekday project forecast by month, and
  the `package_contract` for `forecast_comprehensive`.
- **Staffing codes** — every configured staffing code has `effective_frequency_class =
  weekly_internal_staffing` and a daily rate from its latest COMPLETE month (the partial current month is
  never the basis). Watch `staffing_rate_volatility` warnings.
- **`cadence_change_warnings.jsonl`** — a previously-monthly code now trending multi-entry/month (or
  going quiet) — review before accepting the advisory effective class.
- **`audit/cadence_reconciliation_proof.json`** (monthly) — proves monthly remaining `Σ == CTC`,
  `actual + Σ == final`, and accepted final cost is unchanged by cadence.

## Guardrails

- CostEntries/Sage incurred cost is the only actual-cost source; cadence is timing/shape only — never an
  actual, never a cap, never a change to any accepted final cost (CTC-reconciled).
- Configured weekly internal-staffing override is the authoritative effective cadence; no staff-change
  events are fabricated (future-ready placeholder only).
- Monthly integration is reversible via `forecast_cost_frequency.forecast_monthly_integration_enabled`.
- No source / accepted package / SQLite / Excel mutation; no live external calls (localhost Ollama only).
- Deterministic: same frozen stamp + data-derived window ⇒ byte-identical quantitative core.
