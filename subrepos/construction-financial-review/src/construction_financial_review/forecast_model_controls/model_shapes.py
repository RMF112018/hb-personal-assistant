"""Deterministic monthly shape vectors for operator-selected model types.

Each shape is a normalized ``OrderedDict[month -> Decimal]`` summing to 1 (same convention as
``forecast_comprehensive/monthly_consumer._curve_tilt`` and ``forecast_monthly/cost_entry_trends``).
``existing_model`` and the ``manual_*`` types return ``None`` here — the caller defers to the current
blended model or to the operator's manual values respectively. The actual dollar allocation is done by
``forecast_monthly.monthly_reconcile._allocate`` (last nonzero month absorbs the cent residual), so these
vectors only need to express the *shape*; totals always reconcile exactly downstream.

Shapes (n = number of active months, i = 0-based index):
- linear:            raw = [1]*n                      (flat / equal)
- linear_ascending:  raw = [i+1]                      (increasing over time)
- linear_descending: raw = [n-i]                      (decreasing over time)
- bell_curve:        raw = [min(i+1, n-i)]            (low ends, heavy middle)
- front_loaded_s_curve: triangular peak near n/3      (heavier early, tapering later)
- back_loaded_s_curve:  triangular peak near 2n/3     (heavier later)
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal

from . import control_schema as cs

ZERO = Decimal("0")
ONE = Decimal("1")


def _triangular(n: int, peak_frac: str) -> list:
    """Integer triangular weights peaking at ``round(peak_frac*(n-1))`` (floored at 1)."""
    if n <= 0:
        return []
    p = int((Decimal(peak_frac) * Decimal(n - 1)).to_integral_value(rounding="ROUND_HALF_UP"))
    return [max(1, n - abs(i - p)) for i in range(n)]


def _raw_weights(model_type: str, n: int) -> list | None:
    if n <= 0:
        return None
    if model_type == cs.MT_LINEAR:
        return [1] * n
    if model_type == cs.MT_LINEAR_ASC:
        return [i + 1 for i in range(n)]
    if model_type == cs.MT_LINEAR_DESC:
        return [n - i for i in range(n)]
    if model_type == cs.MT_BELL:
        return [min(i + 1, n - i) for i in range(n)]
    if model_type == cs.MT_FRONT_S:
        return _triangular(n, "0.3333")
    if model_type == cs.MT_BACK_S:
        return _triangular(n, "0.6667")
    return None  # existing_model / manual_* -> no shape vector here


def shape_weights(model_type: str, months: list) -> "OrderedDict | None":
    """Return a normalized month->weight vector for a shape model type, or None to defer."""
    raw = _raw_weights(model_type, len(months))
    if raw is None:
        return None
    total = Decimal(sum(raw))
    if total <= 0:
        n = Decimal(len(months))
        return OrderedDict((m, ONE / n) for m in months)
    return OrderedDict((m, Decimal(r) / total) for m, r in zip(months, raw, strict=False))
