"""Recent cost-trend analyzer for one budget code.

Reads the per-code ``actuals.monthly_actuals`` stream and characterizes recent burn behavior:
recent vs prior burn, acceleration/deceleration, volatility, recency, late-cost emergence, and
credit/deductive patterns. Deterministic, Decimal-only. Completed (``through_may_2026``) months are
the burn baseline; June is partial/leading and excluded (mirrors ``signals.py``).

Nothing here caps or anchors a forecast — it only produces evidence + a directional ``trend_signal``.
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal
from typing import Optional

from ..common.money import D, dec, money_str

RECENT_WINDOW = 3                       # trailing completed months treated as "recent"
ACCEL_HIGH = Decimal("1.15")            # recent burn >= 1.15x prior -> accelerating
ACCEL_LOW = Decimal("0.85")             # recent burn <= 0.85x prior -> decelerating
VOLATILE_COV = Decimal("0.75")          # cov above this is "volatile" (review)
LATE_EMERGENCE_SHARE = Decimal("0.20")  # >= 20% of all spend in the last 2 months


def _cov(values: list[Decimal]) -> Optional[str]:
    """Coefficient of variation over Decimal values, 4dp string, or None."""
    if not values:
        return None
    n = Decimal(len(values))
    mean = sum(values, Decimal("0")) / n
    if mean == 0:
        return None
    var = sum(((v - mean) ** 2 for v in values), Decimal("0")) / n
    std = var.sqrt()
    return str((std / mean).copy_abs().quantize(Decimal("0.0001")))


def _ym(value: Optional[str]) -> Optional[tuple]:
    """Parse a year-month from YYYY-MM or YYYY-MM-DD."""
    if not isinstance(value, str) or len(value) < 7 or value[4] != "-":
        return None
    try:
        return int(value[:4]), int(value[5:7])
    except ValueError:
        return None


def _months_apart(a: Optional[str], b: Optional[str]) -> Optional[int]:
    ya, yb = _ym(a), _ym(b)
    if ya is None or yb is None:
        return None
    return abs((yb[0] - ya[0]) * 12 + (yb[1] - ya[1]))


def analyze(monthly_actuals: list, data_date: Optional[str], project_key: str,
            budget_code_key: str) -> OrderedDict:
    """Return a trend-evidence row for one budget code."""
    completed = sorted((m for m in (monthly_actuals or [])
                        if m.get("actual_period_bucket") == "through_may_2026"),
                       key=lambda m: m.get("month") or "")
    vals = [D(m.get("amount_decimal_string")) for m in completed]
    months = [m.get("month") for m in completed]
    n = len(vals)
    total = sum(vals, Decimal("0"))

    recent_vals = vals[-RECENT_WINDOW:] if vals else []
    prior_vals = vals[-(2 * RECENT_WINDOW):-RECENT_WINDOW] if n >= RECENT_WINDOW + 1 else []
    recent_total = sum(recent_vals, Decimal("0"))
    prior_total = sum(prior_vals, Decimal("0"))
    recent_avg = (recent_total / Decimal(len(recent_vals))) if recent_vals else None
    prior_avg = (prior_total / Decimal(len(prior_vals))) if prior_vals else None

    accel_ratio = None
    accel_class = "indeterminate"
    if recent_avg is not None and prior_avg is not None and prior_avg > 0:
        accel_ratio = (recent_avg / prior_avg)
        if accel_ratio >= ACCEL_HIGH:
            accel_class = "accelerating"
        elif accel_ratio <= ACCEL_LOW:
            accel_class = "decelerating"
        else:
            accel_class = "steady"
    elif recent_avg is not None and (prior_avg is None or prior_avg == 0):
        accel_class = "emerging" if recent_avg > 0 else "flat"

    cov = _cov(vals)
    latest_month = months[-1] if months else None
    recency_gap = _months_apart(latest_month, data_date)

    last2 = sum(vals[-2:], Decimal("0")) if vals else Decimal("0")
    late_emergence = bool(total > 0 and (last2 / total) >= LATE_EMERGENCE_SHARE and n >= 4)
    has_negative_month = any(v < 0 for v in vals)
    credits_deductive = bool(has_negative_month or (recent_total < 0))

    # Directional signal (evidence only; never sets a number).
    cov_d = dec(cov)
    if n < RECENT_WINDOW:
        trend_signal = "review"
    elif credits_deductive and (recent_avg is not None and recent_avg <= 0):
        trend_signal = "supports_decrease"
    elif accel_class in ("accelerating", "emerging"):
        trend_signal = "supports_overrun"
    elif cov_d is not None and cov_d > VOLATILE_COV:
        trend_signal = "review"
    elif accel_class == "decelerating":
        trend_signal = "supports_decrease"
    else:
        trend_signal = "hold"

    return OrderedDict([
        ("project_key", project_key),
        ("budget_code_key", budget_code_key),
        ("months_of_completed_actuals", n),
        ("total_completed_actuals", money_str(total)),
        ("recent_window_months", len(recent_vals)),
        ("recent_period_cost", money_str(recent_total)),
        ("prior_period_cost", money_str(prior_total) if prior_vals else None),
        ("recent_avg_monthly_burn", money_str(recent_avg) if recent_avg is not None else None),
        ("prior_avg_monthly_burn", money_str(prior_avg) if prior_avg is not None else None),
        ("burn_acceleration_ratio",
         str(accel_ratio.quantize(Decimal("0.0001"))) if accel_ratio is not None else None),
        ("burn_acceleration_class", accel_class),
        ("cost_volatility_cov", cov),
        ("latest_actual_month", latest_month),
        ("recency_gap_months", recency_gap),
        ("late_cost_emergence", late_emergence),
        ("credits_deductive_pattern", credits_deductive),
        ("trend_signal", trend_signal),
    ])
