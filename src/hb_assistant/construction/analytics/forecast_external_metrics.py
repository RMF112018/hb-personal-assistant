"""Deterministic accuracy metrics for external-forecast evaluation (Implementation Phase 4).

Pure, stdlib-``Decimal`` arithmetic comparing an external forecast vector against a baseline
vector over matched budget codes. No numpy/scipy, no I/O, no CFR import. Money is quantized to
cents (2dp) and ratios to 4dp, mirroring the CFR conventions. Every function is total: it never
raises on empty/zero inputs, returning ``None`` (no sample) or a zero-guarded result instead.

These are net-new primitives: CFR's ``forecast_accuracy/backtest.py`` MAPE/bias are cohort-
backtest internals, not a compare-vs-baseline API.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal, InvalidOperation
from typing import NamedTuple

CENTS = Decimal("0.01")
RATIO = Decimal("0.0001")


def to_decimal(value: object) -> Decimal | None:
    """Best-effort parse of a money-ish value to Decimal; ``None`` if not numeric."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None
    s = str(value).strip().replace(",", "").replace("$", "")
    if s == "":
        return None
    if s.startswith("(") and s.endswith(")"):  # accounting negatives
        s = "-" + s[1:-1]
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _money(d: Decimal) -> str:
    return str(d.quantize(CENTS))


def _ratio(d: Decimal) -> str:
    return str(d.quantize(RATIO))


class Pair(NamedTuple):
    external: Decimal
    baseline: Decimal


def aligned_pairs(
    external: dict[str, object], baseline: dict[str, object]
) -> list[Pair]:
    """Return (external, baseline) Decimal pairs over keys present and numeric in BOTH maps.

    Deterministic order (sorted by key). Keys missing from either side, or non-numeric, are
    dropped — the caller can compare ``len(pairs)`` against the input sizes to report coverage.
    """
    pairs: list[Pair] = []
    for key in sorted(set(external) & set(baseline)):
        e = to_decimal(external[key])
        b = to_decimal(baseline[key])
        if e is None or b is None:
            continue
        pairs.append(Pair(e, b))
    return pairs


def _sqrt(d: Decimal) -> Decimal:
    # Decimal-friendly square root (Decimal.sqrt via context); d >= 0.
    if d <= 0:
        return Decimal(0)
    return d.sqrt()


def compute_metrics(pairs: Iterable[Pair]) -> dict[str, str]:
    """Compute variance/MAE/RMSE/WAPE/MAPE/bias over aligned pairs.

    Returns a dict of metric -> stringified value. Empty input yields an empty dict (no sample);
    MAPE/WAPE are zero-guarded (rows whose baseline is 0 are excluded from those two only).
    """
    plist = list(pairs)
    n = len(plist)
    if n == 0:
        return {}
    nd = Decimal(n)
    diffs = [p.external - p.baseline for p in plist]
    abs_diffs = [d.copy_abs() for d in diffs]
    total_variance = sum(diffs, Decimal(0))
    mae = sum(abs_diffs, Decimal(0)) / nd
    mse = sum((d * d for d in diffs), Decimal(0)) / nd
    rmse = _sqrt(mse)
    bias = total_variance / nd

    # WAPE: sum|diff| / sum|baseline| (exclude rows with zero baseline from denominator basis).
    nonzero = [(d, p) for d, p in zip(abs_diffs, plist, strict=True) if p.baseline != 0]
    metrics: dict[str, str] = {
        "variance": _money(total_variance),
        "mae": _money(mae),
        "rmse": _money(rmse),
        "bias": _money(bias),
    }
    if nonzero:
        denom = sum((p.baseline.copy_abs() for _, p in nonzero), Decimal(0))
        if denom != 0:
            wape = sum((d for d, _ in nonzero), Decimal(0)) / denom
            metrics["wape"] = _ratio(wape)
        mape = sum(
            (d / p.baseline.copy_abs() for d, p in nonzero), Decimal(0)
        ) / Decimal(len(nonzero))
        metrics["mape"] = _ratio(mape)
    return metrics


def gap(external: object, baseline: object) -> tuple[str | None, str | None]:
    """Return (gap_absolute, gap_percent) for one code/baseline pair, zero-guarded on percent."""
    e = to_decimal(external)
    b = to_decimal(baseline)
    if e is None or b is None:
        return None, None
    diff = e - b
    pct = None if b == 0 else _ratio(diff / b.copy_abs())
    return _money(diff), pct
