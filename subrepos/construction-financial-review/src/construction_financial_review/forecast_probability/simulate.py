"""Vectorized Monte Carlo engine (numpy).

Per run, per code: a one-factor Gaussian copula links codes through a single shared systemic factor
plus idiosyncratic noise, then a shifted-lognormal turns the correlated normal into a cost-to-complete
draw. The actuals floor is exact (CTC >= 0 => final >= actual); there is NO upper cap. Monthly costs
are the simulated CTC time-phased by a Dirichlet perturbation of the deterministic monthly weights,
so per run the months always reconcile exactly to that run's CTC.

Determinism: a single numpy Generator (PCG64) seeded from `seed` drives every draw in a fixed order,
so identical (seed, arrays) => identical float64 draws => identical outputs.
"""
from __future__ import annotations

from collections import OrderedDict

import numpy as np
from scipy.stats import norm, qmc

# Dirichlet concentration is bounded below so weights never collapse to a degenerate simplex corner.
KAPPA_MIN = 2.0
_EPS = 1e-9


def _systemic_normals(rng, runs, antithetic, lhs):
    """Standard-normal systemic factor, length `runs`. Antithetic and/or Latin-Hypercube optional."""
    if lhs:
        sampler = qmc.LatinHypercube(d=1, seed=rng)
        u = sampler.random(n=runs)[:, 0]
        u = np.clip(u, 1e-6, 1 - 1e-6)
        return norm.ppf(u)
    if antithetic:
        half = (runs + 1) // 2
        z = rng.standard_normal(half)
        return np.concatenate([z, -z])[:runs]
    return rng.standard_normal(runs)


def _idiosyncratic_normals(rng, runs, ncodes, antithetic):
    if antithetic:
        half = (runs + 1) // 2
        e = rng.standard_normal((half, ncodes))
        return np.concatenate([e, -e], axis=0)[:runs]
    return rng.standard_normal((runs, ncodes))


def simulate(arrays: dict, *, runs: int, seed: int, antithetic: bool = True,
             lhs: bool = False, draw_months: bool = True) -> OrderedDict:
    """Run the simulation. Returns final-cost and (optionally) monthly-cost matrices.

    final_costs: (runs, n_codes)   simulated final cost per code per run (>= actual).
    ctc:         (runs, n_codes)   simulated cost-to-complete (final - actual).
    month_costs: (runs, n_codes, n_months) or None.
    project_finals: (runs,)        Σ final cost across codes per run.
    """
    rng = np.random.default_rng(seed)
    n = arrays["n_codes"]
    mu = arrays["mu"]
    sigma = arrays["sigma"]
    actual = arrays["actual"]
    # Deterministic prior-month forecast carried forward when a later --forecast-start-month shortens
    # the window (zeros on the default path). Added as a fixed addend; the accounting actual stays the
    # only hard floor (carried >= 0 and ctc >= 0, so final >= actual).
    carried = arrays.get("carried_prior_forecast")
    if carried is None:
        carried = np.zeros(arrays["n_codes"], dtype=np.float64)
    near = arrays["near_complete"]
    rho = float(arrays["rho"])

    z_sys = _systemic_normals(rng, runs, antithetic, lhs)              # (runs,)
    eps = _idiosyncratic_normals(rng, runs, n, antithetic)            # (runs, n)
    a = np.sqrt(rho)
    b = np.sqrt(max(0.0, 1.0 - rho))
    z = a * z_sys[:, None] + b * eps                                  # (runs, n) correlated normal

    ctc = np.exp(mu[None, :] + sigma[None, :] * z)                    # (runs, n)
    if near.any():
        ctc[:, near] = 0.0                                           # complete codes: no remaining cost
    final = actual[None, :] + carried[None, :] + ctc                # floor exact; no upper cap

    project_finals = final.sum(axis=1)

    month_costs = None
    if draw_months:
        month_costs = _simulate_months(rng, ctc, arrays)

    return OrderedDict([
        ("runs", runs), ("seed", seed), ("antithetic", bool(antithetic)), ("lhs", bool(lhs)),
        ("final_costs", final), ("ctc", ctc), ("project_finals", project_finals),
        ("month_costs", month_costs), ("systemic_normals", z_sys),
    ])


def _simulate_months(rng, ctc, arrays):
    """Time-phase each run's CTC with a Dirichlet perturbation of the deterministic monthly weights.

    alpha = base_weights * kappa, kappa = max(KAPPA_MIN, kappa0 * monthly_distribution_score).
    High monthly-distribution confidence => high kappa => weights stay close to the deterministic
    shape; low confidence => more month-to-month dispersion. Per run the weights sum to 1, so
    Σ month_cost == CTC for that run exactly.
    """
    runs, n = ctc.shape
    nm = arrays["n_months"]
    base = arrays["base_weights"]                 # (n, nm)
    score = arrays["monthly_score"]               # (n,)
    kappa0 = float(arrays["kappa0"])
    month_costs = np.zeros((runs, n, nm), dtype=np.float64)
    for j in range(n):
        bw = base[j]
        kappa = max(KAPPA_MIN, kappa0 * float(score[j]))
        alpha = np.maximum(bw * kappa, _EPS)
        w = rng.dirichlet(alpha, size=runs)       # (runs, nm), rows sum to 1
        month_costs[:, j, :] = ctc[:, j][:, None] * w
    return month_costs
