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
from ..mapping import crosswalk as xwalk
from ..schedule_analysis import schedule_io
from . import distributions as dist

ACCEPTED_GLOB = "forecast_accuracy_next_package_tropical_*"
MONTHLY_GLOB = "forecast_monthly_package_tropical_*"


def _latest_dir(data_root: Path, pattern: str):
    matches = sorted(p for p in data_root.glob(pattern) if p.is_dir())
    return matches[-1] if matches else None


def _by_key(path: Path) -> dict:
    return {r["budget_code_key"]: r for r in read_jsonl(path)}


# Accepted operator value caps consumed from the accepted forecast_monthly package (the single source of
# truth: monthly already loaded -> map -> resolved the controls via forecast_model_controls and floored
# them at actuals). Probability re-uses that resolution rather than re-resolving (no schedule re-plumbing,
# no fail-closed window risk). Only NOT_TO_EXCEED reference caps are consumed here; explicit/manual
# value-asserted controls (e.g. 1000.15-16-110.SUB manual_monthly) stay OUTSIDE this path, untouched.
NOT_TO_EXCEED = "not_to_exceed_reference"
PROJECTED_COST_REFERENCE_SOURCE = "projected_cost"
PROJECTED_COST_REFERENCE_FIELD = "projected_costs"


def load_operator_value_constraints(monthly_pkg: Path, rec_by: dict) -> dict:
    """Read the accepted monthly package's resolved model controls and return the binding not_to_exceed
    reference caps as ``{budget_code_key: constraint}``.

    A constraint dict carries the deterministic controlled final/remaining (consumed as the probability
    anchor), the disclosed reference (projected_cost/projected_costs + value), the uncapped model final
    (counterfactual), and ``operator_constrained`` (True only when the cap binds AND respects the actuals
    floor). A reference value below actual cost to date is a floor event: actuals win, the cap is NOT
    applied, and the row is disclosed (never silently capped below actuals).
    """
    path = Path(monthly_pkg) / "audit" / "forecast_model_controls_applied.json"
    if not path.exists():
        return {}
    audit = read_json(path)
    out: dict = {}
    for a in audit.get("applied_model_controls") or []:
        if a.get("value_constraint_policy") != NOT_TO_EXCEED:
            continue                                     # explicit/manual value controls stay untouched
        key = a.get("budget_code_key")
        rec = rec_by.get(key) or {}
        cf = float(D(a.get("controlled_final_cost")))
        rem = float(D(a.get("controlled_remaining")))
        actual = float(D(rec.get("actual_cost_all_source_to_date")))
        reference_value = float(D(rec.get("current_projected_cost")))     # = budget_amounts.projected_costs
        binding = bool(a.get("changes_deterministic_final"))
        floor_event = cf < actual - 0.005               # cap below actuals => actuals win (defensive)
        if not (binding or floor_event):
            continue                                     # non-binding cap: no change vs uncapped anchor
        out[key] = {
            "budget_code_key": key,
            "control_id": a.get("control_id"),
            "model_type": a.get("model_type"),
            "value_constraint_policy": NOT_TO_EXCEED,
            "reference_source": PROJECTED_COST_REFERENCE_SOURCE,
            "reference_field": PROJECTED_COST_REFERENCE_FIELD,
            "reference_value": reference_value,
            "actual_cost_to_date": actual,
            "controlled_final": cf,
            "controlled_remaining": max(0.0, rem),
            "uncapped_model_final": float(D(rec.get("recommended_final_cost"))),
            "cap_binding": bool(binding and not floor_event),
            "floor_event": bool(floor_event),
            "operator_constrained": bool(binding and not floor_event),
        }
    return out


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

    full_months = list(cashflow.get("forecast_months") or [])
    monthly_start = full_months[0] if full_months else None
    months = full_months
    if forecast_start_month:
        months = [m for m in full_months if m >= forecast_start_month]
    if not months:
        raise SystemExit("ERROR: no forecast months resolved (check the monthly package / start month)")

    # When --forecast-start-month is LATER than the monthly package window start, the prior-month
    # deterministic CTC must be carried forward (not reallocated into the shortened window). Sum the
    # per-code recommended/worst month costs for months strictly before the start; calibrate_code
    # subtracts these so the lognormal models only the remaining window CTC.
    window_override_active = bool(forecast_start_month and monthly_start
                                  and forecast_start_month > monthly_start)
    prior_ctc_by = _prior_window_ctc(monthly, forecast_start_month) if window_override_active else {}

    params = dist.params_from_cfg(cfg)
    keys = sorted(rec_by)
    # Authoritative owner SOV scope crosswalk assignment (budget code -> owner scope), used for the
    # owner-scope sensitivity rollup. Consumed verbatim; degrades to {} (-> explicit unavailable row).
    owner_scope_by_key = _owner_scope_by_key(cfg, keys)

    specs = []
    for key in keys:
        rec = rec_by[key]
        mape = _weighted_mape(rec, method_mape, default_mape)
        cal = dist.calibrate_code(rec, conf_by.get(key, {}), trend_by.get(key, {}), mape, params,
                                  ctc_override=prior_ctc_by.get(key))
        parsed = parse_budget_key(key)
        cal["budget_code_key"] = key
        cal["cost_code"] = parsed[1] if parsed else None
        cal["category"] = parsed[2] if parsed else None
        cal["division"] = parsed[1].split("-")[0] if parsed else None
        cal["budget_code_description"] = rec.get("budget_code_description")
        osc = owner_scope_by_key.get(key)
        cal["owner_sov_code"] = osc["owner_sov_code"] if osc else None
        cal["owner_scope_description"] = osc["owner_scope_description"] if osc else None
        cal["base_month_weights"] = _base_weights(remdist_by.get(key, {}), months)
        cal["monthly_distribution_score"] = _score(mconf_by.get(key, {}))
        specs.append(cal)

    arrays = _stack(specs, months, params)
    operator_value_constraints = load_operator_value_constraints(monthly, rec_by)
    project = OrderedDict([
        ("total_actual_to_date", float(D(cashflow.get("total_actual_to_date")))),
        ("total_current_projected_cost", float(D(cashflow.get("total_current_projected_cost")))),
        ("total_recommended_final_cost", float(D(cashflow.get("total_recommended_final_cost")))),
        ("total_worst_credible_final_cost", float(D(cashflow.get("total_worst_credible_final_cost")))),
        # Project revised budget total = sum of per-code revised budgets (the anchor carries
        # revised_budget per code; the cashflow manifest has no project-level total).
        ("total_revised_budget", float(arrays["revised_budget"].sum())),
        # Deterministic prior-month forecast carried forward when a later start month is used
        # (0 on the default path). Used only for window reconciliation reporting — NOT an actual.
        ("total_carried_prior_forecast", float(arrays["carried_prior_forecast"].sum())),
        ("window_override_active", window_override_active),
    ])
    return OrderedDict([
        ("anchor_pkg", anchor), ("monthly_pkg", monthly), ("context_pkg", context_pkg),
        ("project_key", project_key), ("months", months), ("params", params),
        ("forecast_start_month", forecast_start_month), ("monthly_start_month", monthly_start),
        ("window_override_active", window_override_active),
        ("specs", specs), ("arrays", arrays), ("project", project),
        ("backtest", backtest), ("cashflow", cashflow),
        ("context_rows", context_rows), ("owner_history", owner_history),
        ("operator_value_constraints", operator_value_constraints),
    ])


