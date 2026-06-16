"""Advisory monthly distribution: curve-shape weight suggestion, do-not-auto-apply, weights present."""
from decimal import Decimal

from construction_financial_review.forecast_history_informed import history_monthly_distribution as hmd

CFG = {"history_max_weight_when_validated": "0.45"}
SIG = {"budget_code_key": "1000.20-18-110.OVH", "cost_code": "20-18-110",
       "latest_curve_shape_class": "tapering_closeout"}


def test_distribution_is_advisory():
    rel = {"overall_history_reliability_score": "0.7000"}
    monthly = {"monthly_forecast_basis": "schedule_phasing",
               "source_shares": {"schedule_weight": "0.5000", "cost_entries_weight": "0.3000",
                                 "subcontractor_invoice_weight": "0.2000"}}
    d = hmd.build_distribution(SIG, {}, rel, monthly, CFG, "tropical")
    assert d["do_not_auto_apply"] is True
    assert "history_curve_weight" in d["final_suggested_distribution_weights"]


def test_uses_real_accepted_source_shares():
    """When the accepted monthly source shares are present, they drive the suggested blend (not equal)."""
    rel = {"overall_history_reliability_score": "0.7000"}
    monthly = {"monthly_forecast_basis": "schedule_phasing",
               "source_shares": {"schedule_weight": "0.5000", "cost_entries_weight": "0.3000",
                                 "subcontractor_invoice_weight": "0.2000"}}
    d = hmd.build_distribution(SIG, {}, rel, monthly, CFG, "tropical")
    assert d["source_shares_available"] is True
    assert d["distribution_source_basis"] == "accepted_monthly_source_shares"
    # the accepted blend ordering is preserved (schedule > actual-trend > invoice), not equal thirds
    assert (Decimal(d["schedule_weight_suggestion"]) > Decimal(d["actual_trend_weight_suggestion"])
            > Decimal(d["invoice_weight_suggestion"]) > Decimal("0"))


def test_missing_source_shares_falls_back_explicitly():
    rel = {"overall_history_reliability_score": "0.7000"}
    monthly = {"monthly_forecast_basis": "flat_remaining", "source_shares": {}}
    d = hmd.build_distribution(SIG, {}, rel, monthly, CFG, "tropical")
    assert d["source_shares_available"] is False
    assert d["distribution_source_basis"] == "equal_weight_fallback"


def test_informative_curve_earns_weight_when_schedule_weak():
    rel = {"overall_history_reliability_score": "0.8000"}
    monthly = {"monthly_forecast_basis": "flat_remaining",
               "source_shares": {"schedule_weight": "0.0000", "cost_entries_weight": "0.5000",
                                 "subcontractor_invoice_weight": "0.0000"}}
    d = hmd.build_distribution(SIG, {}, rel, monthly, CFG, "tropical")
    assert Decimal(d["history_curve_weight_suggestion"]) > Decimal("0")


def test_uninformative_curve_earns_no_weight():
    sig = {**SIG, "latest_curve_shape_class": "volatile_review"}
    rel = {"overall_history_reliability_score": "0.8000"}
    monthly = {"monthly_forecast_basis": "flat_remaining", "source_shares": {}}
    d = hmd.build_distribution(sig, {}, rel, monthly, CFG, "tropical")
    assert Decimal(d["history_curve_weight_suggestion"]) == Decimal("0")
