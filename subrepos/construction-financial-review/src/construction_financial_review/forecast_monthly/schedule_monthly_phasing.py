"""Per-budget-code schedule monthly weight vector from mapped open-activity spans.

Only code-level associations (direct / cost_code_family / owner_scope / division / vendor_or_commitment)
may phase a code's cost. Project-level association is context only and produces NO vector. Direct codes
use their own mapped open-activity remaining spans; weaker influencing associations use a synthetic
span from the schedule data date to the borrowed latest schedule finish. Weights are clipped to the
forecast window and renormalized; reuses ``schedule_analysis.cashflow._month_day_weights``.
"""
from __future__ import annotations

from collections import OrderedDict
from datetime import date
from decimal import Decimal
from typing import Optional

from ..common.dates import normalize_date
from ..schedule_analysis import cashflow

INFLUENCING = ("direct", "cost_code_family", "owner_scope", "division", "vendor_or_commitment")


def _to_date(s) -> Optional[date]:
    ds = normalize_date(s)
    if not ds:
        return None
    try:
        y, m, d = ds.split("-")
        return date(int(y), int(m), int(d))
    except Exception:
        return None


def analyze(assoc_row: dict, open_features: list, forecast_months: list[str],
            schedule_data_date: Optional[str], project_key: str,
            budget_code_key: str) -> tuple[OrderedDict, Optional["OrderedDict[str, Decimal]"]]:
    """Return (schedule_phasing_row, schedule_weight_vector_or_None)."""
    assoc = assoc_row.get("schedule_association")
    conf = assoc_row.get("schedule_confidence")
    influences = bool(assoc_row.get("influences_code_estimate")) and assoc in INFLUENCING
    forecast_set = set(forecast_months)

    spans: list[tuple[date, date]] = []
    used_reason = None
    if influences:
        if assoc == "direct" and open_features:
            for f in open_features:
                s, e = _to_date(f.get("remaining_start")), _to_date(f.get("remaining_finish"))
                if s and e:
                    spans.append((s, e))
        if not spans:
            lf = _to_date(assoc_row.get("latest_schedule_finish"))
            anchor = _to_date(schedule_data_date) or _to_date(forecast_months[0] + "-01")
            if lf and anchor:
                spans.append((min(anchor, lf), lf))
        if not spans:
            used_reason = "influencing association but no usable activity spans / finish date"
    else:
        used_reason = ("project_level/none association — schedule is context only, does not phase code"
                       if assoc else "no schedule association")

    vector = None
    monthly_dist = []
    if spans:
        merged: dict[str, int] = {}
        for s, e in spans:
            for m, w in cashflow._month_day_weights(s, e).items():
                merged[m] = merged.get(m, 0) + w
        clipped = {m: w for m, w in merged.items() if m in forecast_set}
        total = sum(clipped.values())
        if total > 0:
            vector = OrderedDict((m, Decimal(clipped[m]) / Decimal(total)) for m in sorted(clipped))
            monthly_dist = [OrderedDict([("month", m),
                                         ("weight", str(vector[m].quantize(Decimal("0.0001"))))])
                            for m in vector]
        else:
            used_reason = "schedule activity spans fall outside the forecast window"

    row = OrderedDict([
        ("project_key", project_key),
        ("budget_code_key", budget_code_key),
        ("schedule_association_type", assoc),
        ("schedule_confidence", conf),
        ("associated_activity_count", assoc_row.get("open_activity_count")),
        ("direct_mapped_activity_count", assoc_row.get("direct_mapped_activity_count")),
        ("direct_activity_refs", assoc_row.get("activity_refs") if assoc == "direct" else []),
        ("schedule_data_date", normalize_date(schedule_data_date)),
        ("latest_schedule_finish", assoc_row.get("latest_schedule_finish")),
        ("remaining_activity_duration_days", assoc_row.get("remaining_duration_days")),
        ("used_for_budget_code_phasing", vector is not None),
        ("not_used_reason", used_reason if vector is None else None),
        ("monthly_schedule_weight_distribution", monthly_dist),
    ])
    return row, vector
