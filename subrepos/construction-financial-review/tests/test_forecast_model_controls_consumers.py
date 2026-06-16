"""forecast_model_controls: synthetic unit tests for the comprehensive consumers + combined CSV.

These exercise the integration code paths without the live data root.
"""
from __future__ import annotations

from decimal import Decimal

from construction_financial_review.forecast_actuals import actuals_export
from construction_financial_review.forecast_comprehensive import probability_consumer

KEY = "1000.10-01-800.SUB"


def _decision(final="650.00", actual="150.00", changes=True):
    return {
        "control_id": "c1", "budget_code_key": KEY, "model_type": "existing_model",
        "value_constraint_policy": "explicit_final_value", "reference_source": None,
        "resolved_start_date": None, "resolved_end_date": None, "schedule_end_basis": "explicit_date",
        "active_months": ["2026-06", "2026-07"],
        "controlled_final_cost": Decimal(final), "controlled_remaining": Decimal("500.00"),
        "actual_cost_to_date": Decimal(actual), "uncontrolled_model_final_cost": Decimal("600.00"),
        "monthly_allocation": None, "changes_deterministic_final": changes,
    }


# ---- combined actuals+forecast CSV anti-double-count ----

def test_combined_csv_controlled_anti_double_count():
    actuals_bc = [
        {"budget_code_key": KEY, "month": "2026-05", "actual_cost": "100.00", "cost_code": "10-01-800",
         "cost_type": "SUB", "budget_code_description": "x"},
        {"budget_code_key": KEY, "month": "2026-06", "actual_cost": "50.00", "cost_code": "10-01-800",
         "cost_type": "SUB", "budget_code_description": "x"}]
    actuals_cc = [
        {"cost_code": "10-01-800", "month": "2026-05", "actual_cost": "100.00", "cost_code_description": "x"},
        {"cost_code": "10-01-800", "month": "2026-06", "actual_cost": "50.00", "cost_code_description": "x"}]
    integrated = [{"budget_code_key": KEY, "cost_code": "10-01-800", "monthly_costs": [
        {"forecast_month": "2026-06", "integrated_month_cost": "200.00"},
        {"forecast_month": "2026-07", "integrated_month_cost": "300.00"}]}]
    controlled = {KEY: {"final": "650.00", "actual": "150.00"}}

    out = actuals_export.build_actuals_plus_forecast("tropical", [], actuals_cc, actuals_bc, integrated,
                                                     controlled=controlled)
    audit = out[actuals_export.ACTUALS_PLUS_FORECAST_AUDIT_FILE]
    assert audit["all_controlled_targets_reconcile"] is True
    rec = audit["controlled_target_reconciliation"][0]
    assert rec["combined_csv_total"] == "650.00" and rec["target_final_cost"] == "650.00"
    assert rec["current_month_actuals_included"] == "50.00"
    assert rec["reconciles_to_target_final_cost"] is True
    # the budget-code CSV row itself sums to the controlled final
    bc = out["actuals_plus_forecast_monthly_by_budget_code.csv"]
    row = next(r for r in bc["rows"] if r["budget_code_key"] == KEY)
    months = [c for c in row if len(c) == 7 and c[4] == "-"]
    assert sum(Decimal(row[m]) for m in months) == Decimal("650.00")
    assert row["2026-06"] == "250.00"  # 50 actual + 200 remaining forecast (counted once)


def test_combined_csv_without_addback_would_undercount():
    """Without the controlled add-back the June actual would be dropped (proves the fix matters)."""
    actuals_bc = [
        {"budget_code_key": KEY, "month": "2026-05", "actual_cost": "100.00", "cost_code": "10-01-800",
         "cost_type": "SUB", "budget_code_description": "x"},
        {"budget_code_key": KEY, "month": "2026-06", "actual_cost": "50.00", "cost_code": "10-01-800",
         "cost_type": "SUB", "budget_code_description": "x"}]
    actuals_cc = [
        {"cost_code": "10-01-800", "month": "2026-05", "actual_cost": "100.00", "cost_code_description": "x"},
        {"cost_code": "10-01-800", "month": "2026-06", "actual_cost": "50.00", "cost_code_description": "x"}]
    integrated = [{"budget_code_key": KEY, "cost_code": "10-01-800", "monthly_costs": [
        {"forecast_month": "2026-06", "integrated_month_cost": "200.00"},
        {"forecast_month": "2026-07", "integrated_month_cost": "300.00"}]}]
    out = actuals_export.build_actuals_plus_forecast("tropical", [], actuals_cc, actuals_bc, integrated)
    bc = out["actuals_plus_forecast_monthly_by_budget_code.csv"]
    row = next(r for r in bc["rows"] if r["budget_code_key"] == KEY)
    months = [c for c in row if len(c) == 7 and c[4] == "-"]
    assert sum(Decimal(row[m]) for m in months) == Decimal("600.00")  # undercounts the 50 June actual


# ---- probability consumer (anchor vs provisional) ----

def _sc():
    return {"history_consumption_status": "missing", "frequency_consumption_status": "missing",
            "history_probability_weight": Decimal("0"), "probability_consumption_status": "consumed"}


def test_probability_provisional_when_no_prior_row():
    entry = {"model_control": _decision(), "prob_final": None, "actual_cost_to_date": "150.00",
             "projected_costs": "700.00", "revised_budget": "680.00", "hist_prob": None, "freq": {}}
    row, contrib = probability_consumer.build("tropical", KEY, entry, _sc(), {})
    assert row is not None
    assert row["probability_status"] == "provisional_manual_value_assessment"
    assert row["operator_final_value_anchor_applied"] is False
    assert row["integrated_p50"] == "650.00"
    assert row["integrated_p90"] is None and row["integrated_p95"] is None
    assert row["probability_final_cost_at_or_below_controlled_value"] is None
    assert row["manual_value_assessment"] is not None and row["confidence"] is not None


def test_probability_anchor_when_prior_row_present():
    entry = {"model_control": _decision(), "actual_cost_to_date": "150.00",
             "prob_final": {"simulated_p10": "550.00", "simulated_p50": "600.00", "simulated_p80": "650.00",
                            "simulated_p90": "700.00", "simulated_p95": "750.00"},
             "projected_costs": "700.00", "revised_budget": "680.00", "hist_prob": None, "freq": {}}
    row, contrib = probability_consumer.build("tropical", KEY, entry, _sc(), {})
    assert row["probability_status"] == "accepted_probability_anchor"
    assert row["operator_final_value_anchor_applied"] is True
    assert row["integrated_p50"] == "650.00"            # recentred on the controlled final
    # monotonic and floored at actuals
    q = [Decimal(row[f]) for f in ("integrated_p10", "integrated_p50", "integrated_p80",
                                   "integrated_p90", "integrated_p95")]
    assert q == sorted(q) and all(v >= Decimal("150.00") for v in q)
