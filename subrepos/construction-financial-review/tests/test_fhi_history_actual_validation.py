"""Historical forecast vs CostEntries actuals: zero-inactive, escalation contradiction, credits."""
from decimal import Decimal

from construction_financial_review.forecast_history_informed import history_actual_validation as hav

KEY = "1000.20-18-110.OVH"
MAP = {"budget_code_key": KEY, "mapping_status": "cost_code_unique_budget_match"}


def _fr(snap, pm, amt):
    return {"history_source_package": "cash_flow", "snapshot_month": snap, "cost_code": "20-18-110",
            "description": "FEE", "period_month": pm, "classification": "forecast",
            "amount": Decimal(str(amt)), "source_row": 1}


def _ctx(monthly):
    return {KEY: {"actuals": {"monthly_actuals": monthly}}}


def _ma(values, start=(2025, 5)):
    out, y, m = [], start[0], start[1]
    for v in values:
        out.append({"month": f"{y:04d}-{m:02d}", "amount_decimal_string": str(v),
                    "actual_period_bucket": "through_may_2026"})
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


def test_validated_zero_inactive():
    rows = [_fr("2026-04", "2099-01", 0)]
    ctx = _ctx(_ma([0, 0, 0, 0, 0, 0], start=(2025, 11)))
    v = hav.build_validation("20-18-110", rows, MAP, ctx, {}, "tropical")
    assert v["validation_class"] == "validated_zero_inactive"


def test_contradicted_escalation():
    rows = [_fr("2025-06", "2099-01", 50000)]
    # escalating recent burn, actuals far exceed the prior remaining
    ctx = _ctx(_ma([1000, 1000, 1000, 80000, 90000, 120000], start=(2025, 7)))
    v = hav.build_validation("20-18-110", rows, MAP, ctx, {}, "tropical")
    assert v["validation_class"] == "contradicted_escalation"
    assert Decimal(v["actual_trend_override_score"]) > Decimal("0")


def test_credit_reversal_pattern():
    rows = [_fr("2025-06", "2099-01", 50000)]
    ctx = _ctx(_ma([20000, -5000, 10000], start=(2025, 7)))
    v = hav.build_validation("20-18-110", rows, MAP, ctx, {}, "tropical")
    assert v["credits_deductive_pattern"] is True


def test_no_unique_mapping_is_insufficient():
    rows = [_fr("2025-06", "2099-01", 50000)]
    m = {"budget_code_key": None, "mapping_status": "cost_code_multi_category_rollup"}
    v = hav.build_validation("15-16-110", rows, m, {}, {}, "tropical")
    assert v["validation_class"] == "insufficient_actuals_no_unique_mapping"


def test_no_historical_value_used_as_actual():
    """The actual field is sourced from CostEntries, distinct from the historical forecast field."""
    rows = [_fr("2025-06", "2099-01", 50000)]
    ctx = _ctx(_ma([10000, 10000, 10000], start=(2025, 7)))
    v = hav.build_validation("20-18-110", rows, MAP, ctx, {}, "tropical")
    assert "cost_entries_actual_cost_in_window" in v
    assert "historical_forecasted_remaining_in_window" in v
    assert v["cost_entries_actual_cost_in_window"] != v["historical_forecasted_remaining_in_window"]
