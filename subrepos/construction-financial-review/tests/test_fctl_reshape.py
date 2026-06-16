"""forecast_controls: monthly reshape — post-stop zeroing + reconciliation to cost-to-complete."""
from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal

from construction_financial_review.common.money import D, money_str
from construction_financial_review.forecast_controls import apply

MONTHS = ["2026-06", "2026-07", "2026-08", "2026-09", "2026-10", "2026-11"]
ACTUAL = Decimal("1385588.66")
REC_CTC = Decimal("319269.37")
WORST_CTC = Decimal("668152.70")


def _reconcile():
    even = OrderedDict((m, Decimal("1")) for m in MONTHS)
    month_costs = [OrderedDict([
        ("forecast_month", m), ("month_sequence", i + 1), ("is_current_month", i == 0),
        ("is_partial_current_month", False), ("cost_code", "15-07-590"), ("category", "SUB"),
        ("recommended_month_cost", money_str(REC_CTC / Decimal(len(MONTHS)))),
        ("worst_credible_month_cost", money_str(WORST_CTC / Decimal(len(MONTHS)))),
    ]) for i, m in enumerate(MONTHS)]
    return {
        "budget_code_key": "1000.15-07-590.SUB", "cost_code": "15-07-590", "category": "SUB",
        "actual": ACTUAL, "recommended_final_cost": ACTUAL + REC_CTC,
        "worst_credible_final_cost": ACTUAL + WORST_CTC,
        "recommended_cost_to_complete": REC_CTC, "worst_credible_cost_to_complete": WORST_CTC,
        "current_projected_cost": Decimal("1513192.33"), "revised_budget": Decimal("1500000.00"),
        "month_costs": month_costs, "blended": even, "monthly_forecast_basis": "flat_remaining",
        "reconciliation_ok": True,
    }


def test_accepted_stop_zeros_months_after_stop_and_reconciles():
    decision = {"control_id": "a", "stop_month": "2026-07", "timing_applied": True,
                "accepted_remaining_cost": None, "accepted_final_cost": None, "dollar_applied": False}
    out = apply.reshape_reconcile(_reconcile(), decision)
    by = {mc["forecast_month"]: D(mc["recommended_month_cost"]) for mc in out["month_costs"]}
    for m in ("2026-08", "2026-09", "2026-10", "2026-11"):
        assert by[m] == Decimal("0")
    assert by["2026-06"] > 0 and by["2026-07"] > 0
    total = sum(by.values(), Decimal("0"))
    assert total == REC_CTC                       # redistribution reconciles to CTC
    assert out["recommended_final_cost"] == ACTUAL + REC_CTC   # final unchanged (timing only)
    assert out["reconciliation_ok"] is True
    assert out["monthly_forecast_basis"].startswith("operator_controlled_")


def test_accepted_remaining_allowance_changes_ctc_and_floors():
    decision = {"control_id": "a", "stop_month": "2026-07", "timing_applied": True,
                "accepted_remaining_cost": Decimal("15000.00"), "accepted_final_cost": None,
                "dollar_applied": True}
    out = apply.reshape_reconcile(_reconcile(), decision)
    by = {mc["forecast_month"]: D(mc["recommended_month_cost"]) for mc in out["month_costs"]}
    assert sum(by.values(), Decimal("0")) == Decimal("15000.00")
    assert out["recommended_final_cost"] == ACTUAL + Decimal("15000.00")
    assert out["recommended_final_cost"] >= ACTUAL          # never below actuals floor
    assert out["reconciliation_ok"] is True
