# ADR 285 — Forecast Phase I PR 1: model-engines data + semantic readiness evidence

- **Status:** Accepted
- **Date:** 2026-06-21
- **Phase:** Forecast model-engines (Phase I), PR 1 of N
- **Builds on:** ADR 258–284 (Phases 2–20 + UI DB-config + live promotion); the forecasting semantic
  layer already on `main` (`src/hb_assistant/forecasting/`, `docs/forecasting/semantic-catalog/`) and
  the `docs/evidence/forecasting-db-audit-20260621/` bundle.

## Context

The end-goal of Phase I is to bring a real `statsforecast` time-series model (AutoARIMA / ETS / Theta)
into the forecast as a **7th estimator** wired into the existing six-estimator EAC ensemble
(`forecast_intelligence/estimators_uncapped.py` `INDEPENDENT_METHODS` + `reconcile_final.py`). That
work adds a heavy dependency (`statsforecast` pulls `numba`/`pandas`) and changes forecast math — both
are **deferred**. CFR convention requires a *readiness evidence bundle before code*.

This PR ships that readiness bundle. It must answer **two** questions for the tropical project, and
must not treat the CFR context package as the only source of truth — it reconciles against the
forecasting semantic catalog + gates already built in the main repo:

1. **Time-series sufficiency** — does the per-code monthly actual history support a future
   statsforecast estimator (enough completed months, clean enough series)?
2. **Semantic safety** — are the monthly actuals + budget-code denominators safe to feed a model
   engine under the semantic catalog + gate rules (actuals precedence, ERP sidecar, double-count,
   projection parity, budget column roles, dynamic columns)?

### Repo-truth note

