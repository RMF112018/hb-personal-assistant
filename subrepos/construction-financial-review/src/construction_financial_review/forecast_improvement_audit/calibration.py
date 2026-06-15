"""Priority 3 — calibration / backtesting enhancement diagnostics.

Re-exposes the accepted forecast-accuracy backtest (per method + per cohort) with explicit sample-size
and denominator guards, bias direction, and insufficient-sample warnings. It does NOT fabricate metrics
the upstream package never computed (the accuracy package emits MAPE + mean_bias only; WAPE/MAE are
reported as data gaps, not invented). Coverage is surfaced from the probability backtest when present.
Partially supported, diagnostic-only.
"""
from __future__ import annotations

from collections import OrderedDict

from ..common.money import dec


def _cfg(cfg):
    return (cfg or {}).get("forecast_improvement_audit") or {}


def _bias_direction(mean_bias):
    b = dec(mean_bias)
    if b is None:
        return "unknown"
    if b > dec("0.02"):
        return "over_forecast"
    if b < dec("-0.02"):
        return "under_forecast"
    return "neutral"


def build(inputs: dict, cfg: dict):
    """Return (rows, gaps)."""
    fia = _cfg(cfg)
    min_sample = int(fia.get("calibration_min_sample", 8))
    project_key = inputs["project_key"]
    bt = inputs.get("backtest")
    rows, gaps = [], []

    if not bt:
        gaps.append(OrderedDict([
            ("project_key", project_key), ("improvement", "priority_3_calibration"),
            ("gap_type", "backtest_unavailable"),
            ("detail", "no accepted forecast-accuracy backtest present; calibration unsupported"),
            ("requires_human_acceptance", True)]))
        return rows, gaps

    cohort_size = int(bt.get("cohort_size") or 0)
    detail_rows = int(bt.get("detail_row_count") or 0)

    for m in bt.get("summary_by_method") or []:
        n = int(m.get("n") or 0)
        mape = m.get("mape")
        rows.append(OrderedDict([
            ("project_key", project_key), ("metric_type", "method_calibration"),
            ("method", m.get("method")), ("n", n),
            ("mape", mape), ("mape_denominator_valid", dec(mape) is not None),
            ("mean_bias", m.get("mean_bias")), ("bias_direction", _bias_direction(m.get("mean_bias"))),
            ("sample_sufficient", n >= min_sample),
            ("insufficient_sample", n < min_sample),
            ("metric_basis", "accepted forecast-accuracy model_backtest_results.summary_by_method"),
            ("requires_human_acceptance", True)]))

    for ba in bt.get("before_after_by_method") or []:
        delta = dec(ba.get("mape_delta"))
        rows.append(OrderedDict([
            ("project_key", project_key), ("metric_type", "method_before_after"),
            ("method", ba.get("method")), ("prior_method", ba.get("prior_method")),
            ("prior_mape", ba.get("prior_mape")), ("new_mape", ba.get("new_mape")),
            ("mape_delta", ba.get("mape_delta")),
            ("improved", bool(delta is not None and delta < 0)),
            ("metric_basis", "accepted forecast-accuracy before_after_by_method"),
            ("requires_human_acceptance", True)]))

    for label, items in (("cohort_family", bt.get("cohort_breakdown_by_family") or []),
                         ("cohort_division", bt.get("cohort_breakdown_by_division") or [])):
        for c in items:
            n = int(c.get("n") or 0)
            rows.append(OrderedDict([
                ("project_key", project_key), ("metric_type", label),
                ("cohort", c.get("cost_code_family") or c.get("division") or c.get("cohort")),
                ("n", n), ("mape", c.get("mape")), ("mape_denominator_valid", dec(c.get("mape")) is not None),
                ("sample_sufficient", n >= min_sample), ("insufficient_sample", n < min_sample),
                ("metric_basis", f"accepted forecast-accuracy {label}"),
                ("requires_human_acceptance", True)]))

    # probability coverage (P-range) where the probability backtest exposes it
    pbt = inputs.get("prob_backtest")
    if isinstance(pbt, dict):
        cov = pbt.get("coverage") or pbt.get("pit_coverage") or pbt.get("interval_coverage")
        if cov is not None:
            rows.append(OrderedDict([
                ("project_key", project_key), ("metric_type", "probability_coverage"),
                ("coverage", cov), ("metric_basis", "probability package probabilistic_backtest_results"),
                ("requires_human_acceptance", True)]))
        else:
            gaps.append(OrderedDict([
                ("project_key", project_key), ("improvement", "priority_3_calibration"),
                ("gap_type", "coverage_unavailable"),
                ("detail", "probability backtest present but exposes no coverage/PIT field"),
                ("requires_human_acceptance", True)]))
    else:
        gaps.append(OrderedDict([
            ("project_key", project_key), ("improvement", "priority_3_calibration"),
            ("gap_type", "coverage_unavailable"),
            ("detail", "no probability backtest present; P-range coverage not reported"),
            ("requires_human_acceptance", True)]))

    gaps.append(OrderedDict([
        ("project_key", project_key), ("improvement", "priority_3_calibration"),
        ("gap_type", "metrics_limited_to_mape_and_bias"),
        ("detail", "accepted backtest exposes MAPE + mean_bias only; WAPE/MAE require per-row "
                   "forecast/actual pairs that are not published in the package and are NOT invented"),
        ("requires_human_acceptance", True)]))
    if cohort_size and cohort_size < min_sample:
        gaps.append(OrderedDict([
            ("project_key", project_key), ("improvement", "priority_3_calibration"),
            ("gap_type", "small_backtest_cohort"),
            ("detail", f"backtest cohort_size={cohort_size} (detail_rows={detail_rows}) below "
                       f"min_sample={min_sample}; metrics flagged insufficient_sample, not overstated"),
            ("requires_human_acceptance", True)]))
    rows.sort(key=lambda r: (r["metric_type"], str(r.get("method") or r.get("cohort") or "")))
    return rows, gaps
