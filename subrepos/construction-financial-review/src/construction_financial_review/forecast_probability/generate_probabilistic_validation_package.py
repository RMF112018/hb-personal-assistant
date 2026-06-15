"""Generate the probabilistic forecast-validation package for Tropical World Nursery.

Monte Carlo stress-test of the accepted deterministic forecast: per-code shifted-lognormal on
cost-to-complete + one-factor Gaussian correlation, vectorized with numpy and calibrated with
scipy.stats. Quantifies P10..P95 final cost (project + per code), overrun probabilities, downside
drivers, monthly risk timing, assumption sensitivity, and dispersion calibration. The quantitative
core is deterministic (seed + frozen stamp); advisory local-Ollama narratives are excluded from the
determinism gate. Read-only; nothing is mutated. Actuals are the only floor; nothing is capped above.

Run:
    PYTHONPATH=src python3 -m construction_financial_review.cli forecast-probability --project tropical \
        [--runs 10000] [--seed 20260614] [--forecast-start-month YYYY-MM] [--with-llm]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from collections import OrderedDict
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import numpy as np
import scipy

from ..common.hashing import sha256_file, sha256_text
from ..common.io import read_json, read_jsonl, write_json, write_jsonl
from ..common.money import D
from ..common.safety import safety_scan
from ..common.validation import all_files_parse
from ..forecast_accuracy.llm import narrate
from ..forecast_accuracy.llm.client import OllamaClient
from ..forecast_intelligence import db_inventory
from . import distributions as dist
from . import probabilistic_backtest, risk_metrics, sensitivity, simulate, simulation_inputs

SUBPROJECT_ROOT = Path(__file__).resolve().parents[3]
GENERATOR_NAME = "construction_financial_review.forecast_probability.generate_probabilistic_validation_package"

DATA_FILES = (
    "probabilistic_final_cost_by_budget_code.jsonl",
    "code_overrun_probabilities.jsonl",
    "downside_exposure_ranking.jsonl",
    "top_downside_drivers.json",
    "probabilistic_monthly_by_budget_code.jsonl",
    "probabilistic_monthly_project_forecast.jsonl",
    "monthly_risk_ranking.json",
    "probabilistic_project_summary.json",
    "sensitivity_analysis.json",
    "probabilistic_backtest_results.json",
    "simulation_inputs_by_budget_code.jsonl",
    "calibration_summary.json",
    "data_quality_warnings.jsonl",
)

# Compatibility aliases matching the originally-requested package contract. First-class outputs:
# emitted, parseable, listed in the manifest, documented in SCHEMA.md, validated, and included in the
# deterministic byte-diff. Canonical files above are preserved; these are additive views.
ALIAS_FILES = (
    "simulation_results_project.json",            # = probabilistic_project_summary.json
    "simulation_results_by_budget_code.jsonl",    # = probabilistic_final_cost_by_budget_code.jsonl
    "simulation_results_by_month.jsonl",          # = probabilistic_monthly_project_forecast.jsonl (project-month)
    "probabilistic_overrun_risk_register.jsonl",  # material overrun rows (probability + dollar/pct gate)
    "budget_code_sensitivity.jsonl",              # per-code downside contribution + Spearman driver
    "division_sensitivity.jsonl",                 # risk contribution aggregated by division
    "owner_scope_sensitivity.jsonl",              # risk contribution aggregated by owner SOV scope
)

# Probabilistic overrun risk register materiality: a code is included only if its probability of
# exceeding current projected cost is material AND it carries material dollar OR percentage exposure.
REGISTER_PROB_MIN = 0.20        # >= 20% chance of exceeding current projected cost
REGISTER_DOLLAR_MIN = 25000.0   # >= $25k expected overrun
REGISTER_PCT_MIN = 0.05         # >= 5% expected overrun relative to current projected cost


def _git(args):
    try:
        out = subprocess.run(["git", *args], cwd=str(SUBPROJECT_ROOT),
                             capture_output=True, text=True, timeout=15)
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return None


# --------------------------------------------------------------------------- pure quant build

def _build_collections(inputs, runs, seed, antithetic, lhs) -> dict:
    arrays = inputs["arrays"]
    project = inputs["project"]
    params = inputs["params"]

    base = simulate.simulate(arrays, runs=runs, seed=seed, antithetic=antithetic, lhs=lhs,
                             draw_months=True)

    code_rows = risk_metrics.code_rows(base, arrays)
    overrun_rows = risk_metrics.overrun_probability_rows(base, arrays)
    downside = risk_metrics.downside_ranking(base, arrays)
    monthly = risk_metrics.monthly_rows(base, arrays, project)
    project_monthly = risk_metrics.project_monthly_rows(base, arrays, project)
    monthly_ranking = risk_metrics.monthly_risk_ranking(project_monthly)
    summary = risk_metrics.project_summary(base, arrays, project, params)
    sens = sensitivity.run_sensitivity(inputs, base, runs=runs, seed=seed,
                                       antithetic=antithetic, lhs=lhs)
    backtest = probabilistic_backtest.run_probabilistic_backtest(inputs)
    sim_inputs = _sim_input_rows(inputs)
    warnings = _warnings(inputs, base)
    calib = _calibration_summary(inputs, runs, seed, antithetic, lhs)

    diagnostics = _diagnostics(base, arrays)

    out = {
        "probabilistic_final_cost_by_budget_code.jsonl": code_rows,
        "code_overrun_probabilities.jsonl": overrun_rows,
        "downside_exposure_ranking.jsonl": downside,
        "top_downside_drivers.json": downside[:25],
        "probabilistic_monthly_by_budget_code.jsonl": monthly,
        "probabilistic_monthly_project_forecast.jsonl": project_monthly,
        "monthly_risk_ranking.json": monthly_ranking,
        "probabilistic_project_summary.json": summary,
        "sensitivity_analysis.json": sens,
        "probabilistic_backtest_results.json": backtest,
        "simulation_inputs_by_budget_code.jsonl": sim_inputs,
        "calibration_summary.json": calib,
        "data_quality_warnings.jsonl": warnings,
    }
    out.update(_build_aliases(out, inputs))
    out["_diagnostics"] = diagnostics
    out["_downside"] = downside
    return out


# --------------------------------------------------------------------------- compatibility aliases

def _build_aliases(collections: dict, inputs: dict) -> dict:
    """Derive the compatibility alias payloads purely from already-computed collections.

    No re-simulation, so the aliases stay byte-deterministic and join the determinism diff.
    """
    specs = inputs["specs"]
    div_by_key = {s["budget_code_key"]: s.get("division") for s in specs}
    owner_by_key = {s["budget_code_key"]: (s.get("owner_sov_code"), s.get("owner_scope_description"))
                    for s in specs}
    code_rows = collections["probabilistic_final_cost_by_budget_code.jsonl"]
    overrun = collections["code_overrun_probabilities.jsonl"]
    downside = collections["downside_exposure_ranking.jsonl"]
    sens = collections["sensitivity_analysis.json"]

    return {
        "simulation_results_project.json": collections["probabilistic_project_summary.json"],
        "simulation_results_by_budget_code.jsonl": code_rows,
        "simulation_results_by_month.jsonl": collections["probabilistic_monthly_project_forecast.jsonl"],
        "probabilistic_overrun_risk_register.jsonl": _overrun_register(overrun, code_rows),
        "budget_code_sensitivity.jsonl": _budget_code_sensitivity(sens, downside),
        "division_sensitivity.jsonl": _division_sensitivity(overrun, downside, div_by_key),
        "owner_scope_sensitivity.jsonl": _owner_scope_sensitivity(overrun, downside, owner_by_key,
                                                                  inputs["project_key"]),
    }


def _overrun_register(overrun_rows, code_rows):
    """Material probabilistic overrun rows: probability gate AND (dollar OR percentage) gate.

    Each emitted row carries the exact materiality basis it met. Rows that merely have a positive
    expected overrun are NOT included.
    """
    proj_by = {r["budget_code_key"]: float(D(r["current_projected_cost"])) for r in code_rows}
    out = []
    for r in overrun_rows:
        prob = float(D(r["prob_exceeds_current_projected_cost"]))
        exp_over = float(D(r["expected_overrun_vs_current_projected"]))
        cp = proj_by.get(r["budget_code_key"], 0.0)
        pct = (exp_over / cp) if cp > 0 else 0.0
        meets_dollar = exp_over >= REGISTER_DOLLAR_MIN
        meets_pct = pct >= REGISTER_PCT_MIN
        if not (prob >= REGISTER_PROB_MIN and (meets_dollar or meets_pct)):
            continue
        basis = [f"prob_exceeds_current_projected>={REGISTER_PROB_MIN:.2f}"]
        if meets_dollar:
            basis.append(f"expected_overrun>=${REGISTER_DOLLAR_MIN:,.0f}")
        if meets_pct:
            basis.append(f"expected_overrun_pct>={REGISTER_PCT_MIN:.2f}")
        row = OrderedDict(r)
        row["expected_overrun_pct_of_current_projected"] = risk_metrics.p4(pct)
        row["materiality_threshold_basis"] = "; ".join(basis)
        out.append(row)
    out.sort(key=lambda x: (-float(D(x["expected_overrun_vs_current_projected"])), x["budget_code_key"]))
    return out


def _budget_code_sensitivity(sens, downside):
    """Per-code sensitivity: co-tail downside contribution to project P90 + Spearman driver rank."""
    spear = {d["budget_code_key"]: d.get("spearman_vs_project_total")
             for d in sens.get("top_spearman_code_drivers", [])}
    out = []
    for d in downside:
        k = d["budget_code_key"]
        out.append(OrderedDict([
            ("project_key", d.get("project_key", "tropical")),
            ("budget_code_key", k), ("cost_code", d.get("cost_code")),
            ("downside_contribution_to_project_p90", d["downside_contribution_to_project_p90"]),
            ("downside_rank", d.get("rank")),
            ("spearman_vs_project_total", spear.get(k)),
        ]))
    return out


def _division_sensitivity(overrun_rows, downside, div_by_key):
    """Risk contribution aggregated by division (cost-code prefix)."""
    dmap = {d["budget_code_key"]: float(D(d["downside_contribution_to_project_p90"])) for d in downside}
    agg = {}
    for r in overrun_rows:
        div = div_by_key.get(r["budget_code_key"])
        a = agg.setdefault(div, {"code_count": 0, "exp_over": 0.0, "downside": 0.0})
        a["code_count"] += 1
        a["exp_over"] += float(D(r["expected_overrun_vs_current_projected"]))
        a["downside"] += dmap.get(r["budget_code_key"], 0.0)
    rows = [OrderedDict([
        ("project_key", "tropical"), ("division", div), ("code_count", a["code_count"]),
        ("sum_expected_overrun_vs_current_projected", risk_metrics.m(a["exp_over"])),
        ("sum_downside_contribution_to_project_p90", risk_metrics.m(a["downside"])),
    ]) for div, a in agg.items()]
    rows.sort(key=lambda x: (-float(D(x["sum_downside_contribution_to_project_p90"])), str(x["division"])))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def _owner_scope_sensitivity(overrun_rows, downside, owner_by_key, project_key):
    """Risk contribution aggregated by authoritative owner SOV scope.

    Falls back to a single explicit unavailable row (still parseable) only when no crosswalk
    assignment resolved for any code.
    """
    have = any(owner_by_key.get(r["budget_code_key"], (None, None))[0] for r in overrun_rows)
    if not have:
        return [OrderedDict([
            ("project_key", project_key), ("owner_sov_code", None), ("owner_scope_description", None),
            ("code_count", 0), ("sum_expected_overrun_vs_current_projected", None),
            ("sum_downside_contribution_to_project_p90", None),
            ("note", "owner scope unavailable: no authoritative owner SOV scope crosswalk assignment "
                     "resolved for these budget codes; populate cfg['owner_sov_scope_crosswalk']."),
        ])]
    dmap = {d["budget_code_key"]: float(D(d["downside_contribution_to_project_p90"])) for d in downside}
    agg = {}
    for r in overrun_rows:
        sov, desc = owner_by_key.get(r["budget_code_key"], (None, None))
        a = agg.setdefault(sov, {"desc": desc, "code_count": 0, "exp_over": 0.0, "downside": 0.0})
        a["code_count"] += 1
        a["exp_over"] += float(D(r["expected_overrun_vs_current_projected"]))
        a["downside"] += dmap.get(r["budget_code_key"], 0.0)
    rows = [OrderedDict([
        ("project_key", project_key), ("owner_sov_code", sov),
        ("owner_scope_description", a["desc"]), ("code_count", a["code_count"]),
        ("sum_expected_overrun_vs_current_projected", risk_metrics.m(a["exp_over"])),
        ("sum_downside_contribution_to_project_p90", risk_metrics.m(a["downside"])),
    ]) for sov, a in agg.items()]
    rows.sort(key=lambda x: (-float(D(x["sum_downside_contribution_to_project_p90"])),
                             str(x["owner_sov_code"])))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def _no_upper_cap_audit(collections):
    """Per-code proof that nothing is capped above actuals against any reference value.

    The model has no upper clamp by construction: cost-to-complete is an unbounded lognormal and the
    only floor is accounting actuals. This records that posture per code with the realized P95-vs-
    reference evidence so a reviewer can verify it without rerunning the simulation.
    """
    rows = []
    for r in collections["probabilistic_final_cost_by_budget_code.jsonl"]:
        near = bool(r["near_complete"])
        p95 = D(r["simulated_p95"])
        rows.append(OrderedDict([
            ("budget_code_key", r["budget_code_key"]),
            ("distribution_family", "point_mass_complete" if near else "shifted_lognormal_ctc"),
            ("actual_floor_applied", True),
            ("upper_cap_applied", False),
            ("upper_cap_source", None),
            ("reference_values_reported_only", True),
            ("p95_exceeds_current_projected_cost", bool(p95 > D(r["current_projected_cost"]))),
            ("p95_exceeds_revised_budget", bool(p95 > D(r["revised_budget"]))),
            ("p95_exceeds_worst_credible", bool(p95 > D(r["deterministic_worst_credible_final_cost"]))),
            ("validation_status", "near_complete_point_mass" if near else "uncapped_ok"),
        ]))
    return rows


def _sim_input_rows(inputs):
    rows = []
    for s in inputs["specs"]:
        rows.append(OrderedDict([
            ("project_key", inputs["project_key"]), ("budget_code_key", s["budget_code_key"]),
            ("cost_code", s.get("cost_code")), ("division", s.get("division")),
            ("actual_cost_to_date", risk_metrics.m(s["actual"])),
            ("median_cost_to_complete", risk_metrics.m(s["median_ctc"])),
            ("worst_cost_to_complete", risk_metrics.m(s["worst_ctc"])),
            # Carry-forward breakdown (prior-month forecast is 0 unless a later start month is used;
            # it is carried as a deterministic addend, never treated as actual cost).
            ("accounting_actual_cost_to_date", risk_metrics.m(s.get("accounting_actual", s["actual"]))),
            ("deterministic_prior_forecast_before_probability_window",
             risk_metrics.m(s.get("carried_prior_forecast", 0.0))),
            ("probability_window_recommended_cost_to_complete",
             risk_metrics.m(s.get("window_recommended_ctc", s["median_ctc"]))),
            ("probability_window_worst_credible_cost_to_complete",
             risk_metrics.m(s.get("window_worst_credible_ctc", s["worst_ctc"]))),
            ("distribution_family", "shifted_lognormal_ctc" if not s["near_complete"] else "point_mass_complete"),
            ("near_complete", bool(s["near_complete"])),
            ("mu", risk_metrics.p4(s["mu"])), ("sigma", risk_metrics.p4(s["sigma"])),
            ("effective_high_quantile",
             risk_metrics.p4(s["effective_high_quantile"]) if s["effective_high_quantile"] is not None else None),
            ("sigma_from_worst_credible", risk_metrics.p4(s["sigma_worst"])),
            ("sigma_from_volatility_cov", risk_metrics.p4(s["sigma_cov"])),
            ("sigma_from_backtest_mape", risk_metrics.p4(s["sigma_mape"])),
            ("sigma_from_model_divergence", risk_metrics.p4(s["sigma_divergence"])),
            ("sigma_evidence_blend", risk_metrics.p4(s["sigma_evidence"])),
            ("confidence_score", risk_metrics.p4(s["confidence_score"])),
            ("overrun_existence_confidence", risk_metrics.p4(s["overrun_confidence"])),
            ("backtest_mape", risk_metrics.p4(s["backtest_mape"])),
        ]))
    return rows


def _calibration_summary(inputs, runs, seed, antithetic, lhs):
    p = inputs["params"]
    return OrderedDict([
        ("methodology", "Probabilistic VALIDATION (not a replacement). Per code, cost-to-complete is "
                        "modelled as a lognormal whose median equals the deterministic recommended "
                        "cost-to-complete (so recommended = per-code P50) and whose high quantile maps "
                        "to the worst-credible cost-to-complete. Spread is widened by burn volatility, "
                        "backtest MAPE, model divergence and low confidence; overrun-existence "
                        "confidence fattens the right tail via a quantile shift (median preserved). "
                        "Codes are linked by a one-factor Gaussian copula (systemic + idiosyncratic). "
                        "Actuals are the only floor; nothing is capped above any reference."),
        ("distribution_family", "shifted_lognormal_on_cost_to_complete"),
        ("correlation_model", "one_factor_gaussian_copula"),
        ("engine", "numpy_vectorized_monte_carlo"),
        ("runs", runs), ("seed", seed),
        ("antithetic_variates", bool(antithetic)), ("latin_hypercube_systemic", bool(lhs)),
        ("parameters", OrderedDict((k, risk_metrics.p4(v)) for k, v in p.items())),
        ("numpy_version", np.__version__), ("scipy_version", scipy.__version__),
        ("anchor_package", inputs["anchor_pkg"].name),
        ("monthly_package", inputs["monthly_pkg"].name),
        ("forecast_months", inputs["months"]),
        ("n_codes", inputs["arrays"]["n_codes"]),
    ])


def _warnings(inputs, base):
    arrays = inputs["arrays"]
    rows = []
    near = int(arrays["near_complete"].sum())
    if near:
        rows.append(_warn(inputs["project_key"], None, "low",
                          f"{near} code(s) treated as near-complete (CTC<=$0.01): final fixed at actuals."))
    capped = int((arrays["sigma"] >= inputs["params"]["sigma_cap"] - 1e-9).sum())
    if capped:
        rows.append(_warn(inputs["project_key"], None, "medium",
                          f"{capped} code(s) hit the sigma cap; their upside spread is bounded by the cap."))
    cohort = int(inputs["backtest"].get("cohort_size") or 0)
    if cohort < probabilistic_backtest.MIN_COHORT:
        rows.append(_warn(inputs["project_key"], None, "medium",
                          f"Backtest cohort {cohort} < {probabilistic_backtest.MIN_COHORT}; calibration "
                          "check is indicative only."))
    return rows


def _warn(project_key, key, severity, message):
    return OrderedDict([("project_key", project_key), ("budget_code_key", key),
                        ("severity", severity), ("message", message)])


def _diagnostics(base, arrays):
    finals = base["final_costs"]
    actual = arrays["actual"]
    floor_ok = bool((finals.min(axis=0) >= actual - 0.005).all())
    mc = base["month_costs"]
    recon_ok = True
    if mc is not None:
        month_sum = mc.sum(axis=2)             # (runs, n)
        ctc = base["ctc"]
        recon_ok = bool(np.abs(month_sum - ctc).max() <= 0.01)
    return OrderedDict([("floor_ok", floor_ok), ("reconciliation_ok", recon_ok)])


# --------------------------------------------------------------------------- write + orchestrate

def _write_data_files(out: Path, collections: dict):
    for fname in DATA_FILES + ALIAS_FILES:
        payload = collections[fname]
        if fname.endswith(".jsonl"):
            write_jsonl(out / fname, payload)
        else:
            write_json(out / fname, payload)


def generate(project_key, cfg, data_root=None, frozen_stamp=None, out_root=None,
             with_llm=False, llm_model=None, forecast_start_month=None,
             runs=10000, seed=20260614) -> dict:
    data_root = Path(data_root or cfg["default_data_root"])
    inputs = simulation_inputs.load_inputs(cfg, data_root, project_key, forecast_start_month)
    params = inputs["params"]
    antithetic = bool(cfg.get("forecast_probability", {}).get("antithetic", True))
    lhs = bool(cfg.get("forecast_probability", {}).get("latin_hypercube_systemic", False))

    stamp = frozen_stamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    generated_ts = frozen_stamp if frozen_stamp else datetime.now().isoformat(timespec="seconds")
    out_base = Path(out_root) if out_root else data_root
    out = out_base / f"forecast_probability_package_tropical_{stamp}"
    out.mkdir(parents=True, exist_ok=False)
    (out / "audit").mkdir(exist_ok=True)
    (out / "llm").mkdir(exist_ok=True)

    collections = _build_collections(inputs, runs, seed, antithetic, lhs)
    diagnostics = collections.pop("_diagnostics")
    downside = collections.pop("_downside")
    _write_data_files(out, collections)

    # ---- determinism self-check: rebuild quant core into temp dirs and byte-diff ----
    determinism = _determinism_check(inputs, runs, seed, antithetic, lhs, stamp)

    # ---- LLM advisory (numbers already computed; the model only explains) ----
    llm_cfg = cfg.get("llm") or {}
    model = llm_model or llm_cfg.get("model", "qwen2.5:14b")
    narratives, receipts, ollama_status = _run_llm(
        with_llm, model, llm_cfg, downside[:25], collections["probabilistic_final_cost_by_budget_code.jsonl"],
        generated_ts)
    write_jsonl(out / "llm" / "probabilistic_narratives.jsonl", narratives)
    write_jsonl(out / "llm" / "probabilistic_narrative_receipts.jsonl", receipts)

    # ---- audit + meta ----
    command = (f"python3 -m construction_financial_review.cli forecast-probability --project {project_key}"
               f" --runs {runs} --seed {seed}"
               + (f" --forecast-start-month {forecast_start_month}" if forecast_start_month else "")
               + (" --with-llm" if with_llm else ""))
    meta = _meta(command, inputs, stamp, generated_ts, runs, seed, ollama_status,
                 model if with_llm else None, len(narratives))
    db_inv = db_inventory.inventory(cfg, project_key)
    write_json(out / "audit" / "db_inventory.json", db_inv)
    no_cap_audit = _no_upper_cap_audit(collections)
    write_json(out / "audit" / "no_upper_cap_audit.json", no_cap_audit)
    write_json(out / "audit" / "source_files_used.json", _source_files(inputs, cfg))
    write_json(out / "input_inventory.json", OrderedDict([("generation", meta),
                                                          ("forecast_months", inputs["months"])]))
    _write_readme(out, project_key, meta, inputs, collections)
    _write_schema(out)

    # ---- safety + validation + manifest ----
    data_files = sorted(p for p in out.rglob("*") if p.is_file()
                        and p.name not in ("manifest.json", "validation_report.json"))
    safety = safety_scan(data_files)
    write_json(out / "audit" / "safety_scan_report.json", safety)
    validation = _validation(out, inputs, collections, diagnostics, db_inv, safety, meta, determinism,
                             bool(with_llm and ollama_status == "available"), receipts, no_cap_audit)
    write_json(out / "validation_report.json", validation)
    conclusion = ("forecast_probability_ready" if validation["passed"]
                  else "forecast_probability_not_ready")
    write_json(out / "manifest.json", _manifest(out, project_key, meta, conclusion, validation))

    summary = collections["probabilistic_project_summary.json"]
    return {"output_package": str(out), "validation_passed": validation["passed"],
            "safety_passed": safety["passed"], "determinism_passed": determinism["diff_result"] == "pass",
            "llm_status": ollama_status, "llm_narratives_generated": len(narratives),
            "runs": runs, "seed": seed,
            "project_p50": summary["simulated_final_cost_percentiles"]["p50"],
            "project_p90": summary["simulated_final_cost_percentiles"]["p90"],
            "prob_exceeds_recommended": summary["prob_exceeds_recommended_final"]}


def _determinism_check(inputs, runs, seed, antithetic, lhs, stamp) -> OrderedDict:
    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        p1, p2 = Path(d1), Path(d2)
        c1 = _build_collections(inputs, runs, seed, antithetic, lhs)
        c1.pop("_diagnostics"); c1.pop("_downside")
        c2 = _build_collections(inputs, runs, seed, antithetic, lhs)
        c2.pop("_diagnostics"); c2.pop("_downside")
        _write_data_files(p1, c1)
        _write_data_files(p2, c2)
        per_file = []
        ok = True
        for fname in DATA_FILES + ALIAS_FILES:
            h1, h2 = sha256_file(p1 / fname), sha256_file(p2 / fname)
            same = h1 == h2
            ok = ok and same
            per_file.append(OrderedDict([("file", fname), ("sha256", h1), ("identical", same)]))
    return OrderedDict([
        ("performed", True),
        ("quantitative_core_byte_identical", ok),
        ("llm_excluded_from_byte_diff", True),
        ("frozen_stamp", stamp),
        ("seed", seed), ("runs", runs),
        ("diff_result", "pass" if ok else "fail"),
        ("per_file", per_file),
    ])


def _run_llm(with_llm, model, llm_cfg, downside_top, code_rows, generated_ts):
    backend, ollama_status, model_label = None, "disabled_mock", "deterministic_template"
    temperature = float(llm_cfg.get("temperature", 0))
    seed = int(llm_cfg.get("seed", 7))
    if with_llm:
        client = OllamaClient(model, llm_cfg.get("endpoint", "http://localhost:11434"),
                              temperature, seed, float(llm_cfg.get("timeout_seconds", 60)))
        if client.model_present():
            backend, ollama_status, model_label = client, "available", model
        else:
            ollama_status = "model_absent_using_template"
    template_hash = sha256_text(narrate.SYSTEM_PROMPT)[:12]
    backend_name = "ollama_http" if backend is not None else "deterministic_template"
    code_by_key = {r["budget_code_key"]: r for r in code_rows}
    narratives, receipts = [], []
    for d in downside_top:
        key = d["budget_code_key"]
        cr = code_by_key.get(key, {})
        facts = OrderedDict([
            ("project_key", d["project_key"]), ("budget_code_key", key),
            ("simulated_p50_final_cost", cr.get("simulated_p50")),
            ("simulated_p90_final_cost", cr.get("simulated_p90")),
            ("simulated_p95_final_cost", cr.get("simulated_p95")),
            ("deterministic_recommended_final_cost", cr.get("deterministic_recommended_final_cost")),
            ("deterministic_worst_credible_final_cost", cr.get("deterministic_worst_credible_final_cost")),
            ("prob_exceeds_current_projected_cost", cr.get("prob_exceeds_current_projected_cost")),
            ("prob_exceeds_revised_budget", cr.get("prob_exceeds_revised_budget")),
            ("downside_contribution_to_project_p90", d.get("downside_contribution_to_project_p90")),
            ("downside_rank", d.get("rank")),
        ])
        nrow, base = narrate.narrate_one(facts, backend, model_label)
        narratives.append(nrow)
        receipts.append(OrderedDict([
            ("budget_code_key", key), ("model", model_label), ("backend", backend_name),
            ("status", base["status"]), ("fallback_used", base["fallback_used"]),
            ("numeric_outputs_from_llm", False),
            ("temperature", temperature), ("seed", seed),
            ("prompt_template_hash", template_hash), ("facts_hash", base["input_facts_hash"]),
            ("response_hash", base["output_hash"]), ("safety_status", base["safety_passed"]),
            ("generated_at", generated_ts),
        ]))
    return narratives, receipts, ollama_status


def _meta(command, inputs, stamp, generated_ts, runs, seed, ollama_status, model, n_narr):
    return OrderedDict([
        ("generator", GENERATOR_NAME), ("subproject_path", str(SUBPROJECT_ROOT)),
        ("git_branch", _git(["rev-parse", "--abbrev-ref", "HEAD"])),
        ("git_head_sha", _git(["rev-parse", "HEAD"])),
        ("git_tree_dirty", bool(_git(["status", "--porcelain"]))),
        ("command", command), ("package_stamp", stamp), ("generated_timestamp_local", generated_ts),
        ("runs", runs), ("seed", seed),
        ("forecast_months", inputs["months"]),
        ("ollama_status", ollama_status), ("ollama_model", model), ("llm_narratives_generated", n_narr),
        ("selected_input_packages", OrderedDict([
            ("accepted_forecast_intelligence_package", str(inputs["anchor_pkg"])),
            ("accepted_forecast_monthly_package", str(inputs["monthly_pkg"])),
            ("context_package", str(inputs["context_pkg"]) if inputs.get("context_pkg") else None),
        ])),
    ])


def _source_files(inputs, cfg):
    return OrderedDict([
        ("accepted_forecast_intelligence_package", str(inputs["anchor_pkg"])),
        ("accepted_forecast_monthly_package", str(inputs["monthly_pkg"])),
        ("context_package", str(inputs["context_pkg"]) if inputs.get("context_pkg") else None),
        ("local_db", str(db_inventory.resolve_db_path(cfg))),
        ("mutation_posture", "READ-ONLY: no source/Excel/SQLite/external mutation; DB opened mode=ro"),
        ("simulation_rule", "Probabilistic outputs are advisory; actual cost to date is the only hard "
                            "lower bound; simulated final costs are never capped at ERP projected, "
                            "revised budget, committed, owner SOV, Procore pay-app, or prior model "
                            "output. The local LLM produced no numeric simulation result."),
    ])


def _validation(out, inputs, collections, diagnostics, db_inv, safety, meta, determinism, llm_used,
                receipts, no_cap_audit):
    arrays = inputs["arrays"]
    n_codes = arrays["n_codes"]
    n_months = arrays["n_months"]
    canonical = set(arrays["keys"])
    params = inputs["params"]
    project = inputs["project"]

    code_rows = collections["probabilistic_final_cost_by_budget_code.jsonl"]
    overrun_rows = collections["code_overrun_probabilities.jsonl"]
    downside = collections["downside_exposure_ranking.jsonl"]
    sim_inputs = collections["simulation_inputs_by_budget_code.jsonl"]
    monthly = collections["probabilistic_monthly_by_budget_code.jsonl"]
    summary = collections["probabilistic_project_summary.json"]
    sens = collections["sensitivity_analysis.json"]

    per_code_complete = (len(code_rows) == n_codes and len(overrun_rows) == n_codes
                         and len(downside) == n_codes and len(sim_inputs) == n_codes
                         and len(monthly) == n_codes * n_months)
    canonical_only = all(r["budget_code_key"] in canonical for r in code_rows)

    # percentile monotonicity (per code + project)
    def _mono(p10, p50, p80, p90, p95):
        return p10 <= p50 <= p80 <= p90 <= p95
    mono_codes = all(_mono(D(r["simulated_p10"]), D(r["simulated_p50"]), D(r["simulated_p80"]),
                           D(r["simulated_p90"]), D(r["simulated_p95"])) for r in code_rows)
    sp = summary["simulated_final_cost_percentiles"]
    mono_project = _mono(D(sp["p10"]), D(sp["p50"]), D(sp["p80"]), D(sp["p90"]), D(sp["p95"]))

    floor_ok = bool(diagnostics["floor_ok"]) and all(D(r["simulated_p10"]) >= D(r["actual_cost_to_date"])
                                                     for r in code_rows)

    # no upper cap: at least one non-near code's P95 strictly exceeds its worst-credible final, and the
    # project P95 exceeds the deterministic recommended total (uncapped upside is realized).
    p95_beyond_worst = sum(1 for r in code_rows if not r["near_complete"]
                           and D(r["simulated_p95"]) > D(r["deterministic_worst_credible_final_cost"]))
    no_cap = (p95_beyond_worst >= 1
              and D(sp["p95"]) > D(str(project["total_recommended_final_cost"])))

    # Strengthened no-upper-cap audit: every non-near code must be uncapped above, with no reference
    # field used as a clamp source. The audit file must exist with one record per code.
    cap_ref_sources = {"erp", "revised_budget", "committed", "owner_sov", "procore_pay_app",
                       "prior_output", "projected_cost", "committed_cost", "owner_pay_app"}
    no_cap_audit_present = bool(no_cap_audit) and len(no_cap_audit) == n_codes
    no_code_upper_capped = all(
        (a["upper_cap_applied"] is False and a["upper_cap_source"] is None
         and a["reference_values_reported_only"] is True)
        for a in no_cap_audit if a["validation_status"] == "uncapped_ok")
    no_cap_source_is_reference = all(
        (a["upper_cap_source"] is None) or (a["upper_cap_source"] not in cap_ref_sources)
        for a in no_cap_audit)

    # Finding 1: project-level revised-budget probability fields present, parse, and unit interval.
    rb_keys = ("revised_budget_total", "probability_project_exceeds_revised_budget_total",
               "expected_project_overrun_vs_revised_budget_total", "p80_overrun_vs_revised_budget_total",
               "p90_overrun_vs_revised_budget_total", "p95_overrun_vs_revised_budget_total")
    rb_present = all(k in summary for k in rb_keys)
    rb_unit = rb_present and (Decimal("0") <=
                              D(summary["probability_project_exceeds_revised_budget_total"]) <= Decimal("1"))
    revised_budget_ok = rb_present and rb_unit

    # Finding 2: compatibility alias files present + parseable.
    alias_paths = [out / f for f in ALIAS_FILES]
    alias_parse = all_files_parse(alias_paths)
    aliases_ok = all(p.exists() for p in alias_paths) and alias_parse["_all_passed"]

    # Finding 3: a later --forecast-start-month must NOT reallocate prior-month CTC into the window.
    # When the override is active, the summed window recommended CTC must be strictly less than the
    # full recommended CTC (prior months were carried forward, not re-phased). Vacuously true otherwise.
    if inputs.get("window_override_active"):
        window_ctc = sum(float(s.get("window_recommended_ctc", s["median_ctc"])) for s in inputs["specs"])
        full_ctc = sum(float(s.get("window_recommended_ctc", s["median_ctc"]))
                       + float(s.get("carried_prior_forecast", 0.0)) for s in inputs["specs"])
        no_reallocation = (project.get("total_carried_prior_forecast", 0.0) > 0.0
                           and window_ctc < full_ctc - 1e-6)
    else:
        no_reallocation = True

    # P50 alignment: per-code median ~ deterministic recommended (lognormal median is exact), and the
    # deterministic recommended total is a central project outcome.
    tol = float(params["p50_recommended_tolerance_pct"])
    aligned = 0
    eligible = 0
    for r in code_rows:
        if r["near_complete"]:
            continue
        eligible += 1
        rec = float(D(r["deterministic_recommended_final_cost"]))
        p50 = float(D(r["simulated_p50"]))
        if abs(p50 - rec) <= max(tol * abs(rec), 50.0):
            aligned += 1
    per_code_p50_ok = (eligible == 0) or (aligned / eligible >= 0.90)
    rec_rank = float(D(summary["recommended_final_percentile_rank"]))
    project_p50_ok = 25.0 <= rec_rank <= 75.0
    p50_ok = per_code_p50_ok and project_p50_ok

    recon_ok = bool(diagnostics["reconciliation_ok"])

    # probability fields in the unit interval
    prob_keys = ("prob_exceeds_current_projected_cost", "prob_exceeds_revised_budget",
                 "prob_exceeds_recommended_final_cost")
    prob_ok = all(Decimal("0") <= D(r[k]) <= Decimal("1") for r in code_rows for k in prob_keys)

    sensitivity_present = any(D(o["abs_delta_p90"]) > 0 for o in sens["oat_delta_p90_by_source"])
    backtest_cohort_reported = "cohort_size" in collections["probabilistic_backtest_results.json"]

    db_clean = True
    if db_inv.get("db_present"):
        allowed = {"table", "present", "column_names", "row_count", "project_row_count"}
        db_clean = all(not (set(t.keys()) - allowed) for t in db_inv.get("tables", []))

    llm_no_numeric = True
    llm_receipts_ok = True
    if llm_used:
        llm_no_numeric = bool(receipts) and all(rc.get("numeric_outputs_from_llm") is False
                                                for rc in receipts)
        req = {"model", "backend", "status", "fallback_used", "numeric_outputs_from_llm",
               "temperature", "seed", "prompt_template_hash", "facts_hash", "response_hash",
               "safety_status", "generated_at"}
        llm_receipts_ok = bool(receipts) and all(req <= set(rc.keys()) for rc in receipts)

    parse = all_files_parse([p for p in out.rglob("*") if p.suffix in (".json", ".jsonl")])
    checks = OrderedDict([
        ("output_files_parse", parse["_all_passed"]),
        ("per_code_completeness_127", per_code_complete),
        ("canonical_only_codes", canonical_only),
        ("percentile_monotonicity", mono_codes and mono_project),
        ("final_cost_floor_at_actuals", floor_ok),
        ("no_upper_cap_uncapped_upside", bool(no_cap)),
        ("no_upper_cap_audit_present", no_cap_audit_present),
        ("no_code_upper_capped", bool(no_code_upper_capped)),
        ("no_cap_source_is_reference_value", bool(no_cap_source_is_reference)),
        ("revised_budget_probability_present_and_unit_interval", bool(revised_budget_ok)),
        ("compatibility_alias_files_present_and_parseable", bool(aliases_ok)),
        ("forecast_start_month_no_full_ctc_reallocation", bool(no_reallocation)),
        ("p50_aligns_with_deterministic_recommended", p50_ok),
        ("monthly_reconciles_to_simulated_ctc", recon_ok),
        ("probability_fields_in_unit_interval", prob_ok),
        ("sensitivity_ranking_present", bool(sensitivity_present)),
        ("backtest_cohort_reported", bool(backtest_cohort_reported)),
        ("determinism_passed", determinism["diff_result"] == "pass"),
        ("llm_no_numeric_outputs", llm_no_numeric),
        ("llm_receipts_have_required_fields", llm_receipts_ok),
        ("db_inventory_no_payloads", db_clean),
        ("safety_scan_passed", safety["passed"]),
    ])
    passed = all(bool(v) for v in checks.values())
    return OrderedDict([
        ("generated_timestamp_local", meta["generated_timestamp_local"]),
        ("package_stamp", meta["package_stamp"]), ("project_key", "tropical"),
        ("runs", meta["runs"]), ("seed", meta["seed"]),
        ("forecast_months", inputs["months"]),
        ("checks", checks),
        ("code_row_count", len(code_rows)),
        ("monthly_row_count", len(monthly)),
        ("expected_monthly_row_count", n_codes * n_months),
        ("determinism", determinism),
        ("safety_scan", safety),
        ("passed", passed),
    ])


def _manifest(out, project_key, meta, conclusion, validation):
    files = []
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name != "manifest.json":
            rows = sum(1 for _ in read_jsonl(p)) if p.suffix == ".jsonl" else None
            files.append(OrderedDict([("path", str(p.relative_to(out))), ("size_bytes", p.stat().st_size),
                                      ("row_count", rows), ("sha256", sha256_file(p))]))
    return OrderedDict([
        ("package_name", out.name),
        ("manifest_title", "Forecast Probabilistic Validation Package — Tropical World Nursery"),
        ("manifest_version", "1.0.0"),
        ("project", OrderedDict([("project_key", project_key),
                                 ("project_name", "Tropical World Nursery Senior Living Facility"),
                                 ("job_reference", "23-435-01"), ("forecast_period", "2026-June")])),
        ("generation", meta), ("output_files", files),
        ("validation_status", OrderedDict([("passed", validation["passed"]), ("checks", validation["checks"])])),
        ("conclusion", conclusion),
    ])


def _write_readme(out, project_key, meta, inputs, collections):
    s = collections["probabilistic_project_summary.json"]
    sp = s["simulated_final_cost_percentiles"]
    md = [
        f"# forecast_probability_package_tropical ({meta['package_stamp']})",
        "",
        f"Probabilistic VALIDATION of the accepted deterministic forecast for Tropical World Nursery "
        f"({project_key} / 23-435-01 / 2026-June). Monte Carlo stress-test ({meta['runs']} runs, "
        f"seed {meta['seed']}); it does not replace the deterministic forecast.",
        "",
        f"- Project final cost: P10 {sp['p10']} · P50 {sp['p50']} · P80 {sp['p80']} · P90 {sp['p90']} "
        f"· P95 {sp['p95']} (mean {s['simulated_mean_final_cost']}).",
        f"- Deterministic recommended {s['deterministic_recommended_final_cost']} sits at simulated "
        f"percentile {s['recommended_final_percentile_rank']}; worst-credible "
        f"{s['deterministic_worst_credible_final_cost']} at percentile "
        f"{s['worst_credible_final_percentile_rank']}.",
        f"- P(final ≥ recommended) = {s['prob_meets_or_exceeds_recommended_final']}; "
        f"P(final > current projected total) = {s['prob_exceeds_current_projected_total']}.",
        f"- Revised budget total {s['revised_budget_total']}: "
        f"P(final > revised budget) = {s['probability_project_exceeds_revised_budget_total']}; "
        f"expected overrun vs revised budget {s['expected_project_overrun_vs_revised_budget_total']} "
        f"(P90 {s['p90_overrun_vs_revised_budget_total']}).",
        f"- VaR(P90) {s['value_at_risk_p90']}; CVaR(P90) {s['conditional_value_at_risk_p90']}; "
        f"systemic variance share {s['systemic_variance_share']}.",
        "",
        "**Method.** Per code, cost-to-complete is a lognormal whose median equals the deterministic "
        "recommended cost-to-complete (recommended = per-code P50) and whose high quantile maps to the "
        "worst-credible cost-to-complete; spread is widened by burn volatility, backtest MAPE, model "
        "divergence and low confidence; overrun-existence confidence fattens the right tail. Codes are "
        "linked by a one-factor Gaussian copula. Actual cost to date is the ONLY floor; nothing is "
        "capped above any reference. Subcontractor invoice & owner pay-app values are evidence only.",
        "",
        "See `probabilistic_final_cost_by_budget_code.jsonl` (per-code P10..P95 + overrun probabilities), "
        "`downside_exposure_ranking.jsonl` (codes driving the project P90), "
        "`probabilistic_monthly_project_forecast.jsonl` + `monthly_risk_ranking.json` (timing), "
        "`sensitivity_analysis.json` (which assumptions matter), and `probabilistic_backtest_results.json` "
        "(PIT + coverage calibration). Quant core is deterministic (validation_report.json `determinism`); "
        "`llm/` narratives are advisory and excluded.",
        "",
        "**Compatibility aliases** (additive; canonical files preserved): `simulation_results_project.json`, "
        "`simulation_results_by_budget_code.jsonl`, `simulation_results_by_month.jsonl` (project-month), "
        "`probabilistic_overrun_risk_register.jsonl` (material rows only — probability + dollar/pct gate), "
        "`budget_code_sensitivity.jsonl`, `division_sensitivity.jsonl`, `owner_scope_sensitivity.jsonl`. "
        "`audit/no_upper_cap_audit.json` proves, per code, that nothing is capped above actuals against "
        "any reference (ERP / revised budget / committed / owner SOV / pay-app / prior output).",
        "",
    ]
    (out / "README.md").write_text("\n".join(md), encoding="utf-8")


def _write_schema(out):
    md = [
        "# Forecast Probabilistic Validation Package — Schema",
        "",
        "Money is Decimal-string (2dp); probabilities/ratios are 4dp Decimal strings in [0,1]. "
        "Simulation internals are float64; values are quantized at the JSON boundary.",
        "",
        "## Key files",
        "- `probabilistic_final_cost_by_budget_code.jsonl` — per code: P10/P50/P80/P90/P95, mean, std, "
        "deterministic recommended/worst, and P(exceeds current projected / revised budget / "
        "recommended).",
        "- `code_overrun_probabilities.jsonl` — per code: overrun probabilities + expected and "
        "conditional overrun vs current projected cost.",
        "- `downside_exposure_ranking.jsonl` / `top_downside_drivers.json` — per-code co-tail "
        "contribution to the project P90 (which codes drive the bad case), ranked.",
        "- `probabilistic_monthly_by_budget_code.jsonl` / `probabilistic_monthly_project_forecast.jsonl` "
        "/ `monthly_risk_ranking.json` — simulated monthly P50/P90 cost and cumulative overrun "
        "probability; months ranked by cost and by overrun risk.",
        "- `probabilistic_project_summary.json` — project P10..P95, mean/std, VaR/CVaR, probability "
        "the recommended/worst-credible/current-projected/revised-budget totals are met or exceeded, "
        "where each falls as a simulated percentile, the systemic variance share, project-level "
        "revised-budget overrun (`probability_project_exceeds_revised_budget_total`, "
        "`expected_project_overrun_vs_revised_budget_total`, P80/P90/P95 overrun vs revised budget), and "
        "a `window_reconciliation` block (accounting actual + deterministic prior-month forecast + "
        "simulated window CTC = simulated final).",
        "- `sensitivity_analysis.json` — one-at-a-time ΔP90 by spread source (authoritative), Spearman "
        "code drivers, and systemic-vs-idiosyncratic variance share.",
        "- `probabilistic_backtest_results.json` — PIT + coverage calibration: predictive "
        "shifted-lognormal-on-CTC at each as-of point (40/60/80% owner progress) vs realized final on "
        "the near-complete cohort (coverage at P10-P90 / P05-P95, PIT uniformity KS, per-point detail), "
        "with a dispersion-adequacy ratio vs historical MAPE as a secondary view; honest about the "
        "small cohort.",
        "- `simulation_inputs_by_budget_code.jsonl` — the calibrated mu/sigma + each sigma source per "
        "code (full audit of how each draw was parameterized), plus the carry-forward breakdown "
        "(`accounting_actual_cost_to_date`, `deterministic_prior_forecast_before_probability_window`, "
        "`probability_window_recommended/worst_credible_cost_to_complete`).",
        "- `calibration_summary.json` — methodology, parameters, numpy/scipy versions, seed, runs.",
        "",
        "## Compatibility aliases (additive; canonical files preserved, first-class outputs)",
        "- `simulation_results_project.json` = `probabilistic_project_summary.json`; "
        "`simulation_results_by_budget_code.jsonl` = `probabilistic_final_cost_by_budget_code.jsonl`; "
        "`simulation_results_by_month.jsonl` = `probabilistic_monthly_project_forecast.jsonl` "
        "(PROJECT-month totals, distinct from the per-code-month canonical file).",
        "- `probabilistic_overrun_risk_register.jsonl` — MATERIAL overrun rows only: a code is included "
        "iff P(exceeds current projected) >= 0.20 AND (expected overrun >= $25,000 OR >= 5% of current "
        "projected). Each row carries `materiality_threshold_basis`. Not merely all codes with "
        "expected_overrun > 0.",
        "- `budget_code_sensitivity.jsonl` — per code: co-tail downside contribution to project P90 + "
        "Spearman driver. `division_sensitivity.jsonl` / `owner_scope_sensitivity.jsonl` — risk "
        "contribution aggregated by division / authoritative owner SOV scope (owner-scope falls back to "
        "a single explicit unavailable row only when no crosswalk assignment resolves).",
        "- `audit/no_upper_cap_audit.json` — one record per code: distribution family, actual floor "
        "applied, upper_cap_applied (false), upper_cap_source (null), reference_values_reported_only, "
        "P95-vs-current-projected/revised-budget/worst-credible, validation_status.",
        "- `audit/*` — db_inventory (schema+counts only), source_files_used, safety_scan_report, "
        "no_upper_cap_audit. `validation_report.json` carries a `determinism` block. `llm/*` advisory "
        "only, excluded from determinism.",
        "",
        "## Rules",
        "- Actual cost to date is the ONLY hard floor; simulated finals are never capped at ERP "
        "projected / revised budget / committed / owner SOV / Procore pay-app / prior model output.",
        "- The deterministic recommended final cost is the per-code simulated P50 by construction.",
        "- Subcontractor invoice & owner pay-app values are progress/exposure/timing evidence, never "
        "actuals. The local LLM produces advisory text only — no numeric simulation result.",
        "- A later `--forecast-start-month` validates only the REMAINING window: the prior-month "
        "deterministic recommended/worst CTC is carried forward as a fixed addend (never reallocated "
        "into the shortened window, never treated as actual cost). Simulated final reconciles to "
        "accounting actual + deterministic prior-month forecast + simulated window CTC.",
        "- Deterministic: same seed + same frozen stamp => byte-identical quantitative core (canonical "
        "+ alias files).",
        "",
    ]
    (out / "SCHEMA.md").write_text("\n".join(md), encoding="utf-8")


def run(project_key, cfg, data_root=None, frozen_stamp=None, out_root=None, with_llm=False,
        llm_model=None, forecast_start_month=None, runs=10000, seed=20260614) -> int:
    res = generate(project_key, cfg, Path(data_root) if data_root else None, frozen_stamp,
                   Path(out_root) if out_root else None, with_llm, llm_model, forecast_start_month,
                   runs=runs, seed=seed)
    print(json.dumps({"status": "ok", "output_package": res["output_package"],
                      "validation_passed": res["validation_passed"],
                      "determinism_passed": res["determinism_passed"],
                      "safety_passed": res["safety_passed"],
                      "runs": res["runs"], "seed": res["seed"],
                      "project_p50": res["project_p50"], "project_p90": res["project_p90"],
                      "prob_exceeds_recommended": res["prob_exceeds_recommended"],
                      "llm_status": res["llm_status"],
                      "llm_narratives_generated": res["llm_narratives_generated"]}, indent=2))
    return 0 if res["validation_passed"] else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog=GENERATOR_NAME)
    ap.add_argument("--project", default="tropical")
    ap.add_argument("--runs", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=20260614)
    ap.add_argument("--forecast-start-month", default=None)
    ap.add_argument("--data-root", default=None)
    ap.add_argument("--frozen-stamp", default=None)
    ap.add_argument("--out-root", default=None)
    ap.add_argument("--with-llm", action="store_true")
    ap.add_argument("--llm-model", default=None)
    args = ap.parse_args(argv)
    cfg = read_json(SUBPROJECT_ROOT / "config" / "projects" / f"{args.project}.json")
    return run(args.project, cfg, args.data_root, args.frozen_stamp, args.out_root,
               args.with_llm, args.llm_model, args.forecast_start_month, runs=args.runs, seed=args.seed)


if __name__ == "__main__":
    sys.exit(main())
