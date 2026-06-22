# ADR 290 — Reconciled-backtest fidelity upgrade (trustworthy accuracy measurement)

- **Status:** Accepted
- **Date:** 2026-06-21
- **Phase:** Forecast production-readiness (measurement fidelity for ADR 288/289)
- **Builds on:** ADR 288 (accuracy gate), ADR 289 (completion-stage recalibration).

## Context

The accuracy gate (ADR 288) and the stage-gate recalibration's measured effect (ADR 289) both came
from the reconciled backtest's **approximate** as-of reconstruction: uniform `"medium"` reliability +
neutral trend signal. Production weights the blend by *real* per-method reliability, and at low
completion the overshooting methods (owner_progress, trend) get `"low"`, not medium — so the
approximation **over-weighted exactly the methods that overshoot early**, likely inflating both the
measured over-forecast (0.41/+0.33) and the stage-gate gain (−22%). This upgrade makes the measurement
faithful so the next accuracy decision rests on real numbers. **Evidence-only; no production change.**

## Decision

Fully contained in `forecast_intelligence/reconciled_backtest.py`; reuses real production logic.

- Per as-of observation, reconstruct the trend block via the **real `trend.analyze`** on the monthly
  series truncated to `<= t_month` → faithful `trend_signal`, `cost_volatility_cov`,
  `months_of_completed_actuals`.
- Assign each method its **real** as-of reliability (`estimators_uncapped` rules):
  owner `medium` iff owner% ≥ 0.50; trend `medium` iff months ≥ 6 and CoV ≤ 0.75; commitment `low`
  (pipeline ratio not reconstructable at as-of — conservative); cpi `low`.
- Set the as-of bundle's `trend_signal` from the reconstructed block (was neutral) so the p75 overrun
  trigger fires faithfully.
- Per-method **EAC values** still use `backtest_strong._predict` (full estimator-formula fidelity is
  deferred and documented). The high-leverage gap fixed here is the **blend weighting**.

No change to `backtest_strong`, `select_final`, `generate`, the gate, `INDEPENDENT_METHODS`, schema, or
`hb_assistant`. `_P75_STAGE_GATE` stays off (production forecast unchanged).

## Validation

- CFR suite **630 passed** (628 + 2 new). New unit tests assert the real reliability rules
  (owner low at 40% / medium at 60%; trend low <6 months or high CoV) and that estimates carry the
  supplied reliability. Byte-determinism e2e holds (`trend.analyze` is deterministic). The
  `reconciled_forecast_backtest.json` values change (now faithful) but are not value-goldens.
- ruff/mypy clean; zero new mypy errors.
- Live confirm (faithful vs approximate): see
  `docs/evidence/forecast-reconciled-backtest-fidelity/<stamp>/`.

## Consequences / next

The gate now reports the **true** over-forecast + true stage-gate effect. That evidence decides the
next concrete step: if the faithful over-forecast is small, the earlier signal was largely a
measurement artifact (production reliability already handles it) → likely just flip the stage-gate on
or stop; if still material → flip-on and/or completion-stage reliability damping, now justified on
real numbers. Deferred: full EAC-formula fidelity (rebuild as-of bundles to run the real estimators).
