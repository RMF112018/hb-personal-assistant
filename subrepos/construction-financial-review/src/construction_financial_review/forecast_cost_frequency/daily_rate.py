"""Weekday-normalized internal-staffing daily rate from the latest COMPLETE actual month.

daily_rate = latest_complete_month_actual_cost / weekdays_in(latest_complete_month). The partial current
month (after the latest-complete boundary) is never used as the rate basis. The latest-complete rate is
compared to trailing 3- and 6-month weekday-normalized rates; a material divergence raises a staffing
rate-volatility warning. Credit/negative months are allowed only with a surfaced warning.
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal

from ..common.money import D, money_str
from .weekday_calendar import month_index, weekdays_in_month

ZERO = Decimal("0")
RATE_VOLATILITY_PCT = Decimal("0.25")   # |latest - trailing6| / trailing6 beyond this => volatile


def _q4(x) -> str:
    return str(Decimal(x).quantize(Decimal("0.0001")))


def _complete_actuals(monthly_actuals: list, complete_boundary: str) -> list:
    """(month, amount) for months <= the latest-complete boundary, sorted by month."""
    out = []
    for ma in monthly_actuals or []:
        m = ma.get("month")
        if not m or month_index(m) > month_index(complete_boundary):
            continue
        out.append((m, D(ma.get("amount_decimal_string"))))
    out.sort(key=lambda t: month_index(t[0]))
    return out


def _trailing_weekday_rate(complete: list, basis_month: str, n: int) -> Decimal:
    """Weekday-normalized daily rate over the n complete months ending at basis_month."""
    end = month_index(basis_month)
    window = [(m, a) for m, a in complete if end - (n - 1) <= month_index(m) <= end]
    cost = sum((a for _, a in window), ZERO)
    weekdays = sum((Decimal(weekdays_in_month(m)) for m, _ in window), ZERO)
    return (cost / weekdays) if weekdays > 0 else ZERO


def compute(monthly_actuals: list, complete_boundary: str, cfg_fcf: dict,
            project_key: str, key: str, cost_code: str, category: str) -> OrderedDict:
    complete = _complete_actuals(monthly_actuals, complete_boundary)
    nonzero = [(m, a) for m, a in complete if a != 0]
    base = OrderedDict([
        ("project_key", project_key), ("budget_code_key", key),
        ("cost_code", cost_code), ("category", category),
    ])
    if not nonzero:
        base.update(OrderedDict([
            ("latest_complete_month", None), ("latest_complete_month_actual_cost", None),
            ("latest_complete_month_weekdays", None), ("daily_rate", None),
            ("daily_rate_basis", "no_complete_month_actuals"), ("daily_rate_confidence", "none"),
            ("trailing_3mo_daily_rate", None), ("trailing_6mo_daily_rate", None),
            ("rate_volatility_flag", False), ("credit_month_present", False),
            ("complete_months_observed", len(complete)),
        ]))
        return base

    basis_month, basis_cost = nonzero[-1]
    weekdays = weekdays_in_month(basis_month)
    rate = (basis_cost / Decimal(weekdays)) if weekdays > 0 else ZERO
    t3 = _trailing_weekday_rate(complete, basis_month, 3)
    t6 = _trailing_weekday_rate(complete, basis_month, 6)
    credit_present = any(a < 0 for _, a in complete)

    # volatility: latest-complete rate vs trailing 6-month weekday-normalized rate (relative)
    volatile = bool(t6 > 0 and (abs(rate - t6) / t6) > RATE_VOLATILITY_PCT)
    months_complete = len(nonzero)
    confidence = "high" if months_complete >= 6 and not volatile else ("medium" if months_complete >= 3 else "low")

    base.update(OrderedDict([
        ("latest_complete_month", basis_month),
        ("latest_complete_month_actual_cost", money_str(basis_cost)),
        ("latest_complete_month_weekdays", weekdays),
        ("daily_rate", _q4(rate)),
        ("daily_rate_basis", f"latest_complete_month_weekday_normalized:{basis_month}"),
        ("daily_rate_confidence", confidence),
        ("trailing_3mo_daily_rate", _q4(t3)),
        ("trailing_6mo_daily_rate", _q4(t6)),
        ("rate_volatility_flag", bool(volatile)),
        ("credit_month_present", credit_present),
        ("complete_months_observed", months_complete),
    ]))
    return base
