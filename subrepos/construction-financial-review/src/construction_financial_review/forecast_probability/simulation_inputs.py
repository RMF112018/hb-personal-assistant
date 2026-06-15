"""Load the accepted anchor + monthly packages (read-only) and assemble per-code simulation specs.

No randomness here — this is the deterministic calibration layer. It reads the accepted
forecast_intelligence final-cost package (the anchor) and the accepted forecast_monthly package
(for the deterministic monthly phasing), and turns each canonical budget code into a calibrated
lognormal-CTC spec plus stacked numpy arrays for the vectorized engine.
"""
from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

import numpy as np

from ..common.budget_keys import parse_budget_key
from ..common.io import read_json, read_jsonl
from ..common.money import D
from ..forecast_accuracy import signals
from ..schedule_analysis import schedule_io
from . import distributions as dist

ACCEPTED_GLOB = "forecast_accuracy_next_package_tropical_*"
MONTHLY_GLOB = "forecast_monthly_package_tropical_*"


def _latest_dir(data_root: Path, pattern: str):
    matches = sorted(p for p in data_root.glob(pattern) if p.is_dir())
    return matches[-1] if matches else None


def _by_key(path: Path) -> dict:
    return {r["budget_code_key"]: r for r in read_jsonl(path)}


def _method_mape_map(backtest: dict) -> dict:
    out = {}
    for row in backtest.get("summary_by_method") or []:
        m = row.get("method")
        mv = row.get("mape")
        if m is not None and mv is not None:
            try:
                out[m] = float(D(mv))
            except Exception:
                pass
    return out


def _weighted_mape(rec: dict, method_mape: dict, default: float) -> float:
    """Effective-weight-weighted MAPE across the code's contributing methods."""
    num = den = 0.0
    for c in rec.get("contributions") or []:
        m = c.get("method")
        if m in method_mape:
            w = float(D(c.get("effective_weight"))) if c.get("effective_weight") is not None else 0.0
            w = max(w, 0.0)
            num += w * method_mape[m]
            den += w
    if den > 0:
        return num / den
    return default


def load_inputs(cfg: dict, data_root: Path, project_key: str,
                forecast_start_month: str | None = None) -> OrderedDict:
    """Discover + load the anchor and monthly packages and build the per-code specs and arrays."""
    anchor = _latest_dir(data_root, ACCEPTED_GLOB)
    monthly = _latest_dir(data_root, MONTHLY_GLOB)
    if not anchor:
        raise SystemExit(f"ERROR: accepted forecast_intelligence package not found under {data_root}")
    if not monthly:
        raise SystemExit(f"ERROR: accepted forecast_monthly package not found under {data_root}")

    rec_by = _by_key(anchor / "forecast_recommendations_by_budget_code.jsonl")
    conf_by = _by_key(anchor / "forecast_confidence_by_budget_code.jsonl")
    trend_by = _by_key(anchor / "trend_evidence_by_budget_code.jsonl")
    backtest = read_json(anchor / "model_backtest_results.json")
    method_mape = _method_mape_map(backtest)
    default_mape = (sum(method_mape.values()) / len(method_mape)) if method_mape else 0.5

    remdist_by = _by_key(monthly / "remaining_work_monthly_distribution_by_budget_code.jsonl")
    mconf_by = _by_key(monthly / "monthly_forecast_confidence_by_budget_code.jsonl")
    cashflow = read_json(monthly / "project_monthly_cashflow_summary.json")

    # Context package (read-only): owner pay-app history + per-code actuals, needed to reconstruct the
    # near-complete backtest cohort for the PIT/coverage calibration check. Degrades gracefully.
    context_pkg = schedule_io.discover_packages(data_root, cfg).get("context_package")
    context_rows, owner_history = [], {}
    if context_pkg:
        ctx_summary = context_pkg / "summaries" / "budget_code_forecast_context.jsonl"
        if ctx_summary.exists():
            context_rows = list(read_jsonl(ctx_summary))
        owner_history = signals.load_owner_history(context_pkg)

    months = list(cashflow.get("forecast_months") or [])
    if forecast_start_month:
        months = [m for m in months if m >= forecast_start_month]
    if not months:
        raise SystemExit("ERROR: no forecast months resolved (check the monthly package / start month)")

    params = dist.params_from_cfg(cfg)
    keys = sorted(rec_by)

    specs = []
    for key in keys:
        rec = rec_by[key]
        mape = _weighted_mape(rec, method_mape, default_mape)
        cal = dist.calibrate_code(rec, conf_by.get(key, {}), trend_by.get(key, {}), mape, params)
        parsed = parse_budget_key(key)
        cal["budget_code_key"] = key
        cal["cost_code"] = parsed[1] if parsed else None
        cal["category"] = parsed[2] if parsed else None
        cal["division"] = parsed[1].split("-")[0] if parsed else None
        cal["budget_code_description"] = rec.get("budget_code_description")
        cal["base_month_weights"] = _base_weights(remdist_by.get(key, {}), months)
        cal["monthly_distribution_score"] = _score(mconf_by.get(key, {}))
        specs.append(cal)

    arrays = _stack(specs, months, params)
    project = OrderedDict([
        ("total_actual_to_date", float(D(cashflow.get("total_actual_to_date")))),
        ("total_current_projected_cost", float(D(cashflow.get("total_current_projected_cost")))),
        ("total_recommended_final_cost", float(D(cashflow.get("total_recommended_final_cost")))),
        ("total_worst_credible_final_cost", float(D(cashflow.get("total_worst_credible_final_cost")))),
    ])
    return OrderedDict([
        ("anchor_pkg", anchor), ("monthly_pkg", monthly), ("context_pkg", context_pkg),
        ("project_key", project_key), ("months", months), ("params", params),
        ("specs", specs), ("arrays", arrays), ("project", project),
        ("backtest", backtest), ("cashflow", cashflow),
        ("context_rows", context_rows), ("owner_history", owner_history),
    ])


