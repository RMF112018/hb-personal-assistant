"""Sensitivity: neutralizing a spread source reduces project P90; ranking is ordered."""
from collections import OrderedDict

import numpy as np

from construction_financial_review.forecast_probability import (distributions as dist, sensitivity,
                                                                simulate, simulation_inputs)

PARAMS = dist.params_from_cfg({})


def _spec(key, actual, rec_final, worst_final, cov="0.5", conf="0.4", div="0.3", overrun="0.2"):
    rec = {
        "actual_cost_all_source_to_date": f"{actual:.2f}",
        "recommended_final_cost": f"{rec_final:.2f}",
        "worst_credible_final_cost": f"{worst_final:.2f}",
        "recommended_cost_to_complete": f"{rec_final - actual:.2f}",
        "worst_credible_cost_to_complete": f"{worst_final - actual:.2f}",
        "current_projected_cost": f"{rec_final:.2f}", "revised_budget": f"{rec_final:.2f}",
        "committed_cost": "0.00", "model_divergence": div,
        "confidence_score": conf, "overrun_confidence": overrun,
    }
    cal = dist.calibrate_code(rec, {}, {"cost_volatility_cov": cov}, 0.4, PARAMS)
    cal["budget_code_key"] = key
    return cal


def _inputs(n=6):
    specs = [_spec(f"1000.15-1{i}-100.SUB", 100000, 200000 + 10000 * i, 400000 + 20000 * i)
             for i in range(n)]
    months = ["2026-06", "2026-07"]
    arrays = simulation_inputs._stack(
        [dict(s, base_month_weights=[0.5, 0.5], monthly_distribution_score=0.6,
              cost_code=None, category=None, division=None, budget_code_description=None)
         for s in specs], months, PARAMS)
    return OrderedDict([("specs", specs), ("params", PARAMS), ("arrays", arrays),
                        ("months", months)])


def test_neutralizing_worst_credible_reduces_p90():
    inputs = _inputs()
    base = simulate.simulate(inputs["arrays"], runs=4000, seed=20260614, draw_months=False)
    sens = sensitivity.run_sensitivity(inputs, base, runs=4000, seed=20260614,
                                       antithetic=True, lhs=False)
    by_source = {o["source"]: float(o["delta_p90"]) for o in sens["oat_delta_p90_by_source"]}
    # removing a spread source cannot increase the project P90 (delta = base - neutralized >= ~0)
    assert by_source["worst_credible_spread"] >= -1.0
    assert by_source["cost_volatility_cov"] >= -1.0
    # ranking sorted by abs delta desc
    deltas = [float(o["abs_delta_p90"]) for o in sens["oat_delta_p90_by_source"]]
    assert deltas == sorted(deltas, reverse=True)
    assert sens["most_influential_assumption"] in sensitivity.SOURCES


def test_resigma_drop_reduces_or_holds_sigma():
    spec = _spec("1000.15-10-100.SUB", 100000, 200000, 200000)   # worst==rec -> evidence governs
    full = spec["sigma"]
    dropped = sensitivity._resigma(spec, PARAMS, drop="backtest_mape")
    assert dropped <= full + 1e-9
