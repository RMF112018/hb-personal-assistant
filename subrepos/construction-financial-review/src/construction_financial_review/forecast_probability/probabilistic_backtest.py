"""Calibration of the probabilistic model — a TRUE PIT / coverage test (primary) plus a
dispersion-adequacy ratio (secondary).

Primary (PIT + coverage): reuse the deterministic near-complete cohort reconstruction in
`forecast_intelligence.backtest_strong.run_strong_backtest` (owner >= 95% codes scored at 40/60/80%
owner progress). For each (code, as-of) point we rebuild the predictive distribution the slice's
shifted-lognormal-on-CTC family would have produced AT THAT AS-OF POINT and evaluate it against the
realized final:
  - Each reconstructed method's as-of EAC is recovered exactly from its `signed_bias`
    (eac = realized * (1 + signed_bias); backtest_strong floors EAC at actual-to-date before scoring).
  - `actual_to_t` is recovered exactly from the owner-progress method
    (owner_progress_eac = actual_to_t / owner_pct => actual_to_t = eac_owner * asof_owner_percent).
  - median CTC = calibration-weighted mean of the methods' (eac - actual_to_t); sigma is built from
    the SAME evidence weights the slice uses, restricted to what is reconstructable at as-of
    (cross-method CTC log-dispersion + historical method MAPE; worst-credible band and confidence are
    not available at as-of and are omitted).
  - PIT = F_predicted(realized); coverage at [P10,P90] (nominal 0.80) and [P05,P95] (nominal 0.90);
    PIT uniformity via a Kolmogorov-Smirnov test.

Secondary (dispersion adequacy): compares the slice's median per-code sigma to the sigma implied by
historical method MAPE (ln(1+MAPE)). Honest about the small near-complete cohort throughout.
Deterministic (no RNG); stays inside the determinism self-check.
"""
from __future__ import annotations

import math
from collections import OrderedDict

import numpy as np
from scipy.stats import kstest, lognorm

from ..common.money import D
from ..forecast_intelligence import backtest_strong
from .risk_metrics import m, p2, p4

MIN_COHORT = 8        # secondary dispersion-adequacy threshold
MIN_POINTS = 12       # minimum scored (code, as-of) points for a conclusive PIT/coverage verdict
NOMINAL_80 = 0.80
NOMINAL_90 = 0.90


def _clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


# --------------------------------------------------------------------------- primary: PIT + coverage

def _cohort_weighted_mape(backtest: dict) -> float:
    mape_by = {}
    for r in backtest.get("summary_by_method") or []:
        if r.get("mape") is not None:
            try:
                mape_by[r["method"]] = float(D(r["mape"]))
            except Exception:
                pass
    cw = backtest.get("calibration_weights") or {}
    num = den = 0.0
    for meth, mp in mape_by.items():
        w = float(D(cw.get(meth))) if cw.get(meth) is not None else 1.0
        w = max(w, 0.0)
        num += w * mp
        den += w
    if den > 0:
        return num / den
    return (sum(mape_by.values()) / len(mape_by)) if mape_by else 0.5


