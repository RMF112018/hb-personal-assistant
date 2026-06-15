"""Shared minimal per-code `entry` fixture for forecast_comprehensive unit tests."""
from collections import OrderedDict

KEY = "1000.10-01-302.LAB"


def entry(**over):
    e = {
        "actual_cost_to_date": "40000.00", "revised_budget": "90000.00", "projected_costs": "95000.00",
        "rec": {"budget_code_key": KEY, "recommended_final_cost": "100000.00",
                "recommended_cost_to_complete": "60000.00", "forecast_direction": "increase",
                "confidence_score": "0.50", "owner_scope_value": None},
        "trend": {"trend_signal": "supports_overrun", "burn_acceleration_class": "accelerating"},
        "sched": {"schedule_confidence": "0.0", "influences_code_estimate": False,
                  "schedule_remaining_work_status": "no_schedule_evidence", "schedule_association": "project_level"},
        "conf": {"calibrated_confidence": "0.50", "confidence_band": "medium"},
        "monthly_conf": {"monthly_forecast_basis": "cost_entries_trend",
                         "source_shares": OrderedDict([("schedule_weight", "0.0000"),
                            ("cost_entries_weight", "1.0000"), ("subcontractor_invoice_weight", "0.0000"),
                            ("frequency_weight", "0.0000"), ("flat_weight", "0.0000")])},
        "monthly_dist": {"cost_entries_weight": "1.0000", "subcontractor_invoice_weight": "0.0000",
                         "schedule_weight": "0.0000", "flat_weight": "0.0000",
                         "monthly_distribution_weights": [{"month": "2026-06", "weight": "0.333333"},
                            {"month": "2026-07", "weight": "0.333333"}, {"month": "2026-08", "weight": "0.333334"}]},
        "prob_final": {"simulated_p10": "70000.00", "simulated_p50": "100000.00", "simulated_p80": "130000.00",
                       "simulated_p90": "150000.00", "simulated_p95": "180000.00", "simulated_mean": "110000.00",
                       "simulated_std": "30000.00", "prob_exceeds_recommended_final_cost": "0.5000"},
        "prob_sim": {"sigma": "0.5000"},
        "hist_adj": {"history_informed_adjusted_final_cost": "120000.00",
                     "history_informed_direction": "suggest_increase_review", "upper_cap_applied": False},
        "hist_rel": {"overall_history_reliability_score": "0.7000", "reliability_band": "high", "reason_codes": []},
        "hist_val": {"validation_class": "validated_aligned", "actual_trend_override_score": "0.2000"},
        "hist_mon": {"historical_curve_shape_class": "back_loaded", "history_curve_weight_suggestion": "0.3000"},
        "hist_prob": {"suggested_sigma_multiplier": "1.2000", "suggested_tail_shift_delta": "0.0300",
                      "suggested_probability_direction": "increase_uncertainty"},
        "freq": {"effective_frequency_class": "weekly_internal_staffing", "is_internal_staffing_code": True,
                 "cost_code": "10-01-302", "frequency_confidence": "high", "daily_rate": "1000.0000",
                 "daily_rate_confidence": "medium", "cadence_change_detected": False},
        "freq_phasing": {"monthly_phasing_weights": [{"forecast_month": "2026-06", "weight": "0.340000"},
                            {"forecast_month": "2026-07", "weight": "0.330000"}, {"forecast_month": "2026-08", "weight": "0.330000"}]},
        "owner_pay_app": {"latest_current_value": None},
        "sub_pay_app": {"latest_total_completed_and_stored_to_date_sum": None},
    }
    e.update(over)
    return e
