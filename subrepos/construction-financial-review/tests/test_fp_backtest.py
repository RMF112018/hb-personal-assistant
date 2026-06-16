"""Probabilistic backtest: PIT/coverage on a reconstructed cohort + insufficient-cohort fallback."""
from collections import OrderedDict
from decimal import Decimal

import numpy as np

from construction_financial_review.forecast_probability import distributions as dist
from construction_financial_review.forecast_probability import probabilistic_backtest as pb

PARAMS = dist.params_from_cfg({})
VERDICTS = {"insufficient_cohort", "under_dispersed", "over_dispersed",
            "well_calibrated", "approximately_calibrated"}

MONTHS = ["2025-01", "2025-02", "2025-03", "2025-04", "2025-05", "2025-06", "2025-07", "2025-08", "2025-09"]
OWNER_PTS = [("2025-01-31", "0.20"), ("2025-03-31", "0.40"), ("2025-05-31", "0.60"),
             ("2025-07-31", "0.80"), ("2025-09-30", "0.97")]


def _code(key, total, projected, committed):
    per = total / len(MONTHS)
    ctx = OrderedDict([
        ("budget_code_key", key),
        ("actuals", OrderedDict([
            ("actual_cost_all_source_to_date", f"{total:.2f}"),
            ("monthly_actuals", [OrderedDict([("month", mth),
                                              ("amount_decimal_string", f"{per:.2f}"),
                                              ("actual_period_bucket", "through_may_2026")])
                                 for mth in MONTHS]),
        ])),
        ("owner_pay_app", OrderedDict([("latest_percent_complete", "0.97")])),
        ("budget_amounts", OrderedDict([("committed_costs", f"{committed:.2f}"),
                                        ("projected_costs", f"{projected:.2f}")])),
    ])
    hist = [OrderedDict([("period_to", pt), ("percent_complete", pct)]) for pt, pct in OWNER_PTS]
    return ctx, hist


def _inputs(codes):
    context_rows, owner_history = [], {}
    for key, total, proj, comm in codes:
        ctx, hist = _code(key, total, proj, comm)
        context_rows.append(ctx)
        owner_history[key] = hist
    n = len(codes)
    arrays = OrderedDict([("sigma", np.full(n, 0.4)), ("near_complete", np.zeros(n, dtype=bool))])
    backtest = {
        "cohort_size": n,
        "summary_by_method": [
            {"method": "owner_progress_eac", "mape": "0.20"},
            {"method": "trend_projection_eac", "mape": "0.35"},
            {"method": "commitment_exposure_eac", "mape": "0.10"},
            {"method": "cpi_blend_eac", "mape": "0.15"},
        ],
        "calibration_weights": {"owner_progress_eac": "1.0", "trend_projection_eac": "0.8",
                                "commitment_exposure_eac": "1.2", "cpi_blend_eac": "1.1"},
    }
    return OrderedDict([
        ("project_key", "tropical"), ("params", PARAMS), ("arrays", arrays),
        ("backtest", backtest), ("context_rows", context_rows), ("owner_history", owner_history),
    ])


def test_insufficient_when_no_context():
    inputs = OrderedDict([
        ("project_key", "tropical"), ("params", PARAMS),
        ("arrays", OrderedDict([("sigma", np.array([0.4])), ("near_complete", np.array([False]))])),
        ("backtest", {"cohort_size": 0, "summary_by_method": [], "calibration_weights": {}}),
        ("context_rows", []), ("owner_history", {}),
    ])
    out = pb.run_probabilistic_backtest(inputs)
    assert out["calibration_verdict"] == "insufficient_cohort"
    assert out["coverage_pit_available"] is False
    assert "dispersion_adequacy_secondary" in out


def test_pit_points_in_range_and_structure():
    codes = [(f"1000.15-1{i}-100.SUB", 900000.0 + 10000 * i, 1_000_000.0, 800000.0) for i in range(6)]
    out = pb.run_probabilistic_backtest(_inputs(codes))
    pit = out["pit_coverage"]
    assert pit["n_pit_points"] > 0
    assert out["calibration_verdict"] in VERDICTS
    assert Decimal("0") <= Decimal(out["coverage_p10_p90"]) <= Decimal("1")
    assert Decimal("0") <= Decimal(out["coverage_p05_p95"]) <= Decimal("1")
    assert Decimal("0") <= Decimal(out["pit_mean"]) <= Decimal("1")
    for p in pit["pit_points"]:
        assert Decimal("0") <= Decimal(p["pit"]) <= Decimal("1")
        assert isinstance(p["within_p10_p90"], bool)
        assert Decimal(p["predicted_p10_final"]) <= Decimal(p["predicted_p90_final"])
    # KS fields present when >=2 points
    assert pit["pit_ks_statistic"] is not None
    assert sum(pit["pit_deciles"]) == pit["n_pit_points"]


def test_secondary_dispersion_block_present():
    codes = [(f"1000.15-2{i}-100.SUB", 900000.0, 1_000_000.0, 800000.0) for i in range(3)]
    out = pb.run_probabilistic_backtest(_inputs(codes))
    sec = out["dispersion_adequacy_secondary"]
    assert sec["method"] == "dispersion_adequacy_vs_historical_mape"
    assert "slice_to_historical_sigma_ratio" in sec
