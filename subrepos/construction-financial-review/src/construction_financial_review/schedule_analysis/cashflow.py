"""Schedule cash-flow timing curve (Phase 8): lay remaining forecast exposure onto months.

This is TIMING ONLY. It never changes the total recommended projected cost — the monthly
amounts always sum back to the remaining exposure (within rounding tolerance) or the budget code
is marked ``not_allocated``.

Approved refinement: duration-weighted allocation confidence is capped at ``medium`` (the
schedule has no validated cost/resource loading); ambiguous or unmapped schedule evidence stays
``not_allocated``.
"""
from __future__ import annotations

from collections import OrderedDict
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from ..common.dates import normalize_date
from ..common.money import D, money_str

ROUNDING_TOLERANCE = Decimal("0.01")
ALLOC_DURATION_WEIGHTED = "duration_weighted_remaining_activities"
ALLOC_NOT_ALLOCATED = "not_allocated"


def _to_date(s) -> Optional[date]:
    ds = normalize_date(s)
    if not ds:
        return None
    try:
        y, m, d = ds.split("-")
        return date(int(y), int(m), int(d))
    except Exception:
        return None


def _month_day_weights(start: date, finish: date) -> "OrderedDict[str, int]":
    """Calendar-day count per ``YYYY-MM`` month over the inclusive [start, finish] span."""
    if finish < start:
        finish = start
    weights: "OrderedDict[str, int]" = OrderedDict()
    cur = start
    while cur <= finish:
        key = f"{cur.year:04d}-{cur.month:02d}"
        weights[key] = weights.get(key, 0) + 1
        cur += timedelta(days=1)
    return weights


def remaining_forecast_exposure(current_projected_cost, actual_cost,
                                schedule_integrated_recommended_cost=None) -> Decimal:
    """max(projected - actual, 0); use the schedule-integrated recommended cost when it is higher
    (e.g. floor-to-actuals raised the number)."""
    projected = D(current_projected_cost)
    rec = D(schedule_integrated_recommended_cost) if schedule_integrated_recommended_cost is not None else projected
    basis = max(projected, rec)
    exposure = basis - D(actual_cost)
    return exposure if exposure > 0 else Decimal("0")


def allocate_budget_code(budget_code_key: str, project_key: str, exposure: Decimal,
                         open_features: list[dict]) -> list[dict]:
    """Spread ``exposure`` across months covered by mapped open activities, duration-weighted.

    ``open_features`` are the budget code's *mapped, open* activity feature rows. Returns one row
    per allocated month, or a single ``not_allocated`` row when allocation is not possible.
    """
    def _not_allocated(note: str, conf: str = "none") -> list[dict]:
        return [OrderedDict([
            ("project_key", project_key),
            ("budget_code_key", budget_code_key),
            ("month", None),
            ("remaining_forecast_exposure_total", money_str(exposure)),
            ("scheduled_allocation_amount", money_str(Decimal("0"))),
            ("allocation_percent", "0.0000"),
            ("allocation_method", ALLOC_NOT_ALLOCATED),
            ("supporting_activity_count", 0),
            ("allocation_confidence", conf),
            ("notes", note),
        ])]

    if exposure <= 0:
        return _not_allocated("No positive remaining forecast exposure to allocate.")

    # Aggregate calendar-day weight per month across activities with usable remaining dates.
    month_weight: dict[str, int] = {}
    month_support: dict[str, int] = {}
    usable = 0
    for f in open_features:
        s = _to_date(f.get("remaining_start"))
        e = _to_date(f.get("remaining_finish"))
        if not s or not e:
            continue
        usable += 1
        for m, w in _month_day_weights(s, e).items():
            month_weight[m] = month_weight.get(m, 0) + w
            month_support[m] = month_support.get(m, 0) + 1

    total_weight = sum(month_weight.values())
    if usable == 0 or total_weight == 0:
        return _not_allocated("Mapped open activities lack usable remaining start/finish dates.", "none")

    months = sorted(month_weight)
    rows = []
    allocated = Decimal("0")
    total_w = Decimal(total_weight)
    for i, m in enumerate(months):
        w = Decimal(month_weight[m])
        if i < len(months) - 1:
            amt = (exposure * w / total_w).quantize(ROUNDING_TOLERANCE)
        else:
            amt = exposure - allocated  # last month absorbs rounding so the sum ties exactly
        allocated += amt
        pct = (w / total_w).quantize(Decimal("0.0001"))
        rows.append(OrderedDict([
            ("project_key", project_key),
            ("budget_code_key", budget_code_key),
            ("month", m),
            ("remaining_forecast_exposure_total", money_str(exposure)),
            ("scheduled_allocation_amount", money_str(amt)),
            ("allocation_percent", str(pct)),
            ("allocation_method", ALLOC_DURATION_WEIGHTED),
            ("supporting_activity_count", month_support[m]),
            ("allocation_confidence", "medium"),  # capped at medium: no validated cost/resource loading
            ("notes", None),
        ]))
    return rows


def allocation_ties(rows: list[dict], exposure: Decimal) -> bool:
    """True if the allocated months sum to the exposure within tolerance (or were not allocated)."""
    alloc_rows = [r for r in rows if r["allocation_method"] != ALLOC_NOT_ALLOCATED]
    if not alloc_rows:
        return True
    total = sum((D(r["scheduled_allocation_amount"]) for r in alloc_rows), Decimal("0"))
    return abs(total - exposure) <= ROUNDING_TOLERANCE