def _score_point(row, realized_by_key, calib_w, sigma_mape, params):
    key = row.get("budget_code_key")
    realized = realized_by_key.get(key)
    if realized is None or realized <= 0:
        return None
    try:
        asof_pct = float(D(row.get("asof_owner_percent_complete")))
    except Exception:
        return None
    if asof_pct <= 0:
        return None

    eac_by = {}
    for p in row.get("predictions") or []:
        try:
            bias = float(D(p.get("signed_bias")))
        except Exception:
            continue
        eac = realized * (1.0 + bias)            # backtest floored eac at actual_to_t before scoring
        if eac > 0:
            eac_by[p.get("method")] = eac
    if "owner_progress_eac" not in eac_by:
        return None                              # need it to recover actual_to_t

    actual_to_t = eac_by["owner_progress_eac"] * asof_pct
    if actual_to_t <= 0:
        return None

    ctcs, weights, ln_ctcs = [], [], []
    for meth, eac in eac_by.items():
        ctc = eac - actual_to_t
        if ctc > 0:
            w = float(D(calib_w.get(meth))) if calib_w.get(meth) is not None else 1.0
            ctcs.append(ctc)
            weights.append(max(w, 0.0))
            ln_ctcs.append(math.log(ctc))
    if not ctcs:
        return None
    den = sum(weights) or float(len(ctcs))
    central_ctc = sum(w * c for w, c in zip(weights, ctcs)) / den if sum(weights) > 0 \
        else sum(ctcs) / len(ctcs)
    if central_ctc <= 1.0:
        return None                              # no meaningful remaining work to test

    sigma_div = float(np.std(ln_ctcs, ddof=1)) if len(ln_ctcs) >= 2 else 0.0
    sigma_asof = _clamp(params["sigma_weight_divergence"] * sigma_div
                        + params["sigma_weight_mape"] * sigma_mape,
                        params["sigma_floor"], params["sigma_cap"])

    realized_ctc = max(realized - actual_to_t, 0.0)
    pit = float(lognorm.cdf(realized_ctc, sigma_asof, scale=central_ctc))
    p05c = float(lognorm.ppf(0.05, sigma_asof, scale=central_ctc))
    p10c = float(lognorm.ppf(0.10, sigma_asof, scale=central_ctc))
    p90c = float(lognorm.ppf(0.90, sigma_asof, scale=central_ctc))
    p95c = float(lognorm.ppf(0.95, sigma_asof, scale=central_ctc))
    within80 = bool(p10c <= realized_ctc <= p90c)
    within90 = bool(p05c <= realized_ctc <= p95c)

    return OrderedDict([
        ("budget_code_key", key), ("asof_target", row.get("asof_target")),
        ("asof_owner_percent_complete", row.get("asof_owner_percent_complete")),
        ("realized_final_cost", m(realized)),
        ("actual_to_as_of", m(actual_to_t)),
        ("predicted_central_final", m(actual_to_t + central_ctc)),
        ("predicted_sigma", p4(sigma_asof)),
        ("predicted_p10_final", m(actual_to_t + p10c)),
        ("predicted_p90_final", m(actual_to_t + p90c)),
        ("pit", p4(pit)),
        ("within_p10_p90", within80), ("within_p05_p95", within90),
        ("_pit_value", pit), ("_within80", within80), ("_within90", within90),
    ])


def _pit_block(inputs):
    backtest = inputs["backtest"]
    cohort_size = int(backtest.get("cohort_size") or 0)
    context_rows = inputs.get("context_rows") or []
    if not context_rows:
        return OrderedDict([
            ("method", "pit_coverage_calibration"),
            ("cohort_size", cohort_size), ("n_pit_points", 0),
            ("min_points_for_conclusive_check", MIN_POINTS),
            ("calibration_verdict", "insufficient_cohort"),
            ("cohort_warning", "Context package unavailable; cannot reconstruct the cohort for a "
                               "PIT/coverage test. Falling back to the dispersion-adequacy check only."),
        ])

    bt = backtest_strong.run_strong_backtest(context_rows, inputs.get("owner_history") or {},
                                             inputs["project_key"])
    realized_by_key = {}
    for ctx in context_rows:
        k = ctx.get("budget_code_key")
        rv = (ctx.get("actuals") or {}).get("actual_cost_all_source_to_date")
        if k is not None and rv is not None:
            realized_by_key[k] = float(D(rv))

    params = inputs["params"]
    sigma_mape = math.log(1.0 + max(0.0, _cohort_weighted_mape(backtest)))
    calib_w = backtest.get("calibration_weights") or {}

    points = []
    for row in bt.get("detail_rows") or []:
        pt = _score_point(row, realized_by_key, calib_w, sigma_mape, params)
        if pt:
            points.append(pt)

    n = len(points)
    pits = [pt["_pit_value"] for pt in points]
    cov80 = (sum(1 for pt in points if pt["_within80"]) / n) if n else 0.0
    cov90 = (sum(1 for pt in points if pt["_within90"]) / n) if n else 0.0
    pit_mean = (sum(pits) / n) if n else 0.0
    deciles = [int(c) for c in np.histogram(pits, bins=10, range=(0.0, 1.0))[0]] if n else []
    ks_stat = ks_p = None
    if n >= 2:
        ks = kstest(pits, "uniform")
        ks_stat, ks_p = float(ks.statistic), float(ks.pvalue)

    if n < MIN_POINTS:
        verdict = "insufficient_cohort"
        warning = (f"Only {n} scorable (code, as-of) point(s) (< {MIN_POINTS}); PIT/coverage is "
                   "indicative, not conclusive.")
    elif cov80 < 0.65:
        verdict = "under_dispersed"
        warning = "Realized finals fall outside the predicted P10-P90 band more often than nominal."
    elif cov80 > 0.95:
        verdict = "over_dispersed"
        warning = "Realized finals fall inside the predicted band almost always; bands look too wide."
    elif (abs(cov80 - NOMINAL_80) <= 0.15 and abs(cov90 - NOMINAL_90) <= 0.10
          and (ks_p is None or ks_p > 0.05)):
        verdict = "well_calibrated"
        warning = None
    else:
        verdict = "approximately_calibrated"
        warning = ("Coverage is in range but the PIT departs from uniform (small cohort); treat as "
                   "approximate.")

    block = OrderedDict([
        ("method", "pit_coverage_calibration"),
        ("description", "Predicted shifted-lognormal-on-CTC at each as-of point vs realized final, on "
                        "the owner>=95% near-complete cohort at 40/60/80% progress."),
        ("cohort_size", cohort_size),
        ("n_pit_points", n),
        ("min_points_for_conclusive_check", MIN_POINTS),
        ("nominal_coverage_p10_p90", p2(NOMINAL_80)),
        ("coverage_p10_p90", p4(cov80)),
        ("nominal_coverage_p05_p95", p2(NOMINAL_90)),
        ("coverage_p05_p95", p4(cov90)),
        ("pit_mean_target_0_5", p4(pit_mean)),
        ("pit_deciles", deciles),
        ("pit_ks_statistic", p4(ks_stat) if ks_stat is not None else None),
        ("pit_ks_pvalue", p4(ks_p) if ks_p is not None else None),
        ("calibration_verdict", verdict),
        ("cohort_warning", warning),
        ("pit_points", [_public_point(pt) for pt in points]),
    ])
    return block


