# Production-forecast accuracy / trust gate — live evidence (2026-06-21)

First measurement of whether the **production reconciled forecast** (`recommended_final_cost`) is
accurate vs realized actuals. The reconciled as-of backtest (ADR 288) reconstructs each near-complete
code at 40/60/80% owner progress, blends the as-of per-method EACs through the real
`reconcile_final.select_final`, and scores the result; the gate applies thresholds → verdict.

## Verdict: `not_ready` (rc 1)

| Metric (near-complete cohort) | Value |
|-------------------------------|-------|
| Cohort / observations | 10 codes / 29 |
| Reconciled forecast MAPE | **0.4125** |
| Reconciled mean bias | **+0.3296** (systematic over-forecast) |
| Worst-case ceiling coverage | 0.8966 |
| Best single method (commitment-exposure) MAPE | **0.0739** |
| Blend − best method | **+0.3386** (blend much worse) |
| Naive "trust ERP" MAPE | **0.0526** |
| Reconciled − naive(ERP) | **+0.3600** (blend much worse) |
| Per-target MAPE | 40% → 0.5951, 60% → 0.3635, 80% → 0.2642 |

**Finding:** the reconciled production forecast, reconstructed early, **over-forecasts by ~33% and is
far less accurate than both the best single method (commitment-exposure, 7%) and simply trusting the
ERP projected cost (5%)**. Accuracy improves toward completion (59% → 26% from 40% → 80%) but never
approaches ERP. The over-bias is driven partly by the overrun-protection p75 path inflating
early-stage forecasts.

**Subject to the reconstruction-fidelity caveats** (uniform reliability; neutral trend; approximate
as-of bundle — see `reconstruction_fidelity_caveats` in the artifacts), this is a genuine
production-readiness signal: **the early-stage reconciled forecast should not be certified as-is.**

## Recommended follow-ups (re-measurable through this gate)
- Re-weight toward ERP / commitment-floor at low completion; temper the p75 overrun bump early; or
  gate the reconciliation by completion stage.
- Build a higher-fidelity as-of reconstruction (full signal bundle) to confirm the magnitude.
- Widen the cohort as more codes complete (only 10 near-complete today).

## Files
- `reconciled_forecast_backtest.json` — per-code/target scoring + aggregate (emitted by every forecast-intelligence run).
- `forecast_accuracy_gate_report.json` — the verdict + thresholds + metrics.
