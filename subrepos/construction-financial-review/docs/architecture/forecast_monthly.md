# Forecast Monthly (time-phased month-by-month cost forecast)

Status: current. Module: `src/construction_financial_review/forecast_monthly/`.
CLI: `forecast-monthly`. Output: `forecast_monthly_package_tropical_<stamp>/`.

## Why this exists

The accepted `forecast_intelligence` slice answers *how much* (anticipated final cost + cost-to-complete
per budget code) but not *when*. This slice time-phases that final-cost package into a deterministic
month-by-month forecast — system current month (or `--forecast-start-month` override) through the month
of the latest scheduled finish — by budget code, owner scope, division, and project total, and pinpoints
which months carry the projected overrun exposure.

## Core principle

Actual cost to date is the only hard floor. Subcontractor invoice and owner pay-app values are
progress / exposure / timing evidence ONLY — never accounting actuals, never written as actuals.
Project-level schedule association is context only and never drives a code's monthly cost. Monthly costs
reconcile to cost-to-complete and final cost (cent tolerance). The current month is day-aware: only its
unbooked remainder is forecast (the elapsed/booked portion is already in CostEntries actuals and netted
out of CTC), so current-month actuals are never double-counted.

## Module map

| Module | Responsibility |
|---|---|
| `calendar.py` | Forecast window (start = system/override month, end = latest scheduled finish month); day-aware partial current-month fraction. |
| `cost_entry_trends.py` | CostEntries monthly trend + SHAPED forward weight vector (classification: flat_recent_burn / accelerating_front_loaded / decelerating_back_loaded / recent_spike_review / credit_adjusted / no_stable_pattern). |
| `subcontractor_invoice_trends.py` | Invoice period → monthly billing movement + its OWN forward weight vector; marked `unavailable` where no mapped invoice evidence (never forced, never actuals). |
| `schedule_monthly_phasing.py` | Per-code monthly schedule weights from mapped open-activity spans (reuses `cashflow._month_day_weights`); direct uses own activities, weaker influencing tiers use a synthetic span; project-level produces nothing. |
| `frequency_phasing.py` | Cadence/frequency timing vector — imports the `forecast_cost_frequency` shared logic; weekday-normalized phasing for staffing/weekly codes (the primary timing basis for staffing), None otherwise. Gated by `forecast_cost_frequency.forecast_monthly_integration_enabled`. See `docs/architecture/forecast_cost_frequency.md`. |
| `monthly_reconcile.py` | Blends the schedule / **frequency-cadence** / cost-entry / invoice vectors (reported source shares incl. `frequency_weight`), applies day-aware partial scaling, allocates month costs that tie exactly to CTC/final, detects the overrun month. Frequency reshapes months only — CTC and accepted final cost are unchanged (`audit/cadence_reconciliation_proof.json`). |
| `monthly_confidence.py` | Three split confidences: overrun_existence / final_cost_estimate / monthly_distribution. |
| `monthly_backtest.py` | As-of monthly hold-out; WAPE (primary) + MAE + MAPE; CostEntries-only vs CostEntries+invoice; honest schedule/cohort limitations. |
| `generate_monthly_forecast_package.py` | Orchestrator: 25-file package, determinism self-check, validation gates, safety, manifest, advisory LLM. |

Reuses `common/*`, `forecast_accuracy.signals`, `schedule_analysis/{cashflow,schedule_io,schedule_mapping,
schedule_rollup}`, `forecast_intelligence.db_inventory`, and `forecast_accuracy.llm`.

## Timing blend

Three independent forward weight vectors are built and REPORTED per code. The blended weight is
`schedule_share·schedule + cost_share·cost_entries + invoice_share·invoice`, where
`schedule_share = schedule_confidence`, and the residual splits between CostEntries and invoice by
invoice quality (invoice excluded entirely where unavailable). The partial current month's weight is
scaled by its unbooked day-remainder fraction, then weights are renormalized. Month costs are allocated
in month order with the last nonzero month absorbing the cent residual, so `Σ recommended_month_cost ==
recommended_cost_to_complete` and `actual + Σ == recommended_final_cost` exactly (same for worst-credible).

`monthly_forecast_basis` ∈ {schedule_phasing, subcontractor_invoice_trend, cost_entries_trend, combined,
owner_progress, flat_remaining, insufficient_evidence}.

## Overrun timing

Cumulative cost grows monotonically from actual to final, so the first month its running cumulative
exceeds current projected cost (and revised budget) is deterministic. If actuals already exceed current
projected, the overrun month is month 1 and `overrun_existence_confidence = very_high`. The overrun
register ranks codes by amount with severity tiers and split confidence.

## Hardening

- **Determinism block** in `validation_report.json` (`performed`, `quantitative_core_byte_identical`,
  `llm_excluded_from_byte_diff`, `frozen_stamp`, `diff_result`, per-file hashes) + gate
  `determinism_passed`. The orchestrator builds the quant data twice into temp dirs and byte-diffs them.
- **LLM receipts** carry `model, backend, status, fallback_used, temperature, seed, prompt_template_hash,
  facts_hash, response_hash, safety_status, generated_at`. LLM is advisory only — never numeric, never
  fails the quant package.
- **Split confidence** on every budget-code monthly row and overrun row.

## Validation gates (fail-closed)

output_files_parse; 127×months completeness; window start = system/override AND end = latest-finish
month; canonical-only codes; final ≥ actuals; Σ months == CTC AND actual+Σ == final (cent tolerance);
no current-month double-count; invoice not written as actuals; project-level schedule not driving a code;
direct association has a deterministic activity link; overrun not suppressed; `determinism_passed`; LLM
receipt fields present when LLM used; confidence split present; db_inventory no payloads; safety scan;
no source mutation.

## Guardrails

Code only under this subproject; output only a new timestamped package under the data root. No
source/Excel/SQLite/external mutation (DB opened read-only). Decimal money; actuals the only hard floor;
every row `requires_human_acceptance`. Forecast starts at the system month unless `--forecast-start-month`
overrides; extends through the latest scheduled finish month.
