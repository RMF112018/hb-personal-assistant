"""Per-code lognormal-CTC calibration: median anchor, worst-credible quantile, floor, spread drivers."""
import math

from construction_financial_review.forecast_probability import distributions as dist

PARAMS = dist.params_from_cfg({})


def _rec(actual, rec_final, worst_final, **kw):
    r = {
        "actual_cost_all_source_to_date": f"{actual:.2f}",
        "recommended_final_cost": f"{rec_final:.2f}",
        "worst_credible_final_cost": f"{worst_final:.2f}",
        "recommended_cost_to_complete": f"{rec_final - actual:.2f}",
        "worst_credible_cost_to_complete": f"{worst_final - actual:.2f}",
        "current_projected_cost": f"{rec_final:.2f}",
        "revised_budget": f"{rec_final:.2f}",
        "committed_cost": "0.00",
        "model_divergence": "0.0000",
        "confidence_score": "0.50",
        "overrun_confidence": "0.00",
    }
    r.update(kw)
    return r


def test_median_anchors_to_recommended_ctc():
    cal = dist.calibrate_code(_rec(40000, 100000, 160000), {}, {}, 0.0, PARAMS)
    assert not cal["near_complete"]
    assert math.isclose(cal["mu"], math.log(60000.0), rel_tol=1e-9)
    # lognormal median = exp(mu) = recommended CTC => final P50 = actual + CTC = recommended final
    assert math.isclose(math.exp(cal["mu"]) + cal["actual"], 100000.0, rel_tol=1e-9)


def test_worst_credible_maps_to_high_quantile():
    cal = dist.calibrate_code(_rec(40000, 100000, 160000), {}, {}, 0.0, PARAMS)
    # sigma_worst solves median*exp(sigma*z90) = worst_ctc
    from scipy.stats import norm
    z = norm.ppf(cal["effective_high_quantile"])
    recovered = math.exp(cal["mu"] + cal["sigma_worst"] * z) + cal["actual"]
    assert math.isclose(recovered, 160000.0, rel_tol=1e-6)


def test_near_complete_is_point_mass_at_actual():
    cal = dist.calibrate_code(_rec(50000, 50000, 50000), {}, {}, 0.0, PARAMS)
    assert cal["near_complete"] is True
    assert cal["sigma"] == 0.0
    assert cal["median_ctc"] == 0.0


def test_low_confidence_widens_spread():
    # worst == recommended so sigma_worst == 0 and the evidence blend (incl. confidence) governs sigma.
    trend = {"cost_volatility_cov": "0.50"}
    hi = dist.calibrate_code(_rec(40000, 100000, 100000, confidence_score="0.90"), {}, trend, 0.3, PARAMS)
    lo = dist.calibrate_code(_rec(40000, 100000, 100000, confidence_score="0.10"), {}, trend, 0.3, PARAMS)
    assert lo["sigma"] > hi["sigma"]


def test_overrun_confidence_fattens_tail_without_moving_median():
    base = dist.calibrate_code(_rec(40000, 100000, 160000, overrun_confidence="0.00"), {}, {}, 0.0, PARAMS)
    tail = dist.calibrate_code(_rec(40000, 100000, 160000, overrun_confidence="0.90"), {}, {}, 0.0, PARAMS)
    assert tail["effective_high_quantile"] < base["effective_high_quantile"]
    assert tail["sigma"] > base["sigma"]
    assert math.isclose(tail["mu"], base["mu"], rel_tol=1e-12)   # median preserved


def test_sigma_within_floor_and_cap():
    cal = dist.calibrate_code(_rec(40000, 100000, 1_000_000), {}, {"cost_volatility_cov": "5.0"}, 5.0, PARAMS)
    assert PARAMS["sigma_floor"] <= cal["sigma"] <= PARAMS["sigma_cap"]