def _public_point(pt):
    return OrderedDict((k, v) for k, v in pt.items() if not k.startswith("_"))


# --------------------------------------------------------------------------- secondary: dispersion

def _implied_sigma_from_mape(backtest: dict):
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
    return (float(np.mean(sigmas)) if sigmas else 0.0), per_method


def _dispersion_adequacy(inputs) -> OrderedDict:
    backtest = inputs["backtest"]
    arrays = inputs["arrays"]
    cohort_size = int(backtest.get("cohort_size") or 0)
    implied_sigma, per_method = _implied_sigma_from_mape(backtest)
    sigma = arrays["sigma"]
    near = arrays["near_complete"]
    active = sigma[~near]
    slice_median_sigma = float(np.median(active)) if active.size else 0.0
    ratio = (slice_median_sigma / implied_sigma) if implied_sigma > 0 else None
    return OrderedDict([
        ("method", "dispersion_adequacy_vs_historical_mape"),
        ("cohort_size", cohort_size),
        ("min_cohort_for_conclusive_check", MIN_COHORT),
        ("historical_implied_sigma_mean", p4(implied_sigma)),
        ("slice_median_active_sigma", p4(slice_median_sigma)),
        ("slice_to_historical_sigma_ratio", p4(ratio) if ratio is not None else None),
        ("per_method_implied_sigma", per_method),
        ("interpretation", "The historical MAPE cohort is NEAR-COMPLETE (owner >= 95% complete), which "
                           "carries little remaining-work risk, so it implies a tighter spread than "
                           "codes with substantial cost-to-complete. A slice/historical ratio above 1 "
                           "is therefore expected: most of the slice's per-code spread is anchored to "
                           "the deterministic worst-credible band (forward exposure) plus backtest "
                           "error, not to near-complete error alone."),
    ])


# --------------------------------------------------------------------------- entry point

def run_probabilistic_backtest(inputs) -> OrderedDict:
    primary = _pit_block(inputs)
    secondary = _dispersion_adequacy(inputs)
    return OrderedDict([
        ("primary", "pit_coverage_calibration"),
        ("pit_coverage", primary),
        ("dispersion_adequacy_secondary", secondary),
        ("cohort_size", primary["cohort_size"]),
        ("n_pit_points", primary["n_pit_points"]),
        ("calibration_verdict", primary["calibration_verdict"]),
        ("coverage_p10_p90", primary.get("coverage_p10_p90")),
        ("coverage_p05_p95", primary.get("coverage_p05_p95")),
        ("pit_mean", primary.get("pit_mean_target_0_5")),
        ("coverage_pit_available", primary["n_pit_points"] > 0),
        ("limitations", "PIT/coverage is computed on the small owner>=95% near-complete cohort at "
                        "40/60/80% progress; the predictive sigma at each as-of point omits the "
                        "worst-credible band and confidence inflation (not reconstructable at as-of), "
                        "so it is a lower bound on the slice's deployed spread. Treat verdicts on a "
                        "small cohort as indicative."),
    ])
