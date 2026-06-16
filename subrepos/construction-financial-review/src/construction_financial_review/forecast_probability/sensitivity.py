"""Sensitivity analysis: which assumptions most move the project downside (P90).

Three complementary, deterministic views (numpy/scipy, no extra deps):

1. One-at-a-time (OAT) ΔP90 — re-run the simulation with each spread source neutralized (held at the
   same seed so the difference is structural, not sampling noise) and record how the project P90 moves.
   This is the authoritative ranking of "which assumption matters most".
2. Spearman rank correlation (scipy.stats.spearmanr) of each code's simulated final vs the project
   total — which codes' uncertainty most co-moves with the project outcome.
3. Systemic-vs-idiosyncratic variance share — how much of the project-total spread is the shared
   correlation factor vs code-specific noise.

OAT ignores interactions (documented limitation); for a validation slice it is the simplest defensible
attribution.
"""
from __future__ import annotations

from collections import OrderedDict

import numpy as np
from scipy.stats import spearmanr

from . import distributions as dist
from . import simulate as sim_engine
from .risk_metrics import m, p4

# Spread sources we can neutralize and re-measure.
SOURCES = ("cost_volatility_cov", "backtest_mape", "model_divergence",
           "worst_credible_spread", "overrun_tail", "systemic_correlation")


def _recalibrate(specs, params, *, drop=None, rho_override=None):
    """Rebuild stacked arrays with one spread source neutralized. Returns (arrays-like dict)."""
    import numpy as _np

    keys = [s["budget_code_key"] for s in specs]
    n = len(specs)
    months = []  # not needed for final-only sensitivity
    mu = _np.zeros(n)
    sigma = _np.zeros(n)
    actual = _np.array([s["actual"] for s in specs], dtype=_np.float64)
    near = _np.array([s["near_complete"] for s in specs], dtype=bool)
    for j, s in enumerate(specs):
        mu[j] = s["mu"]
        sigma[j] = _resigma(s, params, drop)
    rho = float(params["systemic_correlation_rho"]) if rho_override is None else float(rho_override)
    return OrderedDict([
        ("n_codes", n), ("n_months", 0), ("months", months), ("keys", keys),
        ("actual", actual), ("mu", mu), ("sigma", sigma), ("near_complete", near),
        ("rho", rho), ("kappa0", float(params["monthly_dirichlet_kappa0"])),
        ("base_weights", _np.zeros((n, 0))), ("monthly_score", _np.zeros(n)),
    ])


def _resigma(spec, params, drop):
    """Recompute a code's sigma with one spread component removed."""
    if spec["near_complete"]:
        return 0.0
    sigma_worst = spec["sigma_worst"]
    sigma_cov = spec["sigma_cov"] if drop != "cost_volatility_cov" else 0.0
    sigma_mape = spec["sigma_mape"] if drop != "backtest_mape" else 0.0
    sigma_div = spec["sigma_divergence"] if drop != "model_divergence" else 0.0
    if drop == "worst_credible_spread":
        sigma_worst = 0.0
    if drop == "overrun_tail":
        # remove the tail widening: recompute sigma_worst at the unshifted high quantile
        from scipy.stats import norm
        median_ctc, worst_ctc = spec["median_ctc"], spec["worst_ctc"]
        z = float(norm.ppf(params["high_quantile"]))
        sigma_worst = (np.log(worst_ctc / median_ctc) / z) if (worst_ctc > median_ctc and z > 0) else 0.0
    conf_score = spec["confidence_score"]
    sigma_evidence = ((params["sigma_weight_cov"] * sigma_cov
                       + params["sigma_weight_mape"] * sigma_mape
                       + params["sigma_weight_divergence"] * sigma_div)
                      * (1.0 + params["confidence_inflation_k"] * (1.0 - conf_score)))
    sigma = max(sigma_worst, sigma_evidence)
    return min(max(sigma, params["sigma_floor"]), params["sigma_cap"])


def run_sensitivity(inputs, base_sim, *, runs, seed, antithetic, lhs) -> OrderedDict:
    specs = inputs["specs"]
    params = inputs["params"]
    base_pf = base_sim["project_finals"]
    base_p90 = float(np.percentile(base_pf, 90))

    oat = []
    for source in SOURCES:
        if source == "systemic_correlation":
            arrays = _recalibrate(specs, params, rho_override=0.0)
        else:
            arrays = _recalibrate(specs, params, drop=source)
        s = sim_engine.simulate(arrays, runs=runs, seed=seed, antithetic=antithetic, lhs=lhs,
                                draw_months=False)
        p90 = float(np.percentile(s["project_finals"], 90))
        oat.append(OrderedDict([
            ("source", source),
            ("base_project_p90", m(base_p90)),
            ("neutralized_project_p90", m(p90)),
            ("delta_p90", m(base_p90 - p90)),
            ("abs_delta_p90", m(abs(base_p90 - p90))),
        ]))
    oat.sort(key=lambda r: float(r["abs_delta_p90"]), reverse=True)
    for rank, row in enumerate(oat, start=1):
        row["rank"] = rank

    # Spearman code-vs-project drivers (top 25).
    finals = base_sim["final_costs"]
    keys = inputs["arrays"]["keys"]
    spear = []
    for j, key in enumerate(keys):
        col = finals[:, j]
        if np.ptp(col) == 0:                       # constant (near-complete) column: undefined corr
            rho_s = 0.0
        else:
            rho_s = float(spearmanr(col, base_pf).statistic)
        spear.append((abs(rho_s), rho_s, key))
    spear.sort(reverse=True)
    spearman_rows = [OrderedDict([("budget_code_key", k), ("spearman_vs_project_total", p4(r))])
                     for _, r, k in spear[:25]]

    return OrderedDict([
        ("method", "one_at_a_time_delta_p90 + spearman_rank + systemic_variance_share"),
        ("base_project_p90", m(base_p90)),
        ("oat_delta_p90_by_source", oat),
        ("top_spearman_code_drivers", spearman_rows),
        ("most_influential_assumption", oat[0]["source"] if oat else None),
        ("limitations", "OAT ΔP90 holds the random seed fixed and neutralizes one spread source at a "
                        "time; it does not capture interactions between sources. Spearman is monotone "
                        "association of a code's draws with the project total, not a causal share."),
    ])
