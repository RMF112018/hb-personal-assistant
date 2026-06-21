# ADR 289 — Completion-stage recalibration of the reconciliation (opt-in, gate-measured)

- **Status:** Accepted
- **Date:** 2026-06-21
- **Phase:** Forecast production-readiness (accuracy follow-up to ADR 288)
- **Builds on:** ADR 288 (accuracy/trust gate). `reconcile_final.select_final`, `reconciled_backtest`.

## Context

ADR 288's gate found the production reconciled forecast **over-forecasts at low completion** (tropical:
MAPE 0.41, +0.33 bias; 0.595/0.364/0.264 at 40/60/80%) — worse than commitment-exposure alone or naive
ERP. Root inflator: the **p75 overrun bump** in `select_final`
(`central = max(weighted_mean, p75)` when an overrun signal fires), appropriate when overruns are real
(high completion) but inflationary early. This recalibrates that by completion stage.

**Doctrine (verified, honored):** ERP is never a cap/floor/anchor (only actual floors); credible
overruns must not be suppressed; the p90/commitment worst-case ceiling + `overrun_not_suppressed` gate
stay intact. → The lever is **stage-gating the p75 bump only**; an ERP-anchor was rejected as
doctrine-violating.

## Decision

- **`reconcile_final.select_final(..., p75_stage_gate: bool = False)`** — opt-in. When ON, under the
  overrun branch `central = weighted_mean + factor·(max(weighted_mean,p75) − weighted_mean)`, where
  `factor` ramps `0` at/below `STAGE_GATE_LO=0.5` completion → `1` at/above `STAGE_GATE_HI=0.8` (or
  when completion is unknown). Completion = `owner_latest_percent_complete`, else `1.0` if schedule
  complete, else unknown→full bump (conservative). When OFF (**default**) → today's `max(weighted_mean,
  p75)` exactly. Never below `weighted_mean`/actual; worst-case ceiling + overrun flags unchanged.
- **`generate_forecast_intelligence_package._P75_STAGE_GATE = False`** — single production flip-point,
  default OFF ⇒ operator-facing forecast values are **unchanged this PR**.
- **`reconciled_backtest`** now scores each as-of observation **both** ways (gate off = baseline,
  on = recalibrated) and reports a `recalibrated` block (`recalibrated_final_mape`,
  `recalibrated_final_mean_bias`, coverage, `mape_improvement`, `bias_abs_improvement`, per-target). The
  as-of bundle carries `owner_latest_percent_complete` so the gate is exercised (baseline value
  unaffected).
- **`forecast_accuracy_gate`** adds a `recalibration_effect` block + advisory `recalibration_recommended`
  (MAPE improvement ≥ 0.05, bias not worse, coverage held). **Verdict stays on baseline (production)
  metrics** — the gate reports what flipping the flag would buy.

## Invariants

- **Default-off ⇒ zero production change**: full CFR suite (incl. the live cost-basis survey-code
  golden 52778.50 + byte-determinism e2e) unchanged. No value-goldens touched.
- Doctrine: no ERP anchoring; overruns not suppressed (`weighted_mean` still carries them; only the
  aggressive p75 jump is tempered, and only at low completion); ceiling untouched.

## Validation

- CFR suite **628 passed** (619 + 9 new). New `test_fi_reconcile_stage_gate` proves: default-off keeps
  the p75 bump; ON tempers at low completion (40% → weighted_mean), full bump at high/unknown
  completion + schedule-complete, partial in the ramp, never below actual. Reconciled-backtest + gate
  tests assert the recalibrated block + effect. mypy/ruff clean; zero new mypy errors.
- Live confirm: see `docs/evidence/forecast-completion-stage-recalibration/<stamp>/`.

## NOT in this PR

Flag ships **off** → no operator-facing value change, no `INDEPENDENT_METHODS`/overrun/schema/
`hb_assistant` change, no new dependency, no live write, no ERP anchoring. Flipping `_P75_STAGE_GATE`
on is a deliberate separate follow-up gated on this PR's evidence.

## Consequences / next

The recalibration mechanism + before/after evidence land now; the production flip-on is a one-line,
evidence-gated follow-up. If the gate shows the stage-gate insufficient alone, the same harness can
measure further levers (completion-stage reliability damping, etc.).
