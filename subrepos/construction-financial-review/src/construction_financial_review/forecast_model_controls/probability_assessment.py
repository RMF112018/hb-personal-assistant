"""Deterministic provisional probability/plausibility assessment for controlled final values.

When an operator pins a deterministic final value, probability handling is degraded-not-fatal:
- a prior accepted probability row exists  -> the comprehensive consumer anchors P50 to the controlled
  value (``probability_status = accepted_probability_anchor``);
- no prior row exists                      -> this module emits a deterministic, evidence-scored
  plausibility classification (``provisional_manual_value_assessment``) — NOT a Monte Carlo distribution
  and never claiming accepted probability lineage;
- too little evidence                      -> ``probability_unavailable_insufficient_evidence``.

The numeric probability fields are left null for provisional assessments (no pseudo-probabilities). The
classification, evidence_support_score, confidence, and data_gaps are always populated.
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal

from ..common.money import D, dec, money_str

ZERO = Decimal("0")
HUNDRED = Decimal("100")

# assessment categories
A_SUPPORTED = "supported"
A_PLAUSIBLE = "plausible"
A_AGGRESSIVE = "aggressive"
A_CONSERVATIVE = "conservative"
A_WEAK = "weakly_supported"
A_UNSUPPORTED = "unsupported"
A_INSUFFICIENT = "insufficient_evidence"

# probability statuses
PS_ANCHOR = "accepted_probability_anchor"
PS_PROVISIONAL = "provisional_manual_value_assessment"
PS_INSUFFICIENT = "probability_unavailable_insufficient_evidence"


def _classify(controlled, model_final, refs, within_pct):
    """Deterministic plausibility classification vs the available reference band."""
    present = [v for v in refs.values() if v is not None]
    if len(present) < 2:
        return A_INSUFFICIENT, ZERO
    lo, hi = min(present), max(present)
    # evidence_support_score = share of references within ±within_pct of the controlled value
    consistent = 0
    for v in present:
        if v == 0:
            continue
        if abs(controlled - v) <= (v * within_pct):
            consistent += 1
    score = (Decimal(consistent) / Decimal(len(present))).quantize(Decimal("0.0001"))

    near_model = model_final is not None and model_final != 0 and abs(controlled - model_final) <= model_final * within_pct
    if near_model and lo <= controlled <= hi:
        return A_SUPPORTED, score
    if lo <= controlled <= hi:
        return A_PLAUSIBLE, score
    band = hi - lo
    tol = (hi * within_pct) if hi else ZERO
    if controlled > hi:
        return (A_CONSERVATIVE if controlled <= hi + max(tol, band) else A_WEAK if controlled <= hi * Decimal("1.25") else A_UNSUPPORTED), score
    # controlled < lo
    return (A_AGGRESSIVE if controlled >= lo - max(tol, band) else A_WEAK if controlled >= lo * Decimal("0.75") else A_UNSUPPORTED), score


def assess(project_key, decision, amounts, prior_prob_present, historical_burn, within_pct) -> "OrderedDict":
    """Build one probability-assessment row for an applied, value-changing controlled key."""
    controlled = decision["controlled_final_cost"]
    model_final = decision["uncontrolled_model_final_cost"]
    actual = decision["actual_cost_to_date"]
    remaining = decision["controlled_remaining"]
    months = len(decision["active_months"])
    amounts = amounts or {}

    refs = OrderedDict([
        ("uncontrolled_model_final_cost", model_final),
        ("projected_costs", dec(amounts.get("projected_costs"))),
        ("revised_budget", dec(amounts.get("revised_budget"))),
        ("committed_costs", dec(amounts.get("committed_costs"))),
        ("original_budget_amount", dec(amounts.get("original_budget_amount"))),
    ])
    classification, score = _classify(controlled, model_final, refs, within_pct)

    if prior_prob_present:
        status = PS_ANCHOR
    elif classification == A_INSUFFICIENT:
        status = PS_INSUFFICIENT
    else:
        status = PS_PROVISIONAL

    delta = (controlled - model_final) if model_final is not None else None
    delta_pct = ((delta / model_final) * HUNDRED).quantize(Decimal("0.01")) if (delta is not None and model_final) else None
    req_burn = (remaining / Decimal(months)).quantize(Decimal("0.01")) if months else None
    data_gaps = [k for k, v in refs.items() if v is None]
    confidence = "high" if score >= Decimal("0.66") else "medium" if score >= Decimal("0.34") else "low"
    if status == PS_INSUFFICIENT:
        confidence = "low"

    return OrderedDict([
        ("project_key", project_key), ("budget_code_key", decision["budget_code_key"]),
        ("control_id", decision["control_id"]),
        ("probability_status", status),
        ("probability_basis", ("prior accepted probability distribution anchored to controlled final"
                               if status == PS_ANCHOR else
                               "deterministic evidence-scored plausibility classification (no Monte Carlo)")),
        ("controlled_final_cost", money_str(controlled)),
        ("uncontrolled_model_final_cost", money_str(model_final) if model_final is not None else None),
        ("delta_from_uncontrolled_model", money_str(delta) if delta is not None else None),
        ("delta_percent_from_uncontrolled_model", str(delta_pct) if delta_pct is not None else None),
        ("actual_cost_to_date", money_str(actual) if actual is not None else None),
        ("projected_costs", money_str(refs["projected_costs"]) if refs["projected_costs"] is not None else None),
        ("revised_budget", money_str(refs["revised_budget"]) if refs["revised_budget"] is not None else None),
        ("committed_costs", money_str(refs["committed_costs"]) if refs["committed_costs"] is not None else None),
        ("required_remaining_burn_rate", money_str(req_burn) if req_burn is not None else None),
        ("historical_burn_rate", money_str(D(historical_burn)) if historical_burn is not None else None),
        ("schedule_window_months", months),
        ("evidence_support_score", str(score)),
        ("manual_value_assessment", classification),
        # numeric probabilities are null for provisional assessments (no pseudo-probabilities)
        ("probability_final_cost_at_or_below_controlled_value", None),
        ("probability_final_cost_exceeds_controlled_value", None),
        ("confidence", confidence),
        ("data_gaps", data_gaps),
    ])
