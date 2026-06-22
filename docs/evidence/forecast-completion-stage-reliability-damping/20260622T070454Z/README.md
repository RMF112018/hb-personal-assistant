# Completion-stage reliability damping — live confirm (2026-06-22)

Measures the new lever (down-weight owner_progress + trend at low completion) on real tropical data,
via the faithful reconciled backtest. Opt-in, ships default-OFF (production unchanged).

## Result — damping adds a further meaningful cut, ceiling held

| Variant | Reconciled MAPE | Mean bias | Worst-case coverage | 40% bucket |
|---|---|---|---|---|
| Baseline (no levers) | 0.4102 | +0.3348 | — | — |
| p75 stage-gate (current production) | 0.3048 | +0.2239 | 0.8966 | 0.4103 |
| **p75 + reliability damping** | **0.2464** | **+0.1667** | **0.8966** | **0.2609** |

- **Incremental over production (p75-only):** MAPE −0.0583, bias_abs −0.0573 → `reliability_damping_recommended: True`.
- **Cumulative (both levers):** early-cohort MAPE 0.41 → 0.25 (~40% reduction), bias halved (+0.33 → +0.17); worst-case ceiling coverage unchanged; gains concentrated at low completion (40% bucket 0.41 → 0.26; 80% unchanged).

Doctrine preserved: reliability weighting only (no ERP anchor), methods still contribute (factor floored), p90/commitment worst-case ceiling unaffected.

## Recommended next
Flip `_RELIABILITY_DAMPING` on (separate PR, with the off-vs-on production diff like #82) to bank this. Residual over-forecast remains (~0.25, still above naive ERP ~0.05); further gains would need different evidence (driver-based features / deferred EAC-formula fidelity), measurable through this same gate.

## Files
- `reconciled_forecast_backtest.json` — baseline + recalibrated(p75) + damped(p75+damping), per-code/target.
- `forecast_accuracy_gate_report.json` — verdict (baseline) + recalibration_effect + reliability_damping_effect.
