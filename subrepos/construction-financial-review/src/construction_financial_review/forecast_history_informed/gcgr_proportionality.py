"""GC-fee / GR proportionality hypothesis test (e.g. 20-18-110 "CONTRACTORS FEE").

Hypothesis: the GC fee tapers toward zero as the cost-of-work (15-* trades) completes, and may be
roughly proportional to cost-of-work percent complete. This is a HYPOTHESIS — proportionality is only
reported ``confirmed`` when the fee's declining remaining forecast genuinely tracks 15-* progress AND
the implied fee total is stable across snapshots. Otherwise the historical decline is reported as a
taper consistent with, but not confirming, proportionality.
"""
from __future__ import annotations

from collections import OrderedDict, defaultdict
from decimal import Decimal

from ..common.money import D, dsum, money_str
from .history_signals import ZERO, ZERO_EPS, snapshot_remaining_series

COST_OF_WORK_FAMILY_PREFIX = "15-"
STABLE_COV = Decimal("0.25")


def _q4(x):
    return str(Decimal(x).quantize(Decimal("0.0001")))


def _cov(vals):
    if len(vals) < 2:
        return None
    m = sum(vals, ZERO) / Decimal(len(vals))
    if m == 0:
        return None
    var = sum(((v - m) ** 2 for v in vals), ZERO) / Decimal(len(vals))
    return (var.sqrt() / m).copy_abs()


def _is_fee_code(cost_code: str, rows: list) -> bool:
    if cost_code == "20-18-110":
        return True
    descs = " ".join((r.get("description") or "") for r in rows).upper()
    return "FEE" in descs and cost_code.startswith("20-")


def _cost_of_work_progress(context_by: dict) -> OrderedDict:
    """Cumulative 15-* actual by month + total revised budget => percent-complete curve."""
    monthly_totals: dict = defaultdict(lambda: ZERO)
    total_revised = ZERO
    code_count = 0
    for key, ctx in context_by.items():
        cc = ctx.get("cost_code") or ""
        if not cc.startswith(COST_OF_WORK_FAMILY_PREFIX):
            continue
        code_count += 1
        ba = ctx.get("budget_amounts") or {}
        total_revised += D(ba.get("revised_budget"))
        for m in ((ctx.get("actuals") or {}).get("monthly_actuals") or []):
            mo = m.get("month")
            if mo:
                monthly_totals[mo] += D(m.get("amount_decimal_string"))
    cumulative = OrderedDict()
    run = ZERO
    for mo in sorted(monthly_totals):
        run += monthly_totals[mo]
        cumulative[mo] = run
    return OrderedDict([
        ("family_prefix", COST_OF_WORK_FAMILY_PREFIX), ("code_count", code_count),
        ("total_revised_budget", money_str(total_revised)),
        ("total_actual_to_date", money_str(run)),
        ("percent_complete_to_date",
         _q4((run / total_revised)) if total_revised > 0 else None),
        ("cumulative_actual_by_month",
         OrderedDict((mo, money_str(v)) for mo, v in cumulative.items())),
        ("_cumulative", cumulative),
        ("_total_revised", total_revised),
    ])


def _percent_complete_at(cow: dict, month: str):
    cum = cow["_cumulative"]
    total = cow["_total_revised"]
    if total <= 0 or not cum:
        return None
    applicable = [v for mo, v in cum.items() if mo <= month]
    if not applicable:
        return ZERO
    return (applicable[-1] / total)


def build_audit(inputs: dict, mapping_by_cc: dict, project_key: str) -> OrderedDict:
    history_rows = inputs["history_rows"]
    context_by = inputs["context_by"]
    by_cc: dict = defaultdict(list)
    for r in history_rows:
        if r.get("cost_code"):
            by_cc[r["cost_code"]].append(r)

    cow = _cost_of_work_progress(context_by)
    fee_codes = sorted(cc for cc, rows in by_cc.items() if _is_fee_code(cc, rows))

    per_fee = []
    overall = "insufficient_evidence"
    for cc in fee_codes:
        rows = by_cc[cc]
        series = snapshot_remaining_series(rows)
        snaps = list(series.keys())
        rem_vals = list(series.values())
        decline = bool(len(rem_vals) >= 2 and rem_vals[-1] < rem_vals[0])
        pct_by_snap = OrderedDict((m, _percent_complete_at(cow, m)) for m in snaps)
        implied_totals = []
        for m in snaps:
            pc = pct_by_snap[m]
            if pc is not None and pc < Decimal("1"):
                implied_totals.append(series[m] / (Decimal("1") - pc))
        implied_cov = _cov(implied_totals)
        pcs = [p for p in pct_by_snap.values() if p is not None]
        inverse = bool(len(rem_vals) >= 2 and len(pcs) >= 2
                       and rem_vals[-1] < rem_vals[0] and pcs[-1] > pcs[0])
        stable = bool(implied_cov is not None and implied_cov <= STABLE_COV)

        if len(rem_vals) < 2 or not pcs:
            status = "insufficient_evidence"
        elif inverse and stable:
            status = "confirmed"
        elif inverse or decline:
            status = "tapering_consistent_not_confirmed"
        else:
            status = "unsupported"

        per_fee.append(OrderedDict([
            ("cost_code", cc),
            ("budget_code_key", mapping_by_cc.get(cc, {}).get("budget_code_key")),
            ("descriptions", sorted({(r.get("description") or "").strip() for r in rows if r.get("description")})),
            ("fee_remaining_forecast_series",
             OrderedDict((m, money_str(v)) for m, v in series.items())),
            ("latest_remaining", money_str(rem_vals[-1]) if rem_vals else None),
            ("historical_decline_observed", decline),
            ("cost_of_work_percent_complete_by_snapshot",
             OrderedDict((m, _q4(p) if p is not None else None) for m, p in pct_by_snap.items())),
            ("implied_fee_total_by_snapshot", [money_str(v) for v in implied_totals]),
            ("implied_fee_total_cov", _q4(implied_cov) if implied_cov is not None else None),
            ("inverse_relationship_with_progress", inverse),
            ("implied_total_stable", stable),
            ("proportionality_status", status),
            ("hypothesis_note",
             "declining remaining is consistent with a tapering GC fee; proportionality to 15-* progress "
             "is reported confirmed only when the relationship is inverse AND the implied fee total is stable"),
        ]))
        if status == "confirmed":
            overall = "confirmed"
        elif status == "tapering_consistent_not_confirmed" and overall != "confirmed":
            overall = "tapering_consistent_not_confirmed"

    return OrderedDict([
        ("project_key", project_key),
        ("hypothesis", "GC fee (e.g. 20-18-110 CONTRACTORS FEE) tapers as cost-of-work completes and may "
                       "be proportional to 15-* cost-of-work percent complete"),
        ("fee_codes_examined", fee_codes),
        ("cost_of_work_basis", OrderedDict((k, v) for k, v in cow.items() if not k.startswith("_"))),
        ("per_fee", per_fee),
        ("overall_status", overall),
        ("requires_human_acceptance", True),
    ])
