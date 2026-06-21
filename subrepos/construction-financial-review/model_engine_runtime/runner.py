"""Isolated statsforecast model-engine runner (Phase I PR 3).

Runs in a DEDICATED Python 3.12 venv (statsforecast / scipy<1.16 / numba / pandas) — never in the
3.14 core. The 3.14 `model_engine_adapter` invokes this script as a subprocess and exchanges
deterministic JSON over stdin/stdout:

  stdin : {"requests": [{"id": str, "series": [float, ...], "horizon": int}, ...]}
  stdout: {"backend": "statsforecast_runtime_v1",
           "results": {id: {"etc": float, "per_model_etc": {...}, "model_set": [...],
                            "fallback_used": bool, "applicable": bool}}}

Mirrors the in-process classical engine's contract (``forecast_intelligence.timeseries_engine``) so
the two are drop-in interchangeable. Models: AutoETS + AutoTheta + AutoARIMA (median per step) when
>= 6 observations, else Naive + RandomWalkWithDrift. Output is the summed ETC over the horizon (the
3.14 side floors EAC to actuals and quantizes to Decimal cents).

Determinism: numba forced single-threaded, statsforecast models are RNG-free (deterministic order
selection), fixed model order, no wall-clock. statsforecast is imported ONLY in this file.
"""

from __future__ import annotations

import os

# Force single-threaded numba BEFORE importing statsforecast/numba, for byte-determinism.
os.environ.setdefault("NUMBA_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import json  # noqa: E402
import sys  # noqa: E402

import numpy as np  # noqa: E402
from statsforecast.models import (  # noqa: E402
    AutoARIMA,
    AutoETS,
    AutoTheta,
    Naive,
    RandomWalkWithDrift,
)

BACKEND_LABEL = "statsforecast_runtime_v1"
MIN_OBS_FULL_ENSEMBLE = 6


def _model_set(n_obs: int) -> list[str]:
    if n_obs >= MIN_OBS_FULL_ENSEMBLE:
        return ["auto_ets", "auto_theta", "auto_arima"]
    return ["naive", "drift"]


def _make(name: str):
    if name == "auto_ets":
        return AutoETS(season_length=1)
    if name == "auto_theta":
        return AutoTheta(season_length=1)
    if name == "auto_arima":
        return AutoARIMA(season_length=1)
    if name == "naive":
        return Naive()
    return RandomWalkWithDrift()


def _forecast_one(series: list[float], horizon: int) -> dict:
    n = len(series)
    if n < 3 or horizon <= 0:
        return {
            "etc": 0.0,
            "per_model_etc": {},
            "model_set": [],
            "fallback_used": False,
            "applicable": False,
        }
    y = np.asarray(series, dtype=float)
    names = _model_set(n)
    per_step = []
    per_model_etc: dict[str, float] = {}
    used: list[str] = []
    for name in names:
        try:
            fc = np.asarray(_make(name).forecast(y=y, h=horizon)["mean"], dtype=float)
        except Exception:  # noqa: BLE001 - a model that won't fit on this series is skipped, deterministically
            continue
        if fc.shape[0] != horizon or not np.all(np.isfinite(fc)):
            continue
        per_step.append(fc)
        per_model_etc[name] = float(np.sum(fc))
        used.append(name)
    if not per_step:
        # Every model declined (degenerate series): deterministic naive fallback.
        fc = np.full(horizon, float(y[-1]), dtype=float)
        per_step.append(fc)
        per_model_etc["naive"] = float(np.sum(fc))
        used = ["naive"]
    median_per_step = np.median(np.vstack(per_step), axis=0)
    return {
        "etc": float(np.sum(median_per_step)),
        "per_model_etc": per_model_etc,
        "model_set": used,
        "fallback_used": n < MIN_OBS_FULL_ENSEMBLE,
        "applicable": True,
    }


def main() -> int:
    payload = json.loads(sys.stdin.read())
    requests = payload.get("requests", [])
    results = {}
    for req in sorted(requests, key=lambda r: str(r.get("id"))):
        rid = str(req.get("id"))
        series = [float(x) for x in (req.get("series") or [])]
        horizon = int(req.get("horizon") or 0)
        results[rid] = _forecast_one(series, horizon)
    json.dump({"backend": BACKEND_LABEL, "results": results}, sys.stdout, sort_keys=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 - surface a clean nonzero rc + stderr to the adapter
        sys.stderr.write(f"model_engine_runtime error: {type(exc).__name__}: {exc}\n")
        sys.exit(1)
