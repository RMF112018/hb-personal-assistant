# Forecast Controls — Architecture

## Purpose

An operator-controlled, human-accepted, auditable constraint layer over the forecast model. It lets the
operator set per-code forecast **stop dates / closeout windows** and accepted **remaining-cost /
final-cost allowances** *before* monthly and comprehensive generation, so substantially-complete codes
stop carrying model forecast through the final month.

Motivating case: Roofing `15-07-590` (`1000.15-07-590.SUB`) is all but complete (only minor punchlist
remains), yet the model carries a large remaining cost-to-complete. A stop-date control concentrates the
allowed remaining cost into the closeout window and zeroes later months.

## Posture (hard guardrails)

- CostEntries/Sage incurred cost is accounting truth; **actual cost to date is the only hard floor**.
- Controls are explicit operator decisions (source, reason, acceptance metadata) — **never model truth**.
- **No source Excel / accepted package / SQLite mutation; no live external calls.**
- **No hidden caps.** Any dollar change is tied to an explicit *accepted* operator control. A stop-date
  control without an accepted amount only redistributes the existing model cost-to-complete through the
  stop window and flags the dollar total as still model-derived.
- Posture-changing controls (post-stop zeroing, dollar changes) apply **only when human-accepted**
  (config-gated). Pending controls surface in the review queue without changing the forecast.

## Control file

Project-level JSONL, in-repo and version-controlled:

```
config/forecast_controls/tropical/code_forecast_controls.jsonl
```

One row per operator decision. Required identity + human-acceptance fields; money fields are
Decimal-strings (2dp) or null. `created_at` / `accepted_at` are stamped deterministically from the
package stamp when left null. Control types:

| type | effect | requires accepted |
| --- | --- | --- |
| `closeout_stop_date`, `forecast_stop_date`, `inactive_after_date` | zero months after the stop month; redistribute allowed remaining cost | yes (post-stop zero) |
| `remaining_cost_allowance` | set integrated remaining cost to the accepted amount (≥ actuals floor) | yes |
| `accepted_final_cost_override` | set integrated final cost to the accepted amount (≥ actuals floor) | yes |
| `monthly_distribution_override` | reshape monthly timing | yes |
| `watch_only` | monitor only; no forecast change | n/a |

## Module layout (`src/construction_financial_review/forecast_controls/`)

- `control_schema.py` — control types, canonical field order, `normalize_control`, posture/stop/dollar helpers.
- `load_controls.py` — resolve path from config; fail-closed JSONL parse; duplicate-id + required-field detection.
- `mapping.py` — map controls to canonical budget codes (explicit must be canonical; cost-code resolves only when unique; else ambiguous/invented).
- `apply.py` — `resolve` (precedence accepted > pending → per-key applied decisions, application/queue/warning rows, floor + superseded records) and `reshape_reconcile` / `restrict_weights` / `effective_ctc` (monthly reshaping reused by both integrations).
- `integration.py` — `prepare` (load → map → resolve) + `assert_integration_safe` (fail-closed gate) imported by monthly and comprehensive.
- `generate_forecast_controls_package.py` — standalone package generator (deterministic, audited).
- `validation.py` — fail-closed gates for the standalone package.

## How controls reach the forecasts

`forecast_monthly` and `forecast_comprehensive` import `forecast_controls.integration` and read the
control file **directly** (it is a deterministic, always-present config file) rather than discovering a
generated package — so integration is order-independent. The standalone `forecast-controls` package is
the human-facing audit/review artifact, built from the same resolver.

- **Monthly** (`generate_monthly_forecast_package.py`): after `monthly_reconcile.reconcile_code`, an
  applied *timing* decision reshapes `month_costs` via `reshape_reconcile` (zero post-stop months,
  redistribute CTC, reconcile to CTC/final). `audit/forecast_controls_applied.json` records what was
  applied. Dollar overrides flow through the controls/comprehensive layer, not monthly.
- **Comprehensive** (`generate_comprehensive_forecast_package.py`): controls become the
  `operator_forecast_control` evidence family (independence group `operator_control`); `monthly_consumer`
  restricts integrated monthly weights to the allowed window; `intelligence_consumer` applies accepted
  dollar overrides (floored at actuals); `conflicts.py` adds five operator-control conflict classes.

## Precedence + proration

- When multiple controls target one budget code, the **accepted** control is applied and pending controls
  are recorded as `superseded_by` it (latest `control_id` wins within a tier). This is deterministic.
- Stop dates use **month-level proration** with `stop_date_post_month_policy = zero_after_stop_month`: the
  month containing the stop date is kept; months strictly after it are zeroed. (Day-level proration is not
  implemented; the current-month day-aware partial from `forecast_monthly/calendar.py` still applies.)

## Configuration (`config/projects/tropical.json` → `forecast_controls`)

```json
{
  "enabled": true,
  "control_file": "config/forecast_controls/tropical/code_forecast_controls.jsonl",
  "require_accepted_status_for_final_cost_change": true,
  "require_accepted_status_for_post_stop_zero": true,
  "allow_pending_controls_in_review_queue": true,
  "allow_pending_timing_controls": false,
  "default_month_proration_policy": "month_level",
  "stop_date_post_month_policy": "zero_after_stop_month",
  "fail_on_ambiguous_cost_code": true,
  "preserve_actuals_floor": true
}
```

## Outputs (`forecast_controls_package_tropical_<stamp>/`)

`forecast_controls_by_budget_code.jsonl`, `forecast_controls_application_by_budget_code.jsonl`,
`forecast_controls_monthly_adjustments_by_budget_code.jsonl`, `forecast_controls_review_queue.jsonl`,
`forecast_controls_warnings.jsonl`, `project_forecast_controls_summary.json`,
`audit/{control_mapping_audit,control_application_audit,actuals_floor_audit,no_hidden_cap_audit,
source_hashes_before_after,safety_scan_report}.json`, plus `README.md`, `SCHEMA.md`, `manifest.json`,
`input_inventory.json`, `validation_report.json`.

## Fail-closed validation gates

Control file unparseable; duplicate `control_id`; ambiguous mapping; invented `budget_code_key`; accepted
final/remaining below actuals; nonzero forecast after an accepted stop; hidden cap without an accepted
control; monthly adjustments not reconciling; missing human-acceptance fields; missing application
lineage; source hashes changed; safety scan fail. `integration.assert_integration_safe` raises before
monthly/comprehensive generation when any of these would make integration unsafe.

## Determinism

Same frozen stamp + same inputs ⇒ byte-identical quantitative core + audits (tempdir rebuild + SHA-256
compare). Controls are static config, so resolution is a pure function of the inputs.