def _owner_scope_by_key(cfg: dict, canonical_keys: list) -> dict:
    """Budget code -> {owner_sov_code, owner_scope_description} from the authoritative crosswalk.

    Resolves cfg['owner_sov_scope_crosswalk'] (relative to the subproject root), loads it verbatim
    and builds the explicit budget-code assignment. Returns {} on any miss so the owner-scope
    rollup can emit an explicit unavailable row rather than fail.
    """
    rel = cfg.get("owner_sov_scope_crosswalk")
    if not rel:
        return {}
    root = Path(__file__).resolve().parents[3]
    path = (root / rel) if not Path(rel).is_absolute() else Path(rel)
    if not path.exists():
        return {}
    try:
        rows = xwalk.load_crosswalk(path)
        assign, _dups = xwalk.build_budget_assignment(rows, set(canonical_keys))
        return {k: {"owner_sov_code": r.get("owner_sov_code"),
                    "owner_scope_description": r.get("owner_scope_description")}
                for k, r in assign.items()}
    except Exception:
        return {}


def _prior_window_ctc(monthly_dir: Path, forecast_start_month: str) -> dict:
    """Per-code deterministic CTC for months strictly BEFORE the probability window start.

    Sums recommended/worst-credible month costs from the monthly package so the probability window
    carries them forward as a fixed deterministic addend instead of reallocating them into the
    shortened window. Returns {budget_code_key: {prior_recommended_ctc, prior_worst_credible_ctc}}.
    """
    out: dict = {}
    path = monthly_dir / "monthly_forecast_by_budget_code.jsonl"
    if not path.exists():
        return out
    for r in read_jsonl(path):
        fm = r.get("forecast_month")
        if not fm or fm >= forecast_start_month:
            continue
        agg = out.setdefault(r["budget_code_key"],
                             {"prior_recommended_ctc": 0.0, "prior_worst_credible_ctc": 0.0})
        agg["prior_recommended_ctc"] += float(D(r.get("recommended_month_cost") or 0))
        agg["prior_worst_credible_ctc"] += float(D(r.get("worst_credible_month_cost") or 0))
    return out


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
        ("carried_prior_forecast",
         np.array([s.get("carried_prior_forecast", 0.0) for s in specs], dtype=np.float64)),
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
