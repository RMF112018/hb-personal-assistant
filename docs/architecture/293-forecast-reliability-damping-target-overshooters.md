# ADR 293 — Reliability damping targets overshooters (monotonic-down)

- **Status:** Accepted
- **Date:** 2026-06-22
- **Phase:** Forecast production-readiness (refinement of ADR 292's lever, before any production flip)
- **Builds on:** ADR 292 (the damping lever, shipped default-off PR #83).

## Context

Attempting to flip `_RELIABILITY_DAMPING` on (ADR 292's lever) surfaced a real defect on the live
forecast: it **raised** one overrun code (`1000.15-09-600.SUB`) by **+$113k** instead of reducing it.
The lever damped a **fixed method set** (`owner_progress`, `trend`), but for that code those were the
**low** estimates ($968k–$1.42M) while the real overshooter was `procore_progress` ($17.9M, not in the
damped set) — so down-weighting the low anchors shifted the blend **up**. The aggregate backtest had
masked it (the damped set isn't always the overshooter, and the gate's reconstruction omits
`procore_progress`). The flip was **abandoned** (not merged); this ADR refines the lever instead.

## Decision

Damp by **position, not method identity**: at low completion, down-weight any independent estimate
whose EAC is **above the blend median** (`damp_ref = _median(independent EACs)`), by the same
completion ramp. `DAMPED_METHODS` is removed.

- **Monotonic-down by construction:** down-weighting only above-median estimates makes `weighted_mean`
  non-increasing; `p75`/`p90`/commitment are percentile/weight-independent, so `central`/`recommended`
  are non-increasing. **Damping can never raise the forecast** — the +$113k class of surprise is
  impossible.
- Targets the actual overshooter regardless of method (e.g. `procore_progress`), which the fixed set
  missed.
- Doctrine unchanged: reliability weighting only (no ERP anchor); the p90/commitment **worst-case
  ceiling preserves the overrun exposure** (test-asserted), so a credible overrun is never erased —
  only the early *central* is kept from being inflated by it.
- Still **opt-in, default-off** (`_RELIABILITY_DAMPING` off on main) ⇒ zero production change here.

## Validation

- CFR suite **641 passed**; default-off ⇒ byte-identical (all value-goldens incl. live cost-basis;
  byte-determinism). New unit tests assert: monotonic-down (incl. the previously-+$113k shape now
  **reduces**), no-op at high/unknown completion and when off, actuals floor held, worst-case ceiling
  unchanged, `damp_ref` = median of independent EACs.
- ruff/mypy clean; zero new errors (the lone `reconcile_final` `fam` F841 is pre-existing baseline).
- Live re-diff: see `docs/evidence/forecast-reliability-damping-target-overshooters/<stamp>/` — confirms
  the production off-vs-on diff is now all-reductions/no-increase (specifically `1000.15-09-600.SUB`).

## NOT in this PR

Flag stays off (no operator-facing change); no `INDEPENDENT_METHODS`/overrun/schema/`hb_assistant`
change; no p75-stage-gate change; no new dependency; no live write; no ERP anchoring. **Noted fidelity
follow-up:** the gate's backtest still reconstructs only the 4 `backtest_strong` methods (omits
`procore_progress` etc.); the refined lever is safe-by-construction regardless, but extending gate
method coverage would make the gate's measured damping effect fully representative. Flipping
`_RELIABILITY_DAMPING` on remains a later evidence-gated PR.

## Lesson

A lever validated by an aggregate backtest can still misbehave per-code in production when the backtest
omits methods that dominate live behavior. The off-vs-on production diff (not just the aggregate gate
metric) caught it; designing the lever to be **monotonic in the safe direction** removes the whole risk
class.
