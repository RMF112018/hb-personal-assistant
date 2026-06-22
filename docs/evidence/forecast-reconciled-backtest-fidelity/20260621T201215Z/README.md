# Reconciled-backtest fidelity upgrade — live confirm (2026-06-21)

Re-measures the production reconciled forecast's accuracy with a **faithful** as-of reconstruction:
real per-method reliabilities (estimators_uncapped rules) + the real trend signal (trend.analyze on
the as-of-truncated series), replacing the earlier uniform-"medium" reliability + neutral trend.
Evidence-only; production forecast unchanged (`_P75_STAGE_GATE` still off).

## Headline: the over-forecast is REAL, not a measurement artifact

| Metric (near-complete cohort, 10 codes / 29 obs) | Approximate (PR#79/#80) | **Faithful (this PR)** |
|---|---|---|
| Baseline reconciled MAPE | 0.4125 | **0.4102** |
| Baseline mean bias | +0.3296 | **+0.3348** |
| Worst-case ceiling coverage | 0.8966 | 0.8966 |
| Stage-gate recalibrated MAPE | 0.3204 | **0.3048** |
| Stage-gate improvement | −0.0922 | **−0.1055 (~26%)** |
| Per-target baseline (40/60/80%) | 0.595/0.364/0.264 | **0.598/0.362/0.254** |
| Per-target recalibrated | 0.428/0.264/0.264 | **0.410/0.245/0.254** |
| Best single method (commitment-exposure) | 0.0739 | 0.0739 |
| Naive "trust ERP" | 0.0526 | 0.0526 |

**Conclusion:** using the *real* production reliabilities + trend signal yields essentially the same
result as the approximation — the reconciled forecast genuinely over-forecasts early (~+33% bias, MAPE
0.41), far worse than commitment-exposure alone (0.07) or naive ERP (0.05). The earlier hypothesis
that uniform-"medium" reliability inflated the finding is **refuted**. The accuracy decisions are now
on trustworthy numbers.

## What this unblocks (recommended next, on faithful evidence)
1. **Flip `_P75_STAGE_GATE` on** — the faithful stage-gate cuts MAPE ~26% (0.41→0.30), bias +0.33→+0.22,
   ceiling held; `recalibration_recommended: True`. (Separate PR: changes operator values for
   low-completion overrun codes; update value-goldens.)
2. **Add completion-stage reliability damping** for the residual (still 0.30, worse than ERP), now
   justified — re-measure through this same gate.

## Files
- `reconciled_forecast_backtest.json` — faithful baseline + recalibrated, per-code/target.
- `forecast_accuracy_gate_report.json` — verdict (not_ready, baseline) + recalibration_effect.
