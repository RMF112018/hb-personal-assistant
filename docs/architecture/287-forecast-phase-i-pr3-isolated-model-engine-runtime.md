# ADR 287 — Forecast Phase I PR 3: isolated statsforecast model-engine runtime

- **Status:** Accepted
- **Date:** 2026-06-21
- **Phase:** Forecast model-engines (Phase I), PR 3 of N
- **Builds on:** ADR 285 (readiness), ADR 286 (shadow estimator, #77).

## Context

PR 2's shadow time-series estimator uses an in-process **classical numpy** ensemble because
`statsforecast` cannot install on the project's Python 3.14 (`scipy<1.16` pin, no 3.14 wheel). PR 2's
backtest showed the classical engine does not beat naive — but left open whether **real
statsforecast** would. This PR answers that **without polluting the 3.14 core**: a dedicated Python
3.12 statsforecast runtime, invoked across a subprocess + JSON boundary, powering the shadow
**evidence artifacts only**. The central forecast and the classical fallback are untouched; the
estimator stays a shadow (not in `INDEPENDENT_METHODS`).

## Decision

```
3.14 core (CFR)                          isolated runtime (Python 3.12, separate venv — not committed)
  model_engine_adapter  ──stdin JSON──▶   model_engine_runtime/runner.py
                        ◀─stdout JSON──      statsforecast / scipy<1.16 / numba / pandas
  classical fallback when CFR_MODEL_ENGINE_PYTHON is unset/unavailable
```

- **`model_engine_runtime/`** (sibling to `src/`, NOT on the package path): `runner.py` (statsforecast
  imported ONLY here; AutoETS+AutoTheta+AutoARIMA median ≥6 obs, Naive+Drift below; single-threaded,
  RNG-free, sorted, no wall-clock), `requirements.txt` (pinned), `setup_venv.sh` (creates the 3.12
  venv under `~/Library/Application Support/HB Model Engine/.venv-3.12`), `README.md`.
- **`forecast_intelligence/model_engine_adapter.py`** (3.14, dependency-free): `available()` never
  raises; `forecast_batch()` does ONE subprocess call, JSON in/out, raises `ModelEngineUnavailable`
  on missing config / nonzero exit / timeout / bad output. Mirrors `analysis/final_forecast_runner`
  (subprocess discipline) + the Ollama client (graceful availability). Env: `CFR_MODEL_ENGINE_PYTHON`,
  optional `CFR_MODEL_ENGINE_RUNNER`, and `CFR_MODEL_ENGINE_PROBE_IMPORT` (default `statsforecast`,
  overridable for tests).
- **`_timeseries_shadow_artifacts`** now batches one runtime call (full-horizon comparison + holdout
  prefixes) when `available()`, else the classical in-process engine. Each artifact records its
  `backend`. The per-code central loop and the in-loop classical `timeseries_eac` estimate are
  unchanged.

## Invariants

- **Core untouched:** no central-forecast change; `INDEPENDENT_METHODS` unchanged; the 3.14
  `pyproject.toml` gets no new dependency. A grep test asserts no `import statsforecast` anywhere in
  the 3.14 `src/`.
- **Fallback = today:** with the runtime unset/unavailable, output is byte-identical to PR 2
  (classical). The determinism gate compares two runs in the *same* env (same backend) → byte-identical.
- **Runtime determinism:** pinned versions, single-thread, RNG-free; 3.14 quantizes to Decimal cents.

## Validation

- CFR suite **608 passed** (598 + 10 new). New `test_fi_model_engine_adapter` exercises the boundary
  via a deterministic **stub runner** through `sys.executable` (no venv needed): availability branches,
  batch happy path, missing-runner / nonzero-exit / bad-JSON → `ModelEngineUnavailable`, and a
  generate run routed through the stub (artifacts labelled `stub_runtime`). Determinism e2e still
  byte-identical; new code ruff/mypy clean; zero new mypy errors.
- Real-statsforecast evidence: see `docs/evidence/forecast-statsforecast-shadow/<stamp>-statsforecast-runtime/`.

## NOT in this PR

Still shadow: `timeseries_eac` not in `INDEPENDENT_METHODS`; no central-forecast/recommendation
change; no calibration weight; no schema/migrator change; no `hb_assistant` edit; no new 3.14
dependency; no live write.

## Deferred (next PR)

If real statsforecast beats naive: promote into `INDEPENDENT_METHODS` + `backtest_strong` with its
own before/after evidence. If it also fails to beat naive, keep shadow-only (or drop) — also a
legitimate outcome.
