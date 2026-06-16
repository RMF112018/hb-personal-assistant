"""Vectorized engine: determinism, actuals floor, monthly reconciliation, correlation widens tail."""
from collections import OrderedDict

import numpy as np

from construction_financial_review.forecast_probability import simulate


def _arrays(n=6, nm=4, rho=0.3, sigma=0.4):
    rng = np.random.default_rng(0)
    actual = np.full(n, 100000.0)
    mu = np.log(np.full(n, 50000.0))
    sig = np.full(n, sigma)
    near = np.zeros(n, dtype=bool)
    bw = np.full((n, nm), 1.0 / nm)
    return OrderedDict([
        ("n_codes", n), ("n_months", nm), ("months", [f"2026-{m:02d}" for m in range(6, 6 + nm)]),
        ("keys", [f"c{i}" for i in range(n)]),
        ("actual", actual), ("mu", mu), ("sigma", sig), ("near_complete", near),
        ("recommended_final", actual + 50000.0), ("worst_credible_final", actual + 90000.0),
        ("current_projected", actual + 40000.0), ("revised_budget", actual + 45000.0),
        ("committed", np.zeros(n)),
        ("base_weights", bw), ("monthly_score", np.full(n, 0.6)),
        ("rho", rho), ("kappa0", 40.0),
    ])


def test_same_seed_is_identical():
    a = simulate.simulate(_arrays(), runs=2000, seed=20260614)
    b = simulate.simulate(_arrays(), runs=2000, seed=20260614)
    assert np.array_equal(a["final_costs"], b["final_costs"])
    assert np.array_equal(a["month_costs"], b["month_costs"])


def test_different_seed_differs():
    a = simulate.simulate(_arrays(), runs=2000, seed=1)
    b = simulate.simulate(_arrays(), runs=2000, seed=2)
    assert not np.array_equal(a["final_costs"], b["final_costs"])


def test_floor_at_actuals():
    s = simulate.simulate(_arrays(), runs=3000, seed=7)
    assert (s["final_costs"] >= 100000.0).all()


def test_monthly_reconciles_to_ctc():
    s = simulate.simulate(_arrays(), runs=2000, seed=7)
    month_sum = s["month_costs"].sum(axis=2)
    assert np.abs(month_sum - s["ctc"]).max() <= 1e-6


def test_near_complete_codes_stay_at_actual():
    arr = _arrays(n=3)
    arr["near_complete"] = np.array([True, False, False])
    s = simulate.simulate(arr, runs=500, seed=3)
    assert np.allclose(s["final_costs"][:, 0], arr["actual"][0])
    assert np.allclose(s["ctc"][:, 0], 0.0)


def test_correlation_widens_project_tail():
    indep = simulate.simulate(_arrays(n=30, rho=0.0), runs=4000, seed=11, draw_months=False)
    corr = simulate.simulate(_arrays(n=30, rho=0.6), runs=4000, seed=11, draw_months=False)
    assert corr["project_finals"].std() > indep["project_finals"].std()
