# Model-engine runtime (isolated Python 3.12)

A **dedicated, isolated** statsforecast runtime for the forecast time-series shadow estimator. It
exists so the heavy scientific stack (statsforecast / scipy<1.16 / numba / pandas) stays **out of the
3.14 core app and CFR** — those cannot install statsforecast (scipy<1.16 has no Python 3.14 wheel).

## Architecture

```
3.14 core (CFR)                         this runtime (Python 3.12, separate venv)
  model_engine_adapter  ──stdin JSON──▶  runner.py
                        ◀─stdout JSON──     statsforecast / scipy / numba / pandas
  classical fallback when this runtime is not configured/available
```

- `runner.py` — the only place `statsforecast` is imported. Reads
  `{"requests":[{"id","series":[float],"horizon":int}]}` and writes
  `{"backend":"statsforecast_runtime_v1","results":{id:{etc,per_model_etc,model_set,fallback_used,applicable}}}`.
  Models: AutoETS + AutoTheta + AutoARIMA (median per step) at ≥6 obs, else Naive + Drift. Output is
  summed ETC over the horizon; the 3.14 side floors EAC to actuals and quantizes to Decimal cents.
- `requirements.txt` — pinned for byte-deterministic forecasts.
- `setup_venv.sh` — creates the venv (default `~/Library/Application Support/HB Model Engine/.venv-3.12`).

## Use

```bash
bash model_engine_runtime/setup_venv.sh
export CFR_MODEL_ENGINE_PYTHON="$HOME/Library/Application Support/HB Model Engine/.venv-3.12/bin/python"
```

When `CFR_MODEL_ENGINE_PYTHON` is set and importable, the forecast-intelligence shadow comparison +
holdout backtest are produced with the real statsforecast backend; otherwise they fall back to the
in-process classical numpy ensemble. **Either way the central forecast is unchanged** — the
time-series estimator is a shadow (not in `INDEPENDENT_METHODS`).

## Determinism & isolation

- numba forced single-threaded (`NUMBA_NUM_THREADS=1`); statsforecast models are RNG-free; fixed model
  order; no wall-clock. Two runs in the same environment produce byte-identical results.
- The venv is machine-local and **not committed**. This directory is **not** on the
  `construction_financial_review` package path, so the 3.14 import graph never touches statsforecast.
