# Real statsforecast shadow evidence — isolated 3.12 runtime (2026-06-21)

Go/no-go evidence for promoting `timeseries_eac` into the weighted ensemble, now using the **real
statsforecast** backend via the isolated Python 3.12 runtime (ADR 287). Read-only on the 3.14 side;
the central forecast is unchanged (shadow estimator).

- Runtime: isolated `~/Library/Application Support/HB Model Engine/.venv-3.12` — statsforecast 2.0.3,
  scipy 1.15.3, numba 0.65.1, pandas 2.3.3. Invoked via subprocess/JSON; **statsforecast never enters
  the 3.14 core**.
- Models: AutoETS + AutoTheta + AutoARIMA (median) at ≥6 obs, else Naive + Drift. `frozen_stamp` run;
  two runs produced **byte-identical** backtests (deterministic).

## Result — real statsforecast does NOT beat naive (do NOT promote)

| Metric (79 eligible codes) | statsforecast | naive baseline | classical (PR 2) |
|----------------------------|---------------|----------------|------------------|
| Median abs % error         | **0.7030**    | **0.5042**     | 0.5514           |
| Engine ≥ naive (win/tie)   | **40 / 79 (50.6%)** | —        | 49.4%            |

Real statsforecast is **worse** than a naive last-month baseline on tropical's short, noisy monthly
burn — and worse than the classical ensemble. This confirms the PR 2 finding with the real backend:
**time-series modeling does not add value over naive here.**

**Recommendation: do NOT promote `timeseries_eac` to `INDEPENDENT_METHODS`.** Keep it shadow-only.
The value delivered: the isolated-runtime architecture answered the statsforecast question
definitively with zero forecast risk. If revisited later, more productive directions than raw
monthly-burn extrapolation: longer/standardized history, per-code model selection gated on
historical accuracy, or driver-based (schedule/commitment) features — each re-checkable through this
same shadow harness.

## Files
- `statsforecast_shadow_backtest.json` — holdout accuracy (statsforecast vs naive), per code + aggregate.
- `statsforecast_shadow_comparison.jsonl` — per-code statsforecast EAC vs the central recommended final cost.
