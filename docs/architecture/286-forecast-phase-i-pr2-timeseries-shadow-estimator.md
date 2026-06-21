# ADR 286 — Forecast Phase I PR 2: time-series shadow estimator

- **Status:** Accepted
- **Date:** 2026-06-21
- **Phase:** Forecast model-engines (Phase I), PR 2 of N
- **Builds on:** ADR 285 (PR 1 readiness, PR #76). End-goal: a time-series estimator as a weighted
  member of the forecast_intelligence EAC ensemble.

## Context

PR 1 produced read-only evidence that the tropical data is READY for a time-series estimator. The
end-goal is a 7th **weighted** estimator in `forecast_intelligence` (`INDEPENDENT_METHODS` +
`reconcile_final`). PR 2 takes the low-risk first step: add the estimator as a **shadow/reference**
— computed, emitted, and backtested, but **never weighted**, so it changes **zero** central forecast
values. This mirrors the existing `erp_projected_reference` / `erp_eac_reference` estimators (in
`ALL_ESTIMATORS`, not in `INDEPENDENT_METHODS`). Promotion is PR 3, gated on the backtest here.

### Backend decision (changed from the plan)

The plan called for `statsforecast`. It **cannot install on the project's Python 3.14**: statsforecast
2.0.3 pins `scipy<1.16`, but scipy ships 3.14 wheels only from 1.16+, so it tries to build scipy 1.15
from source (needs gfortran) and would downgrade the shared venv's scipy 1.17. Decision: implement the
same robust ensemble in **pure numpy** (already a CFR dependency) behind an isolated engine seam —
**no new dependency**. A statsforecast (or other) backend can replace the engine later without
touching the estimator/audit callers.

## Decision

- **`forecast_intelligence/timeseries_engine.py`** (new) — `forecast_etc(monthly, horizon)`: a
  median ensemble of **naive + drift + Holt-linear + theta-like** (fixed smoothing params, no
  optimizer, no RNG), with a **naive+drift-only** path when `< 6` observations. Pure numpy float64;
  deterministic and isolated. `BACKEND_LABEL = "classical_ensemble_v1"`.
- **`estimators_uncapped.timeseries_eac(b)`** (new) — reads the completed monthly series + remaining
  horizon (same precedence as `trend_projection_eac`), calls the engine, EAC quantized to Decimal
  cents and floored to actuals via `_norm` (extended with a `source` kwarg → `"shadow_timeseries"`).
  Applicable only at `≥ 3` completed months and `horizon > 0`. **Appended to `ALL_ESTIMATORS`; NOT in
  `INDEPENDENT_METHODS`.** `METHOD_FAMILY["timeseries_eac"] = "timeseries"` (forward-use).
- **`evidence.assemble_evidence`** threads `monthly_actuals_completed` (CostEntries `through_may_2026`,
  sorted) into the bundle.
- **`generate_forecast_intelligence_package`** emits two evidence artifacts (deterministic,
  frozen-stamp): `statsforecast_shadow_comparison.jsonl` (per-code `timeseries_eac` vs the central
  `recommended_final_cost`) and `audit/statsforecast_shadow_backtest.json` (holdout: fit on the
  prefix, predict the last h months, score vs a naive baseline; aggregate MAPE + win-rate). This is
  the promotion evidence for PR 3.

## Invariants

- **Shadow:** `timeseries_eac` is absent from every `reconciliation_basis` / `contributions`; the
  central forecast is byte-identical to pre-PR. Proven by `test_fi_timeseries_shadow`.
- **Deterministic:** fixed params, no RNG, single-threaded, cent-quantized. `test_fi_e2e`
  `test_deterministic_mock_output` still byte-identical.
- **Uncapped + floored:** the shadow estimate obeys the actuals floor like any estimate
  (`every_estimate_geq_actuals` gate still passes).

## Validation

- CFR suite **598 passed** (588 + 10 new); `test_fi_e2e`/`test_fi_estimators_uncapped`/`test_fi_backtest`
  green. New `test_fi_timeseries_engine` (7) + `test_fi_timeseries_shadow` (3, on real data).
- mypy: new engine clean; **zero new errors** vs the origin/main baseline on the edited files. CFR is
  not ruff-gated (large pre-existing baseline); new files are ruff-clean; pre-existing files not
  reformatted.

## NOT in this PR

`timeseries_eac` is not weighted; no central-forecast/recommendation change; no calibration weight;
no `reconcile_final` weighting-logic change; no schema/migrator change; no `hb_assistant` edit; no
live write.

## Deferred to PR 3 (promotion)

Add `timeseries_eac` to `INDEPENDENT_METHODS` + `backtest_strong.METHODS`/`_predict` (calibration
weight) with a reliability mapping — **gated on this PR's holdout backtest beating the naive
baseline**. That PR changes central forecast values and carries its own before/after evidence. A
statsforecast backend may also be swapped into `timeseries_engine` once 3.14-compatible.

> Note: the two shadow artifacts keep the `statsforecast_shadow_*` filenames for continuity with the
> Phase I narrative and PR 3; the current backend is the classical numpy ensemble (`classical_ensemble_v1`),
> recorded in each artifact's `backend` field.
