"""Deterministic classical time-series engine for the shadow EAC estimator (Phase I PR 2).

Backend seam for the model-engines work. The Phase I plan calls for statsforecast (AutoETS/AutoTheta/
AutoARIMA), but statsforecast cannot install on the project's Python 3.14 (its ``scipy<1.16`` pin has
no 3.14 wheel). This module fills the same seam with a robust ensemble implemented in **pure numpy**
(already a CFR dependency) — naive, drift, Holt linear, and a theta-like method, **median-combined**
per step, with a naive+drift-only path when there are fewer than 6 observations. A statsforecast (or
other) backend can later replace ``forecast_etc`` without touching the estimator/audit callers.

Determinism: fixed smoothing parameters (no optimizer, no RNG), numpy float64 arithmetic, models run
in a fixed order. Two calls on the same series return identical floats; callers quantize to Decimal
cents, which absorbs any last-ULP noise. This is a SHADOW estimator — its output never changes the
central forecast (see ``estimators_uncapped.timeseries_eac``).
"""

from __future__ import annotations

import numpy as np

BACKEND_LABEL = "classical_ensemble_v1"

# Fixed (un-fitted) smoothing constants — chosen for stability on short, noisy construction series.
_HOLT_ALPHA = 0.5
_HOLT_BETA = 0.3
_SES_ALPHA = 0.5

# Model set is data-dependent: the trend-bearing models need a minimum history.
MIN_OBS_FULL_ENSEMBLE = 6


def _naive(y: np.ndarray, h: int) -> np.ndarray:
    return np.full(h, float(y[-1]), dtype=float)


def _drift(y: np.ndarray, h: int) -> np.ndarray:
    n = len(y)
    slope = (float(y[-1]) - float(y[0])) / (n - 1) if n > 1 else 0.0
    return float(y[-1]) + slope * np.arange(1, h + 1, dtype=float)


def _holt_linear(y: np.ndarray, h: int) -> np.ndarray:
    level = float(y[0])
    trend = float(y[1] - y[0]) if len(y) > 1 else 0.0
    for val in y[1:]:
        prev_level = level
        level = _HOLT_ALPHA * float(val) + (1.0 - _HOLT_ALPHA) * (prev_level + trend)
        trend = _HOLT_BETA * (level - prev_level) + (1.0 - _HOLT_BETA) * trend
    return level + trend * np.arange(1, h + 1, dtype=float)


def _theta_like(y: np.ndarray, h: int) -> np.ndarray:
    """0.5 * linear extrapolation + 0.5 * simple exponential smoothing level (constant)."""
    n = len(y)
    idx: np.ndarray = np.arange(1, n + 1, dtype=float)
    slope, intercept = np.polyfit(idx, y.astype(float), 1)  # deterministic least squares
    future_idx: np.ndarray = np.arange(n + 1, n + h + 1, dtype=float)
    linear = intercept + slope * future_idx
    ses = float(y[0])
    for val in y[1:]:
        ses = _SES_ALPHA * float(val) + (1.0 - _SES_ALPHA) * ses
    return 0.5 * linear + 0.5 * ses


def model_set(n_obs: int) -> list[str]:
    """Deterministic model names used for a series of ``n_obs`` observations."""
    if n_obs >= MIN_OBS_FULL_ENSEMBLE:
        return ["naive", "drift", "holt_linear", "theta_like"]
    return ["naive", "drift"]


_MODELS = {"naive": _naive, "drift": _drift, "holt_linear": _holt_linear, "theta_like": _theta_like}


def forecast_etc(monthly: list[float], horizon: int) -> dict:
    """Median-ensemble forecast of the next ``horizon`` monthly amounts; return summed ETC.

    Returns ``{"etc", "per_model_etc", "model_set", "fallback_used", "horizon", "n_obs"}``. ``etc`` is
    the sum over the horizon of the per-step median across the active models (may be negative for
    declining/credit series; the caller floors EAC to actuals). Deterministic and RNG-free.
    """
    n = len(monthly)
    if n < 3 or horizon <= 0:
        return {
            "etc": 0.0,
            "per_model_etc": {},
            "model_set": [],
            "fallback_used": False,
            "horizon": int(horizon),
            "n_obs": n,
            "applicable": False,
        }
    y = np.asarray(monthly, dtype=float)
    names = model_set(n)
    per_step = []  # one array per model, in fixed name order
    per_model_etc = {}
    for name in names:
        fc = _MODELS[name](y, horizon)
        per_step.append(fc)
        per_model_etc[name] = float(np.sum(fc))
    stacked = np.vstack(per_step)
    median_per_step = np.median(stacked, axis=0)
    return {
        "etc": float(np.sum(median_per_step)),
        "per_model_etc": per_model_etc,
        "model_set": names,
        "fallback_used": n < MIN_OBS_FULL_ENSEMBLE,
        "horizon": int(horizon),
        "n_obs": n,
        "applicable": True,
    }
