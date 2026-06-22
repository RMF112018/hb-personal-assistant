"""Unit tests for the deterministic classical time-series engine + timeseries_eac estimator."""

from __future__ import annotations

from construction_financial_review.forecast_intelligence import estimators_uncapped as est
from construction_financial_review.forecast_intelligence import timeseries_engine as te


def _series(n, base=100.0, step=10.0):
    return [base + step * i for i in range(n)]


def test_full_ensemble_and_determinism():
    s = [100.0, 120.0, 110.0, 130.0, 140.0, 135.0, 150.0, 160.0, 155.0, 170.0, 180.0, 175.0]
    a = te.forecast_etc(s, 6)
    b = te.forecast_etc(s, 6)
    assert a == b  # deterministic, RNG-free
    assert a["model_set"] == ["naive", "drift", "holt_linear", "theta_like"]
    assert a["fallback_used"] is False
    assert a["applicable"] is True
    assert set(a["per_model_etc"]) == set(a["model_set"])


def test_fallback_under_six_obs():
    f = te.forecast_etc(_series(4), 3)
    assert f["model_set"] == ["naive", "drift"]
    assert f["fallback_used"] is True


def test_not_applicable_too_short_or_no_horizon():
    assert te.forecast_etc(_series(2), 3)["applicable"] is False
    assert te.forecast_etc(_series(6), 0)["applicable"] is False


def test_naive_etc_is_last_value_times_horizon():
    # A flat series => every model collapses to ~last value; ETC ~= last*h.
    s = [50.0] * 8
    out = te.forecast_etc(s, 4)
    assert abs(out["etc"] - 200.0) < 1e-6


def test_estimator_applicable_floors_and_labels():
    bundle = {
        "actual_cost_all_source_to_date": "1000000.00",
        "remaining_months_project": "6",
        "monthly_actuals_completed": [
            {"month": f"2025-{i:02d}", "amount": str(100000 + 1000 * i)} for i in range(1, 13)
        ],
    }
    r = est.timeseries_eac(bundle)
    assert r["method"] == "timeseries_eac"
    assert r["source"] == "shadow_timeseries"
    assert r["applicable"] is True
    assert r["association_scale"] == "0.0"
    assert r["inputs"]["backend"] == te.BACKEND_LABEL
    assert r["inputs"]["horizon_months"] == 6
    assert r["inputs"]["model_set"] == ["naive", "drift", "holt_linear", "theta_like"]
    # EAC floored to >= actuals.
    from construction_financial_review.common.money import D

    assert D(r["eac"]) >= D(bundle["actual_cost_all_source_to_date"])


def test_estimator_not_applicable_short_history():
    r = est.timeseries_eac(
        {
            "actual_cost_all_source_to_date": "100.00",
            "remaining_months_project": "6",
            "monthly_actuals_completed": [{"month": "2025-01", "amount": "50"}],
        }
    )
    assert r["applicable"] is False
    assert r["eac"] is None


def test_registered_as_shadow_not_independent():
    assert est.timeseries_eac in est.ALL_ESTIMATORS
    assert "timeseries_eac" not in est.INDEPENDENT_METHODS
