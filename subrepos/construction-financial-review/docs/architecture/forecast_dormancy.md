# Forecast Dormancy / Closed-Code Suppression

`forecast_dormancy` is a deterministic layer that decides, **before** any monthly phasing / model shape /
S-curve / history / frequency / schedule allocation runs, whether a canonical `budget_code_key` is still
forecastable. Codes that are `CLOSED - DO NOT USE`, or idle past a trailing window (default 18 months)
with no affirmative remaining-cost evidence, have their remaining forecast **suppressed**: CTC = 0, future
months = 0, final = actual cost to date.

> This is a **trend/inactivity conclusion, not a budget cap.** Actual cost to date is never reduced and
> the final forecast never falls below actuals. Suppression is overridden only by affirmative remaining
> evidence or a **value-asserting** accepted operator model control.

## Why

The model forecast was inventing future cost for `CLOSED - DO NOT USE` codes with no incurred cost for
18–20 months (e.g. `0000.03-01-413.LAB`: 19 months idle, 0 committed, yet ~$186k future CTC, 146% over
budget). Generic phasing/shapes were applied without first asking whether the code is forecastable. Shape
controls should only **distribute a validated remaining amount** — they must not **create** it.

## Statuses (`forecast_dormancy/classify.py`)

`active_forecastable`, `active_with_remaining_evidence`, `operator_controlled`, `closed_do_not_use`,
`inactive_no_remaining_evidence`, `dormant_no_recent_cost`, `recent_zero_run_after_prior_activity`. The
last four suppress.

## Recent-zero-run suppression (staffing / general-conditions)

Beyond long-idle closed codes, active **staffing / general-conditions** codes can stop: prior cost
activity, then a short trailing run of zero-cost months, yet the model resumes future dollars (e.g. the
SUPERINTENDENT 1 codes `1000.10-01-312.LAB/.LBN/.MAT` — last actual 2026-02, 4-month zero run, no
commitment, no staffing-plan assignment, ~$74k/$18.7k/$3.7k future CTC). `recent_zero_run_after_prior_activity`
treats the zero run as a stopped cost stream and suppresses (CTC 0 / final = actual) at a low threshold.

- **Staffing/GC detection** (`_is_staffing_or_gc`, category-aware): the staffing code list
  (`forecast_cost_frequency.weekly_internal_staffing_budget_code_keys`); OR for LAB/LBN, cost-code family
  in `staffing_general_conditions_cost_code_families` (10-01 = General Conditions) **or** a staffing/GC
  description term; OR for any other category (e.g. MAT), family **and** a staffing/GC description term (or
  a staffing-plan assignment) — **family alone is never enough** for a material code, so generic GC
  materials (temp fencing/power) are not suppressed.
- **Thresholds:** staffing/GC `trailing_zero_month_threshold` (default 3). The **non-staffing arm is
  disabled by default** this slice — a non-staffing code matching the pattern (idle ≥ the non-staffing
  threshold, default 6) is NOT suppressed; it emits advisory evidence only
  (`non_staffing_suppression_candidate = true`, `suppression_reason = non_staffing_recent_zero_run_advisory_only`,
  conflict class `non_staffing_recent_zero_run_advisory`).
- **Recent actual cost** is evaluated against the staffing zero-run threshold for an active staffing/GC
  code (so idle past that short window counts as stopped) and against the long lookback otherwise (so a
  closed code paid within the lookback stays active) — and it is checked **before** closure, so a
  recently-paid code is never suppressed.
- **Override:** an active **staffing-plan future assignment** (`plan_implied_remaining_cost > 0`, loaded in
  intelligence via `forecast_staffing_plan.integration.prepare`) is affirmative remaining evidence ⇒
  `active_with_remaining_evidence` (not suppressed). A value-asserting accepted operator model control
  revives; shape/window/timing-only controls do not.
- **Gate:** `no_positive_forecast_for_recent_zero_run_without_evidence`.

## Precedence (contrary evidence overrides closure)

1. **value-asserting** accepted operator model control (`changes_deterministic_final` **and**
   `controlled_remaining > 0`) → `operator_controlled` (revived). **Shape/window/timing-only controls
   never revive a dormant code** — they only distribute a validated remaining amount.
