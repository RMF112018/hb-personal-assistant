"""Generate the next-gen forecast-intelligence package for Tropical World Nursery.

Projects the real anticipated final cost per canonical budget code (dual posture: a balanced-central
``recommended_final_cost`` plus an evidence-supported ``worst_credible_final_cost``), surfaces
budget-code-level overruns (defined against current projected cost), and explains changes vs the
prior package. Uncapped above ERP/budget/commitment/owner SOV; actuals are the only hard floor.

Quantitative core is deterministic (frozen stamp). The optional local-Ollama narrative layer is
advisory, never numeric, and excluded from the byte-identical determinism gate. Source data, Excel,
and SQLite are never mutated (the DB is opened read-only for a schema+counts inventory).

Run:
    PYTHONPATH=src python3 -m construction_financial_review.cli forecast-intelligence --project tropical [--with-llm]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter, OrderedDict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional

from ..common import lineage
from ..common.dates import normalize_date
from ..common.hashing import sha256_file
from ..common.io import read_json, read_jsonl, write_json, write_jsonl
from ..common.money import D, dec, materiality, money_str
from ..common.safety import safety_scan
from ..common.validation import all_files_parse
from ..forecast_accuracy import signals
from ..forecast_accuracy.llm import narrate
from ..forecast_actuals import actuals_export
from ..forecast_accuracy.llm.client import OllamaClient
from ..forecast_cost_basis import apply as cost_basis_apply
from ..forecast_dormancy import classify as dormancy_classify
from ..forecast_dormancy import suppress as dormancy_suppress
from ..schedule_analysis import schedule_io, schedule_mapping, schedule_rollup
from . import (backtest_strong, change_explanation, confidence_intel, db_inventory,
               estimators_uncapped, evidence, overrun_register, reconcile_final,
               reconciled_backtest, schedule_association, trend)

SUBPROJECT_ROOT = Path(__file__).resolve().parents[3]
GENERATOR_NAME = "construction_financial_review.forecast_intelligence.generate_forecast_intelligence_package"
SCHEDULE_INTEGRATED_GLOB = "schedule_integrated_forecast_package_tropical_*"
PRIOR_ACCURACY_GLOB = "forecast_accuracy_package_tropical_*"

CONCLUSION_OVERRUNS = "forecast_intelligence_ready_with_overrun_risks"
CONCLUSION_READY = "forecast_intelligence_ready"

# Completion-stage recalibration: ENABLED. Tempers the p75 overrun bump at low completion to cut the
# early-stage over-forecast the accuracy gate found (faithful backtest: reconciled MAPE 0.41 -> 0.30,
# bias +0.33 -> +0.22, worst-case ceiling held; ADR 288/289/290). Doctrine-safe: no ERP anchor, never
# below weighted_mean, ceiling untouched. Only known-low-completion overrun codes are affected.
_P75_STAGE_GATE = True
CONCLUSION_NOT_READY = "forecast_intelligence_not_ready"

LLM_SUBSET_CAP = 60


def _git(args: list[str]) -> Optional[str]:
    try:
        out = subprocess.run(["git", *args], cwd=str(SUBPROJECT_ROOT),
                             capture_output=True, text=True, timeout=15)
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return None


def _latest_dir(data_root: Path, pattern: str) -> Optional[Path]:
    matches = sorted(p for p in data_root.glob(pattern) if p.is_dir())
    return matches[-1] if matches else None


def generate(project_key: str, cfg: dict, data_root: Optional[Path] = None,
             frozen_stamp: Optional[str] = None, out_root: Optional[Path] = None,
             with_llm: bool = False, llm_model: Optional[str] = None) -> dict:
    data_root = Path(data_root or cfg["default_data_root"])
    cfg, _ctx_pkg, ctx_lineage = lineage.pin_context_into_cfg(cfg, data_root, project_key)
    packages = schedule_io.discover_packages(data_root, cfg)
    context_pkg = packages.get("context_package")
    analysis_pkg = packages.get("analysis_v2_package")
    schedule_raw_pkg = packages.get("schedule_package")
    sched_integrated_pkg = _latest_dir(data_root, SCHEDULE_INTEGRATED_GLOB)
    prior_accuracy_pkg = _latest_dir(data_root, PRIOR_ACCURACY_GLOB)
    for label, p in (("context_package", context_pkg), ("analysis_v2_package", analysis_pkg)):
        if not p:
            raise SystemExit(f"ERROR: required {label} not found under {data_root}")

    stamp = frozen_stamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    generated_ts = frozen_stamp if frozen_stamp else datetime.now().isoformat(timespec="seconds")
    out_base = Path(out_root) if out_root else data_root
    out = out_base / f"forecast_accuracy_next_package_tropical_{stamp}"
    out.mkdir(parents=True, exist_ok=False)
    (out / "audit").mkdir(exist_ok=True)
    (out / "backtest").mkdir(exist_ok=True)
    (out / "llm").mkdir(exist_ok=True)

    llm_cfg = cfg.get("llm") or {}
    model = llm_model or llm_cfg.get("model", "qwen2.5:14b")
    command = (f"python3 -m construction_financial_review.cli forecast-intelligence --project {project_key}"
               + (" --with-llm" if with_llm else ""))

    # ---- Load inputs -------------------------------------------------------
    budget_codes = list(read_jsonl(context_pkg / "canonical" / "budget_codes.jsonl"))
    context_rows = list(read_jsonl(context_pkg / "summaries" / "budget_code_forecast_context.jsonl"))
    context_by_key = {r["budget_code_key"]: r for r in context_rows}
    recs = list(read_jsonl(analysis_pkg / "forecast_recommendations_by_budget_code.jsonl"))
    rec_by_key = {r["budget_code_key"]: r for r in recs}
    owner_history = signals.load_owner_history(context_pkg)

    # monthly actuals (CostEntries/Sage only) for the actuals export + recommendation-row fields
    actuals_load = actuals_export.load_costentries_monthly(context_pkg)
    monthly_actuals_by_key = actuals_load["by_key"]
    actuals_to_date_by_key = {r["budget_code_key"]: (r.get("actuals") or {}).get(
        "actual_cost_all_source_to_date") for r in context_rows if r.get("budget_code_key")}

    cashflow_totals = {}
    if sched_integrated_pkg:
        cashflow_totals = signals.load_cashflow_totals(sched_integrated_pkg)

    data_date = project_finish = None
    if schedule_raw_pkg:
        md = schedule_io.read_schedule_manifest(schedule_raw_pkg).get("metadata", {})
        data_date, project_finish = md.get("data_date"), md.get("scheduled_finish_date")

    # ---- Schedule rollup + activity ids (recomputed for deterministic links) ----
    rollup_by_key, direct_ids_by_key, schedule_inventory = _build_schedule(
        schedule_raw_pkg, budget_codes, project_key)

    # ---- Per-code metadata (for association grouping) ----------------------
    code_meta = {}
    for bc in budget_codes:
        key = bc["budget_code_key"]
        rec = rec_by_key.get(key, {})
        cc = bc.get("cost_code")
        code_meta[key] = {
            "cost_code": cc,
            "family": _family(cc),
            "division": (cc.split("-")[0] if isinstance(cc, str) and cc else None),
            "owner_sov_code": rec.get("assigned_owner_sov_code"),
            "revised_budget": (bc.get("amounts") or {}).get("revised_budget"),
            "budget_code_description": bc.get("budget_code_description"),
        }
    indices = schedule_association.build_group_indices(rollup_by_key, code_meta)
    project_has_remaining = bool(normalize_date(data_date) and normalize_date(project_finish)
                                 and normalize_date(data_date) < normalize_date(project_finish))

    # ---- Prior package (change explanation + before/after) -----------------
    prior_model_rec_by_key, prior_bt_summary = _load_prior(prior_accuracy_pkg)

    # ---- Backtest + calibration -------------------------------------------
    bt = backtest_strong.run_strong_backtest(context_rows, owner_history, project_key, prior_bt_summary)
    calibration = bt["calibration_weights"]

    # ---- Per-budget-code build (canonical 127) -----------------------------
    # Dormant / closed-code suppression runs BEFORE phasing: a CLOSED - DO NOT USE code, or a code idle
    # past the lookback window with no affirmative remaining evidence, gets CTC=0 / final=actual here so
    # no shape/history/frequency/schedule allocator can invent future cost downstream.
    dcfg = cfg.get("dormant_code_suppression") or {}
    dorm_enabled = bool(dcfg.get("enabled"))
    # Anchor "months since last actual" to the current FORECAST month (first month being phased), not the
    # schedule data_date (a prior month-end as-of). For Tropical forecast_period "2026-June" => 2026-06.
    current_forecast_month = _forecast_period_month(cfg, data_date)
    # Staffing/general-conditions signals for recent-zero-run suppression: the staffing code list and the
    # codes with an active staffing-plan future assignment (affirmative remaining evidence that revives a
    # stopped staffing cost stream).
    staffing_code_list = (cfg.get("forecast_cost_frequency") or {}).get(
        "weekly_internal_staffing_budget_code_keys") or []
    staffing_future_keys = _load_staffing_future_assignments(
        cfg, data_root, budget_codes, context_by_key, rec_by_key, project_key, stamp)
    dorm_decisions, dorm_audit = [], []
    cost_basis_rows = []
    recommendations, model_evidence, sched_evidence, trend_rows = [], [], [], []
    remaining_rows, confidences, changes, bundles = [], [], [], []
    ts_shadow_inputs = []  # (key, timeseries_eac estimate, recommended_final_cost, completed series)
    for bc in sorted(budget_codes, key=lambda r: r["budget_code_key"]):
        key = bc["budget_code_key"]
        ctx = context_by_key.get(key, {"budget_code_key": key, "sub_job": bc.get("sub_job"),
                                       "cost_code": bc.get("cost_code"), "category": bc.get("category"),
                                       "budget_code_description": bc.get("budget_code_description"),
                                       "budget_amounts": bc.get("amounts") or {}})
        rec = rec_by_key.get(key, {})
        sched_rollup = rollup_by_key.get(key)
        monthly = (ctx.get("actuals") or {}).get("monthly_actuals") or []

        tr = trend.analyze(monthly, data_date, project_key, key)
        assoc = schedule_association.classify(key, code_meta[key], rollup_by_key, direct_ids_by_key,
                                              indices, project_has_remaining, project_key)
        bundle = evidence.assemble_evidence(ctx, rec, sched_rollup, owner_history.get(key, []),
                                            cashflow_totals.get(key), assoc, tr, data_date,
                                            project_finish, project_key)
        ests = estimators_uncapped.estimate_all(bundle)
        recommendation = reconcile_final.select_final(key, project_key, ests, bundle, calibration,
                                                      p75_stage_gate=_P75_STAGE_GATE)

        # dormant / closed-code suppression (authoritative decision; emitted as the status file)
        if dorm_enabled:
            decision = dormancy_classify.classify(
                _dormancy_inputs(key, bc, ctx, bundle, assoc, monthly, current_forecast_month,
                                 staffing_code_list, key in staffing_future_keys), dcfg)
            dorm_decisions.append(decision)
            before = OrderedDict([("recommended_cost_to_complete", recommendation.get("recommended_cost_to_complete")),
                                  ("recommended_final_cost", recommendation.get("recommended_final_cost"))])
            if decision["suppression_applied"]:
                recommendation, before = dormancy_suppress.suppress_recommendation(recommendation, decision)
            dorm_audit.append(dormancy_suppress.audit_row(decision, before))

        ts_est = next((e for e in ests if e["method"] == "timeseries_eac"), None)
        ts_shadow_inputs.append((key, ts_est, recommendation.get("recommended_final_cost"),
                                 bundle.get("monthly_actuals_completed"),
                                 bundle.get("actual_cost_all_source_to_date")))

        conf = confidence_intel.score(bundle, recommendation)
        change = change_explanation.explain_change(recommendation, prior_model_rec_by_key.get(key),
                                                   rec, project_key)

        bundles.append(bundle)
        trend_rows.append(tr)
        sched_evidence.append(assoc)
        confidences.append(conf)
        changes.append(change)
        remaining_rows.append(_remaining_row(assoc, sched_rollup, data_date))
        model_evidence.append(OrderedDict([
            ("project_key", project_key), ("budget_code_key", key),
            ("reconciliation_basis", recommendation.get("reconciliation_basis")),
            ("n_independent_models", recommendation.get("n_independent_models")),
            ("model_eac_low", recommendation.get("model_eac_low")),
            ("model_eac_high", recommendation.get("model_eac_high")),
            ("model_eac_median", recommendation.get("model_eac_median")),
            ("model_divergence", recommendation.get("model_divergence")),
            ("contributions", recommendation.get("contributions")),
            ("estimates", ests),
        ]))
        # BudgetDetails projected-cost basis disclosure (asymmetric/corrective). Operator MODEL
        # controls are not known at the intelligence layer — they compose authoritatively in the
        # comprehensive package, which re-applies this decision and wins. Here we correct a proven
        # under-forecast so forecast_recommendations_by_budget_code.jsonl is not left materially wrong,
        # and emit pre_cost_basis_model_* + cost_basis_status for downstream idempotency.
        dorm_dec = decision if dorm_enabled else None
        cb_decision = _apply_cost_basis_intel(key, bc, recommendation, dorm_dec)
        cost_basis_rows.append(cost_basis_apply.build_cost_basis_audit_row(cb_decision))

        recommendations.append(_recommendation_row(
            recommendation, conf, rec, bc, actuals_export.rec_row_fields(monthly_actuals_by_key.get(key, {}))))

    rec_by = {r["budget_code_key"]: r for r in recommendations}
    evidence_by_key = {b["budget_code_key"]: b for b in bundles}
    confidence_by_key = {c["budget_code_key"]: c for c in confidences}

    # ---- Overrun register, change ranking, accuracy-next, warnings ---------
    register = overrun_register.build_register(recommendations, evidence_by_key, confidence_by_key,
                                               project_key)
    accuracy_next = [_accuracy_next_row(r) for r in recommendations]
    change_ranked = sorted((c for c in changes if c.get("material_change")),
                           key=lambda c: abs(D(c.get("delta"))), reverse=True)
    warnings = [w for w in (_warning_row(r, project_key) for r in recommendations) if w]

    # ---- LLM advisory subset ----------------------------------------------
    narratives, receipts, ollama_status, model_label = _run_llm(
        with_llm, model, llm_cfg, recommendations, evidence_by_key, confidence_by_key)

    # ---- Write artifacts ---------------------------------------------------
    write_jsonl(out / "forecast_recommendations_by_budget_code.jsonl", recommendations)
    write_jsonl(out / "dormant_code_status_by_budget_code.jsonl", dorm_decisions)
    write_json(out / "audit" / "dormant_code_suppression_audit.json",
               _dormant_audit(project_key, dorm_decisions, dorm_audit, dcfg))
    _cb_counts = {}
    for _r in cost_basis_rows:
        _cb_counts[_r["cost_basis_status"]] = _cb_counts.get(_r["cost_basis_status"], 0) + 1
    write_json(out / "audit" / "forecast_cost_basis_decision_audit.json", OrderedDict([
        ("project_key", project_key),
        ("layer", "forecast_intelligence"),
        ("summary_counts_by_cost_basis_status", _cb_counts),
        ("note", "intelligence-layer disclosure; operator model controls compose authoritatively in "
                 "the comprehensive package, which re-applies this decision and wins"),
        ("rows", sorted(cost_basis_rows, key=lambda r: r.get("budget_code_key") or "")),
    ]))
    write_jsonl(out / "forecast_accuracy_next_by_budget_code.jsonl", accuracy_next)
    write_jsonl(out / "forecast_model_evidence_by_budget_code.jsonl", model_evidence)
    # SHADOW time-series comparison + holdout backtest (evidence only; never changes the forecast).
    ts_comparison, ts_backtest = _timeseries_shadow_artifacts(project_key, ts_shadow_inputs)
    write_jsonl(out / "statsforecast_shadow_comparison.jsonl", ts_comparison)
    write_json(out / "audit" / "statsforecast_shadow_backtest.json", ts_backtest)
    write_jsonl(out / "schedule_forecast_evidence_by_budget_code.jsonl", sched_evidence)
    write_jsonl(out / "trend_evidence_by_budget_code.jsonl", trend_rows)
    write_jsonl(out / "remaining_work_evidence_by_budget_code.jsonl", remaining_rows)
    write_jsonl(out / "forecast_overrun_risk_register.jsonl", register)
    write_jsonl(out / "forecast_confidence_by_budget_code.jsonl", confidences)
    write_jsonl(out / "forecast_change_explanation.jsonl", changes)
    write_jsonl(out / "data_quality_warnings.jsonl", warnings)
    write_json(out / "model_backtest_results.json", _backtest_results(bt))
    write_json(out / "model_calibration_summary.json", _calibration_summary(bt))
    # As-of backtest of the PRODUCTION reconciled forecast (trust gate scoring; evidence only).
    write_json(out / "reconciled_forecast_backtest.json", reconciled_backtest.run_reconciled_backtest(
        context_rows, owner_history, project_key, calibration, bt.get("summary_by_method")))
    write_jsonl(out / "llm" / "forecast_narratives.jsonl", narratives)
    write_jsonl(out / "llm" / "llm_receipts.jsonl", receipts)

    summary = _project_summary(project_key, budget_codes, recommendations, register, confidences,
                               sched_evidence, bt, ollama_status, model if with_llm else None,
                               len(narratives))
    write_json(out / "project_forecast_summary.json", summary)
    write_json(out / "top_overrun_risks.json", overrun_register.rank_top(register, 25))
    write_json(out / "top_forecast_changes.json", change_ranked[:25])

    # ---- monthly actuals export (CostEntries/Sage only; additive evidence contract) ----
    actuals_collections = actuals_export.build_collections(
        project_key, budget_codes, monthly_actuals_by_key, actuals_to_date_by_key,
        rec_by_key=rec_by, forecast_start_month=None)
    actuals_export.write_collections(out, actuals_collections)

    # ---- Audit -------------------------------------------------------------
    meta = _generation_metadata(command, context_pkg, analysis_pkg, sched_integrated_pkg,
                                prior_accuracy_pkg, schedule_raw_pkg, stamp, generated_ts,
                                ollama_status, model if with_llm else None, len(narratives))
    db_inv = db_inventory.inventory(cfg, project_key)
    co_agg = db_inventory.change_order_aggregation(cfg, project_key)
    write_json(out / "audit" / "db_inventory.json", db_inv)
    write_json(out / "audit" / "schedule_inventory.json", schedule_inventory)
    write_json(out / "audit" / "source_files_used.json", _source_files(
        context_pkg, analysis_pkg, sched_integrated_pkg, prior_accuracy_pkg, schedule_raw_pkg,
        cfg, project_key))
    write_json(out / "audit" / "analysis_reconciliation.json", _analysis_reconciliation(
        budget_codes, recommendations, co_agg, bt))
    write_json(out / "input_inventory.json", OrderedDict([
        ("generation", meta),
        ("context_lineage", ctx_lineage),
        ("inputs", OrderedDict([
            ("forecast_context_package", str(context_pkg)),
            ("forecast_analysis_crosswalk_v2_package", str(analysis_pkg)),
            ("schedule_integrated_package", str(sched_integrated_pkg) if sched_integrated_pkg else None),
            ("schedule_raw_package", str(schedule_raw_pkg) if schedule_raw_pkg else None),
            ("prior_forecast_accuracy_package", str(prior_accuracy_pkg) if prior_accuracy_pkg else None),
        ])),
    ]))
    _write_readme(out, project_key, meta, summary)
    _write_schema(out)

    # ---- Validation + safety + manifest ------------------------------------
    data_files = sorted(p for p in out.rglob("*") if p.is_file()
                        and p.name not in ("manifest.json", "validation_report.json"))
    safety = safety_scan(data_files)
    write_json(out / "audit" / "safety_scan_report.json", safety)
    validation = _build_validation_report(out, recommendations, model_evidence, confidences,
                                          sched_evidence, trend_rows, remaining_rows, changes,
                                          budget_codes, bundles, db_inv, safety, meta, bt,
                                          actuals_collections=actuals_collections,
                                          actuals_contamination_ok=actuals_load["contamination_ok"],
                                          dorm_decisions=dorm_decisions)
    write_json(out / "validation_report.json", validation)
    conclusion = (CONCLUSION_OVERRUNS if (validation["passed"] and register)
                  else (CONCLUSION_READY if validation["passed"] else CONCLUSION_NOT_READY))
    write_json(out / "manifest.json", _build_manifest(out, project_key, meta, conclusion, validation))

    return {
        "output_package": str(out),
        "conclusion": conclusion,
        "validation_passed": validation["passed"],
        "safety_passed": safety["passed"],
        "llm_status": ollama_status,
        "llm_narratives_generated": len(narratives),
        "overrun_count": len(register),
        "summary": summary,
    }


# --------------------------------------------------------------------------- helpers

def _family(cc):
    from ..common.budget_keys import cost_code_family
    return cost_code_family(cc) if cc else None


def _build_schedule(schedule_raw_pkg, budget_codes, project_key):
    """Recompute schedule rollup + per-code mapped activity ids from raw activities."""
    rollup_by_key, direct_ids_by_key = {}, {}
    inventory = OrderedDict([("schedule_package_present", bool(schedule_raw_pkg))])
    if not schedule_raw_pkg:
        return rollup_by_key, direct_ids_by_key, inventory
    activities = list(schedule_io.iter_activities(schedule_raw_pkg))
    index = schedule_mapping.build_canonical_index(budget_codes)
    decisions = schedule_mapping.map_activities(activities, index)
    decisions_by_objid = {d.get("activity_object_id"): d for d in decisions}
    features = schedule_rollup.build_activity_features(activities, decisions_by_objid)
    rollup_rows = schedule_rollup.build_budget_rollup(budget_codes, features, project_key)
    rollup_by_key = {r["budget_code_key"]: r for r in rollup_rows}
    for f in features:
        if f["schedule_mapping_status"] == schedule_mapping.STATUS_MAPPED and f["mapped_budget_code_key"]:
            direct_ids_by_key.setdefault(f["mapped_budget_code_key"], []).append(f["activity_id"])
    md = schedule_io.read_schedule_manifest(schedule_raw_pkg).get("metadata", {})
    mapped = sum(1 for r in rollup_rows if r["schedule_mapping_status"] == "mapped")
    inventory.update(OrderedDict([
        ("schedule_data_date", md.get("data_date")),
        ("schedule_scheduled_finish", md.get("scheduled_finish_date")),
        ("activity_count", len(activities)),
        ("codes_with_direct_schedule_mapping", mapped),
        ("codes_with_open_remaining_work",
         sum(1 for r in rollup_rows if (r.get("open_activity_count") or 0) > 0)),
    ]))
    return rollup_by_key, direct_ids_by_key, inventory


def _load_prior(prior_pkg):
    prior_model_rec_by_key, prior_bt_summary = {}, None
    if not prior_pkg:
        return prior_model_rec_by_key, prior_bt_summary
    rec_file = prior_pkg / "forecast_accuracy_recommendations.jsonl"
    if rec_file.exists():
        prior_model_rec_by_key = {r["budget_code_key"]: r for r in read_jsonl(rec_file)}
    bt_file = prior_pkg / "backtest" / "backtest_accuracy_by_method.json"
    if bt_file.exists():
        prior_bt_summary = read_json(bt_file).get("summary_by_method")
    return prior_model_rec_by_key, prior_bt_summary


def _apply_cost_basis_intel(key, bc, recommendation, dorm_dec):
    """Apply/disclose the deterministic cost-basis decision on an intelligence recommendation.

    Mutates `recommendation` in place for a budgetdetails_projected_cost_basis selection (raising a
    proven under-forecast) and stamps pre_cost_basis_model_* + cost_basis_status for downstream
    idempotency. Operator model controls are unknown here (operator_controlled=False); comprehensive
    re-applies authoritatively.
    """
    amts = bc.get("amounts") or {}
    model_final = recommendation.get("recommended_final_cost")
    model_ctc = recommendation.get("recommended_cost_to_complete")
    suppressed = bool(dorm_dec and dorm_dec.get("suppression_applied"))
    ev = {
        "budget_code_key": key,
        "cost_code": bc.get("cost_code"),
        "category": bc.get("category"),
        "actual_cost_to_date": recommendation.get("actual_cost_all_source_to_date"),
        "pre_cost_basis_model_final": model_final,
        "pre_cost_basis_model_ctc": model_ctc,
        "operator_controlled": False,
        "dormant_suppressed": suppressed,
        "dormant_status": (dorm_dec or {}).get("dormant_status"),
        "has_recent_actual_activity": bool(recommendation.get("actuals_month_count_nonzero")),
    }
    for f in ("committed_costs", "commitment_invoiced", "erp_direct_costs", "erp_job_to_date_costs",
              "pending_cost_changes", "projected_costs", "estimated_cost_at_completion",
              "forecast_to_complete", "revised_budget", "projected_budget"):
        ev[f] = amts.get(f)
    _, _, decision = cost_basis_apply.apply_cost_basis_decision(
        D(model_final), D(model_ctc), D(ev["actual_cost_to_date"] or "0"), ev)
    recommendation["cost_basis_status"] = decision["cost_basis_status"]
    recommendation["pre_cost_basis_model_final"] = decision["pre_cost_basis_model_final"]
    recommendation["pre_cost_basis_model_ctc"] = decision["pre_cost_basis_model_ctc"]
    if decision["cost_basis_status"] == "budgetdetails_projected_cost_basis":
        sel_final = decision["selected_final_cost"]
        sel_ctc = decision["selected_cost_to_complete"]
        recommendation["recommended_final_cost"] = sel_final
        recommendation["recommended_cost_to_complete"] = sel_ctc
        # keep the ceiling monotonic (worst >= recommended) after raising the central estimate
        if D(recommendation.get("worst_credible_final_cost") or "0") < D(sel_final):
            recommendation["worst_credible_final_cost"] = sel_final
            recommendation["worst_credible_cost_to_complete"] = sel_ctc
    return decision


def _recommendation_row(recommendation, conf, v2_rec, bc, actuals_fields=None):
    row = OrderedDict(recommendation)
    row["budget_code_description"] = bc.get("budget_code_description")
    row["confidence_score"] = conf.get("calibrated_confidence")
    row["confidence_band"] = conf.get("confidence_band")
    row["overrun_confidence"] = conf.get("overrun_confidence")
    # Additive monthly-actuals history (CostEntries; never changes the recommendation values).
    for k, v in (actuals_fields or {}).items():
        row[k] = v
    # Rule-based reference (read only; never overrides the model number).
    row["rule_based_forecast_action"] = v2_rec.get("forecast_action")
    row["rule_based_recommended_projected_cost"] = v2_rec.get("recommended_projected_cost")
    return row


_MONTH_NAMES = {"JANUARY": 1, "FEBRUARY": 2, "MARCH": 3, "APRIL": 4, "MAY": 5, "JUNE": 6, "JULY": 7,
                "AUGUST": 8, "SEPTEMBER": 9, "OCTOBER": 10, "NOVEMBER": 11, "DECEMBER": 12}


def _forecast_period_month(cfg, data_date) -> Optional[str]:
    """Current forecast month (YYYY-MM) from cfg['forecast_period'] (e.g. '2026-June'); fallback data_date."""
    fp = cfg.get("forecast_period")
    if isinstance(fp, str) and "-" in fp:
        y, mon = fp.split("-", 1)
        m = _MONTH_NAMES.get(mon.strip().upper()) or (int(mon) if mon.strip().isdigit() else None)
        if m and y.strip().isdigit():
            return f"{int(y):04d}-{int(m):02d}"
    d = normalize_date(data_date)
    return d[:7] if d else None


def _load_staffing_future_assignments(cfg, data_root, budget_codes, context_by_key, rec_by_key,
                                      project_key, stamp_iso):
    """Set of budget_code_keys with an active staffing-plan future assignment (plan_implied_remaining_cost
    > 0). Best-effort + guarded: a missing/unsafe staffing package just yields no staffing evidence (codes
    without a confirmed assignment); it never crashes intelligence."""
    sp = cfg.get("forecast_staffing_plan") or {}
    if not sp.get("enabled"):
        return set()
    try:
        from ..forecast_staffing_plan import integration as fsp_integration
        actuals_by_key = {r["budget_code_key"]: D((r.get("actuals") or {}).get("actual_cost_all_source_to_date"))
                          for r in context_by_key.values() if r.get("budget_code_key")}
        monthly_actuals_by_key = {k: (v.get("actuals") or {}).get("monthly_actuals") or []
                                  for k, v in context_by_key.items()}
        bundle = fsp_integration.prepare(cfg, SUBPROJECT_ROOT, data_root, budget_codes, actuals_by_key,
                                         rec_by_key, project_key, stamp_iso=stamp_iso,
                                         monthly_actuals_by_key=monthly_actuals_by_key)
        if not fsp_integration.integration_active(cfg, bundle):
            return set()
        return {k for k, d in (bundle["resolved"]["by_key"] or {}).items()
                if D(d.get("plan_implied_remaining_cost")) > Decimal("0")}
    except Exception:                                       # noqa: BLE001 - staffing evidence is optional
        return set()


def _dormancy_inputs(key, bc, ctx, bundle, assoc, monthly, current_month, staffing_code_list,
                     staffing_plan_future_assignment):
    """Assemble the per-code signals the dormancy classifier consumes from intelligence context."""
    amounts = ctx.get("budget_amounts") or bc.get("amounts") or {}
    owner = ctx.get("owner_pay_app") or {}
    sub = ctx.get("procore_subcontractor_pay_apps") or {}
    assoc = assoc or {}
    return {
        "budget_code_key": key, "cost_code": bc.get("cost_code") or ctx.get("cost_code"),
        "category": bc.get("category") or ctx.get("category"),
        "sub_job_description": ctx.get("sub_job_description") or bc.get("sub_job_description"),
        "budget_code_description": ctx.get("budget_code_description") or bc.get("budget_code_description"),
        "cost_type_description": bc.get("cost_type_description") or ctx.get("cost_type_description"),
        "monthly_actuals": monthly,
        "actual_cost_to_date": bundle.get("actual_cost_all_source_to_date"),
        "current_forecast_month": current_month,
        "revised_budget": amounts.get("revised_budget"), "projected_costs": amounts.get("projected_costs"),
        "committed_costs": amounts.get("committed_costs"),
        "commitment_invoiced": amounts.get("commitment_invoiced"),
        "owner_latest_period_to": owner.get("latest_period_to"),
        "procore_latest_period_end": sub.get("latest_period_end"),
        "schedule_remaining_work_status": assoc.get("schedule_remaining_work_status"),
        "schedule_open_activity_count": assoc.get("open_activity_count"),
        "schedule_latest_finish": assoc.get("latest_schedule_finish"),
        "staffing_code_list": staffing_code_list,
        "staffing_plan_future_assignment": staffing_plan_future_assignment,
        "model_control": None,  # operator value controls compose at the consumers, not at the origin
    }


def _dormant_audit(project_key, decisions, audit_rows, dcfg) -> OrderedDict:
    from collections import Counter
    suppressed = [d for d in decisions if d["suppression_applied"]]
    return OrderedDict([
        ("project_key", project_key),
        ("enabled", bool(dcfg.get("enabled"))),
        ("lookback_months_without_actual_cost", dcfg.get("lookback_months_without_actual_cost")),
        ("closed_description_patterns", dcfg.get("closed_description_patterns")),
        ("recent_zero_run", dcfg.get("recent_zero_run")),
        ("status_counts", dict(Counter(d["dormant_status"] for d in decisions))),
        ("suppressed_count", len(suppressed)),
        ("suppressed_budget_codes", [d["budget_code_key"] for d in suppressed]),
        ("recent_zero_run_suppressed_count",
         sum(1 for d in suppressed if d["dormant_status"] == "recent_zero_run_after_prior_activity")),
        ("non_staffing_recent_zero_run_advisory_codes",
         [d["budget_code_key"] for d in decisions if d.get("non_staffing_suppression_candidate")]),
        ("rows", audit_rows),
        ("rule", "CLOSED - DO NOT USE codes and codes idle >= lookback with no affirmative remaining "
                 "evidence get CTC=0 / final=actual; a trend/inactivity conclusion, never a budget cap; "
                 "actuals are never reduced and final never falls below actuals; overridden only by "
                 "affirmative remaining evidence or a value-asserting accepted operator control"),
    ])


def _timeseries_shadow_artifacts(project_key, ts_shadow_inputs):
    """SHADOW time-series comparison + deterministic holdout backtest (evidence only).

    Uses the isolated statsforecast runtime when ``CFR_MODEL_ENGINE_PYTHON`` is configured and
    available (one batched subprocess call); otherwise the in-process classical ensemble — byte
    identical to a runtime-absent run. Each artifact records its ``backend``. Nothing here changes
    the central forecast; it is the go/no-go evidence for promoting the estimator (next PR).
    """
    from . import model_engine_adapter as mea
    from . import timeseries_engine

    def _money2(x):
        return money_str(Decimal(str(round(float(x), 2))))

    def _pct4(x):
        return str(Decimal(str(round(float(x), 6))).quantize(Decimal("0.0001")))

    # Deterministic per-code plan (sorted): parse series, horizon, and the holdout split.
    plan = []
    for key, ts_est, rec_final, series, actual in sorted(ts_shadow_inputs, key=lambda t: t[0] or ""):
        vals = [float(D(p.get("amount"))) for p in (series or [])]
        n = len(vals)
        horizon = int((ts_est or {}).get("inputs", {}).get("horizon_months") or 0)
        h = prefix = actual_holdout = None
        if n >= 4:
            hh = 1 if n < 6 else (2 if n < 9 else 3)
            if n - hh >= 3:
                ah = sum(vals[-hh:])
                if ah != 0:
                    h, prefix, actual_holdout = hh, vals[:-hh], ah
        plan.append((key, ts_est, rec_final, vals, actual, n, horizon, h, prefix, actual_holdout))

    # Try the isolated runtime once (batched: full-horizon for the comparison + holdout prefixes for
    # the backtest). Any unavailability falls back to the classical in-process engine.
    use_runtime = False
    runtime_full: dict = {}
    runtime_holdout: dict = {}
    backend = timeseries_engine.BACKEND_LABEL
    runtime_ok, _reason = mea.available()
    if runtime_ok:
        reqs = []
        for (key, ts_est, _rf, vals, _a, n, horizon, h, prefix, _ah) in plan:
            if ts_est is not None and ts_est.get("applicable") and horizon > 0 and n >= 3:
                reqs.append({"id": key + "|full", "series": vals, "horizon": horizon})
            if h is not None:
                reqs.append({"id": key + "|holdout", "series": prefix, "horizon": h})
        if reqs:
            try:
                resp = mea.forecast_batch(reqs)
                for rid, r in (resp.get("results") or {}).items():
                    if rid.endswith("|full"):
                        runtime_full[rid[: -len("|full")]] = r.get("etc")
                    elif rid.endswith("|holdout"):
                        runtime_holdout[rid[: -len("|holdout")]] = r.get("etc")
                backend = resp.get("backend") or backend
                use_runtime = True
            except mea.ModelEngineUnavailable:
                use_runtime = False

    comparison, bt_rows = [], []
    for (key, ts_est, rec_final, vals, actual, n, horizon, h, prefix, actual_holdout) in plan:
        if ts_est is not None and ts_est.get("applicable") and dec(ts_est.get("eac")) is not None:
            if use_runtime and runtime_full.get(key) is not None:
                act = D(actual)
                raw = act + Decimal(str(round(float(runtime_full[key]), 2)))
                ts_eac = raw if raw >= act else act
            else:
                ts_eac = D(ts_est["eac"])
            rec = dec(rec_final)
            delta = (ts_eac - rec) if rec is not None else None
            pct = (delta / rec) if (rec is not None and rec != 0 and delta is not None) else None
            comparison.append(OrderedDict([
                ("project_key", project_key),
                ("budget_code_key", key),
                ("timeseries_eac", money_str(ts_eac)),
                ("recommended_final_cost", money_str(rec) if rec is not None else None),
                ("delta_timeseries_minus_recommended", money_str(delta) if delta is not None else None),
                ("delta_pct", str(pct.quantize(Decimal("0.0001"))) if pct is not None else None),
                ("backend", backend),
            ]))
        if h is None:
            continue
        if use_runtime and runtime_holdout.get(key) is not None:
            engine_pred = float(runtime_holdout[key])
        else:
            engine_pred = timeseries_engine.forecast_etc(prefix, h)["etc"]
        naive_pred = prefix[-1] * h
        eng_ape = abs(engine_pred - actual_holdout) / abs(actual_holdout)
        nai_ape = abs(naive_pred - actual_holdout) / abs(actual_holdout)
        bt_rows.append(OrderedDict([
            ("budget_code_key", key),
            ("n_completed_months", n),
            ("holdout_months", h),
            ("actual_holdout", _money2(actual_holdout)),
            ("engine_pred", _money2(engine_pred)),
            ("naive_pred", _money2(naive_pred)),
            ("engine_abs_pct_error", _pct4(eng_ape)),
            ("naive_abs_pct_error", _pct4(nai_ape)),
            ("engine_wins", eng_ape <= nai_ape),
        ]))

    def _median_pct(rows, field):
        xs = sorted(float(r[field]) for r in rows)
        if not xs:
            return None
        m = len(xs) // 2
        med = xs[m] if len(xs) % 2 else (xs[m - 1] + xs[m]) / 2
        return _pct4(med)

    total = len(bt_rows)
    wins = sum(1 for r in bt_rows if r["engine_wins"])
    summary = OrderedDict([
        ("project_key", project_key),
        ("backend", backend),
        ("backtest_scheme", "holdout last h completed months (h=1 if <6 obs, 2 if <9, 3 else); fit "
                            "the engine on the prefix, predict h and sum vs the actual held-out "
                            "months; naive baseline = last observed month repeated h. Codes with <4 "
                            "completed months or zero held-out actuals are excluded."),
        ("eligible_code_count", total),
        ("engine_median_abs_pct_error", _median_pct(bt_rows, "engine_abs_pct_error")),
        ("naive_median_abs_pct_error", _median_pct(bt_rows, "naive_abs_pct_error")),
        ("engine_better_or_equal_count", wins),
        ("engine_better_or_equal_rate",
         str((Decimal(wins) / Decimal(total)).quantize(Decimal("0.0001"))) if total else None),
        ("per_code", bt_rows),
        ("note", "SHADOW evidence only; timeseries_eac is NOT in INDEPENDENT_METHODS and never "
                 "changes the central forecast. Promotion to the weighted ensemble is gated on this."),
    ])
    return comparison, summary


def _accuracy_next_row(r):
    return OrderedDict([
        ("project_key", r["project_key"]),
        ("budget_code_key", r["budget_code_key"]),
        ("actual_cost_all_source_to_date", r["actual_cost_all_source_to_date"]),
        ("current_projected_cost", r["current_projected_cost"]),
        ("revised_budget", r["revised_budget"]),
        ("recommended_final_cost", r["recommended_final_cost"]),
        ("recommended_cost_to_complete", r["recommended_cost_to_complete"]),
        ("worst_credible_final_cost", r["worst_credible_final_cost"]),
        ("variance_to_current_projected_cost", r["recommended_variance_to_current_projected_cost"]),
        ("variance_to_revised_budget", r["recommended_variance_to_revised_budget"]),
        ("forecast_direction", r["forecast_direction"]),
        ("overrun_projected", r["overrun_projected"]),
        ("overrun_basis", r["overrun_basis"]),
        ("n_independent_models", r["n_independent_models"]),
        ("model_divergence", r["model_divergence"]),
        ("confidence_score", r["confidence_score"]),
        ("confidence_band", r["confidence_band"]),
        ("requires_human_acceptance", True),
    ])


def _remaining_row(assoc, sched_rollup, data_date):
    pct_remaining = None
    if sched_rollup:
        completed = sched_rollup.get("completed_activity_count") or 0
        open_ct = sched_rollup.get("open_activity_count") or 0
        total = completed + open_ct
        if total > 0:
            pct_remaining = str((D(open_ct) / D(total)).quantize(Decimal("0.0001")))
    return OrderedDict([
        ("project_key", assoc["project_key"]),
        ("budget_code_key", assoc["budget_code_key"]),
        ("schedule_association", assoc["schedule_association"]),
        ("schedule_confidence", assoc["schedule_confidence"]),
        ("influences_code_estimate", assoc["influences_code_estimate"]),
        ("open_activity_count", assoc["open_activity_count"]),
        ("remaining_duration_days", assoc["remaining_duration_days"]),
        ("percent_schedule_activities_remaining", pct_remaining),
        ("latest_schedule_finish", assoc["latest_schedule_finish"]),
        ("schedule_data_date", normalize_date(data_date)),
        ("schedule_remaining_work_status", assoc["schedule_remaining_work_status"]),
        ("direct_mapped_activity_count", assoc["direct_mapped_activity_count"]),
        ("activity_refs", assoc["activity_refs"]),
        ("association_basis", assoc["association_basis"]),
    ])


def _warning_row(r, project_key):
    gaps = r.get("limiting_data_gaps") or []
    if not gaps and r.get("n_independent_models"):
        return None
    severity = "high" if r.get("n_independent_models") == 0 else "medium"
    return OrderedDict([
        ("project_key", project_key),
        ("budget_code_key", r["budget_code_key"]),
        ("severity", severity),
        ("n_independent_models", r.get("n_independent_models")),
        ("forecast_direction", r.get("forecast_direction")),
        ("limiting_data_gaps", gaps),
    ])


def _run_llm(with_llm, model, llm_cfg, recommendations, evidence_by_key, confidence_by_key):
    backend, ollama_status, model_label = None, "disabled_mock", "deterministic_template"
    if with_llm:
        client = OllamaClient(model, llm_cfg.get("endpoint", "http://localhost:11434"),
                              float(llm_cfg.get("temperature", 0)), int(llm_cfg.get("seed", 7)),
                              float(llm_cfg.get("timeout_seconds", 60)))
        if client.model_present():
            backend, ollama_status, model_label = client, "available", model
        else:
            ollama_status = "model_absent_using_template"

    subset = [r for r in recommendations
              if r.get("overrun_projected") or r.get("forecast_direction") in ("increase", "review")]
    subset = sorted(subset, key=lambda r: (-D(r.get("recommended_variance_to_current_projected_cost") or 0),
                                           r["budget_code_key"]))[:LLM_SUBSET_CAP]
    narratives, receipts = [], []
    for r in subset:
        key = r["budget_code_key"]
        facts = _intel_facts(r, evidence_by_key.get(key, {}), confidence_by_key.get(key, {}))
        nrow, rrow = narrate.narrate_one(facts, backend, model_label)
        narratives.append(nrow)
        receipts.append(rrow)
    return narratives, receipts, ollama_status, model_label


def _intel_facts(r, bundle, conf):
    return OrderedDict([
        ("project_key", r.get("project_key")),
        ("budget_code_key", r.get("budget_code_key")),
        ("budget_code_description", bundle.get("budget_code_description")),
        ("actual_cost_all_source_to_date", r.get("actual_cost_all_source_to_date")),
        ("current_projected_cost", r.get("current_projected_cost")),
        ("revised_budget", r.get("revised_budget")),
        ("recommended_final_cost", r.get("recommended_final_cost")),
        ("worst_credible_final_cost", r.get("worst_credible_final_cost")),
        ("recommended_cost_to_complete", r.get("recommended_cost_to_complete")),
        ("forecast_direction", r.get("forecast_direction")),
        ("overrun_projected", r.get("overrun_projected")),
        ("overrun_basis", r.get("overrun_basis")),
        ("n_independent_models", r.get("n_independent_models")),
        ("model_divergence", r.get("model_divergence")),
        ("schedule_association", bundle.get("schedule_association")),
        ("trend_signal", bundle.get("trend_signal")),
        ("primary_evidence", r.get("primary_evidence")),
        ("confidence_band", conf.get("confidence_band")),
    ])


def _money_sum(rows, field):
    total = Decimal("0")
    for r in rows:
        total += D(r.get(field))
    return total


def _project_summary(project_key, budget_codes, recommendations, register, confidences,
                     sched_evidence, bt, ollama_status, model, n_narratives):
    direction = Counter(r["forecast_direction"] for r in recommendations)
    band = Counter(c["confidence_band"] for c in confidences)
    assoc = Counter(a["schedule_association"] for a in sched_evidence)
    total_final = _money_sum(recommendations, "recommended_final_cost")
    total_worst = _money_sum(recommendations, "worst_credible_final_cost")
    total_proj = _money_sum(recommendations, "current_projected_cost")
    total_actual = _money_sum(recommendations, "actual_cost_all_source_to_date")
    overrun_amt = sum((D(r["recommended_final_cost"]) - D(r["current_projected_cost"])
                       for r in recommendations
                       if D(r["recommended_final_cost"]) > D(r["current_projected_cost"])), Decimal("0"))
    underrun_amt = sum((D(r["current_projected_cost"]) - D(r["recommended_final_cost"])
                        for r in recommendations
                        if D(r["recommended_final_cost"]) < D(r["current_projected_cost"])), Decimal("0"))
    return OrderedDict([
        ("project_key", project_key),
        ("budget_codes", len(budget_codes)),
        ("codes_with_independent_models",
         sum(1 for r in recommendations if (r["n_independent_models"] or 0) >= 1)),
        ("forecast_direction_distribution", dict(direction)),
        ("confidence_band_distribution", dict(band)),
        ("schedule_association_distribution", dict(assoc)),
        ("overrun_counts", OrderedDict([
            ("overrun_projected", sum(1 for r in recommendations if r["overrun_projected"])),
            ("overrun_vs_revised_budget", sum(1 for r in recommendations if r["overrun_vs_revised_budget"])),
            ("overrun_vs_committed_cost", sum(1 for r in recommendations if r["overrun_vs_committed_cost"])),
            ("overrun_vs_owner_scope_value", sum(1 for r in recommendations if r["overrun_vs_owner_scope_value"])),
            ("worst_credible_overrun_only", sum(1 for r in recommendations if r["worst_credible_overrun"])),
        ])),
        ("totals", OrderedDict([
            ("total_actual_to_date", money_str(total_actual)),
            ("total_current_projected_cost", money_str(total_proj)),
            ("total_recommended_final_cost", money_str(total_final)),
            ("total_worst_credible_final_cost", money_str(total_worst)),
            ("total_projected_overrun", money_str(overrun_amt)),
            ("total_projected_underrun", money_str(underrun_amt)),
            ("net_recommended_vs_current_projected", money_str(total_final - total_proj)),
        ])),
        ("backtest_cohort_size", bt["cohort_size"]),
        ("calibration_weights", bt["calibration_weights"]),
        ("llm_status", ollama_status),
        ("llm_model", model),
        ("llm_narratives_generated", n_narratives),
    ])


def _backtest_results(bt):
    out = OrderedDict(bt)
    out["detail_row_count"] = len(bt["detail_rows"])
    out.pop("detail_rows", None)
    return out


def _calibration_summary(bt):
    return OrderedDict([
        ("calibration_weights", bt["calibration_weights"]),
        ("reliability_weight_map", {"high": "1.0", "medium": "0.6", "low": "0.3"}),
        ("summary_by_method", bt["summary_by_method"]),
        ("before_after_by_method", bt["before_after_by_method"]),
        ("methodology", bt["methodology"]),
    ])


def _generation_metadata(command, context_pkg, analysis_pkg, sched_integrated, prior_pkg,
                         schedule_raw, stamp, generated_ts, ollama_status, model, n_narratives):
    return OrderedDict([
        ("generator", GENERATOR_NAME),
        ("subproject_path", str(SUBPROJECT_ROOT)),
        ("git_branch", _git(["rev-parse", "--abbrev-ref", "HEAD"])),
        ("git_head_sha", _git(["rev-parse", "HEAD"])),
        ("git_tree_dirty", bool(_git(["status", "--porcelain"]))),
        ("command", command),
        ("package_stamp", stamp),
        ("generated_timestamp_local", generated_ts),
        ("ollama_status", ollama_status),
        ("ollama_model", model),
        ("llm_narratives_generated", n_narratives),
        ("selected_input_packages", OrderedDict([
            ("context_package", str(context_pkg)),
            ("analysis_v2_package", str(analysis_pkg)),
            ("schedule_integrated_package", str(sched_integrated) if sched_integrated else None),
            ("schedule_raw_package", str(schedule_raw) if schedule_raw else None),
            ("prior_forecast_accuracy_package", str(prior_pkg) if prior_pkg else None),
        ])),
    ])


def _source_files(context_pkg, analysis_pkg, sched_integrated, prior_pkg, schedule_raw, cfg, project_key):
    return OrderedDict([
        ("context_package", str(context_pkg)),
        ("analysis_v2_package", str(analysis_pkg)),
        ("schedule_integrated_package", str(sched_integrated) if sched_integrated else None),
        ("schedule_raw_package", str(schedule_raw) if schedule_raw else None),
        ("prior_forecast_accuracy_package", str(prior_pkg) if prior_pkg else None),
        ("local_db", str(db_inventory.resolve_db_path(cfg))),
        ("rule_based_recommendation_source",
         "forecast_recommendations_by_budget_code.jsonl (crosswalk_v2) — read only, reference only"),
        ("mutation_posture", "READ-ONLY: no source/Excel/SQLite/external mutation; DB opened mode=ro"),
    ])


def _analysis_reconciliation(budget_codes, recommendations, co_agg, bt):
    return OrderedDict([
        ("canonical_budget_code_count", len(budget_codes)),
        ("recommendation_row_count", len(recommendations)),
        ("change_order_aggregation_project_level", co_agg),
        ("backtest_cohort_size", bt["cohort_size"]),
        ("backtest_excluded_rows", bt["excluded_rows"]),
        ("note", "Change-order dollars are project-level context only; they are not attributed to "
                 "any budget code and never set a per-code estimate."),
    ])


def _build_validation_report(out, recommendations, model_evidence, confidences, sched_evidence,
                             trend_rows, remaining_rows, changes, budget_codes, bundles, db_inv,
                             safety, meta, bt, actuals_collections=None,
                             actuals_contamination_ok=True, dorm_decisions=None) -> OrderedDict:
    n = len(budget_codes)
    canonical = {bc["budget_code_key"] for bc in budget_codes}
    per_code = (recommendations, model_evidence, confidences, sched_evidence, trend_rows,
                remaining_rows, changes)
    one_per = all(len(x) == n and len({r["budget_code_key"] for r in x}) == n for x in per_code)
    canonical_only = all(r["budget_code_key"] in canonical
                         for x in per_code for r in x)

    actual_by_key = {r["budget_code_key"]: D(r.get("actual_cost_all_source_to_date"))
                     for r in recommendations}
    # Actuals are the only hard floor.
    final_floor_ok = all(
        D(r["recommended_final_cost"]) >= actual_by_key[r["budget_code_key"]]
        and D(r["worst_credible_final_cost"]) >= actual_by_key[r["budget_code_key"]]
        for r in recommendations)
    est_floor_ok = all(
        dec(e["eac"]) is None or dec(e["eac"]) >= actual_by_key.get(me["budget_code_key"], Decimal("0"))
        for me in model_evidence for e in me["estimates"] if e["applicable"])

    # Overrun never suppressed for exceeding ERP/budget.
    overrun_not_suppressed = all(
        not (D(r["recommended_final_cost"]) > D(r["current_projected_cost"])
             and materiality(r["recommended_final_cost"], r["current_projected_cost"])[2]
             and not r["overrun_projected"])
        for r in recommendations if r.get("current_projected_cost") is not None)

    # Explicit uncapped proof (positive existence): recommendations exceed references in practice,
    # AND the estimator layer itself produces values above ERP/budget (never clamped to a reference).
    uncapped_demonstrated = any(
        r["overrun_vs_current_projected_cost"] or r["overrun_vs_revised_budget"]
        or r["overrun_vs_committed_cost"] or r["overrun_vs_owner_scope_value"]
        for r in recommendations)
    estimates_exceed_refs = any(
        e.get("exceeds_erp_projected") or e.get("exceeds_revised_budget")
        for me in model_evidence for e in me["estimates"]
        if e["source"] == "independent" and e["applicable"])
    no_clamp = uncapped_demonstrated and estimates_exceed_refs

    # Direct schedule association requires a deterministic mapped activity link.
    direct_link_ok = all(
        (a["schedule_association"] != "direct") or (a["direct_mapped_activity_count"] >= 1
                                                    and len(a["activity_refs"]) >= 1)
        for a in sched_evidence)

    # No pay-app value overwrote accounting actuals (byte-equal to context actuals).
    ctx_actual = {b["budget_code_key"]: b.get("actual_cost_all_source_to_date") for b in bundles}
    no_payapp_overwrite = all(
        r["actual_cost_all_source_to_date"] == ctx_actual.get(r["budget_code_key"])
        for r in recommendations)

    # DB inventory carries schema+counts only (no value fields / payload keys).
    db_inv_clean = _db_inventory_clean(db_inv)

    parse = all_files_parse([p for p in out.rglob("*") if p.suffix in (".json", ".jsonl")])
    backtest_ok = bt["cohort_size"] >= 1

    # ---- dormant / closed-code suppression gates (fail closed) ----
    dorm = dorm_decisions or []
    rec_by_v = {r["budget_code_key"]: r for r in recommendations}
    supp = [d for d in dorm if d["suppression_applied"]]
    dorm_ctc_zero = all(D(rec_by_v.get(d["budget_code_key"], {}).get("recommended_cost_to_complete")) == Decimal("0")
                        for d in supp)
    dorm_final_eq_actual = all(
        D(rec_by_v.get(d["budget_code_key"], {}).get("recommended_final_cost")) == actual_by_key.get(d["budget_code_key"], Decimal("0"))
        for d in supp)
    dorm_actual_unchanged = all(
        D(rec_by_v.get(d["budget_code_key"], {}).get("actual_cost_all_source_to_date")) == D(d["actual_cost_to_date"])
        for d in supp)
    dorm_final_geq_actual = all(
        D(rec_by_v.get(d["budget_code_key"], {}).get("recommended_final_cost")) >= D(d["actual_cost_to_date"])
        for d in supp)
    no_positive_for_closed = all(
        not (d["closure_phrase_detected"] and not d["operator_control_override"] and not d["remaining_evidence"]
             and D(rec_by_v.get(d["budget_code_key"], {}).get("recommended_cost_to_complete")) > Decimal("0"))
        for d in dorm)
    no_positive_for_recent_zero_run = all(
        not (d["dormant_status"] == "recent_zero_run_after_prior_activity" and not d["operator_control_override"]
             and not d["remaining_evidence"]
             and D(rec_by_v.get(d["budget_code_key"], {}).get("recommended_cost_to_complete")) > Decimal("0"))
        for d in dorm)

    checks = OrderedDict([
        ("output_files_parse", parse["_all_passed"]),
        ("one_row_per_canonical_key", one_per),
        ("canonical_only_codes", canonical_only),
        ("final_cost_geq_actuals", final_floor_ok),
        ("every_estimate_geq_actuals", est_floor_ok),
        ("forecast_is_uncapped", bool(uncapped_demonstrated and no_clamp)),
        ("overrun_not_suppressed", overrun_not_suppressed),
        ("direct_assoc_requires_deterministic_link", direct_link_ok),
        ("no_payapp_overwrite_of_actuals", no_payapp_overwrite),
        ("db_inventory_no_payloads", db_inv_clean),
        ("backtest_cohort_present", backtest_ok),
        ("dormant_suppressed_ctc_zero", dorm_ctc_zero),
        ("dormant_suppressed_final_equals_actual", dorm_final_eq_actual),
        ("dormant_suppression_did_not_change_actuals", dorm_actual_unchanged),
        ("dormant_suppressed_final_not_below_actuals", dorm_final_geq_actual),
        ("no_positive_forecast_for_closed_without_evidence", no_positive_for_closed),
        ("no_positive_forecast_for_recent_zero_run_without_evidence", no_positive_for_recent_zero_run),
        ("safety_scan_passed", safety["passed"]),
    ])
    if actuals_collections is not None:
        checks.update(actuals_export.validation_gates(actuals_collections, canonical,
                                                      actuals_contamination_ok))
    passed = all(bool(v) for v in checks.values())
    return OrderedDict([
        ("generated_timestamp_local", meta["generated_timestamp_local"]),
        ("package_stamp", meta["package_stamp"]),
        ("project_key", "tropical"),
        ("checks", checks),
        ("recommendation_row_count", len(recommendations)),
        ("canonical_budget_code_count", n),
        ("overrun_projected_count", sum(1 for r in recommendations if r["overrun_projected"])),
        ("backtest_cohort_size", bt["cohort_size"]),
        ("safety_scan", safety),
        ("passed", passed),
    ])


def _db_inventory_clean(db_inv) -> bool:
    if not db_inv.get("db_present"):
        return True
    allowed = {"table", "present", "column_names", "row_count", "project_row_count"}
    for t in db_inv.get("tables", []):
        if set(t.keys()) - allowed:
            return False
    return True


def _build_manifest(out, project_key, meta, conclusion, validation) -> OrderedDict:
    files = []
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name != "manifest.json":
            rel = p.relative_to(out)
            rows = sum(1 for _ in read_jsonl(p)) if p.suffix == ".jsonl" else None
            files.append(OrderedDict([("path", str(rel)), ("size_bytes", p.stat().st_size),
                                      ("row_count", rows), ("sha256", sha256_file(p))]))
    return OrderedDict([
        ("package_name", out.name),
        ("manifest_title", "Forecast Intelligence Package — Tropical World Nursery"),
        ("manifest_version", "1.0.0"),
        ("project", OrderedDict([("project_key", project_key),
                                 ("project_name", "Tropical World Nursery Senior Living Facility"),
                                 ("job_reference", "23-435-01"), ("forecast_period", "2026-June")])),
        ("generation", meta),
        ("output_files", files),
        ("validation_status", OrderedDict([("passed", validation["passed"]),
                                           ("checks", validation["checks"])])),
        ("conclusion", conclusion),
    ])


def _write_readme(out, project_key, meta, summary):
    t = summary["totals"]
    md = [
        f"# forecast_accuracy_next_package_tropical ({meta['package_stamp']})",
        "",
        f"Next-gen forecast intelligence for Tropical World Nursery ({project_key} / 23-435-01 / "
        "2026-June). Projects the real anticipated final cost per budget code and surfaces "
        "budget-code-level overruns.",
        "",
        "**Uncapped principle:** actual cost to date is the ONLY hard floor. `recommended_final_cost` "
        "and `worst_credible_final_cost` are never capped at ERP projected cost, revised budget, "
        "committed cost, owner SOV value, or Procore pay-app value. References are reported for "
        "comparison only. Overrun is defined against current projected cost.",
        "",
        "**Dual posture:** a balanced-central `recommended_final_cost` plus an evidence-supported "
        "`worst_credible_final_cost` exposure ceiling per code.",
        "",
        f"- Codes with >=1 independent model: {summary['codes_with_independent_models']}/{summary['budget_codes']}",
        f"- Projected overruns (vs current projected cost): {summary['overrun_counts']['overrun_projected']}",
        f"- Total current projected: {t['total_current_projected_cost']} -> "
        f"recommended final: {t['total_recommended_final_cost']} "
        f"(net {t['net_recommended_vs_current_projected']}); worst-credible "
        f"{t['total_worst_credible_final_cost']}",
        f"- Backtest cohort: {summary['backtest_cohort_size']} codes; LLM: {summary['llm_status']} "
        f"({summary['llm_narratives_generated']} narratives)",
        "",
        "See `SCHEMA.md` and `validation_report.json`. The quantitative core is deterministic; the "
        "`llm/` narratives are advisory, model-generated, safety-scanned, and excluded from the "
        "determinism gate. Accounting actuals are truth; every recommendation requires human acceptance.",
        "",
    ]
    (out / "README.md").write_text("\n".join(md), encoding="utf-8")


def _write_schema(out):
    md = [
        "# Forecast Intelligence Package — Schema",
        "",
        "Money is Decimal-string (2dp). Per-code JSONL files have exactly 127 rows sorted by "
        "budget_code_key. Actual cost to date is the only hard floor; nothing is capped at ERP / "
        "budget / commitment / owner SOV / Procore values.",
        "",
        "## Recommendation semantics (`forecast_recommendations_by_budget_code.jsonl`)",
        "- `recommended_final_cost` — balanced-central anticipated final cost (may exceed ERP).",
        "- `worst_credible_final_cost` — evidence-supported exposure ceiling.",
        "- `recommended_cost_to_complete`, `worst_credible_cost_to_complete`.",
        "- `recommended_variance_to_current_projected_cost`, `recommended_variance_to_revised_budget`.",
        "- `forecast_direction` — increase | decrease | hold | review | insufficient_evidence.",
        "- `overrun_projected` (= overrun vs current projected cost) plus separate "
        "`overrun_vs_current_projected_cost` / `overrun_vs_revised_budget` / "
        "`overrun_vs_committed_cost` / `overrun_vs_owner_scope_value` / `worst_credible_overrun`.",
        "- `overrun_basis` — actuals | trend | schedule_remaining_work | commitment_exposure | "
        "owner_progress | procore_progress | calibrated_model | combined | none.",
        "- `confidence_score`, `confidence_band`, `primary_evidence`, `limiting_data_gaps`, "
        "`requires_human_acceptance` (always true). `erp_projected_reference` is reference only.",
        "",
        "## Evidence + audit",
        "- `forecast_model_evidence_by_budget_code.jsonl` — per code, all uncapped estimates + "
        "weighted contributions (ETC and EAC kept distinct; ERP entries are labeled references).",
        "- `schedule_forecast_evidence_by_budget_code.jsonl` / `remaining_work_evidence_*` — schedule "
        "association (direct/cost_code_family/owner_scope/division/vendor_or_commitment/project_level/"
        "none), confidence, remaining duration, activity refs. `direct` requires a deterministic link.",
        "- `trend_evidence_by_budget_code.jsonl` — recent vs prior burn, acceleration, volatility, "
        "recency, late-cost emergence, credit/deductive pattern, trend signal.",
        "- `forecast_overrun_risk_register.jsonl`, `top_overrun_risks.json` — overruns ranked by amount.",
        "- `forecast_confidence_by_budget_code.jsonl` — calibrated 0-1 + schedule-association component.",
        "- `forecast_change_explanation.jsonl`, `top_forecast_changes.json` — vs prior package / rule-based.",
        "- `model_backtest_results.json`, `model_calibration_summary.json` — multi-as-of-T backtest, "
        "division/family cohorts, before/after vs the prior package, excluded rows.",
        "- `audit/db_inventory.json` — schema + counts only (read-only, no payloads). "
        "`audit/schedule_inventory.json`, `audit/source_files_used.json`, "
        "`audit/analysis_reconciliation.json`, `audit/safety_scan_report.json`.",
        "",
        "## Rules",
        "- Accounting actuals are truth; never overwritten by pay-app evidence. Final cost >= actuals.",
        "- ERP projected cost is reference only — never a cap and never a fallback floor.",
        "- Project-level schedule association is context only; it never drives a code-level estimate.",
        "- LLM is advisory, JSON-validated, safety-scanned fail-closed, temp 0; excluded from determinism.",
        "",
    ]
    (out / "SCHEMA.md").write_text("\n".join(md), encoding="utf-8")


def run(project_key: str, cfg: dict, data_root=None, frozen_stamp=None, out_root=None,
        with_llm: bool = False, llm_model=None) -> int:
    res = generate(project_key, cfg, Path(data_root) if data_root else None, frozen_stamp,
                   Path(out_root) if out_root else None, with_llm, llm_model)
    print(json.dumps({
        "status": "ok",
        "output_package": res["output_package"],
        "conclusion": res["conclusion"],
        "validation_passed": res["validation_passed"],
        "safety_passed": res["safety_passed"],
        "overrun_count": res["overrun_count"],
        "llm_status": res["llm_status"],
        "llm_narratives_generated": res["llm_narratives_generated"],
    }, indent=2))
    return 0 if res["validation_passed"] else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog=GENERATOR_NAME)
    ap.add_argument("--project", default="tropical")
    ap.add_argument("--data-root", default=None)
    ap.add_argument("--frozen-stamp", default=None)
    ap.add_argument("--out-root", default=None)
    ap.add_argument("--with-llm", action="store_true")
    ap.add_argument("--llm-model", default=None)
    args = ap.parse_args(argv)
    cfg = read_json(SUBPROJECT_ROOT / "config" / "projects" / f"{args.project}.json")
    return run(args.project, cfg, args.data_root, args.frozen_stamp, args.out_root,
               args.with_llm, args.llm_model)


if __name__ == "__main__":
    sys.exit(main())
