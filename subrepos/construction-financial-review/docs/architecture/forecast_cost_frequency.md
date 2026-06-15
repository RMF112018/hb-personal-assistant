# Forecast Cost-Frequency / Billing-Cadence Evidence Layer

Additive, deterministic slice (`forecast_cost_frequency`, CLI `forecast-cost-frequency`, package
`forecast_cost_frequency_package_tropical_<stamp>/`) that classifies each canonical budget code's
cost-incurrence cadence from real CostEntries and supplies a weekday-normalized timing signal that is
also wired into `forecast_monthly`. CostEntries/Sage incurred cost is accounting truth; cadence is
timing/shape evidence only — never an actual, never a cap, never a change to any accepted final cost.

## Why

The monthly model phased every code with the same three timing signals (cost-entry trend, subcontractor
invoice, schedule) plus a flat fallback. Internal staffing / labor-burden codes are incurred *weekly*,
so a flat or trend-based phasing misstates their month shape. This slice recognizes cadence explicitly —
especially the 23 configured weekly staffing codes — and feeds a weekday-normalized shape into the
monthly reconciliation without touching cost-to-complete or final cost.

## Inputs (read-only)

- `forecast_context_package/canonical/budget_codes.jsonl` — the 127 canonical codes (`budget_code_key`,
  `cost_code`, `category`).
- `forecast_context_package/canonical/cost_entries.jsonl` — transaction-level actuals (`accounting_date`)
  for intra-month spacing.
- `forecast_context_package/summaries/budget_code_forecast_context.jsonl` — `actuals.monthly_actuals[]`
  carry per-month `amount` + `entry_count` (the primary cadence signal) and `actual_period_bucket`.
- accepted `forecast_accuracy_next_package` recommendations — `recommended_cost_to_complete` (used only
  to scale staffing timing; never to change final cost).
- schedule package — latest finish date → forecast-window end.

## Pipeline

1. **Window** (`frequency_io.derive_window`): forecast start = the repo period-bucket to-date month
   (`2026-06`); latest-complete boundary = the prior month (`2026-05`, so the partial current month is
   excluded from cadence/rate evidence); end = schedule latest finish month. Data-derived → deterministic
   regardless of wall-clock.
2. **Staffing recognition** (`staffing_codes`): configured `weekly_internal_staffing_budget_code_keys`
   is authoritative; `staff_change_events` is a future-ready placeholder (never fabricated).
3. **Cadence detection** (`frequency_detect`): per code, from per-month `entry_count` (+ transaction-date
   spacing when available), classify `weekly_observed / twice_monthly_observed / monthly_observed /
   irregular / one_time_or_milestone / inactive_or_complete / insufficient_evidence`. Graceful
   degradation: with only monthly aggregates (no transaction dates), weekly is never inferred for
   non-staffing codes. Emits `cadence_source` (configured/observed/inferred),
   `transaction_level_costentries_available`, `monthly_aggregate_fallback_used`.
4. **Staffing daily rate** (`daily_rate`): `latest_complete_month_actual_cost /
   weekdays_in(latest_complete_month)`; the partial current month is never the basis; compared to
   trailing 3/6-month weekday-normalized rates → `staffing_rate_volatility` warning when divergent.
5. **Revalidation** (`frequency_revalidation`): recent `cadence_change_recent_months` vs overall cadence;
   surfaces `cadence_change_detected` and updates the advisory effective class (staffing override wins).
6. **Phasing** (`monthly_frequency_phasing`, the shared logic): cadence → normalized monthly weight
   vector (weekday-normalized for staffing/weekly; even for monthly/twice; none otherwise). Staffing raw
   projection (`daily_rate × weekdays`) is scaled to accepted CTC, preserving the weekday shape — proving
   the projection never changes final cost.
7. **Validate + package** (`validation`, `generate_forecast_cost_frequency_package`): fail-closed gates,
   determinism self-check, manifest (`contract_version`), source-hash no-mutation proof, safety scan.

## Monthly integration (shared logic, enabled)

`forecast_monthly/frequency_phasing.py` imports the same pure functions and returns the established
`(row, weight_vector_or_None, confidence)` evidence contract. `monthly_reconcile.reconcile_code` gained
trailing keyword params `frequency_weights` / `frequency_confidence`: a `FREQUENCY_FACTOR` share is
carved from the post-schedule residual (staffing weekday cadence is the **primary** timing basis for
staffing codes), blended into the month weights, and exposed as `source_shares.frequency_weight`. The
`_allocate` step still scales the blended shape to exactly the cost-to-complete, so `Σ month_cost == CTC`
and `actual + Σ == final` hold and the accepted final cost is unchanged. Gated by
`forecast_cost_frequency.forecast_monthly_integration_enabled` (reversible). `audit/cadence_reconciliation_proof.json`
asserts per project: all codes reconcile, and accepted final cost equals the accepted-intelligence final
cost per code (cadence reshapes months only). The integration is conservative — only weekday cadence
(staffing + observed weekly) contributes a vector; other codes defer to existing timing sources.

## Module map

| Module | Responsibility |
|---|---|
| `frequency_io.py` | Discover + load inputs (read-only); derive deterministic window; group transaction dates; pre-run source hashes. |
| `staffing_codes.py` | Configured weekly-staffing recognition + policy census + staff-change-event placeholder. |
| `weekday_calendar.py` | Mon-Fri counts + normalized weekday weight vector + month math (self-contained; no forecast_monthly import). |
| `frequency_detect.py` | Cadence classification from entry counts + spacing; fallback handling; observation rows. |
| `daily_rate.py` | Staffing weekday-normalized daily rate from latest complete month; trailing comparison + volatility. |
| `frequency_revalidation.py` | Recent-vs-overall cadence change detection; staffing override. |
| `monthly_frequency_phasing.py` | **Shared** cadence→weight-vector + staffing projection + scale-to-CTC (used by the slice and forecast_monthly). |
| `validation.py` | Fail-closed gates. |
| `generate_forecast_cost_frequency_package.py` | Orchestrator: collections, determinism self-check, audit/meta/README/SCHEMA, safety, manifest, package contract. |
| `forecast_monthly/frequency_phasing.py` | Adapter that imports the shared logic into the monthly model. |

## Contract for `forecast_comprehensive`

`project_cost_frequency_summary.json` → `package_contract` (`contract_version`, `consumable_by:
forecast_comprehensive`, `primary_artifacts`, `phasing_weight_key`, `effective_class_field`,
`timing_only_guarantee`). A consumer reads `effective_frequency_class` from
`cost_frequency_by_budget_code.jsonl` and the normalized `monthly_phasing_weights` from
`frequency_adjusted_monthly_phasing_by_budget_code.jsonl`, plus staffing daily rates and the weekday
calendar. Every phasing row carries `do_not_change_accepted_final_cost == true`.

## Posture / guardrails

CostEntries are the only actual-cost source; cadence never becomes an actual and never changes any
accepted final cost (timing/shape only, CTC-reconciled). No source / accepted package / SQLite / Excel
mutation; no live external calls (localhost Ollama only, advisory non-numeric, excluded from
determinism). Deterministic: same frozen stamp + data-derived window ⇒ byte-identical quantitative core.
