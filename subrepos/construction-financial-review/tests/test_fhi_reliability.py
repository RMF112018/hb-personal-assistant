"""Reliability blend: validated history scores high; contradiction collapses the score."""
from decimal import Decimal

from construction_financial_review.forecast_history_informed import history_reliability as hr

KEY = "1000.20-18-110.OVH"


def _sig(strength="0.8000", stability="0.9000", latest="2026-04"):
    return {"cost_code": "20-18-110", "historical_signal_strength": strength,
            "forecast_stability_score": stability, "latest_historical_forecast_month": latest,
            "mapping_status": "cost_code_unique_budget_match", "duplicate_cost_code_warning": False}


def _msrc(invoice_weight):
    return {"source_shares": {"subcontractor_invoice_weight": invoice_weight}}


def test_validated_history_scores_high():
    v = {"validation_class": "validated_aligned", "actual_trend_override_score": "0.2000"}
    rel = hr.build_reliability(_sig(), v, {}, KEY, "2026-04", 6, None, "tropical")
    assert Decimal(rel["overall_history_reliability_score"]) >= Decimal("0.5")
    assert rel["reliability_band"] in ("high", "very_high", "medium")


def test_contradiction_collapses_score():
    v = {"validation_class": "contradicted_escalation", "actual_trend_override_score": "0.9500"}
    rel = hr.build_reliability(_sig(), v, {}, KEY, "2026-04", 6, None, "tropical")
    assert Decimal(rel["overall_history_reliability_score"]) <= Decimal("0.20")
    assert "actuals_contradict_history" in rel["reason_codes"]


def test_stale_history_flagged():
    v = {"validation_class": "inconclusive", "actual_trend_override_score": "0.3000"}
    rel = hr.build_reliability(_sig(latest="2024-06"), v, {}, KEY, "2026-04", 6, None, "tropical")
    assert "stale_history" in rel["reason_codes"]
    assert Decimal(rel["history_recency_score"]) < Decimal("0.25")


def test_actual_evidence_support_hierarchy():
    """CostEntries activity (primary) > subcontractor-invoice support (secondary) > density (tertiary)."""
    sig, ref = _sig(), "2026-04"
    # CostEntries-only: strong recent burn, no invoice share, no completed-actuals density
    v_ce = {"validation_class": "inconclusive", "actual_trend_override_score": "0.0000",
            "recent_6mo_burn": "60000.00", "recent_12mo_burn": "60000.00",
            "cost_entries_actual_cost_in_window": "60000.00"}
    rel_ce = hr.build_reliability(sig, v_ce, {}, KEY, ref, 6, _msrc("0.0000"), "tropical")
    # invoice-only: no CostEntries burn, full invoice source share, no density
    v_zero = {"validation_class": "inconclusive", "actual_trend_override_score": "0.0000",
              "recent_6mo_burn": "0.00", "recent_12mo_burn": "0.00",
              "cost_entries_actual_cost_in_window": "0.00"}
    rel_inv = hr.build_reliability(sig, v_zero, {}, KEY, ref, 6, _msrc("1.0000"), "tropical")
    # density-only: no CostEntries burn, no invoice share, months_of_completed_actuals present
    intel_density = {"trend": {KEY: {"months_of_completed_actuals": 9}}}
    rel_den = hr.build_reliability(sig, v_zero, intel_density, KEY, ref, 6, _msrc("0.0000"), "tropical")

    ce = Decimal(rel_ce["cost_entry_activity_support_score"])
    inv = Decimal(rel_inv["subcontractor_invoice_support_score"])
    den = Decimal(rel_den["actual_history_density_support_score"])
    assert ce == Decimal("1.0000") and inv == Decimal("1.0000") and den == Decimal("1.0000")
    # combined evidence support strictly ranks CostEntries > invoice > density
    assert (Decimal(rel_ce["actual_evidence_support_score"])
            > Decimal(rel_inv["actual_evidence_support_score"])
            > Decimal(rel_den["actual_evidence_support_score"]))
    # the misleading field is gone
    assert "invoice_support_score" not in rel_ce
