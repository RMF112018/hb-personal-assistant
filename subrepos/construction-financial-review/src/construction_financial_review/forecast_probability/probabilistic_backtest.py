"""Calibration honesty check for the probabilistic model.

The accepted anchor package ships only the AGGREGATE backtest (`summary_by_method` MAPE + cohort
size); it does not carry per-code realized-vs-predicted detail rows, so a true row-level PIT / coverage
test cannot be computed from the package alone. Rather than reconstruct the cohort (fragile, and
out of scope for an additive validation slice), this module performs an honest DISPERSION-ADEQUACY
check: it compares the spread this slice assigns (median per-code sigma) against the spread implied by
the historical method errors (sigma ~ ln(1 + MAPE)). It is explicit about its limits and never
silently "passes" on thin data.
"""
from __future__ import annotations

import math
from collections import OrderedDict

import numpy as np

from ..common.money import D
from .risk_metrics import p4

MIN_COHORT = 8


def _implied_sigma_from_mape(backtest: dict) -> tuple[float, dict]:
    per_method = OrderedDict()
    sigmas = []
    for row in backtest.get("summary_by_method") or []:
        mv = row.get("mape")
        if mv is None:
            continue
        try:
            mape = float(D(mv))
        except Exception:
            continue
        s = math.log(1.0 + max(0.0, mape))
        per_method[row.get("method")] = OrderedDict([("mape", p4(mape)), ("implied_sigma", p4(s))])
        sigmas.append(s)
    mean_sigma = float(np.mean(sigmas)) if sigmas else 0.0
    return mean_sigma, per_method


def run_probabilistic_backtest(inputs) -> OrderedDict:
    backtest = inputs["backtest"]
    arrays = inputs["arrays"]
    cohort_size = int(backtest.get("cohort_size") or 0)

    implied_sigma, per_method = _implied_sigma_from_mape(backtest)
    sigma = arrays["sigma"]
    near = arrays["near_complete"]
    active = sigma[~near]
    slice_median_sigma = float(np.median(active)) if active.size else 0.0

    ratio = (slice_median_sigma / implied_sigma) if implied_sigma > 0 else None

    if cohort_size < MIN_COHORT:
        verdict = "insufficient_cohort"
        warning = (f"Backtest cohort is only {cohort_size} near-complete code(s) (< {MIN_COHORT}); "
                   "the dispersion-adequacy check is indicative, not conclusive.")
    elif ratio is None:
        verdict = "indeterminate_no_historical_error"
        warning = "No historical method MAPE available to imply a comparison spread."
    elif ratio < 0.7:
        verdict = "under_dispersed"
        warning = "Slice spread is materially tighter than historical method error implies."
    elif ratio > 1.5:
        verdict = "over_dispersed"
        warning = "Slice spread is materially wider than historical method error implies."
    else:
        verdict = "dispersion_consistent_with_history"
        warning = None

    return OrderedDict([
        ("method", "dispersion_adequacy_vs_historical_mape"),
        ("cohort_size", cohort_size),
        ("min_cohort_for_conclusive_check", MIN_COHORT),
        ("historical_implied_sigma_mean", p4(implied_sigma)),
        ("slice_median_active_sigma", p4(slice_median_sigma)),
        ("slice_to_historical_sigma_ratio", p4(ratio) if ratio is not None else None),
        ("per_method_implied_sigma", per_method),
        ("calibration_verdict", verdict),
        ("cohort_warning", warning),
        ("coverage_pit_available", False),
        ("interpretation", "The historical MAPE cohort is NEAR-COMPLETE (owner >= 95% complete), which "
                           "carries little remaining-work risk, so it implies a tighter spread than "
                           "codes with substantial cost-to-complete. A slice/historical ratio above 1 "
                           "is therefore expected: most of the slice's per-code spread is anchored to "
                           "the deterministic worst-credible band (forward exposure) plus backtest "
                           "error, not to near-complete error alone."),
        ("limitations", "Aggregate-only: the anchor package does not carry per-code realized finals, "
                        "so a row-level PIT/coverage test is not computed. This compares the slice's "
                        "assigned dispersion to the dispersion implied by historical method MAPE on a "
                        f"small near-complete cohort ({cohort_size}). Treat as a sanity check."),
    ])
