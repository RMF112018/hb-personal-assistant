"""Reliability blend: validated history scores high; contradiction collapses the score."""
from decimal import Decimal

from construction_financial_review.forecast_history_informed import history_reliability as hr

KEY = "1000.20-18-110.OVH"


def _sig(strength="0.8000", stability="0.9000", latest="2026-04"):
    return {"cost_code": "20-18-110", "historical_signal_strength": strength,
            "forecast_stability_score": stability, "latest_historical_forecast_month": latest,
            "mapping_status": "cost_code_unique_budget_match", "duplicate_cost_code_warning": False}


def test_validated_history_scores_high():
    v = {"validation_class": "validated_aligned", "actual_trend_override_score": "0.2000"}
    rel = hr.build_reliability(_sig(), v, {}, KEY, "2026-04", 6, "tropical")
    assert Decimal(rel["overall_history_reliability_score"]) >= Decimal("0.5")
    assert rel["reliability_band"] in ("high", "very_high", "medium")


def test_contradiction_collapses_score():
    v = {"validation_class": "contradicted_escalation", "actual_trend_override_score": "0.9500"}
    rel = hr.build_reliability(_sig(), v, {}, KEY, "2026-04", 6, "tropical")
    assert Decimal(rel["overall_history_reliability_score"]) <= Decimal("0.20")
    assert "actuals_contradict_history" in rel["reason_codes"]


def test_stale_history_flagged():
    v = {"validation_class": "inconclusive", "actual_trend_override_score": "0.3000"}
    rel = hr.build_reliability(_sig(latest="2024-06"), v, {}, KEY, "2026-04", 6, "tropical")
    assert "stale_history" in rel["reason_codes"]
    assert Decimal(rel["history_recency_score"]) < Decimal("0.25")
