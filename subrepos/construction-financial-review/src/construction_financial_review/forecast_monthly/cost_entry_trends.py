"""CostEntries monthly trend per budget code + a SHAPED forward weight vector.

CostEntries are accounting actual-cost truth. This module characterizes the recent monthly burn shape
and classifies it, then emits a forward monthly weight vector that is NOT flat-by-default: it is
shaped by the classification (front/back-loaded, flat, or review). The weight vector is a pure SHAPE
over the forecast months (sums to 1); dollar amounts and day-aware partial-month scaling are applied
later by the reconciler.
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal
from typing import Optional

from ..common.money import D, dec, money_str

ACCEL_HIGH = Decimal("1.15")
ACCEL_LOW = Decimal("0.85")
VOLATILE_COV = Decimal("0.75")
SPIKE_FACTOR = Decimal("2.0")

# classifications
FLAT = "flat_recent_burn"
FRONT = "accelerating_front_loaded"
BACK = "decelerating_back_loaded"
SPIKE = "recent_spike_review"
CREDIT = "credit_adjusted"
NONE = "no_stable_pattern"


def _cov(values: list[Decimal]) -> Optional[Decimal]:
    if not values:
        return None
    n = Decimal(len(values))
    mean = sum(values, Decimal("0")) / n
    if mean == 0:
        return None
    var = sum(((v - mean) ** 2 for v in values), Decimal("0")) / n
    return (var.sqrt() / mean).copy_abs()


def shape_weights(months: list[str], kind: str) -> "OrderedDict[str, Decimal]":
    """Forward monthly weight vector (sums to 1) for a shape classification."""
    n = len(months)
    if n == 0:
        return OrderedDict()
    if kind == FRONT:
        raw = [Decimal(n - i) for i in range(n)]          # linearly decreasing (heavier near-term)
    elif kind == BACK:
        raw = [Decimal(i + 1) for i in range(n)]          # linearly increasing (heavier later)
    else:
        raw = [Decimal("1") for _ in range(n)]            # flat / spike / credit / none
    total = sum(raw, Decimal("0"))
    return OrderedDict((m, raw[i] / total) for i, m in enumerate(months))


def analyze(monthly_actuals: list, forecast_months: list[str], project_key: str,
            budget_code_key: str) -> tuple[OrderedDict, "OrderedDict[str, Decimal]"]:
    """Return (trend_row, cost_entries_weight_vector)."""
    completed = sorted((m for m in (monthly_actuals or [])
                        if m.get("actual_period_bucket") == "through_may_2026"),
                       key=lambda m: m.get("month") or "")
    vals = [D(m.get("amount_decimal_string")) for m in completed]
    n = len(vals)
    current_month_actual = sum((D(m.get("amount_decimal_string")) for m in (monthly_actuals or [])
                                if m.get("actual_period_bucket") == "june_2026_to_date"), Decimal("0"))

    burn1 = vals[-1] if n >= 1 else None
    burn3 = (sum(vals[-3:], Decimal("0")) / Decimal(min(3, n))) if n >= 1 else None
    burn6 = (sum(vals[-6:], Decimal("0")) / Decimal(min(6, n))) if n >= 1 else None
    prior3 = (sum(vals[-6:-3], Decimal("0")) / Decimal(3)) if n >= 6 else None
    accel = (burn3 / prior3) if (burn3 is not None and prior3 and prior3 > 0) else None
    cov = _cov(vals)
    has_negative = any(v < 0 for v in vals)
    recent_neg = sum(vals[-3:], Decimal("0")) < 0
    spike = bool(n >= 4 and burn3 is not None and burn3 > 0 and burn1 is not None
                 and burn1 > burn3 * SPIKE_FACTOR)

    if n < 3:
        kind = NONE
    elif has_negative or recent_neg:
        kind = CREDIT
    elif spike:
        kind = SPIKE
    elif accel is not None and accel >= ACCEL_HIGH:
        kind = FRONT
    elif accel is not None and accel <= ACCEL_LOW:
        kind = BACK
    else:
        kind = FLAT

    stable_enough = kind in (FLAT, FRONT, BACK)
    if kind == FRONT:
        signal = "supports_overrun"
    elif kind == BACK:
        signal = "supports_underrun"
    elif kind in (SPIKE, NONE):
        signal = "review"
    elif kind == CREDIT:
        signal = "supports_underrun"
    else:
        signal = "hold"

    weights = shape_weights(forecast_months, kind)
    row = OrderedDict([
        ("project_key", project_key),
        ("budget_code_key", budget_code_key),
        ("months_of_completed_actuals", n),
        ("recent_1mo_burn", money_str(burn1) if burn1 is not None else None),
        ("recent_3mo_burn", money_str(burn3) if burn3 is not None else None),
        ("recent_6mo_burn", money_str(burn6) if burn6 is not None else None),
        ("prior_3mo_burn", money_str(prior3) if prior3 is not None else None),
        ("current_month_actual_booked", money_str(current_month_actual)),
        ("burn_acceleration_ratio",
         str(accel.quantize(Decimal("0.0001"))) if accel is not None else None),
        ("cost_volatility_cov", str(cov.quantize(Decimal("0.0001"))) if cov is not None else None),
        ("latest_actual_month", completed[-1]["month"] if completed else None),
        ("credits_deductive_pattern", bool(has_negative or recent_neg)),
        ("recent_spike", spike),
        ("cost_entry_trend_shape", kind),
        ("cost_entry_trend_signal", signal),
        ("stable_enough_for_phasing", stable_enough),
        ("partial_current_month_treatment",
         "current-month actuals booked are excluded from the forward vector and netted out of CTC"),
        ("forward_weight_shape", kind),
    ])
    return row, weights
