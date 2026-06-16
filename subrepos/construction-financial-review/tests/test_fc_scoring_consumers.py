"""Evidence scoring + intelligence/monthly/probability consumers (advisory, bounded, floored, no-cap)."""
from decimal import Decimal

from tests._fc_fixtures import KEY, entry

from construction_financial_review.forecast_comprehensive import evidence_scoring as scoring
from construction_financial_review.forecast_comprehensive import intelligence_consumer as ic
from construction_financial_review.forecast_comprehensive import monthly_consumer as mc
from construction_financial_review.forecast_comprehensive import probability_consumer as pc

CFG = {"max_history_final_cost_weight": "0.45", "max_history_monthly_shape_weight": "0.30",
       "max_history_probability_weight": "0.25", "max_frequency_monthly_shape_weight": "0.60"}


def test_validated_history_weight_is_bounded():
    sc = scoring.score_code(entry(), CFG)
    # reliability 0.7 * (1-0.2 contradiction) = 0.56 -> clamped to the 0.45 bound
    assert Decimal(str(sc["history_final_cost_weight"])) == Decimal("0.45")
    assert sc["history_consumption_status"] == "consumed"
    assert sc["frequency_consumption_status"] == "consumed"


def test_contradicted_history_is_downgraded_to_zero():
    sc = scoring.score_code(entry(hist_val={"validation_class": "contradicted_escalation",
                                            "actual_trend_override_score": "0.9500"}), CFG)
    assert Decimal(str(sc["history_final_cost_weight"])) == Decimal("0")
    assert sc["history_consumption_status"] == "downgraded"
    assert sc["contradicted"] is True


def test_intelligence_blend_floored_and_uncapped():
    e = entry()
    sc = scoring.score_code(e, CFG)
    f_row, rec, floor_audit, integ_final, integ_ctc = ic.build("tropical", KEY, e, sc)
    # 100000*(1-0.45) + 120000*0.45 = 109000 ; above the 40000 floor; never capped
    assert Decimal(f_row["integrated_recommended_final_cost"]) == Decimal("109000.00")
    assert f_row["upper_cap_applied"] is False
    assert f_row["floored_at_actuals"] is False
    assert f_row["frequency_final_cost_weight"] == "0.0000"      # cadence never weights final cost
    assert f_row["acceptance_status"] == "pending"
    assert integ_ctc == Decimal("69000.00")                      # 109000 - 40000 actual floor


def test_intelligence_respects_actual_floor():
    e = entry(actual_cost_to_date="200000.00",
              rec={"recommended_final_cost": "100000.00", "recommended_cost_to_complete": "0.00"},
              hist_adj={"history_informed_adjusted_final_cost": "50000.00"})
    sc = scoring.score_code(e, CFG)
    f_row, *_ = ic.build("tropical", KEY, e, sc)
    assert Decimal(f_row["integrated_recommended_final_cost"]) >= Decimal("200000.00")
    assert f_row["floored_at_actuals"] is True


def test_monthly_reconciles_to_integrated_ctc():
    e = entry()
    sc = scoring.score_code(e, CFG)
    row, months, audit = mc.build("tropical", KEY, e, sc, Decimal("60000.00"))
    total = sum(Decimal(m["integrated_month_cost"]) for m in row["monthly_costs"])
    assert total == Decimal("60000.00")
    assert row["reconciles_to_integrated_ctc"] is True
    # frequency (weekday) + history shape shares both contributed (timing only)
    assert Decimal(row["source_shares"]["frequency_share"]) > 0
    assert Decimal(row["source_shares"]["history_shape_share"]) > 0


def test_probability_deterministic_adjustment_floored_uncapped():
    e = entry()
    sc = scoring.score_code(e, CFG)
    row, contrib = pc.build("tropical", KEY, e, sc, CFG)
    assert row["probability_method"] == "accepted_distribution_deterministic_adjustment"
    assert row["upper_cap_applied"] is False
    # widen: history sigma multiplier 1.2 dampened by 0.25 weight -> >1.0
    assert Decimal(row["integrated_sigma_multiplier"]) > Decimal("1.0")
    assert row["integrated_uncertainty_direction"] == "widen"
    assert Decimal(row["integrated_p10"]) >= Decimal("40000.00")   # floored at actuals
