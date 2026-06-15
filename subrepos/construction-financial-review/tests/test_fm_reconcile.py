"""Monthly reconciliation: sums tie to CTC and final, day-aware partial, overrun-month, no double count."""
from datetime import date
from decimal import Decimal

from construction_financial_review.forecast_cost_frequency.weekday_calendar import weekday_weight_vector
from construction_financial_review.forecast_monthly import calendar as cal
from construction_financial_review.forecast_monthly import cost_entry_trends as cet
from construction_financial_review.forecast_monthly import monthly_reconcile as mr

CAL = cal.build_calendar("2026-08-31", date(2026, 6, 14))   # Jun(partial)/Jul/Aug
MONTHS = [m["forecast_month"] for m in CAL["months"]]

REC = {
    "budget_code_key": "1000.10-01-100.SUB",
    "actual_cost_all_source_to_date": "400000.00",
    "recommended_final_cost": "1000000.00",
    "worst_credible_final_cost": "1000000.00",
    "recommended_cost_to_complete": "600000.00",
    "worst_credible_cost_to_complete": "600000.00",
    "current_projected_cost": "800000.00",
    "revised_budget": "900000.00",
    "overrun_vs_current_projected_cost": True,
    "overrun_vs_revised_budget": True,
    "forecast_direction": "increase",
}


def _reconcile():
    cost_w = cet.shape_weights(MONTHS, cet.FLAT)
    return mr.reconcile_code(REC, CAL, cost_w, None, None, None, "none", "flat_recent_burn", "tropical")


def test_months_sum_to_ctc_and_final():
    r = _reconcile()
    rec_sum = sum((Decimal(m["recommended_month_cost"]) for m in r["month_costs"]), Decimal("0"))
    assert rec_sum == Decimal("600000.00")
    assert Decimal("400000.00") + rec_sum == Decimal("1000000.00")
    assert r["reconciliation_ok"] is True


def test_day_aware_partial_reduces_current_month():
    r = _reconcile()
    by = {m["forecast_month"]: Decimal(m["recommended_month_cost"]) for m in r["month_costs"]}
    # June is partial (17/30) so it carries less than the full months
    assert by["2026-06"] < by["2026-07"]
    assert by["2026-07"] == by["2026-08"]


def test_no_current_month_double_count():
    r = _reconcile()
    june = next(m for m in r["month_costs"] if m["forecast_month"] == "2026-06")
    assert Decimal(june["recommended_month_cost"]) <= Decimal(REC["recommended_cost_to_complete"])


def test_overrun_month_detected():
    r = _reconcile()
    assert r["overrun_vs_current_projected_cost"] is True
    # cumulative crosses 800k only in the final month (400k + 600k = 1.0M)
    assert r["first_month_exceed_current_projected"] == "2026-08"


def test_cumulative_monotonic_and_caps_at_final():
    r = _reconcile()
    cums = [Decimal(m["cumulative_recommended_cost_through_month"]) for m in r["month_costs"]]
    assert cums == sorted(cums)
    assert cums[-1] == Decimal("1000000.00")


def test_frequency_cadence_reshapes_but_never_changes_final_or_ctc():
    cost_w = cet.shape_weights(MONTHS, cet.FLAT)
    freq_w = weekday_weight_vector(MONTHS)
    r = mr.reconcile_code(REC, CAL, cost_w, None, None, None, "none", "flat_recent_burn", "tropical",
                          frequency_weights=freq_w, frequency_confidence="high")
    # frequency carved a dominant timing share and became the basis
    assert r["source_shares"]["frequency_weight"] == "0.8000"
    assert r["monthly_forecast_basis"] == "frequency_cadence"
    # but the totals are untouched: months sum to CTC, actual + sum == final cost (unchanged)
    rec_sum = sum((Decimal(m["recommended_month_cost"]) for m in r["month_costs"]), Decimal("0"))
    assert rec_sum == Decimal("600000.00")
    assert r["recommended_final_cost"] == Decimal("1000000.00")
    assert r["reconciliation_ok"] is True


def test_no_frequency_is_backward_compatible():
    cost_w = cet.shape_weights(MONTHS, cet.FLAT)
    r = mr.reconcile_code(REC, CAL, cost_w, None, None, None, "none", "flat_recent_burn", "tropical")
    # frequency_weight present but zero; behavior identical to before integration
    assert r["source_shares"]["frequency_weight"] == "0.0000"
    assert r["reconciliation_ok"] is True


def test_zero_ctc_emits_zero_months():
    rec0 = dict(REC, recommended_cost_to_complete="0.00", worst_credible_cost_to_complete="0.00",
                recommended_final_cost="400000.00", worst_credible_final_cost="400000.00",
                overrun_vs_current_projected_cost=False, overrun_vs_revised_budget=False)
    cost_w = cet.shape_weights(MONTHS, cet.FLAT)
    r = mr.reconcile_code(rec0, CAL, cost_w, None, None, None, "none", "flat_recent_burn", "tropical")
    assert all(Decimal(m["recommended_month_cost"]) == Decimal("0.00") for m in r["month_costs"])
    assert r["reconciliation_ok"] is True
