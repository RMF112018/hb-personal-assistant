# Enable completion-stage recalibration in production — evidence (2026-06-22)

Flips `_P75_STAGE_GATE` ON in `generate_forecast_intelligence_package`, activating the completion-stage
tempering of the p75 overrun bump (ADR 289) now that the faithful backtest (ADR 290) confirmed the
early over-forecast is real and the stage-gate cuts it ~26% with the ceiling held.

## Production impact (real tropical) — surgical, all reductions
- 5 of 127 codes change; **all reductions** (removing early p75 over-inflation).
- Project recommended total: −$51,671 (−0.08%).
- Only low-completion overrun codes affected; high-completion + under-forecast (cost-basis-raised)
  codes unchanged.

See `production_impact.json` for the per-code diff (off vs on, deltas, overrun flags, worst-case).

## Safety
- CFR suite **630 passed with the flag on** — zero value-goldens broke (incl. the live cost-basis
  survey-code golden); byte-determinism holds.
- Doctrine preserved: no ERP anchor, reductions toward weighted_mean (never below), worst-case ceiling
  (p90/commitment) untouched, actuals floor intact.

## Files
- `production_impact.json` — off-vs-on per-code diff + project totals.
