# ADR 288 — Production-forecast accuracy / trust gate

- **Status:** Accepted
- **Date:** 2026-06-21
- **Phase:** Forecast production-readiness (trust gate)
- **Builds on:** ADR 285–287 (model-engines: closed — time-series doesn't beat naive). `backtest_strong`
  as-of machinery + `reconcile_final.select_final`.

## Context

The model-engine path is closed: the production forecast stays the deterministic six-estimator
ensemble. The open production-readiness question is whether **the forecast we actually ship**
(`reconcile_final.select_final`'s `recommended_final_cost`) is accurate and unbiased. The pipeline
already backtests *individual estimator methods* (`backtest_strong` → `model_backtest_results.json`)
but **never scored the reconciled forecast operators consume**. This closes that gap.

## Decision

Both an integrated per-run scoring artifact and a standalone verdict gate (evidence-only; the central
forecast and forecast math are unchanged).

- **`forecast_intelligence/reconciled_backtest.py`** (new): `run_reconciled_backtest` reuses
  `backtest_strong._reconstruct`/`_predict` (40/60/80% owner-progress as-of, near-complete owner≥95%
  cohort, realized = current actual-to-date), builds `select_final`-shaped estimate dicts + a minimal
  as-of bundle, calls the **real** `reconcile_final.select_final` (same calibration), and scores the
  blended `recommended_final_cost` vs realized: MAPE, signed **bias**, worst-case ceiling coverage,
  blend-vs-best-single-method, and vs a naive "trust ERP" baseline. Deterministic.
- **`generate_forecast_intelligence_package.py`** emits `reconciled_forecast_backtest.json` every run
  (additive; no change to recommendations / the central forecast).
- **`workflows/forecast_accuracy_gate.py`** + **`forecast-accuracy-gate` CLI**: reads the reconciled
  backtest from an existing package (explicit `--package` or `--data-root` discovery), applies
  deterministic thresholds (`MIN_COHORT=8`, `MAPE_PASS=0.15`, `MAPE_FAIL=0.30`, `BIAS_ABS_PASS=0.10`,
  `COVERAGE_PASS=0.90`) → verdict `pass | review_recommended | not_ready | insufficient_evidence`,
  emits `forecast_accuracy_gate_report.json`. rc 0 pass / 1 otherwise / 3 controlled refusal.

### Reconstruction fidelity (disclosed)

Approximate: rebuilds only the fields `select_final` reads; uniform "medium" reliability (calibration
weights carry per-method differentiation); neutral trend signal (no reconstructed `supports_overrun`
beyond the ERP-exceedance path); schedule method absent (no history); realized truth valid only for
the near-complete cohort. Caveats are recorded in both artifacts.

## Validation

- CFR suite **619 passed** (608 + 11 new). New unit tests: reconciled backtest on a synthetic
  near-complete code (scores, deterministic, empty-cohort); gate verdict branches (pass / review /
  not_ready / insufficient_evidence) + preflight refusals (non-tropical, missing artifact, work_root
  under live root) + latest-package discovery. Determinism e2e still byte-identical; new code
  ruff/mypy clean; zero new mypy errors vs baseline.
- Live evidence: see `docs/evidence/forecast-accuracy-gate/<stamp>/`.

## Finding (live, tropical)

On the near-complete cohort (10 codes, 29 obs) the reconciled forecast reconstructed at 40/60/80% is
**materially inaccurate and high-biased**: MAPE ≈ 0.41, mean bias ≈ +0.33 (systematic over-forecast),
ceiling coverage ≈ 0.90 — while the **best single method (commitment-exposure) ≈ 0.07** and **naive
"trust ERP" ≈ 0.05**. The production blend is far worse than its own inputs at early completion,
driven in part by the overrun-protection p75 path inflating early-stage forecasts. Subject to the
fidelity caveats, this is a real trust signal: **do not certify the early-stage reconciled forecast;
it over-forecasts and is beaten by ERP and by commitment-exposure alone.**

## NOT in this PR

No change to the central forecast / recommendations / `INDEPENDENT_METHODS` / forecast math; no
schema/migrator change; no `hb_assistant` edit; no new dependency; no live write. `select_final` is
called only to score history.

## Consequences / next

The gate makes accuracy a first-class, per-run + on-demand checkpoint. The finding points to concrete
follow-ups (not in this PR): re-weight toward ERP / commitment at low completion, temper the p75
overrun bump early, or gate the reconciliation by completion stage — each re-measurable through this
same gate.
