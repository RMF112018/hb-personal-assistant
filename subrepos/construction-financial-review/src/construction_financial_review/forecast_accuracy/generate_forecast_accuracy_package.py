"""Generate the forecast-accuracy package for Tropical World Nursery.

Builds independent EAC/ETC estimates, reconciles an advisory model-recommended forecast (floored to
actuals, human-gated), calibrates confidence with a backtest, flags ERP forecast adequacy, and adds
an optional advisory local-Ollama narrative layer. The deterministic rule-based recommendation is
read but never modified. Writes ONE new timestamped package under the data root.

Run via the CLI:
    PYTHONPATH=src python3 -m construction_financial_review.cli forecast-accuracy --project tropical [--with-llm]
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

from ..common.dates import normalize_date
from ..common.hashing import sha256_file
from ..common.io import read_json, read_jsonl, write_json, write_jsonl
from ..common.money import D, dec
from ..common.safety import safety_scan
from ..common.validation import all_files_parse
from ..schedule_analysis import schedule_io
from . import backtest as bt
from . import confidence as conf
from . import estimators, forecast_adequacy, reconcile, signals
from .llm import narrate
from .llm.client import OllamaClient

SUBPROJECT_ROOT = Path(__file__).resolve().parents[3]   # .../construction-financial-review
GENERATOR_NAME = "construction_financial_review.forecast_accuracy.generate_forecast_accuracy_package"
SCHEDULE_INTEGRATED_GLOB = "schedule_integrated_forecast_package_tropical_*"

CONCLUSION_READY = "forecast_accuracy_ready"
CONCLUSION_REVIEW = "forecast_accuracy_ready_with_review_items"
CONCLUSION_NOT_READY = "forecast_accuracy_not_ready"

LLM_SUBSET_CAP = 60
HIGH_DIVERGENCE = Decimal("0.25")


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
    packages = schedule_io.discover_packages(data_root, cfg)
    context_pkg = packages.get("context_package")
    analysis_pkg = packages.get("analysis_v2_package")
    schedule_raw_pkg = packages.get("schedule_package")
    sched_integrated_pkg = _latest_dir(data_root, SCHEDULE_INTEGRATED_GLOB)
    for label, p in (("context_package", context_pkg), ("analysis_v2_package", analysis_pkg)):
        if not p:
            raise SystemExit(f"ERROR: required {label} not found under {data_root}")

    stamp = frozen_stamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    generated_ts = frozen_stamp if frozen_stamp else datetime.now().isoformat(timespec="seconds")
    out_base = Path(out_root) if out_root else data_root
    out = out_base / f"forecast_accuracy_package_tropical_{stamp}"
    out.mkdir(parents=True, exist_ok=False)
    (out / "audit").mkdir(exist_ok=True)
    (out / "backtest").mkdir(exist_ok=True)
    (out / "llm").mkdir(exist_ok=True)

    llm_cfg = cfg.get("llm") or {}
    model = llm_model or llm_cfg.get("model", "qwen2.5:14b")
    command = (f"python3 -m construction_financial_review.cli forecast-accuracy --project {project_key}"
               + (" --with-llm" if with_llm else ""))

    # ---- Load inputs -------------------------------------------------------
    budget_codes = list(read_jsonl(context_pkg / "canonical" / "budget_codes.jsonl"))
    context_rows = list(read_jsonl(context_pkg / "summaries" / "budget_code_forecast_context.jsonl"))
    context_by_key = {r["budget_code_key"]: r for r in context_rows}
    recs = list(read_jsonl(analysis_pkg / "forecast_recommendations_by_budget_code.jsonl"))
    rec_by_key = {r["budget_code_key"]: r for r in recs}
    owner_history = signals.load_owner_history(context_pkg)

    rollup_by_key, cashflow_totals = {}, {}
    if sched_integrated_pkg:
        rfile = sched_integrated_pkg / "schedule_budget_code_rollup.jsonl"
        if rfile.exists():
            rollup_by_key = {r["budget_code_key"]: r for r in read_jsonl(rfile)}
        cashflow_totals = signals.load_cashflow_totals(sched_integrated_pkg)

    data_date = project_finish = None
    if schedule_raw_pkg:
        md = schedule_io.read_schedule_manifest(schedule_raw_pkg).get("metadata", {})
        data_date, project_finish = md.get("data_date"), md.get("scheduled_finish_date")

    # ---- Backtest + calibration -------------------------------------------
    backtest_result = bt.run_backtest(context_rows, owner_history, project_key)
    calibration = backtest_result["calibration_weights"]

    # ---- Per-budget-code build (canonical 127) -----------------------------
    bundles, estimate_rows, reconciliations, confidences, adequacies, recommendations = [], [], [], [], [], []
    for bc in sorted(budget_codes, key=lambda r: r["budget_code_key"]):
        key = bc["budget_code_key"]
        ctx = context_by_key.get(key, {"budget_code_key": key, "sub_job": bc.get("sub_job"),
                                       "cost_code": bc.get("cost_code"), "category": bc.get("category"),
                                       "budget_code_description": bc.get("budget_code_description")})
        rec = rec_by_key.get(key, {})
        sched = rollup_by_key.get(key)
        bundle = signals.build_signal_bundle(ctx, rec, sched, owner_history.get(key, []),
                                             cashflow_totals.get(key), data_date, project_finish, project_key)
        ests = estimators.estimate_all(bundle)
        rc = reconcile.reconcile(key, project_key, ests, bundle.get("actual_cost_all_source_to_date"), calibration)
        cf = conf.score_confidence(bundle, rc)
        ad = forecast_adequacy.assess_adequacy(rc, project_key)

        bundles.append(bundle)
        estimate_rows.append(OrderedDict([("project_key", project_key), ("budget_code_key", key),
                                          ("estimates", ests)]))
        reconciliations.append(rc)
        confidences.append(cf)
        adequacies.append(ad)
        recommendations.append(OrderedDict([
            ("project_key", project_key),
            ("budget_code_key", key),
            ("actual_cost_all_source_to_date", bundle.get("actual_cost_all_source_to_date")),
            ("authoritative_forecast_action", rec.get("forecast_action")),
            ("authoritative_recommended_projected_cost", rec.get("recommended_projected_cost")),
            ("erp_projected_costs", rc.get("erp_projected_costs")),
            ("model_recommended_projected_cost", rc.get("model_recommended_projected_cost")),
            ("model_reconciled_eac", rc.get("model_reconciled_eac")),
            ("model_eac_low", rc.get("model_eac_low")),
            ("model_eac_high", rc.get("model_eac_high")),
            ("model_divergence", rc.get("model_divergence")),
            ("n_independent_models", rc.get("n_independent_models")),
            ("reconciliation_basis", rc.get("reconciliation_basis")),
            ("model_vs_erp_gap", rc.get("model_vs_erp_gap")),
            ("forecast_adequacy", ad.get("forecast_adequacy")),
            ("adequacy_severity", ad.get("adequacy_severity")),
            ("calibrated_confidence", cf.get("calibrated_confidence")),
            ("confidence_band", cf.get("confidence_band")),
            ("requires_human_acceptance", True),
            ("review_notes", None),
        ]))

    adequacy_by_key = {a["budget_code_key"]: a for a in adequacies}
    reconciliation_by_key = {r["budget_code_key"]: r for r in reconciliations}
    confidence_by_key = {c["budget_code_key"]: c for c in confidences}
    bundle_by_key = {b["budget_code_key"]: b for b in bundles}

    # ---- LLM advisory subset ----------------------------------------------
    backend, ollama_status, model_label = None, "disabled_mock", "deterministic_template"
    if with_llm:
        client = OllamaClient(model, llm_cfg.get("endpoint", "http://localhost:11434"),
                              float(llm_cfg.get("temperature", 0)), int(llm_cfg.get("seed", 7)),
                              float(llm_cfg.get("timeout_seconds", 60)))
        if client.model_present():
            backend, ollama_status, model_label = client, "available", model
        else:
            ollama_status = "model_absent_using_template"

    subset_keys = []
    for key in sorted(bundle_by_key):
        ad = adequacy_by_key[key]
        rc = reconciliation_by_key[key]
        rec = rec_by_key.get(key, {})
        if (ad["forecast_adequacy"] in ("likely_low", "likely_high")
                or rec.get("forecast_action") == "review_required"
                or (dec(rc.get("model_divergence")) or Decimal("0")) >= HIGH_DIVERGENCE
                or bundle_by_key[key].get("schedule_remaining_work_status") == "material_remaining_work"):
            subset_keys.append(key)
    subset_keys = subset_keys[:LLM_SUBSET_CAP]

    narratives, receipts = [], []
    for key in subset_keys:
        facts = narrate.build_facts(bundle_by_key[key], reconciliation_by_key[key],
                                    confidence_by_key[key], adequacy_by_key[key])
        nrow, rrow = narrate.narrate_one(facts, backend, model_label)
        narratives.append(nrow)
        receipts.append(rrow)

    # ---- Write artifacts ---------------------------------------------------
    write_jsonl(out / "signal_bundle_by_budget_code.jsonl", bundles)
    write_jsonl(out / "eac_estimates_by_budget_code.jsonl", estimate_rows)
    write_jsonl(out / "forecast_reconciliation_by_budget_code.jsonl", reconciliations)
    write_jsonl(out / "forecast_confidence_by_budget_code.jsonl", confidences)
    write_jsonl(out / "forecast_adequacy_by_budget_code.jsonl", adequacies)
    write_jsonl(out / "forecast_accuracy_recommendations.jsonl", recommendations)
    write_json(out / "backtest" / "backtest_accuracy_by_method.json", OrderedDict([
        ("cohort_size", backtest_result["cohort_size"]),
        ("summary_by_method", backtest_result["summary_by_method"]),
        ("calibration_weights", calibration),
        ("methodology", "Reconstruct each method's EAC at a mid-progress as-of period (owner apps + "
                        "monthly actuals <= T) on the owner>=95% cohort; score APE/bias vs realized "
                        "actual-to-date; calibration multiplier = (1/(1+MAPE)) normalized to mean 1.0."),
    ]))
    write_jsonl(out / "backtest" / "backtest_detail.jsonl", backtest_result["detail_rows"])
    write_jsonl(out / "llm" / "forecast_narratives.jsonl", narratives)
    write_jsonl(out / "llm" / "llm_receipts.jsonl", receipts)

    # ---- Summaries ---------------------------------------------------------
    adequacy_dist = Counter(a["forecast_adequacy"] for a in adequacies)
    band_dist = Counter(c["confidence_band"] for c in confidences)
    likely_low = sorted(a["budget_code_key"] for a in adequacies if a["forecast_adequacy"] == "likely_low")
    likely_high = sorted(a["budget_code_key"] for a in adequacies if a["forecast_adequacy"] == "likely_high")
    gaps = sorted(
        ({"budget_code_key": a["budget_code_key"], "forecast_adequacy": a["forecast_adequacy"],
          "adequacy_severity": a["adequacy_severity"], "model_minus_erp_gap": a["model_minus_erp_gap"],
          "gap_percent": a["gap_percent"]}
         for a in adequacies if a["forecast_adequacy"] in ("likely_low", "likely_high")),
        key=lambda r: abs(D(r["model_minus_erp_gap"])), reverse=True)
    codes_with_independent = sum(1 for r in reconciliations if (r["n_independent_models"] or 0) >= 1)

    indeterminate = sum(1 for a in adequacies if a["forecast_adequacy"] == "indeterminate")
    review_items = len(likely_low) + len(likely_high) + indeterminate
    conclusion = CONCLUSION_REVIEW if review_items else CONCLUSION_READY

    summary = OrderedDict([
        ("project_key", project_key),
        ("conclusion", conclusion),
        ("budget_codes", len(budget_codes)),
        ("codes_with_independent_models", codes_with_independent),
        ("adequacy_distribution", dict(adequacy_dist)),
        ("confidence_band_distribution", dict(band_dist)),
        ("budget_codes_forecast_likely_low", likely_low),
        ("budget_codes_forecast_likely_high", likely_high),
        ("backtest_cohort_size", backtest_result["cohort_size"]),
        ("backtest_summary_by_method", backtest_result["summary_by_method"]),
        ("calibration_weights", calibration),
        ("llm_status", ollama_status),
        ("llm_model", model if with_llm else None),
        ("llm_narratives_generated", len(narratives)),
        ("llm_subset_size", len(subset_keys)),
        ("review_item_count", review_items),
    ])
    write_json(out / "summaries" / "project_forecast_accuracy_summary.json", summary)
    write_json(out / "summaries" / "top_forecast_adequacy_gaps.json", gaps[:25])
    _write_summary_md(out, project_key, summary, gaps, backtest_result)

    # ---- Audit -------------------------------------------------------------
    meta = _generation_metadata(command, packages, sched_integrated_pkg, stamp, generated_ts,
                                ollama_status, model if with_llm else None, len(subset_keys))
    write_json(out / "audit" / "source_files_used.json", OrderedDict([
        ("context_package", str(context_pkg)),
        ("analysis_v2_package", str(analysis_pkg)),
        ("schedule_integrated_package", str(sched_integrated_pkg) if sched_integrated_pkg else None),
        ("schedule_raw_package", str(schedule_raw_pkg) if schedule_raw_pkg else None),
        ("authoritative_recommendation_source",
         "forecast_recommendations_by_budget_code.jsonl (crosswalk_v2) — read only, never modified"),
    ]))
    write_json(out / "audit" / "calibration_snapshot.json", OrderedDict([
        ("cohort_size", backtest_result["cohort_size"]),
        ("summary_by_method", backtest_result["summary_by_method"]),
        ("calibration_weights", calibration),
    ]))
    write_json(out / "input_inventory.json", OrderedDict([
        ("generation", meta),
        ("inputs", OrderedDict([
            ("forecast_context_package", str(context_pkg)),
            ("forecast_analysis_crosswalk_v2_package", str(analysis_pkg)),
            ("schedule_integrated_package", str(sched_integrated_pkg) if sched_integrated_pkg else None),
        ])),
    ]))
    _write_readme(out, project_key, meta, summary)
    _write_schema(out)

    # ---- Validation + safety + manifest ------------------------------------
    data_files = sorted(p for p in out.rglob("*") if p.is_file()
                        and p.name not in ("manifest.json", "validation_report.json"))
    safety = safety_scan(data_files)
    write_json(out / "audit" / "safety_scan_report.json", safety)
    validation_report = _build_validation_report(out, recommendations, estimate_rows, reconciliations,
                                                 confidences, budget_codes, safety, conclusion, meta,
                                                 backtest_result)
    write_json(out / "validation_report.json", validation_report)
    write_json(out / "manifest.json", _build_manifest(out, project_key, meta, conclusion, validation_report))

    return {
        "output_package": str(out),
        "conclusion": conclusion,
        "validation_passed": validation_report["passed"],
        "safety_passed": safety["passed"],
        "llm_status": ollama_status,
        "llm_narratives_generated": len(narratives),
        "summary": summary,
    }


def _generation_metadata(command, packages, sched_integrated, stamp, generated_ts, ollama_status,
                         model, subset_size) -> OrderedDict:
    dirty = _git(["status", "--porcelain"])
    return OrderedDict([
        ("generator", GENERATOR_NAME),
        ("subproject_path", str(SUBPROJECT_ROOT)),
        ("git_branch", _git(["rev-parse", "--abbrev-ref", "HEAD"])),
        ("git_head_sha", _git(["rev-parse", "HEAD"])),
        ("git_tree_dirty", bool(dirty)),
        ("command", command),
        ("package_stamp", stamp),
        ("generated_timestamp_local", generated_ts),
        ("ollama_status", ollama_status),
        ("ollama_model", model),
        ("llm_subset_size", subset_size),
        ("selected_input_packages", OrderedDict([
            ("context_package", str(packages.get("context_package")) if packages.get("context_package") else None),
            ("analysis_v2_package", str(packages.get("analysis_v2_package")) if packages.get("analysis_v2_package") else None),
            ("schedule_integrated_package", str(sched_integrated) if sched_integrated else None),
        ])),
    ])


def _build_validation_report(out, recommendations, estimate_rows, reconciliations, confidences,
                             budget_codes, safety, conclusion, meta, backtest_result) -> OrderedDict:
    n = len(budget_codes)
    one_per = all(len(x) == n for x in (recommendations, estimate_rows, reconciliations, confidences))
    actual_by_key = {rc["budget_code_key"]: D(rc.get("actual_cost_all_source_to_date"))
                     for rc in reconciliations}
    # Floor invariant: model_recommended >= actual, and every applicable estimate eac >= actual.
    floor_ok = all(
        (dec(rc.get("model_recommended_projected_cost")) is None
         or dec(rc["model_recommended_projected_cost"]) >= D(rc.get("actual_cost_all_source_to_date")))
        for rc in reconciliations)
    est_floor_ok = all(
        dec(e["eac"]) >= actual_by_key.get(er["budget_code_key"], Decimal("0"))
        for er in estimate_rows for e in er["estimates"]
        if e["applicable"] and dec(e["eac"]) is not None)
    conf_bounds_ok = all(Decimal("0") <= dec(c["calibrated_confidence"]) <= Decimal("1") for c in confidences)
    backtest_ok = backtest_result["cohort_size"] >= 1
    parse = all_files_parse([p for p in out.rglob("*") if p.suffix in (".json", ".jsonl")])

    checks = OrderedDict([
        ("output_files_parse", parse["_all_passed"]),
        ("one_row_per_canonical_key", one_per),
        ("model_recommended_floored_to_actuals", floor_ok),
        ("every_estimate_floored_to_actuals", est_floor_ok),
        ("confidence_in_unit_interval", conf_bounds_ok),
        ("backtest_cohort_present", backtest_ok),
        ("safety_scan_passed", safety["passed"]),
    ])
    passed = all(bool(v) for v in checks.values())
    return OrderedDict([
        ("generated_timestamp_local", meta["generated_timestamp_local"]),
        ("package_stamp", meta["package_stamp"]),
        ("project_key", "tropical"),
        ("checks", checks),
        ("recommendation_row_count", len(recommendations)),
        ("canonical_budget_code_count", n),
        ("backtest_cohort_size", backtest_result["cohort_size"]),
        ("safety_scan", safety),
        ("passed", passed),
        ("conclusion", conclusion if passed else CONCLUSION_NOT_READY),
    ])


def _build_manifest(out, project_key, meta, conclusion, validation_report) -> OrderedDict:
    files = []
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name != "manifest.json":
            rel = p.relative_to(out)
            rows = sum(1 for _ in read_jsonl(p)) if p.suffix == ".jsonl" else None
            files.append(OrderedDict([("path", str(rel)), ("size_bytes", p.stat().st_size),
                                      ("row_count", rows), ("sha256", sha256_file(p))]))
    return OrderedDict([
        ("package_name", out.name),
        ("project", OrderedDict([("project_key", project_key),
                                 ("project_name", "Tropical World Nursery Senior Living Facility"),
                                 ("job_reference", "23-435-01"), ("forecast_period", "2026-June")])),
        ("generation", meta),
        ("output_files", files),
        ("validation_status", OrderedDict([("passed", validation_report["passed"]),
                                           ("checks", validation_report["checks"])])),
        ("conclusion", conclusion),
    ])


def _write_summary_md(out, project_key, summary, gaps, backtest_result):
    (out / "summaries").mkdir(exist_ok=True)

    def _gap_lines(items, n):
        rows = [f"- {g['budget_code_key']}: {g['forecast_adequacy']} ({g['adequacy_severity']}), "
                f"gap {g['model_minus_erp_gap']} ({g['gap_percent']})" for g in items[:n]]
        return rows if rows else ["- none"]

    def _gap_lines_exec(items, n):
        rows = [f"- {g['budget_code_key']}: ERP vs model gap {g['model_minus_erp_gap']} "
                f"({g['forecast_adequacy']})" for g in items[:n]]
        return rows if rows else ["- none"]

    rev = [
        "# Forecast Accuracy — Reviewer Summary",
        "",
        f"Project: Tropical World Nursery ({project_key} / 23-435-01 / 2026-June). "
        f"Conclusion: **{summary['conclusion']}**.",
        "",
        "Independent multi-method EAC estimates, backtest-calibrated, with an advisory "
        "`model_recommended_projected_cost` (floored to actuals, human-gated). The deterministic "
        "rule-based recommendation is unchanged.",
        "",
        f"- Codes with >=1 independent model: {summary['codes_with_independent_models']}/{summary['budget_codes']}",
        f"- Adequacy distribution: {summary['adequacy_distribution']}",
        f"- Confidence bands: {summary['confidence_band_distribution']}",
        f"- Backtest cohort: {summary['backtest_cohort_size']} codes; per-method MAPE in "
        "`backtest/backtest_accuracy_by_method.json`",
        f"- LLM narratives: {summary['llm_narratives_generated']} ({summary['llm_status']})",
        "",
        "## Top forecast-adequacy gaps (ERP vs independent model)",
        *_gap_lines(gaps, 10),
        "",
        "## Known limitations",
        "- Backtest calibration is from the near-complete cohort, applied corpus-wide.",
        "- Codes with no progress evidence fall back to the ERP baseline at low confidence.",
        "- Owner %-complete and CPI proxies treat progress as cost-proportional (advisory).",
        "",
    ]
    (out / "forecast_review_summary_accuracy.md").write_text("\n".join(rev), encoding="utf-8")
    exec_md = [
        "# Forecast Accuracy — Executive Summary",
        "",
        f"Project: Tropical World Nursery ({project_key} / 23-435-01 / 2026-June).",
        "",
        "Independent quantitative models now cross-check the ERP forecast. Accounting actuals remain "
        "truth; the model number is advisory and human-gated.",
        "",
        f"- Budget codes where ERP looks LOW vs model: {len(summary['budget_codes_forecast_likely_low'])}",
        f"- Budget codes where ERP looks HIGH vs model: {len(summary['budget_codes_forecast_likely_high'])}",
        f"- Backtest cohort: {summary['backtest_cohort_size']} completed codes scored for accuracy.",
        f"- Local-model advisory narratives: {summary['llm_narratives_generated']} ({summary['llm_status']}).",
        "",
        "## Most material adequacy gaps",
        *_gap_lines_exec(gaps, 8),
        "",
    ]
    (out / "executive_forecast_summary_accuracy.md").write_text("\n".join(exec_md), encoding="utf-8")


def _write_readme(out, project_key, meta, summary):
    md = [
        f"# forecast_accuracy_package_tropical ({meta['package_stamp']})",
        "",
        f"Forecast accuracy, ability & confidence layer for Tropical World Nursery ({project_key} / "
        "23-435-01 / 2026-June).",
        "",
        "Independent multi-method EAC/ETC estimates (burn-rate, owner %-complete, commitment floor, "
        "schedule ETC, CPI proxy) reconciled into an advisory `model_recommended_projected_cost` "
        "(always floored to accounting actuals, `requires_human_acceptance: true`), a backtest-"
        "calibrated 0-1 confidence, ERP forecast-adequacy flags, and an advisory local-Ollama "
        "narrative layer. The deterministic rule-based recommendation is read but never modified.",
        "",
        f"- Conclusion: **{summary['conclusion']}**",
        f"- Codes with independent models: {summary['codes_with_independent_models']}/{summary['budget_codes']}",
        f"- Backtest cohort: {summary['backtest_cohort_size']}; LLM: {summary['llm_status']} "
        f"({summary['llm_narratives_generated']} narratives)",
        "",
        "See `SCHEMA.md` and `validation_report.json`. The quantitative core is deterministic; the "
        "`llm/` narratives are advisory, model-generated, safety-scanned, and excluded from the "
        "determinism gate.",
        "",
    ]
    (out / "README.md").write_text("\n".join(md), encoding="utf-8")


def _write_schema(out):
    md = [
        "# Forecast Accuracy Package — Schema",
        "",
        "Money is Decimal-string (2dp). JSONL sorted by budget_code_key. Every EAC >= actual-to-date.",
        "",
        "## Files",
        "- `signal_bundle_by_budget_code.jsonl` (127) — assembled per-code signals (actuals, budget, "
        "burn, owner, procore, commitment, schedule, horizons, evidence_depth).",
        "- `eac_estimates_by_budget_code.jsonl` (127) — per code, the list of independent + ERP-baseline "
        "estimates (method, source, applicable, eac, etc, reliability, inputs).",
        "- `forecast_reconciliation_by_budget_code.jsonl` (127) — weighted `model_reconciled_eac`, "
        "advisory `model_recommended_projected_cost` (floored to actuals), range, divergence, contributions.",
        "- `forecast_confidence_by_budget_code.jsonl` (127) — calibrated 0-1 score, band, components, drivers.",
        "- `forecast_adequacy_by_budget_code.jsonl` (127) — ERP vs model: likely_low/adequate/likely_high/"
        "indeterminate + severity.",
        "- `forecast_accuracy_recommendations.jsonl` (127) — authoritative rule-based action + advisory "
        "model number + adequacy + confidence + `requires_human_acceptance`.",
        "- `backtest/backtest_accuracy_by_method.json` — per-method MAPE/bias + calibration weights + methodology.",
        "- `backtest/backtest_detail.jsonl` — per-code as-of reconstruction on the completed cohort.",
        "- `llm/forecast_narratives.jsonl` — advisory narratives (subset). `source` is `ollama:<model>` or "
        "`deterministic_template`. Advisory only; never a number.",
        "- `llm/llm_receipts.jsonl` — hash-only receipts (model, status, fallback_used, hashes, safety_passed).",
        "- `summaries/`, `audit/`, `manifest.json`, `input_inventory.json`, `validation_report.json`.",
        "",
        "## Rules",
        "- Accounting actuals are truth; every estimate and the model recommendation are floored to actuals.",
        "- The advisory model number never overwrites the authoritative rule-based recommendation.",
        "- LLM is advisory, JSON-validated, safety-scanned fail-closed, temp 0; excluded from determinism gate.",
        "- Backtest calibration multiplier = (1/(1+MAPE)) normalized to mean 1.0 over the completed cohort.",
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
