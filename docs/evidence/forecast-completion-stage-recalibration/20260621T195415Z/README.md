# Completion-stage recalibration — live confirm (2026-06-21)

Confirms the completion-stage p75 stage-gate (ADR 289) against the accuracy gate (ADR 288) on real
tropical data. The recalibration is **opt-in and ships default-OFF** — production forecast values are
unchanged; this measures what flipping it on would buy.

## Result — the stage-gate materially reduces early over-forecast, ceiling intact

| Metric (near-complete cohort, 29 obs) | Baseline (production, flag-off) | Recalibrated (stage-gate on) |
|---|---|---|
| Reconciled MAPE | 0.4125 | **0.3204** (−0.0922, −22%) |
| Mean bias | +0.3296 | **+0.2374** (−0.0922) |
| Worst-case ceiling coverage | 0.8966 | 0.8966 (held) |
| Per-target MAPE (40/60/80%) | 0.595 / 0.364 / 0.264 | **0.428 / 0.264 / 0.264** |

`recalibration_recommended: True`. The gate verdict stays **not_ready** (it reports the baseline =
production behavior with the flag off).

**Reading:** stage-gating the p75 overrun bump cuts the early-stage (40/60%) over-forecast substantially
and leaves high completion (80%) and the worst-case ceiling untouched — doctrine-safe (no ERP anchor,
overruns not suppressed). It is **not a full fix**: the recalibrated forecast still over-forecasts
(+24% bias, MAPE 0.32 > the 0.30 fail bar) and remains worse than naive ERP (~0.05), because the
residual `weighted_mean` of early-overshooting methods is still high. That points to a follow-up lever
(e.g. completion-stage reliability damping of the overshooting methods), measurable through this same
gate. Subject to the reconstruction-fidelity caveats in the artifacts.

## Recommended next step
Flip `_P75_STAGE_GATE` on (one line, separate PR) to bank this improvement, AND/OR add a second
completion-stage lever (down-weight owner/trend early) and re-run this gate.

## Files
- `reconciled_forecast_backtest.json` — baseline + `recalibrated` block, per-code/target.
- `forecast_accuracy_gate_report.json` — verdict (baseline) + `recalibration_effect`.
