"""Explain how the next-gen recommended final cost differs from prior numbers.

Compares ``recommended_final_cost`` against (a) the prior forecast-accuracy package's advisory
``model_recommended_projected_cost`` when present, and (b) the crosswalk-v2 rule-based
``recommended_projected_cost``. Surfaces materially changed and newly-flagged-overrun codes.
"""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal
from typing import Optional

from ..common.money import D, dec, materiality, money_str


def explain_change(recommendation: dict, prior_model_rec: Optional[dict],
                   v2_rec: Optional[dict], project_key: str) -> OrderedDict:
    key = recommendation["budget_code_key"]
    new_cost = D(recommendation.get("recommended_final_cost"))

    prior_model = dec((prior_model_rec or {}).get("model_recommended_projected_cost"))
    rule_based = dec((v2_rec or {}).get("recommended_projected_cost"))
    baseline = prior_model if prior_model is not None else rule_based
    baseline_source = ("prior_forecast_accuracy_model" if prior_model is not None
                       else ("crosswalk_v2_rule_based" if rule_based is not None else "none"))

    delta = (new_cost - baseline) if baseline is not None else None
    delta_pct = None
    material = False
    if baseline is not None and baseline > 0 and delta is not None:
        delta_pct = (delta / baseline)
        material = materiality(new_cost, baseline)[2]

    direction = "hold"
    if delta is not None:
        if delta > 0:
            direction = "increase"
        elif delta < 0:
            direction = "decrease"

    return OrderedDict([
        ("project_key", project_key),
        ("budget_code_key", key),
        ("new_recommended_final_cost", recommendation.get("recommended_final_cost")),
        ("baseline_source", baseline_source),
        ("prior_model_recommended", money_str(prior_model) if prior_model is not None else None),
        ("rule_based_recommended", money_str(rule_based) if rule_based is not None else None),
        ("baseline_value", money_str(baseline) if baseline is not None else None),
        ("delta", money_str(delta) if delta is not None else None),
        ("delta_percent", str(delta_pct.quantize(Decimal("0.0001"))) if delta_pct is not None else None),
        ("change_direction", direction),
        ("material_change", material),
        ("now_flags_overrun", bool(recommendation.get("overrun_projected"))),
        ("forecast_direction", recommendation.get("forecast_direction")),
        ("change_drivers", recommendation.get("primary_evidence")),
    ])
