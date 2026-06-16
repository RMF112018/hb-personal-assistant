"""Priority 3 calibration tests: denominator + sample-size guards, bias direction, determinism."""
from construction_financial_review.forecast_improvement_audit import calibration

from tests._fia_fixtures import minimal_inputs

BACKTEST = {
    "cohort_size": 10, "detail_row_count": 29,
    "summary_by_method": [
        {"method": "owner_progress_eac", "n": 29, "mape": "0.3447", "mean_bias": "0.1863"},
        {"method": "thin_method", "n": 3, "mape": None, "mean_bias": "-0.20"},
    ],
    "before_after_by_method": [
        {"method": "owner_progress_eac", "prior_method": "owner_pct", "prior_mape": "0.13",
         "new_mape": "0.34", "mape_delta": "0.21"},
    ],
    "cohort_breakdown_by_family": [{"cost_code_family": "15-03", "n": 12, "mape": "0.36"}],
    "cohort_breakdown_by_division": [],
}


def test_valid_denominator_and_sufficient_sample():
    rows, _ = calibration.build(minimal_inputs(backtest=BACKTEST), {})
    owner = next(r for r in rows if r.get("method") == "owner_progress_eac"
                 and r["metric_type"] == "method_calibration")
    assert owner["mape_denominator_valid"] is True
    assert owner["sample_sufficient"] is True
    assert owner["insufficient_sample"] is False
    assert owner["bias_direction"] == "over_forecast"


def test_zero_denominator_and_insufficient_sample_and_under_bias():
    rows, _ = calibration.build(minimal_inputs(backtest=BACKTEST), {})
    thin = next(r for r in rows if r.get("method") == "thin_method"
                and r["metric_type"] == "method_calibration")
    assert thin["mape_denominator_valid"] is False     # mape is null -> denominator invalid
    assert thin["insufficient_sample"] is True          # n=3 < min 8
    assert thin["bias_direction"] == "under_forecast"


def test_unavailable_backtest_emits_gap():
    rows, gaps = calibration.build(minimal_inputs(backtest=None), {})
    assert rows == []
    assert any(g["gap_type"] == "backtest_unavailable" for g in gaps)


def test_metrics_limited_gap_present():
    _, gaps = calibration.build(minimal_inputs(backtest=BACKTEST), {})
    assert any(g["gap_type"] == "metrics_limited_to_mape_and_bias" for g in gaps)


def test_deterministic():
    a, _ = calibration.build(minimal_inputs(backtest=BACKTEST), {})
    b, _ = calibration.build(minimal_inputs(backtest=BACKTEST), {})
    assert a == b
