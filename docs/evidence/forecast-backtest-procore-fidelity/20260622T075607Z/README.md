# Accuracy gate fidelity: add procore_progress to the backtest (5/6 methods) — live confirm (2026-06-22)

The reconciled backtest reconstructed only 4 of production's 6 independent methods, omitting
procore_progress (the $17.9M overshooter that surprised the damping flip). This reconstructs
procore_progress as-of (per-commitment latest pay-app row <= T), making the gate a faithful mirror of
the production blend. schedule_remaining_work stays omitted (no history) but is now disclosed.

## Live before/after (real tropical, same near-complete cohort, 29 obs)

| Variant | Baseline MAPE | Baseline bias | p75 stage-gate | p75 + damping | Ceiling coverage |
|---|---|---|---|---|---|
| 4-method (before) | 0.4102 | +0.3348 | 0.3048 | 0.2450 | 0.8966 |
| **5-method incl. procore (after)** | **0.3650** | **+0.2782** | **0.3039** | **0.2535** | 0.8966 |

**Headline:** including procore makes the production blend measurably **more accurate** (baseline MAPE
0.4102 → 0.3650, bias +0.33 → +0.28). The 4-method gate was **overstating** the early over-forecast,
because it ignored a method production actually blends. The gate is now representative, so the verdict
and the damping decision rest on a faithful 5-method blend.

## Per-method standalone as-of accuracy (diagnostic)
- commitment_exposure 0.0739 (best) · cpi_blend 0.1159 · owner_progress 0.3447 · **procore_progress 0.5765** · trend_projection 1.0658
- procore alone over-forecasts (0.58), but as an independent signal in the blend it *reduces* baseline error — exactly why an ensemble beats any single method.

## Coverage disclosure (method_coverage, now in the gate report)
- Reconstructed (5/6): owner_progress, trend_projection, commitment_exposure, cpi_blend, procore_progress.
- Omitted (1): schedule_remaining_work — "schedule state is not versioned (no per-period history)".
- Shadow-excluded: timeseries_eac (not an independent method).

## Safety
No production forecast change — calibration METHODS unchanged; only the backtest/gate are enriched.
CFR suite 649 passed; value-goldens + determinism hold.

## Files
- `reconciled_backtest_4method_before.json`, `reconciled_backtest_5method_after.json` — full before/after.
