"""Blend the three monthly timing vectors into month costs and reconcile to CTC and final cost.

Blended weight per month = schedule_share·schedule + cost_share·cost_entries + invoice_share·invoice
(missing vectors contribute 0). schedule_share = schedule_confidence; the residual splits between
CostEntries and invoice by invoice quality. The partial current month's weight is scaled by its
unbooked day-remainder fraction, then weights are renormalized. Month costs sum EXACTLY to the
cost-to-complete (last nonzero month absorbs the cent residual), so actual + Σ == final cost.
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal
from typing import Optional

from ..common.budget_keys import parse_budget_key
from ..common.money import D, dec, materiality, money_str

CENTS = Decimal("0.01")
INVOICE_FACTOR = {"high": Decimal("0.5"), "medium": Decimal("0.4"), "low": Decimal("0.25")}
# Cadence/frequency timing share carved from the post-schedule residual (staffing weekday cadence is
# the primary timing basis for staffing codes). "none" => no frequency contribution.
FREQUENCY_FACTOR = {"high": Decimal("0.8"), "medium": Decimal("0.6"), "low": Decimal("0.4"),
                    "none": Decimal("0")}


def _clamp01(x: Decimal) -> Decimal:
    return Decimal("0") if x < 0 else (Decimal("1") if x > 1 else x)


def _allocate(ctc: Decimal, blended: "OrderedDict[str, Decimal]", months: list[str]) -> dict:
    """Allocate ctc across months by blended weights; last nonzero month absorbs the residual."""
    out = {m: Decimal("0") for m in months}
    if ctc == 0:
        return out
    nonzero = [m for m in months if blended[m] > 0]
    if not nonzero:
        # No timing weight anywhere — flat over all months (last absorbs residual).
        nonzero = months
        even = OrderedDict((m, Decimal("1") / Decimal(len(months))) for m in months)
        blended = even
    last = nonzero[-1]
    alloc = Decimal("0")
    for m in months:
        if blended[m] <= 0 or m == last:
            continue
        amt = (ctc * blended[m]).quantize(CENTS)
        out[m] = amt
        alloc += amt
    out[last] = ctc - alloc
    return out


def reconcile_code(rec: dict, calendar: dict, cost_weights: "OrderedDict[str, Decimal]",
                   invoice_weights: Optional["OrderedDict[str, Decimal]"],
                   schedule_weights: Optional["OrderedDict[str, Decimal]"],
                   schedule_confidence, invoice_confidence: str, cost_shape: str,
                   project_key: str,
                   frequency_weights: Optional["OrderedDict[str, Decimal]"] = None,
                   frequency_confidence: str = "none") -> dict:
    months = [m["forecast_month"] for m in calendar["months"]]
    frac = {m["forecast_month"]: dec(m["month_remaining_fraction"]) or Decimal("1")
            for m in calendar["months"]}
    partial_month = next((m["forecast_month"] for m in calendar["months"]
                          if m["is_partial_current_month"]), None)

    actual = D(rec.get("actual_cost_all_source_to_date"))
    rec_final = D(rec.get("recommended_final_cost"))
    worst_final = D(rec.get("worst_credible_final_cost"))
    rec_ctc = D(rec.get("recommended_cost_to_complete"))
    worst_ctc = D(rec.get("worst_credible_cost_to_complete"))
    projected = dec(rec.get("current_projected_cost"))
    revised = dec(rec.get("revised_budget"))

    # ---- source shares ----
    # schedule first; then cadence/frequency (staffing weekday cadence is the primary timing basis);
    # the remaining residual splits between invoice and cost-entries as before. Adding frequency only
    # reshapes month weights — it never changes the cost-to-complete or the accepted final cost.
    sched_share = _clamp01(dec(schedule_confidence) or Decimal("0")) if schedule_weights else Decimal("0")
    remaining = Decimal("1") - sched_share
    freq_factor = FREQUENCY_FACTOR.get(frequency_confidence, Decimal("0")) if frequency_weights else Decimal("0")
    freq_share = remaining * freq_factor
    remaining = remaining - freq_share
    inv_factor = INVOICE_FACTOR.get(invoice_confidence, Decimal("0")) if invoice_weights else Decimal("0")
    inv_share = remaining * inv_factor
    cost_share = remaining - inv_share

    blended: "OrderedDict[str, Decimal]" = OrderedDict()
    for m in months:
        w = cost_share * cost_weights.get(m, Decimal("0"))
        if schedule_weights:
            w += sched_share * schedule_weights.get(m, Decimal("0"))
        if frequency_weights:
            w += freq_share * frequency_weights.get(m, Decimal("0"))
        if invoice_weights:
            w += inv_share * invoice_weights.get(m, Decimal("0"))
        blended[m] = w
    # day-aware partial current month
    if partial_month and partial_month in blended:
        blended[partial_month] *= frac.get(partial_month, Decimal("1"))
    total = sum(blended.values(), Decimal("0"))
    if total > 0:
        for m in months:
            blended[m] = blended[m] / total
    else:
        for m in months:
            blended[m] = Decimal("1") / Decimal(len(months))

    rec_month = _allocate(rec_ctc, blended, months)
    worst_month = _allocate(worst_ctc, blended, months)

    # ---- per-month rows + cumulative + overrun timing ----
    parsed = parse_budget_key(rec.get("budget_code_key"))
    cost_code = parsed[1] if parsed else None
    category = parsed[2] if parsed else None
    var_proj = (rec_final - projected) if projected is not None else None
    var_rev = (rec_final - revised) if revised is not None else None
    # Authoritative overrun flags come from the accepted forecast-intelligence package (already
    # materiality-gated); the monthly final cost is that package's final cost, so they are consistent.
    over_proj = bool(rec.get("overrun_vs_current_projected_cost"))
    over_rev = bool(rec.get("overrun_vs_revised_budget"))

    cum_rec = actual
    cum_worst = actual
    first_exceed_proj = first_exceed_rev = None
    peak_month_cost = Decimal("0")
    month_costs = []
    calendar_by = {m["forecast_month"]: m for m in calendar["months"]}
    for m in months:
        cum_rec += rec_month[m]
        cum_worst += worst_month[m]
        if first_exceed_proj is None and projected is not None and cum_rec > projected:
            first_exceed_proj = m
        if first_exceed_rev is None and revised is not None and cum_rec > revised:
            first_exceed_rev = m
        if rec_month[m] > peak_month_cost:
            peak_month_cost = rec_month[m]
        cmeta = calendar_by[m]
        month_costs.append(OrderedDict([
            ("forecast_month", m),
            ("month_sequence", cmeta["month_sequence"]),
            ("is_current_month", cmeta["is_current_month"]),
            ("is_partial_current_month", cmeta["is_partial_current_month"]),
            ("cost_code", cost_code),
            ("category", category),
            ("recommended_month_cost", money_str(rec_month[m])),
            ("worst_credible_month_cost", money_str(worst_month[m])),
            ("cumulative_recommended_cost_through_month", money_str(cum_rec)),
            ("cumulative_worst_credible_cost_through_month", money_str(cum_worst)),
            ("remaining_recommended_cost_after_month", money_str(rec_final - cum_rec)),
            ("remaining_worst_credible_cost_after_month", money_str(worst_final - cum_worst)),
            ("blended_month_weight", str(blended[m].quantize(Decimal("0.000001")))),
        ]))

    # ---- basis ----
    direction = rec.get("forecast_direction")
    if direction == "insufficient_evidence":
        basis = "insufficient_evidence"
    elif freq_share >= Decimal("0.5"):
        basis = "frequency_cadence"
    elif sched_share >= Decimal("0.5"):
        basis = "schedule_phasing"
    elif (sched_share > 0 or freq_share > 0) and (cost_share > 0 or inv_share > 0):
        basis = "combined"
    elif inv_share > 0 and inv_share >= cost_share:
        basis = "subcontractor_invoice_trend"
    elif cost_shape in ("flat_recent_burn", "accelerating_front_loaded", "decelerating_back_loaded"):
        basis = "cost_entries_trend"
    else:
        basis = "flat_remaining"

    # reconciliation checks (cent tolerance)
    rec_sum = sum((D(r["recommended_month_cost"]) for r in month_costs), Decimal("0"))
    worst_sum = sum((D(r["worst_credible_month_cost"]) for r in month_costs), Decimal("0"))
    rec_ok = abs(rec_sum - rec_ctc) <= CENTS and abs((actual + rec_sum) - rec_final) <= CENTS
    worst_ok = abs(worst_sum - worst_ctc) <= CENTS and abs((actual + worst_sum) - worst_final) <= CENTS

    return {
        "budget_code_key": rec.get("budget_code_key"),
        "cost_code": cost_code,
        "category": category,
        "actual": actual,
        "recommended_final_cost": rec_final,
        "worst_credible_final_cost": worst_final,
        "recommended_cost_to_complete": rec_ctc,
        "worst_credible_cost_to_complete": worst_ctc,
        "current_projected_cost": projected,
        "revised_budget": revised,
        "variance_to_current_projected_cost": var_proj,
        "variance_to_revised_budget": var_rev,
        "overrun_vs_current_projected_cost": over_proj,
        "overrun_vs_revised_budget": over_rev,
        "month_costs": month_costs,
        "blended": blended,
        "source_shares": OrderedDict([
            ("schedule_weight", str(sched_share.quantize(Decimal("0.0001")))),
            ("cost_entries_weight", str(cost_share.quantize(Decimal("0.0001")))),
            ("subcontractor_invoice_weight", str(inv_share.quantize(Decimal("0.0001")))),
            ("frequency_weight", str(freq_share.quantize(Decimal("0.0001")))),
            ("flat_weight", "0.0000"),
        ]),
        "monthly_forecast_basis": basis,
        "first_month_exceed_current_projected": first_exceed_proj,
        "first_month_exceed_revised_budget": first_exceed_rev,
        "peak_month_cost": money_str(peak_month_cost),
        "already_exceeds_projected": bool(projected is not None and actual > projected),
        "reconciliation_ok": bool(rec_ok and worst_ok),
    }
