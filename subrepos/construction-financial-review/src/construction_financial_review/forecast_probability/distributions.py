"""Per-code distribution calibration for the probabilistic validation layer.

Each budget code's final cost is modelled as a SHIFTED LOGNORMAL on cost-to-complete (CTC):

    final = actual + CTC,   CTC = exp(mu + sigma * Z),  Z ~ N(0,1)

This makes the actuals floor exact and automatic (CTC >= 0 => final >= actual) with NO upper cap.
Calibration anchors the deterministic numbers:

- median(CTC) = recommended_cost_to_complete  => mu = ln(median_ctc)  => deterministic recommended
  sits at the per-code P50 by construction (the lognormal median is exp(mu), independent of sigma).
- P_eff(CTC) ~ worst_credible_cost_to_complete => sigma_worst = ln(worst/median) / z(eff_quantile),
  so worst-credible lands near its high quantile by construction.

The spread is widened by the evidence the deterministic package already produced (burn volatility,
backtest error, model divergence, low confidence). overrun_existence_confidence is folded in by
lowering the quantile that worst-credible is mapped to (fatter tail) WITHOUT moving the median, so the
P50 anchor is preserved exactly.
"""
from __future__ import annotations

import math
from collections import OrderedDict

from scipy.stats import norm

from ..common.money import D

# Defaults (overridable from config["forecast_probability"]).
DEFAULTS = OrderedDict([
    ("high_quantile", 0.90),
    ("overrun_tail_quantile_shift", 0.10),
    ("sigma_floor", 0.02),
    ("sigma_cap", 1.00),
    ("confidence_inflation_k", 0.40),
    ("sigma_weight_cov", 0.25),
    ("sigma_weight_mape", 0.50),
    ("sigma_weight_divergence", 0.20),
    ("systemic_correlation_rho", 0.35),
    ("monthly_dirichlet_kappa0", 40.0),
    ("p50_recommended_tolerance_pct", 0.03),
])

# A code whose recommended CTC is at or below this (dollars) is treated as effectively complete:
# final == actual, zero spread. Honors the floor and avoids log(0).
NEAR_COMPLETE_EPS = 0.01


def params_from_cfg(cfg: dict) -> OrderedDict:
    """Resolve numeric parameters from config['forecast_probability'] over DEFAULTS."""
    raw = (cfg or {}).get("forecast_probability") or {}
    out = OrderedDict()
    for k, default in DEFAULTS.items():
        v = raw.get(k)
        out[k] = float(v) if v is not None else float(default)
    return out


def _f(v, default=0.0) -> float:
    """Decimal-safe float (uses common.money.D so blanks/None -> 0)."""
    try:
        d = D(v)
    except Exception:
        return default
    return float(d)


