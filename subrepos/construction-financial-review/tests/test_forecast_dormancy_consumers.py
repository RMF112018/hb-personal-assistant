"""forecast_dormancy: comprehensive consumer enforcement unit tests (no data root)."""
from __future__ import annotations

from decimal import Decimal

from construction_financial_review.forecast_comprehensive import (conflicts, intelligence_consumer,
                                                                  monthly_consumer, probability_consumer)

KEY = "0000.03-01-413.MAT"


def _dormant(**kw):
    d = {"budget_code_key": KEY, "dormant_status": "closed_do_not_use", "suppression_applied": True,
         "closure_phrase_detected": True, "suppression_reason": "closure phrase 'CLOSED - DO NOT USE' idle",
         "operator_control_override": False, "remaining_evidence": [], "open_commitment_remaining": "0.00",
         "schedule_remaining_evidence": False, "actual_cost_to_date": "4278.99"}
    d.update(kw)
    return d


def _entry(dormant, model_control=None, prob_final=None):
    return {
        "actual_cost_to_date": "4278.99", "revised_budget": "4278.99", "projected_costs": "4278.99",
        "rec": {"recommended_final_cost": "4278.99", "recommended_cost_to_complete": "0.00"},
        "hist_adj": {"history_informed_adjusted_final_cost": "15000.00"},   # history tries to inflate
        "monthly_dist": {"monthly_distribution_weights": [{"month": "2026-06", "weight": "1.0"}]},
        "prob_final": prob_final, "hist_mon": None, "freq": {}, "freq_phasing": {}, "hist_prob": None,
        "sched": {}, "monthly_conf": {}, "owner_pay_app": {}, "sub_pay_app": {},
        "model_control": model_control, "dormant": dormant,
    }


def _sc():
    return {"history_final_cost_weight": Decimal("0.45"), "history_consumption_status": "consumed",
            "frequency_consumption_status": "missing", "probability_consumption_status": "consumed",
            "monthly_consumption_status": "consumed", "schedule_consumption_status": "missing",
            "pay_app_consumption_status": "missing", "reason_codes": [],
            "history_monthly_shape_weight": Decimal("0"), "frequency_monthly_weight": Decimal("0"),
            "history_probability_weight": Decimal("0"), "contradicted": False, "validation_class": "na"}


def test_intelligence_consumer_history_cannot_reinflate_dormant():
    f, rec, floor, integ_final, integ_ctc, _cb = intelligence_consumer.build("tropical", KEY, _entry(_dormant()), _sc())
    assert f["integrated_recommended_final_cost"] == "4278.99"   # history did not lift it
    assert f["integrated_cost_to_complete"] == "0.00"
    assert f["dormant_suppression_applied"] is True
    assert integ_final == Decimal("4278.99") and integ_ctc == Decimal("0")


def test_monthly_consumer_zeroes_dormant():
    row, months, audit = monthly_consumer.build("tropical", KEY, _entry(_dormant()), _sc(), Decimal("0"))
    assert sum(Decimal(m["integrated_month_cost"]) for m in row["monthly_costs"]) == Decimal("0")
    assert row["dormant_suppression_applied"] is True and audit["reconciled"] is True


def test_probability_consumer_marks_dormant_suppressed():
    row, contrib = probability_consumer.build("tropical", KEY, _entry(_dormant()), _sc(), {})
    assert row["probability_status"] == "dormant_suppressed"
    assert row["integrated_p50"] == "4278.99" and row["integrated_p95"] == "4278.99"
    assert row["operator_final_value_anchor_applied"] is False
    assert contrib["direction"] == "dormant"


def test_value_asserting_control_revives_dormant_in_consumers():
    mc = {"control_id": "c1", "changes_deterministic_final": True, "controlled_remaining": Decimal("5000.00"),
          "controlled_final_cost": Decimal("9278.99"), "value_constraint_policy": "explicit_remaining_value",
          "model_type": "existing_model", "monthly_allocation": {"2026-06": Decimal("5000.00")},
          "active_months": ["2026-06"], "resolved_start_date": None, "resolved_end_date": None,
          "schedule_end_basis": "x"}
    entry = _entry(_dormant(), model_control=mc,
                   prob_final={"simulated_p10": "8000.00", "simulated_p50": "9000.00",
                               "simulated_p80": "9500.00", "simulated_p90": "9800.00", "simulated_p95": "10000.00"})
    f, rec, floor, integ_final, integ_ctc, _cb = intelligence_consumer.build("tropical", KEY, entry, _sc())
    # operator value control wins over dormancy
    assert integ_final == Decimal("9278.99") and integ_ctc == Decimal("5000.00")
    assert f["dormant_suppression_applied"] is False
    prow, _ = probability_consumer.build("tropical", KEY, entry, _sc(), {})
    assert prow["probability_status"] != "dormant_suppressed"   # operator anchor, not dormant


def test_conflicts_emit_dormant_classes():
    classes = [c["conflict_class"] for c in conflicts.build("tropical", KEY, _entry(_dormant()), _sc(),
                                                            Decimal("4278.99"))]
    assert "closed_code_forecast_suppressed" in classes
