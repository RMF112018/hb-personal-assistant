"""Reconcile independent EAC estimates into an advisory model-recommended forecast.

Produces ``model_reconciled_eac`` (reliability x calibration weighted point), the advisory
``model_recommended_projected_cost`` (floored to actuals, human-gated), a low/high range, and a
normalized divergence metric. ERP baselines are reported for comparison but do not drive the
reconciled number. Never sets the authoritative rule-based recommendation.
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal
from typing import Optional

from ..common.money import D, dec, money_str

RELIABILITY_WEIGHT = {"high": Decimal("1.0"), "medium": Decimal("0.6"), "low": Decimal("0.3")}


def _median(values: list[Decimal]) -> Decimal:
    s = sorted(values)
    n = len(s)
    if n == 0:
        return Decimal("0")
    mid = n // 2
    if n % 2 == 1:
        return s[mid]
    return (s[mid - 1] + s[mid]) / Decimal("2")


def reconcile(budget_code_key: str, project_key: str, estimates: list[dict], actual,
              calibration: Optional[dict] = None) -> OrderedDict:
    """Combine applicable independent estimates for one budget code."""
    calibration = calibration or {}
    actual_d = D(actual)
    independent = [e for e in estimates if e["source"] == "independent" and e["applicable"]]
    erp = {e["method"]: e for e in estimates if e["source"] == "erp"}

    contributions = []
    weighted_sum = Decimal("0")
    weight_total = Decimal("0")
    eac_values = []
    for e in independent:
        eac = dec(e["eac"])
        if eac is None:
            continue
        base = RELIABILITY_WEIGHT.get(e["reliability"], Decimal("0.3"))
        calw = dec(calibration.get(e["method"])) or Decimal("1")
        w = base * calw
        weighted_sum += eac * w
        weight_total += w
        eac_values.append(eac)
        contributions.append(OrderedDict([
            ("method", e["method"]), ("eac", e["eac"]),
            ("reliability", e["reliability"]),
            ("calibration_weight", str(calw)), ("effective_weight", str(w)),
        ]))

    erp_projected = dec((erp.get("baseline_projected") or {}).get("eac"))

    if eac_values:
        reconciled = weighted_sum / weight_total
        median = _median(eac_values)
        low, high = min(eac_values), max(eac_values)
        divergence = ((high - low) / median) if median > 0 else Decimal("0")
        basis = "+".join(c["method"] for c in contributions)
        n_independent = len(eac_values)
    else:
        # No independent evidence: fall back to the ERP projected number (advisory, low confidence).
        reconciled = erp_projected if erp_projected is not None else actual_d
        median = reconciled
        low = high = reconciled
        divergence = Decimal("0")
        basis = "erp_baseline_only"
        n_independent = 0

    model_recommended = reconciled if reconciled >= actual_d else actual_d  # floor to actuals
    erp_gap = (model_recommended - erp_projected) if erp_projected is not None else None

    return OrderedDict([
        ("project_key", project_key),
        ("budget_code_key", budget_code_key),
        ("actual_cost_all_source_to_date", money_str(actual_d)),
        ("erp_projected_costs", money_str(erp_projected) if erp_projected is not None else None),
        ("n_independent_models", n_independent),
        ("model_reconciled_eac", money_str(reconciled)),
        ("model_recommended_projected_cost", money_str(model_recommended)),
        ("model_recommended_floored_to_actuals", bool(reconciled < actual_d)),
        ("model_eac_low", money_str(low)),
        ("model_eac_high", money_str(high)),
        ("model_eac_median", money_str(median)),
        ("model_divergence", str(divergence.quantize(Decimal("0.0001")))),
        ("model_vs_erp_gap", money_str(erp_gap) if erp_gap is not None else None),
        ("reconciliation_basis", basis),
        ("contributions", contributions),
        ("requires_human_acceptance", True),
    ])
