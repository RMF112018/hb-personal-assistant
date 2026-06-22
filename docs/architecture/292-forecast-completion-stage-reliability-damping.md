# ADR 292 — Completion-stage reliability damping (opt-in, gate-measured)

- **Status:** Accepted
- **Date:** 2026-06-22
- **Phase:** Forecast production-readiness (second recalibration lever)
- **Builds on:** ADR 288 (accuracy gate), 289/291 (p75 stage-gate, now live), 290 (faithful backtest).

## Context

The p75 stage-gate (live, PR #82) cut the early over-forecast ~26% but left a residual: the faithful
backtest still shows reconciled MAPE ~0.30 / bias ~+0.22 at low completion — driven by the
`weighted_mean` of the early-overshooting methods (`owner_progress_eac` = actual/owner%;
`trend_projection_eac`). This adds the next doctrine-safe lever: **down-weight those two methods at low
completion** so the steadier methods (commitment, cpi) carry more of the early blend. Same rollout:
opt-in, default-off, gate-measured, flip-on later.

## Decision

- **`reconcile_final.select_final(..., reliability_damping: bool = False)`** — when on, multiply the
  blend weight of `DAMPED_METHODS = (owner_progress_eac, trend_projection_eac)` by
  `_reliability_damp_factor(completion)`: `DAMP_MIN=0.3` at/below `DAMP_LO=0.4`, ramping to `1.0` at/above
  `DAMP_HI=0.7`; unknown/high completion → `1.0` (no damp). Default off ⇒ weights unchanged ⇒
  byte-identical. Doctrine-safe: reliability weighting only (no ERP anchor), factor floored (methods
  always still contribute), and the p90/commitment **worst-case ceiling is unaffected** (test-asserted)
  so overrun *exposure* is preserved even when central drops.
- **`generate _RELIABILITY_DAMPING = False`** flip-point, passed to `select_final` alongside
  `_P75_STAGE_GATE` (which is on).
- **`reconciled_backtest`** adds a third `damped` variant (p75 + damping) scored per as-of observation,
  reporting the **incremental** improvement over the p75-only recalibration (current production) and the
  total over baseline. **`forecast_accuracy_gate`** adds a `reliability_damping_effect` block + advisory
  `reliability_damping_recommended`. Verdict stays on baseline (production) metrics.

## Validation

- CFR suite **639 passed** (630 + 9 new); **default-off ⇒ zero value-goldens break** (incl. the live
  cost-basis golden); byte-determinism holds. New unit tests prove damping lowers central at low
  completion, is a no-op at high/unknown completion and when off, never goes below the actuals floor,
  and leaves the worst-case ceiling unchanged.
- ruff/mypy clean; zero new errors vs baseline.
- Live confirm: see `docs/evidence/forecast-completion-stage-reliability-damping/<stamp>/`.

## NOT in this PR

Flag ships **off** ⇒ no operator-facing value change, no `INDEPENDENT_METHODS`/overrun/schema/`hb_assistant`
change, no new dependency, no live write, no ERP anchoring. Flipping `_RELIABILITY_DAMPING` on (and
tuning the ramp / damped-method set) is a deliberate, evidence-gated follow-up.

## Next

If the live `reliability_damping_effect` shows a material incremental improvement with the ceiling held,
flip `_RELIABILITY_DAMPING` on (separate PR, with the off-vs-on production diff like #82).
