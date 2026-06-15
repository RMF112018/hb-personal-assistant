"""Validate historical forecast assumptions against CostEntries/Sage actual cost (the reality check).

CostEntries are accounting truth; historical forecasts are prior assumptions. For each code we take the
latest historical snapshot's remaining forecast and compare it to the actual cost actually incurred in
the months after that snapshot, then classify whether the prior assumption was validated, contradicted
by escalation, or contradicted by unexpected activity (a stale-zero that later booked cost). A recent
escalating actual trend produces an override score so stale history never wins.
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal

from ..common.money import D, dsum, money_str
from .history_signals import ZERO, ZERO_EPS, snapshot_remaining_series

MATERIAL = Decimal("25000")
TOLERANCE = Decimal("0.20")        # |actual-forecast|/forecast within 20% => aligned


def _q4(x):
    return str(Decimal(x).quantize(Decimal("0.0001")))


def _monthly_actuals(context_row: dict) -> "OrderedDict[str, Decimal]":
    out = OrderedDict()
    for m in ((context_row.get("actuals") or {}).get("monthly_actuals") or []):
        mo = m.get("month")
        if mo:
            out[mo] = out.get(mo, ZERO) + D(m.get("amount_decimal_string"))
    return OrderedDict(sorted(out.items()))


def _trailing_burn(ordered_months: list, n: int) -> Decimal:
    return dsum([v for _, v in ordered_months[-n:]]) if ordered_months else ZERO


def build_validation(cost_code: str, rows: list, mapping: dict, context_by: dict,
                     intel: dict, project_key: str) -> OrderedDict:
    key = mapping.get("budget_code_key")
    series = snapshot_remaining_series(rows)
    latest_snap = list(series.keys())[-1] if series else None
    remaining = series[latest_snap] if latest_snap else ZERO

    base = OrderedDict([
        ("project_key", project_key),
        ("budget_code_key", key),
        ("cost_code", cost_code),
        ("mapping_status", mapping.get("mapping_status")),
        ("historical_forecast_month", latest_snap),
        ("historical_forecasted_remaining_in_window", money_str(remaining) if latest_snap else None),
    ])

    ctx = context_by.get(key) if key else None
    if not key or ctx is None:
        base.update(OrderedDict([
            ("validation_window_start", None), ("validation_window_end", None),
            ("cost_entries_actual_cost_in_window", None),
            ("absolute_variance", None), ("percentage_variance", None),
            ("actual_inactivity_months_after_forecast", None),
            ("recent_1mo_burn", None), ("recent_3mo_burn", None),
            ("recent_6mo_burn", None), ("recent_12mo_burn", None),
            ("late_cost_emergence", None), ("burn_acceleration_class", None),
            ("credits_deductive_pattern", None), ("actual_trend_override_score", _q4(ZERO)),
            ("validation_class", "insufficient_actuals_no_unique_mapping"),
            ("validation_confidence", _q4(ZERO)),
            ("requires_human_acceptance", True),
            ("notes", "no unique canonical mapping or no per-code actuals available"),
        ]))
        return base

    months = list(_monthly_actuals(ctx).items())
    after = [(mo, v) for mo, v in months if latest_snap and mo > latest_snap]
    window_end = months[-1][0] if months else None
    actual_in_window = dsum([v for _, v in after])
    abs_var = actual_in_window - remaining
    pct_var = (abs_var / remaining) if remaining > 0 else None
    inactivity = sum(1 for _, v in after if v.copy_abs() <= ZERO_EPS)
    credits = any(v < 0 for _, v in months)

    burn1, burn3, burn6, burn12 = (_trailing_burn(months, n) for n in (1, 3, 6, 12))
    prior3 = dsum([v for _, v in months[-6:-3]]) if len(months) >= 6 else ZERO
    accel_ratio = (burn3 / prior3) if prior3 > 0 else None
    accel_class = _accel_class(intel, key, accel_ratio)
    late_emergence = _late_emergence(months)

    vclass, vconf, override = _classify(remaining, actual_in_window, abs_var, accel_ratio,
                                        inactivity, len(after), burn12, bool(months))

    base.update(OrderedDict([
        ("validation_window_start", after[0][0] if after else None),
        ("validation_window_end", window_end),
        ("cost_entries_actual_cost_in_window", money_str(actual_in_window)),
        ("absolute_variance", money_str(abs_var)),
        ("percentage_variance", _q4(pct_var) if pct_var is not None else None),
        ("actual_inactivity_months_after_forecast", inactivity),
        ("recent_1mo_burn", money_str(burn1)), ("recent_3mo_burn", money_str(burn3)),
        ("recent_6mo_burn", money_str(burn6)), ("recent_12mo_burn", money_str(burn12)),
        ("late_cost_emergence", late_emergence),
        ("burn_acceleration_class", accel_class),
        ("credits_deductive_pattern", credits),
        ("actual_trend_override_score", _q4(override)),
        ("validation_class", vclass),
        ("validation_confidence", _q4(vconf)),
        ("requires_human_acceptance", True),
        ("notes", None),
    ]))
    return base


def _accel_class(intel, key, accel_ratio):
    trend = (intel.get("trend") or {}).get(key) if intel else None
    if trend and trend.get("burn_acceleration_class"):
        return trend["burn_acceleration_class"]
    if accel_ratio is None:
        return "indeterminate"
    if accel_ratio >= Decimal("1.15"):
        return "accelerating"
    if accel_ratio <= Decimal("0.85"):
        return "decelerating"
    return "steady"


def _late_emergence(months: list) -> bool:
    """Cost emerges after a sustained zero gap (>=3 trailing-then-active)."""
    nonzero_idx = [i for i, (_, v) in enumerate(months) if v.copy_abs() > ZERO_EPS]
    if len(nonzero_idx) < 2:
        return False
    gaps = [nonzero_idx[i] - nonzero_idx[i - 1] for i in range(1, len(nonzero_idx))]
    return any(g >= 3 for g in gaps)


def _classify(remaining, actual, abs_var, accel_ratio, inactivity, n_after, recent_12mo_burn, has_actuals):
    """Return (validation_class, confidence, actual_trend_override_score)."""
    escalating = accel_ratio is not None and accel_ratio >= Decimal("1.15")
    if remaining <= ZERO_EPS:
        # zero-remaining recommendation requires actual inactivity evidence (no meaningful recent burn)
        if not has_actuals:
            return "inconclusive_zero", Decimal("0.40"), ZERO
        if actual > MATERIAL:
            return "contradicted_unexpected_actuals", Decimal("0.70"), Decimal("0.90")
        if recent_12mo_burn.copy_abs() <= MATERIAL:
            return "validated_zero_inactive", Decimal("0.75"), ZERO
        return "inconclusive_zero", Decimal("0.40"), ZERO
    # nonzero remaining forecast
    if escalating and actual > remaining + MATERIAL:
        return "contradicted_escalation", Decimal("0.75"), Decimal("0.95")
    rel = (abs_var / remaining).copy_abs() if remaining > 0 else None
    if rel is not None and rel <= TOLERANCE:
        return "validated_aligned", Decimal("0.70"), Decimal("0.20")
    if actual < remaining and rel is not None and rel > TOLERANCE:
        return "history_overstated_remaining", Decimal("0.55"), Decimal("0.30")
    if actual > remaining:
        return "actuals_exceed_history", Decimal("0.55"), Decimal("0.70")
    return "inconclusive", Decimal("0.35"), Decimal("0.30")
