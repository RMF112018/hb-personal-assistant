"""Risk reducers: percentile monotonicity, unit-interval probabilities, CVaR>=VaR, downside ranking."""
from collections import OrderedDict
from decimal import Decimal

import numpy as np

from construction_financial_review.forecast_probability import risk_metrics, simulate


def _arrays(n=8, nm=3):
    actual = np.linspace(50000, 400000, n)
    mu = np.log(np.linspace(20000, 150000, n))
    sig = np.full(n, 0.4)
    return OrderedDict([
        ("n_codes", n), ("n_months", nm), ("months", ["2026-06", "2026-07", "2026-08"]),
        ("keys", [f"1000.15-0{i}-100.SUB" for i in range(n)]),
        ("actual", actual), ("mu", mu), ("sigma", sig), ("near_complete", np.zeros(n, dtype=bool)),
        ("recommended_final", actual + np.exp(mu)), ("worst_credible_final", actual + 2 * np.exp(mu)),
        ("current_projected", actual + 0.8 * np.exp(mu)), ("revised_budget", actual + 0.9 * np.exp(mu)),
        ("committed", np.zeros(n)),
        ("base_weights", np.full((n, nm), 1.0 / nm)), ("monthly_score", np.full(n, 0.6)),
        ("rho", 0.3), ("kappa0", 40.0),
    ])


def _project():
    return OrderedDict([
        ("total_actual_to_date", 1_000_000.0), ("total_current_projected_cost", 2_000_000.0),
        ("total_recommended_final_cost", 2_200_000.0), ("total_worst_credible_final_cost", 3_000_000.0),
        ("total_revised_budget", 2_300_000.0),
        ("total_carried_prior_forecast", 0.0), ("window_override_active", False),
    ])


def test_code_percentiles_monotonic_and_probs_unit_interval():
    arr = _arrays()
    sim = simulate.simulate(arr, runs=4000, seed=5)
    rows = risk_metrics.code_rows(sim, arr)
    for r in rows:
        ps = [Decimal(r[k]) for k in ("simulated_p10", "simulated_p50", "simulated_p80",
                                      "simulated_p90", "simulated_p95")]
        assert ps == sorted(ps)
        for k in ("prob_exceeds_current_projected_cost", "prob_exceeds_revised_budget",
                  "prob_exceeds_recommended_final_cost"):
            assert Decimal("0") <= Decimal(r[k]) <= Decimal("1")


def test_project_summary_cvar_ge_var_and_ranks():
    arr = _arrays()
    sim = simulate.simulate(arr, runs=4000, seed=5)
    s = risk_metrics.project_summary(sim, arr, _project(), {"systemic_correlation_rho": 0.3})
    assert Decimal(s["conditional_value_at_risk_p90"]) >= Decimal(s["value_at_risk_p90"])
    sp = s["simulated_final_cost_percentiles"]
    assert Decimal(sp["p10"]) <= Decimal(sp["p50"]) <= Decimal(sp["p90"]) <= Decimal(sp["p95"])
    assert 0 <= float(s["recommended_final_percentile_rank"]) <= 100


def test_project_revised_budget_probability_present_and_valid():
    arr = _arrays()
    sim = simulate.simulate(arr, runs=4000, seed=5)
    s = risk_metrics.project_summary(sim, arr, _project(), {"systemic_correlation_rho": 0.3})
    for k in ("revised_budget_total", "probability_project_exceeds_revised_budget_total",
              "expected_project_overrun_vs_revised_budget_total", "p80_overrun_vs_revised_budget_total",
              "p90_overrun_vs_revised_budget_total", "p95_overrun_vs_revised_budget_total"):
        assert k in s
    assert Decimal("0") <= Decimal(s["probability_project_exceeds_revised_budget_total"]) <= Decimal("1")
    # expected overrun matches mean(max(pf - revised_budget, 0)) exactly
    pf = sim["project_finals"]
    det_rb = _project()["total_revised_budget"]
    expected = float(np.maximum(pf - det_rb, 0.0).mean())
    assert abs(float(s["expected_project_overrun_vs_revised_budget_total"]) - expected) <= 0.01
    # overrun percentiles are floored at 0 and monotonic
    p80, p90, p95 = (float(s[f"p{q}_overrun_vs_revised_budget_total"]) for q in (80, 90, 95))
    assert 0.0 <= p80 <= p90 <= p95


def test_window_reconciliation_identity_holds():
    arr = _arrays()
    sim = simulate.simulate(arr, runs=4000, seed=5)
    s = risk_metrics.project_summary(sim, arr, _project(), {"systemic_correlation_rho": 0.3})
    wr = s["window_reconciliation"]
    # default (no override): carried forecast is zero; identity reconciles to the simulated mean
    assert wr["forecast_start_override_active"] is False
    total = (float(wr["accounting_actual_cost_to_date"])
             + float(wr["deterministic_prior_forecast_before_probability_window"])
             + float(wr["simulated_probability_window_cost_to_complete"]))
    assert abs(total - float(wr["simulated_final_cost_including_carried_forecast"])) <= 0.01


def test_downside_ranking_is_sorted_and_complete():
    arr = _arrays()
    sim = simulate.simulate(arr, runs=4000, seed=5)
    rows = risk_metrics.downside_ranking(sim, arr)
    assert len(rows) == arr["n_codes"]
    contribs = [float(r["downside_contribution_to_project_p90"]) for r in rows]
    assert contribs == sorted(contribs, reverse=True)
    assert [r["rank"] for r in rows] == list(range(1, len(rows) + 1))


def test_monthly_reconciles_at_project_level():
    arr = _arrays()
    sim = simulate.simulate(arr, runs=3000, seed=5)
    prows = risk_metrics.project_monthly_rows(sim, arr, _project())
    # sum of project monthly means ~ project mean CTC
    mean_months = sum(float(r["simulated_mean_month_cost"]) for r in prows)
    mean_ctc = float(sim["ctc"].sum(axis=1).mean())
    assert abs(mean_months - mean_ctc) <= max(1.0, 1e-6 * mean_ctc)