The forecasting semantic layer was initially mistaken for "missing" because the working checkout sat
on a pre-merge feature branch. Verified: `origin/main` carries the full layer (gates, readiness,
catalog, validation queries, tests). This PR is therefore based on `origin/main` and the
`feature/forecasting-db-audit-20260621` branch is **not** merged (it is behind main, missing PR #74/#75).

## Decision

Add a read-only CFR workflow `workflows/model_engines_readiness.py` + a `model-engines-readiness` CLI
command. It reads an EXISTING context package (`canonical/monthly_actuals_by_budget_code.jsonl` for
the time-series; `canonical/budget_codes.jsonl` for the coverage denominator) and runs the
hb_assistant forecasting semantic gates against an operator-supplied `--db-path` read-only.

- **Time-series half (pure CFR/stdlib):** per-code completed-month counting bucketed on the row's own
  `actual_period_bucket == "through_may_2026"` (deterministic; never a wall clock). Tiers 3/6/12
  deliberately match the existing `trend_projection_eac` gates. Data-quality flags: `all_zero`,
  `negative_or_credit_months`, `single_spike`, `has_gaps`, `short_history`, `source_contamination`.
  Eligibility excludes all-zero / single-spike / too-short / contaminated; negatives and interior gaps
  are reported but do not disqualify.
- **Semantic half (lazy, fail-closed):** calls
  `hb_assistant.forecasting.readiness.evaluate_forecast_semantic_gates(db_path, mode)` (the 5 gates:
  double-count, actuals-reconciliation, projection-parity, budget-dynamic-columns, cost-type-guard).
  If the layer is unavailable or the gate call fails, the section is recorded `not_available` and a
  READY decision is blocked — never silently passed.
- **Coverage:** code-coverage (eligible / total) and dollar-coverage (eligible CTC / total CTC).
  Cumulative actual is derived from the CostEntries monthly series itself (`through_may_2026` +
  `june_2026_to_date`) — precedence #1 (`forecast_monthly_actuals_by_budget_code`), which sidesteps
  the 100%-null `actual_cost`. `projected_costs` is used **only** as a coverage-denominator scale.

### Decision rule (deterministic)

```
semantic_hard_fail = gate error_count > 0  OR  gates not_available
no completed actuals                          -> not_ready
semantic_hard_fail                            -> not_ready (record readiness_blockers)
code_cov >= 0.30 AND dollar_cov >= 0.50       -> model_engines_data_ready (gate warnings carried)
code_cov >= 0.05 OR  dollar_cov >= 0.05       -> model_engines_data_insufficient
otherwise                                     -> not_ready
```

Gate **warnings** (and the known projection-parity limits — RFQ scope mismatch, prime change-order
line-item fan-out) are carried into `readiness_warnings` and never block READY. Gate **errors** and
gates-not-available block READY (cannot certify semantic safety).

## Semantic rules honored

- `actual_cost` is 100% null on the live copy → never a basis. Cumulative-actual basis is
  CostEntries monthly to date; the DB semantic cumulative basis is `job_to_date_costs` (primary when
  `actual_cost` null). ERP (`erp_direct_costs`/`erp_job_to_date_costs`) is `explicit_sidecar` —
  compare-only, never substituted/summed (`erp_basis_handling`).
- Invoice/progress, monthly actuals, payment/cash-flow, and cumulative-budget facts stay distinct
  (never summed).
- Terminal/calculated budget columns are reference-only, never features (`budget_column_role_policy`).
- Unmapped dynamic budget columns are `review_required`, never auto-eligible
  (`dynamic_budget_column_policy`; enforced by the budget-dynamic-columns gate).

## Report

Deterministic, sorted-key JSON under `<work_root>/model_engines_readiness/`. Fields:
`decision`/`status`, `semantic_catalog_version`, `actuals_basis_used`, `actuals_basis_caveats`,
`erp_basis_handling`, `budget_column_role_policy`, `dynamic_budget_column_policy`,
`forecast_gate_summary`, `projection_parity_summary`, `double_count_risk_summary`,
`readiness_blockers`, `readiness_warnings`, `statsforecast_candidate_code_count`,
`statsforecast_candidate_dollar_coverage`, `fallback_to_existing_ensemble_count`, `inputs` (+sha256),
`thresholds`, `aggregate` (+ histogram), `coverage`, `data_quality`, `per_code`, and a `deferral`
block asserting no dependency / no core edit / no schema change / no hb_forecasting edit / no live write.

## Module layout

- `subrepos/.../workflows/model_engines_readiness.py` — the workflow.
- `subrepos/.../cli.py` — `cmd_model_engines_readiness` + `model-engines-readiness` subparser + dispatch
  (rc 0 ready / 1 insufficient|not-ready / 3 controlled refusal).
- `subrepos/.../tests/test_model_engines_readiness.py` — 23 pure-CFR unit tests (synthetic fixtures +
  injected fake gate fn).
- `tests/test_forecast_model_engines_readiness_phase_i_pr1.py` — repo-root CLI wiring test against the
  real hb_assistant gates with a hermetic empty SQLite (empty DB ⇒ all gates pass).

## Consequences / NOT in this PR

No `statsforecast`/any dependency; `INDEPENDENT_METHODS` stays a 6-tuple and `reconcile_final` is
untouched; no forecast-math change; no schema/migrator change; nothing under
`src/hb_assistant/forecasting/*` is edited (consumed only); no package generation, LLM, or network;
no live-root or live-DB write (DB read-only). A NOT_READY / INSUFFICIENT outcome is a legitimate
finding that would re-scope or cancel the statsforecast PR.

## Validation

CFR suite 588 passed (565 + 23). Repo-root `test_forecasting_gates`/`test_forecasting_readiness` +
the new wiring test green. ruff check + format + mypy clean on the new module.

## Deferred

PR 2+: add `statsforecast`, build `statsforecast_projected_eac`, wire it as the 7th member of
`INDEPENDENT_METHODS` + `reconcile_final` with its own gating/calibration — gated on this report
showing READY (time-series-sufficient AND semantically safe) on real data.
