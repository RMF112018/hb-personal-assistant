"""Cadence -> monthly phasing weights (the single shared logic for the slice + forecast_monthly).

A cadence class maps to a normalized monthly weight vector (sums to 1) that shapes HOW a code's
remaining cost spreads across months — never how much. Staffing / weekly cadence uses weekday-normalized
weights (a month with more weekdays carries proportionally more). Monthly/twice-monthly cadence spreads
evenly. One-time / irregular / inactive / insufficient cadence returns None so other timing sources
(schedule / cost-entry trend / invoice) phase the code instead.

For staffing codes we also project raw cost (daily_rate x weekdays per month) and scale it to the
accepted cost-to-complete, preserving the weekday shape — this proves the projection never changes any
accepted final cost (it only redistributes CTC by weekday).
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal

from ..common.money import D, money_str
from .weekday_calendar import weekday_weight_vector, weekdays_in_month

ZERO = Decimal("0")
ONE = Decimal("1")

# cadence classes that yield a usable monthly phasing shape
_WEEKDAY_CLASSES = ("weekly_internal_staffing", "weekly_observed")
_EVEN_CLASSES = ("twice_monthly_observed", "monthly_observed")


def phasing_weight_vector(effective_class: str, forecast_months: list):
    """Normalized monthly weight vector for the cadence, or None when cadence is non-informative."""
    if not forecast_months:
        return None
    if effective_class in _WEEKDAY_CLASSES:
        return weekday_weight_vector(forecast_months)
    if effective_class in _EVEN_CLASSES:
        n = Decimal(len(forecast_months))
        return OrderedDict((m, ONE / n) for m in forecast_months)
    return None


def phasing_confidence(effective_class: str, detected_confidence: str, is_staffing: bool) -> str:
    """Confidence band the monthly reconciler turns into a frequency source share."""
    if is_staffing or effective_class == "weekly_internal_staffing":
        return "high"
    if effective_class == "weekly_observed":
        return detected_confidence if detected_confidence in ("high", "medium", "low") else "medium"
    if effective_class in _EVEN_CLASSES:
        return "low"
    return "none"


def recommended_basis(effective_class: str, is_staffing: bool) -> str:
    if is_staffing or effective_class == "weekly_internal_staffing":
        return "weekday_normalized_staffing"
    if effective_class == "weekly_observed":
        return "weekday_normalized_weekly"
    if effective_class in _EVEN_CLASSES:
        return "even_monthly"
    return "defer_to_other_timing_sources"


def staffing_projection(daily_rate, forecast_months: list) -> "OrderedDict[str, Decimal]":
    """Raw weekday-driven cost projection: daily_rate x weekdays-in-month per forecast month."""
    rate = D(daily_rate)
    return OrderedDict((m, rate * Decimal(weekdays_in_month(m))) for m in forecast_months)


def scale_to_ctc(projection: "OrderedDict[str, Decimal]", ctc):
    """Scale a raw projection to exactly the accepted cost-to-complete, preserving weekday shape.

    Returns (scaled_projection, scaled_flag, factor). Shape (relative month weights) is unchanged;
    only the level is set to CTC, so no accepted final cost is altered — timing only.
    """
    total = sum(projection.values(), ZERO)
    ctc_d = D(ctc) if ctc is not None else None
    if ctc_d is None or total <= 0:
        return OrderedDict(projection), False, None
    factor = ctc_d / total
    scaled = OrderedDict((m, v * factor) for m, v in projection.items())
    return scaled, (factor != ONE), factor


def phasing_row(project_key: str, key: str, cost_code: str, category: str, is_staffing: bool,
                effective_class: str, detected_confidence: str, forecast_months: list,
                daily_rate, ctc) -> OrderedDict:
    """Per-code advisory phasing row for frequency_adjusted_monthly_phasing_by_budget_code.jsonl."""
    vector = phasing_weight_vector(effective_class, forecast_months)
    basis = recommended_basis(effective_class, is_staffing)
    weights = [OrderedDict([("forecast_month", m), ("weight", str(vector[m].quantize(Decimal("0.000001"))))])
               for m in forecast_months] if vector else []
    staffing_scaled_flag = False
    staffing_months = []
    if is_staffing and daily_rate is not None:
        raw = staffing_projection(daily_rate, forecast_months)
        scaled, staffing_scaled_flag, _ = scale_to_ctc(raw, ctc)
        staffing_months = [OrderedDict([
            ("forecast_month", m), ("weekdays", weekdays_in_month(m)),
            ("raw_weekday_projection", money_str(raw[m])),
            ("scaled_to_ctc_projection", money_str(scaled[m])),
        ]) for m in forecast_months]
    return OrderedDict([
        ("project_key", project_key),
        ("budget_code_key", key),
        ("cost_code", cost_code),
        ("category", category),
        ("is_internal_staffing_code", is_staffing),
        ("effective_frequency_class", effective_class),
        ("recommended_monthly_phasing_basis", basis),
        ("phasing_weights_available", bool(vector)),
        ("monthly_phasing_weights", weights),
        ("staffing_projection_scaled_to_ctc", staffing_scaled_flag),
        ("staffing_monthly_projection", staffing_months),
        ("phasing_confidence", phasing_confidence(effective_class, detected_confidence, is_staffing)),
        ("do_not_change_accepted_final_cost", True),
        ("requires_human_acceptance", True),
    ])