def _base_weights(remdist: dict, months: list) -> list:
    """Deterministic monthly weights from the monthly package, aligned to `months` and renormalized."""
    raw = {w.get("month"): float(D(w.get("weight"))) for w in (remdist.get("monthly_distribution_weights") or [])}
    vec = [max(0.0, raw.get(m, 0.0)) for m in months]
    s = sum(vec)
    if s <= 0:
        return [1.0 / len(months)] * len(months)   # uniform fallback
    return [v / s for v in vec]


def _score(mconf: dict) -> float:
    v = mconf.get("monthly_distribution_score")
    try:
        return max(0.0, min(1.0, float(D(v)))) if v is not None else 0.5
    except Exception:
        return 0.5


def _stack(specs: list, months: list, params: dict) -> OrderedDict:
    n = len(specs)
    nm = len(months)
    return OrderedDict([
        ("n_codes", n), ("n_months", nm), ("months", list(months)),
        ("keys", [s["budget_code_key"] for s in specs]),
        ("actual", np.array([s["actual"] for s in specs], dtype=np.float64)),
        ("mu", np.array([s["mu"] for s in specs], dtype=np.float64)),
        ("sigma", np.array([s["sigma"] for s in specs], dtype=np.float64)),
        ("near_complete", np.array([s["near_complete"] for s in specs], dtype=bool)),
        ("recommended_final", np.array([s["recommended_final_cost"] for s in specs], dtype=np.float64)),
        ("worst_credible_final", np.array([s["worst_credible_final_cost"] for s in specs], dtype=np.float64)),
        ("current_projected", np.array([s["current_projected_cost"] for s in specs], dtype=np.float64)),
        ("revised_budget", np.array([s["revised_budget"] for s in specs], dtype=np.float64)),
        ("committed", np.array([s["committed_cost"] for s in specs], dtype=np.float64)),
        ("base_weights", np.array([s["base_month_weights"] for s in specs], dtype=np.float64).reshape(n, nm)),
        ("monthly_score", np.array([s["monthly_distribution_score"] for s in specs], dtype=np.float64)),
        ("rho", float(params["systemic_correlation_rho"])),
        ("kappa0", float(params["monthly_dirichlet_kappa0"])),
    ])