2. recent actual cost (`months_since_last_actual < lookback`) → `active_forecastable`.
3. affirmative remaining evidence (open commitment remaining `committed - invoiced > $0.01`; owner/sub
   pay-app activity within lookback; mapped `material_remaining_work` / open activities with a future
   finish) → `active_with_remaining_evidence`.
4. closure phrase detected → `closed_do_not_use` (suppress).
5. never incurred cost & no evidence → `inactive_no_remaining_evidence` (suppress).
6. idle ≥ lookback & no evidence → `dormant_no_recent_cost` (suppress).

`months_since_last_actual` is measured to the current **forecast** month (e.g. `forecast_period`
`2026-June` → `2026-06`), not the schedule `data_date`.

## Closure detection (strict, avoids false positives)

Strong patterns (`CLOSED - DO NOT USE`, `DO NOT USE`, `INACTIVE`) match the normalized description blob.
Bare `CLOSED` counts only when it is status-like (the whole `sub_job_description`, or a standalone token /
prefix there) — never an arbitrary substring like "closed cell insulation".

## Single source of truth

The authoritative decision is computed **once** in `forecast_intelligence` (per-code, around
`reconcile_final.select_final`) and emitted as `dormant_code_status_by_budget_code.jsonl` +
`audit/dormant_code_suppression_audit.json`. The intelligence recommendation is suppressed in place (CTC 0
/ final = actual). Downstream consumers **enforce** that decision defensively but never invent a
conflicting classification.

## Downstream enforcement

- **forecast_monthly** — reads the status file; the suppressed rec (CTC 0) drives every allocator to 0;
  rows disclose `dormant_status`; `audit/dormant_code_suppression_applied.json`; gate
  `dormant_suppressed_future_months_zero`.
- **forecast_comprehensive** — `evidence_registry` loads `per_code[key]["dormant"]`; `intelligence_consumer`
  forces `integrated_final = actual`, `integrated_ctc = 0` (the history blend cannot re-inflate);
  `monthly_consumer` reconciles to 0; `probability_consumer` emits a degenerate `dormant_suppressed` row
  (`integrated_p10..p95 = actual`, no broad risk distribution); `conflicts` emit the dormant review classes;
  `validation` gates `dormant_suppressed_integrated_final_equals_actual` /
  `dormant_suppressed_probability_marked`. A value-asserting operator model control overrides at the
  consumer (`operator_control_override`); shape/window/timing-only controls do not.
- **forecast_actuals** — combined actuals+forecast CSV future months are 0 for dormant codes (integrated
  monthly is 0), so the row sums to actual cost to date = final.

## Conflict / review classes

`closed_code_forecast_suppressed`, `dormant_code_model_forecast_suppressed`,
`dormant_code_overridden_by_operator_control`, `closed_code_has_positive_forecast_without_operator_acceptance`,
`dormant_code_has_positive_forecast_without_remaining_evidence`, `dormant_code_has_open_commitment_remaining`,
`dormant_code_has_future_schedule_evidence`.

## Validation gates (fail closed)

Intelligence: `dormant_suppressed_ctc_zero`, `dormant_suppressed_final_equals_actual`,
`dormant_suppression_did_not_change_actuals`, `dormant_suppressed_final_not_below_actuals`,
`no_positive_forecast_for_closed_without_evidence`. Monthly: `dormant_suppressed_future_months_zero`.
Comprehensive: `dormant_suppressed_integrated_final_equals_actual`, `dormant_suppressed_probability_marked`.

## Config — `config/projects/tropical.json` → `dormant_code_suppression`

`enabled` (true), `lookback_months_without_actual_cost` (18), `closed_description_patterns`,
`closed_bare_token_status_fields`, `require_affirmative_remaining_evidence`,
`fail_on_positive_forecast_for_closed_code_without_evidence`, `allow_operator_control_override`,
`operator_override_requires_positive_asserted_remaining`. `enabled:true` is intentional — it corrects the
real closed-code overruns; suppression sets final = actual (= revised = projected for these codes), never
below actuals.

## Verified example codes

`0000.03-01-025.MAT` (20 mo idle), `0000.03-01-413.LAB` (19), `0000.03-01-413.LBN` (19),
`0000.03-01-413.MAT` (18) — all `closed_do_not_use`, CTC 0, final = actual to date.

See `docs/architecture/forecast_model_controls.md` for the operator-control override precedence.