def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def calibrate_code(rec: dict, conf: dict, trend: dict, mape_value: float, params: dict,
                   ctc_override: dict | None = None) -> OrderedDict:
    """Return the calibrated lognormal-CTC parameters + audit sources for one budget code.

    rec   = forecast_recommendations_by_budget_code row (anchor package)
    conf  = forecast_confidence_by_budget_code row (anchor package; may be {})
    trend = trend_evidence_by_budget_code row (anchor package; may be {})
    mape_value = method-weighted backtest MAPE for this code (>= 0)
    ctc_override = optional {"prior_recommended_ctc", "prior_worst_credible_ctc"} used when a later
        --forecast-start-month shortens the probability window. The prior-month deterministic
        recommended/worst CTC is subtracted so the lognormal models ONLY the remaining window CTC;
        the subtracted recommended amount is carried forward as a fixed deterministic addend
        (NOT treated as actual cost). Default (None) => carried 0, window == full CTC, unchanged.
    """
    actual = _f(rec.get("actual_cost_all_source_to_date"))
    rec_final = _f(rec.get("recommended_final_cost"))
    worst_final = _f(rec.get("worst_credible_final_cost"))
    current_projected = _f(rec.get("current_projected_cost"))
    revised_budget = _f(rec.get("revised_budget"))
    committed = _f(rec.get("committed_cost"))

    # Prefer the explicit CTC fields from the anchor; fall back to final - actual.
    rec_ctc = rec.get("recommended_cost_to_complete")
    worst_ctc_field = rec.get("worst_credible_cost_to_complete")
    median_ctc = max(0.0, _f(rec_ctc) if rec_ctc is not None else (rec_final - actual))
    worst_ctc = max(median_ctc,
                    _f(worst_ctc_field) if worst_ctc_field is not None else (worst_final - actual))

    # Carry-forward for a later --forecast-start-month: subtract prior-month deterministic CTC so the
    # window models only the remaining work; the prior recommended amount is a fixed deterministic
    # addend (accounting actual is unchanged and remains the only hard floor).
    carried_prior_forecast = 0.0
    if ctc_override:
        prior_rec = max(0.0, _f(ctc_override.get("prior_recommended_ctc")))
        prior_worst = max(0.0, _f(ctc_override.get("prior_worst_credible_ctc")))
        carried_prior_forecast = min(prior_rec, median_ctc)     # cannot carry more than the full CTC
        median_ctc = max(0.0, median_ctc - prior_rec)           # window recommended CTC
        worst_ctc = max(median_ctc, worst_ctc - prior_worst)    # window worst-credible CTC

    cov = max(0.0, _f(trend.get("cost_volatility_cov")))
    divergence = max(0.0, _f(rec.get("model_divergence")))
    conf_score = _clamp(_f(rec.get("confidence_score"), 0.5) or 0.5, 0.0, 1.0)
    overrun_conf = _clamp(_f(rec.get("overrun_confidence")), 0.0, 1.0)
    mape = max(0.0, float(mape_value or 0.0))

    near_complete = median_ctc <= NEAR_COMPLETE_EPS

    sigma_floor = params["sigma_floor"]
    sigma_cap = params["sigma_cap"]

    if near_complete:
        return OrderedDict([
            ("actual", actual), ("recommended_final_cost", rec_final),
            ("worst_credible_final_cost", worst_final),
            ("current_projected_cost", current_projected), ("revised_budget", revised_budget),
            ("committed_cost", committed),
            ("median_ctc", median_ctc), ("worst_ctc", worst_ctc),
            ("accounting_actual", actual), ("carried_prior_forecast", carried_prior_forecast),
            ("window_recommended_ctc", median_ctc), ("window_worst_credible_ctc", worst_ctc),
            ("mu", 0.0), ("sigma", 0.0), ("effective_high_quantile", None),
            ("near_complete", True),
            ("sigma_worst", 0.0), ("sigma_cov", 0.0), ("sigma_mape", 0.0),
            ("sigma_divergence", 0.0), ("sigma_evidence", 0.0),
            ("cost_volatility_cov", cov), ("model_divergence", divergence),
            ("confidence_score", conf_score), ("overrun_confidence", overrun_conf),
            ("backtest_mape", mape),
        ])

    mu = math.log(median_ctc)
    eff_q = _clamp(params["high_quantile"] - params["overrun_tail_quantile_shift"] * overrun_conf,
                   0.55, 0.99)
    z = float(norm.ppf(eff_q))
    sigma_worst = (math.log(worst_ctc / median_ctc) / z) if (worst_ctc > median_ctc and z > 0) else 0.0

    sigma_cov = math.sqrt(math.log(1.0 + cov * cov))          # exact lognormal CoV identity
    sigma_mape = math.log(1.0 + mape)                          # error-band proxy
    sigma_div = min(divergence, sigma_cap)                    # already a dispersion ratio
    sigma_evidence = ((params["sigma_weight_cov"] * sigma_cov
                       + params["sigma_weight_mape"] * sigma_mape
                       + params["sigma_weight_divergence"] * sigma_div)
                      * (1.0 + params["confidence_inflation_k"] * (1.0 - conf_score)))

    sigma = _clamp(max(sigma_worst, sigma_evidence), sigma_floor, sigma_cap)

    return OrderedDict([
        ("actual", actual), ("recommended_final_cost", rec_final),
        ("worst_credible_final_cost", worst_final),
        ("current_projected_cost", current_projected), ("revised_budget", revised_budget),
        ("committed_cost", committed),
        ("median_ctc", median_ctc), ("worst_ctc", worst_ctc),
        ("accounting_actual", actual), ("carried_prior_forecast", carried_prior_forecast),
        ("window_recommended_ctc", median_ctc), ("window_worst_credible_ctc", worst_ctc),
        ("mu", mu), ("sigma", sigma), ("effective_high_quantile", eff_q),
        ("near_complete", False),
        ("sigma_worst", sigma_worst), ("sigma_cov", sigma_cov), ("sigma_mape", sigma_mape),
        ("sigma_divergence", sigma_div), ("sigma_evidence", sigma_evidence),
        ("cost_volatility_cov", cov), ("model_divergence", divergence),
        ("confidence_score", conf_score), ("overrun_confidence", overrun_conf),
        ("backtest_mape", mape),
    ])
