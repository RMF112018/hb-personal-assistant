# ADR 291 — Enable completion-stage recalibration in production (_P75_STAGE_GATE on)

- **Status:** Accepted
- **Date:** 2026-06-22
- **Phase:** Forecast production-readiness (activation of ADR 289, gated on ADR 290)
- **Builds on:** ADR 288 (accuracy gate), 289 (the stage-gate mechanism, shipped default-off), 290
  (faithful reconstruction confirming the over-forecast is real).

## Context

ADR 289 added the completion-stage p75 stage-gate to `select_final` behind `_P75_STAGE_GATE`, default
**off**. ADR 290's faithful reconstruction confirmed the early over-forecast is **real** (not a
measurement artifact) and that the stage-gate cuts the reconciled MAPE ~26% (0.41 → 0.30), bias
+0.33 → +0.22, with the worst-case ceiling held. This ADR **enables it in production**.

## Decision

Set `_P75_STAGE_GATE = True` in `generate_forecast_intelligence_package`. No code/logic change beyond
the flag; the mechanism, doctrine guarantees (no ERP anchor, never below weighted_mean, ceiling
untouched), and the gate are unchanged.

## Production impact (real tropical, frozen stamp; `production_impact.json`)

- **5 of 127 codes** change — all **reductions** (removing early-stage p75 over-inflation), total
  **−$51,671 (−0.08%)** of the project recommended cost. Surgical: only low-completion overrun codes
  where the p75 bump fired are affected; high-completion codes and under-forecast codes (final raised
  to ERP by the cost-basis layer) are unchanged.
- Largest moves: `1000.15-16-400.SUB` −$32,473; `1000.15-15-410.SUB` −$18,650; remainder < $400.

## Validation

- CFR suite **630 passed with the flag on** — **zero value-goldens broke** (incl. the live cost-basis
  survey-code golden 52778.50, which is an under-forecast code absorbed by the cost-basis raise; the
  e2e tests assert structure/inequalities + byte-determinism, all hold).
- ruff/mypy unaffected (one-line flag change).
- Off-vs-on diff captured as `production_impact.json` (deterministic, frozen stamp).

## Invariants preserved

Actuals floor; worst-case ceiling (p90/commitment, untouched); overrun flags re-derive consistently;
no ERP cap/anchor; reductions are toward `weighted_mean` (never below). `INDEPENDENT_METHODS`, schema,
`hb_assistant`: unchanged. No live write.

## Next

Residual over-forecast remains (recalibrated MAPE ~0.30, still above naive ERP ~0.05) → completion-stage
reliability damping of the early-overshooting methods is the next lever, re-measurable through the gate.
