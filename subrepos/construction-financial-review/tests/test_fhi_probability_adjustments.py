"""Advisory probability spread: tighten when validated, widen when contradicted/volatile."""
from decimal import Decimal

from construction_financial_review.forecast_history_informed import history_probability_adjustments as hpa

SIG = {"budget_code_key": "1000.20-18-110.OVH", "cost_code": "20-18-110",
       "historical_pattern_class": "stable_nonzero"}
SIM = {"sigma": "0.4000"}
OVR = {"prob_exceeds_current_projected_cost": "0.6000"}


def test_validated_tightens_spread():
    v = {"validation_class": "validated_aligned"}
    rel = {"overall_history_reliability_score": "0.8000"}
    a = hpa.build_probability_adjustment(SIG, v, rel, SIM, OVR, "tropical")
    assert Decimal(a["suggested_sigma_multiplier"]) < Decimal("1")
    assert a["suggested_probability_direction"] == "decrease_uncertainty"
    assert a["do_not_auto_apply"] is True


def test_contradicted_widens_spread():
    v = {"validation_class": "contradicted_escalation"}
    rel = {"overall_history_reliability_score": "0.1000"}
    a = hpa.build_probability_adjustment(SIG, v, rel, SIM, OVR, "tropical")
    assert Decimal(a["suggested_sigma_multiplier"]) > Decimal("1")
    assert a["suggested_probability_direction"] == "increase_uncertainty"


def test_volatile_history_widens_spread():
    sig = {**SIG, "historical_pattern_class": "volatile_review"}
    v = {"validation_class": "inconclusive"}
    rel = {"overall_history_reliability_score": "0.4000"}
    a = hpa.build_probability_adjustment(sig, v, rel, SIM, OVR, "tropical")
    assert Decimal(a["suggested_sigma_multiplier"]) > Decimal("1")


def test_neutral_holds():
    v = {"validation_class": "inconclusive"}
    rel = {"overall_history_reliability_score": "0.4000"}
    a = hpa.build_probability_adjustment(SIG, v, rel, SIM, OVR, "tropical")
    assert Decimal(a["suggested_sigma_multiplier"]) == Decimal("1")
    assert a["suggested_probability_direction"] == "hold"
