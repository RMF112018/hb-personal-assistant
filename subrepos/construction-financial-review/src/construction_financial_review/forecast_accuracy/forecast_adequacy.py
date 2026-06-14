"""Forecast adequacy: is the ERP projected_costs likely low / adequate / high vs the model?

Uses the approved materiality gate ($25k AND 10% of the larger basis). Advisory only.
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal

from ..common.money import D, dec, materiality, money_str

# severity tiers (consistent with the analysis package)
SEV_CRITICAL_ABS = Decimal("250000")
SEV_CRITICAL_PCT = Decimal("0.25")
SEV_HIGH_ABS = Decimal("100000")
SEV_HIGH_PCT = Decimal("0.15")


def _severity(gap: Decimal, pct) -> str:
    if pct is None:
        return "low"
    if gap >= SEV_CRITICAL_ABS and pct >= SEV_CRITICAL_PCT:
        return "critical"
    if gap >= SEV_HIGH_ABS and pct >= SEV_HIGH_PCT:
        return "high"
    return "medium"


def assess_adequacy(reconciliation: dict, project_key: str) -> OrderedDict:
    key = reconciliation.get("budget_code_key")
    erp = dec(reconciliation.get("erp_projected_costs"))
    model = dec(reconciliation.get("model_recommended_projected_cost"))
    n_ind = reconciliation.get("n_independent_models") or 0

    classification = "indeterminate"
    severity = "informational"
    gap = None
    pct = None
    if erp is not None and model is not None and n_ind >= 1:
        gap_d, pct_d, is_material = materiality(model, erp)
        gap = gap_d
        pct = pct_d
        if not is_material:
            classification = "adequate"
            severity = "low"
        elif model > erp:
            classification = "likely_low"          # ERP under-forecasts vs independent model
            severity = _severity(gap_d, pct_d)
        else:
            classification = "likely_high"         # ERP over-forecasts vs independent model
            severity = _severity(gap_d, pct_d)
    elif n_ind == 0:
        classification = "indeterminate"
        severity = "informational"

    return OrderedDict([
        ("project_key", project_key),
        ("budget_code_key", key),
        ("erp_projected_costs", reconciliation.get("erp_projected_costs")),
        ("model_recommended_projected_cost", reconciliation.get("model_recommended_projected_cost")),
        ("model_minus_erp_gap", money_str(D(model) - D(erp)) if (erp is not None and model is not None) else None),
        ("gap_percent", str(pct.quantize(Decimal("0.0001"))) if pct is not None else None),
        ("forecast_adequacy", classification),
        ("adequacy_severity", severity),
        ("n_independent_models", n_ind),
        ("requires_human_review", classification in ("likely_low", "likely_high")),
        ("notes", None),
    ])
