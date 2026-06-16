"""Split confidence for the monthly forecast: three distinct questions.

- overrun_existence_confidence: how sure are we an overrun exists? (very_high once actuals already
  exceed current projected cost — that is a fact, not a projection.)
- final_cost_estimate_confidence: how sure is the anticipated final cost? (from the accepted package's
  calibrated confidence — future ETC can be uncertain even when an overrun is certain.)
- monthly_distribution_confidence: how sure is the MONTH-by-month split? (from timing-evidence quality.)
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal

from ..common.money import dec
from ..forecast_accuracy.confidence import band

COST_Q_STABLE = Decimal("0.6")
COST_Q_UNSTABLE = Decimal("0.3")
SCHED_Q = Decimal("0.7")          # capped: schedule has no validated cost/resource loading
INV_Q = {"high": Decimal("0.7"), "medium": Decimal("0.5"), "low": Decimal("0.3"), "none": Decimal("0")}


def score(rec: dict, reconcile: dict, cost_stable: bool, invoice_confidence: str) -> OrderedDict:
    # overrun existence
    if reconcile.get("already_exceeds_projected"):
        overrun_existence = "very_high"
    elif rec.get("overrun_projected"):
        overrun_existence = band(dec(rec.get("overrun_confidence")) or Decimal("0"))
    else:
        overrun_existence = "not_applicable"

    final_cost_estimate = rec.get("confidence_band") or "very_low"

    shares = reconcile.get("source_shares", {})
    sched_s = dec(shares.get("schedule_weight")) or Decimal("0")
    cost_s = dec(shares.get("cost_entries_weight")) or Decimal("0")
    inv_s = dec(shares.get("subcontractor_invoice_weight")) or Decimal("0")
    cost_q = COST_Q_STABLE if cost_stable else COST_Q_UNSTABLE
    inv_q = INV_Q.get(invoice_confidence, Decimal("0"))
    dist_score = (sched_s * SCHED_Q + cost_s * cost_q + inv_s * inv_q)
    if reconcile.get("monthly_forecast_basis") == "flat_remaining":
        dist_score = min(dist_score, Decimal("0.30"))
    dist_score = dist_score.quantize(Decimal("0.01"))

    return OrderedDict([
        ("overrun_existence_confidence", overrun_existence),
        ("final_cost_estimate_confidence", final_cost_estimate),
        ("monthly_distribution_confidence", band(dist_score)),
        ("monthly_distribution_score", str(dist_score)),
    ])
