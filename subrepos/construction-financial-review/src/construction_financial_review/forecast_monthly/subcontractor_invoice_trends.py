"""Subcontractor invoice / Procore pay-app monthly trend per budget code + its OWN weight vector.

Subcontractor invoice values are progress / exposure / timing evidence — NEVER accounting actuals and
never written as actuals. Where a code has mapped invoice history this builds an independent forward
monthly weight vector (its own timing signal). Where there is no mapped invoice evidence the row is
marked ``unavailable`` and contributes nothing to the blend (invoice is not forced).
"""
from __future__ import annotations

from collections import OrderedDict, defaultdict
from decimal import Decimal
from typing import Optional

from ..common.money import D, dec, money_str
from .cost_entry_trends import (ACCEL_HIGH, ACCEL_LOW, BACK, FLAT, FRONT, NONE, shape_weights)


def _monthly_movement(rows: list) -> "OrderedDict[str, Decimal]":
    """Sum work_completed_this_period per period_end month (the period's billing movement)."""
    by_month: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for r in rows:
        pe = r.get("period_end")
        if not pe or len(pe) < 7:
            continue
        by_month[pe[:7]] += D(r.get("work_completed_this_period"))
    return OrderedDict((m, by_month[m]) for m in sorted(by_month))


def analyze(invoice_rows: list, forecast_months: list[str], project_key: str,
            budget_code_key: str, cost_latest_month: Optional[str]) -> tuple[OrderedDict, Optional["OrderedDict[str, Decimal]"]]:
    """Return (invoice_trend_row, invoice_weight_vector_or_None)."""
    rows = [r for r in (invoice_rows or []) if r.get("mapping_status") == "mapped"]
    if not rows:
        row = OrderedDict([
            ("project_key", project_key),
            ("budget_code_key", budget_code_key),
            ("invoice_evidence", "unavailable"),
            ("historical_invoice_periods", 0),
            ("invoice_trend_signal", "unavailable"),
            ("invoice_leads_or_lags_cost_entries", "unavailable"),
            ("confidence_in_invoice_trend", "none"),
            ("note", "No mapped subcontractor invoice evidence for this budget code."),
        ])
        return row, None

    movement = _monthly_movement(rows)
    months = list(movement)
    vals = list(movement.values())
    n = len(months)
    latest_period = max((r.get("period_end") for r in rows if r.get("period_end")), default=None)
    latest_completed = max((dec(r.get("total_completed_and_stored_to_date")) or Decimal("0")
                            for r in rows), default=Decimal("0"))
    latest_scheduled = max((dec(r.get("scheduled_value")) or Decimal("0") for r in rows),
                           default=Decimal("0"))
    latest_retainage = max((dec(r.get("retainage_held")) or Decimal("0") for r in rows),
                           default=Decimal("0"))
    remaining_balance = (latest_scheduled - latest_completed) if latest_scheduled > 0 else None

    burn3 = (sum(vals[-3:], Decimal("0")) / Decimal(min(3, n))) if n >= 1 else None
    prior3 = (sum(vals[-6:-3], Decimal("0")) / Decimal(3)) if n >= 6 else None
    accel = (burn3 / prior3) if (burn3 is not None and prior3 and prior3 > 0) else None
    has_negative = any(v < 0 for v in vals)

    if n < 2:
        kind = NONE
    elif accel is not None and accel >= ACCEL_HIGH:
        kind = FRONT
    elif accel is not None and accel <= ACCEL_LOW:
        kind = BACK
    else:
        kind = FLAT

    if has_negative:
        signal = "supports_underrun"
    elif kind == FRONT:
        signal = "supports_overrun"
    elif kind == BACK:
        signal = "supports_underrun"
    elif kind == NONE:
        signal = "review"
    else:
        signal = "hold"

    # leads/lags: invoice billing recency vs latest CostEntries month
    leads_lags = "concurrent"
    inv_month = latest_period[:7] if latest_period else None
    if inv_month and cost_latest_month:
        if inv_month > cost_latest_month:
            leads_lags = "invoice_leads_cost"
        elif inv_month < cost_latest_month:
            leads_lags = "invoice_lags_cost"
    confidence = "high" if n >= 6 else ("medium" if n >= 3 else "low")

    vector = shape_weights(forecast_months, kind) if n >= 2 else None
    row = OrderedDict([
        ("project_key", project_key),
        ("budget_code_key", budget_code_key),
        ("invoice_evidence", "available"),
        ("historical_invoice_periods", n),
        ("earliest_invoice_month", months[0] if months else None),
        ("latest_invoice_period", latest_period),
        ("latest_completed_and_stored_to_date", money_str(latest_completed)),
        ("latest_scheduled_value", money_str(latest_scheduled) if latest_scheduled else None),
        ("latest_retainage_held", money_str(latest_retainage)),
        ("invoice_remaining_balance", money_str(remaining_balance) if remaining_balance is not None else None),
        ("recent_3mo_invoice_movement", money_str(burn3) if burn3 is not None else None),
        ("prior_3mo_invoice_movement", money_str(prior3) if prior3 is not None else None),
        ("invoice_acceleration_ratio", str(accel.quantize(Decimal("0.0001"))) if accel is not None else None),
        ("deductive_credit_indicator", has_negative),
        ("invoice_trend_shape", kind),
        ("invoice_trend_signal", signal),
        ("invoice_leads_or_lags_cost_entries", leads_lags),
        ("confidence_in_invoice_trend", confidence),
        ("forward_weight_shape", kind if vector is not None else None),
        ("note", None),
    ])
    return row, vector
