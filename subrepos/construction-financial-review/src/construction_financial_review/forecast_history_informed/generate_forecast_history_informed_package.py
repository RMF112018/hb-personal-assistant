"""Generate the additive historical-forecast-assumption evidence package for Tropical World Nursery.

Mines prior cash-flow and GC/GR forecast assumptions, validates each against CostEntries/Sage actual
cost, and emits ADVISORY recommendations, confidence/uncertainty shifts, monthly-shape signals and
probability-spread suggestions. Historical forecasts are prior-assumption evidence — never actuals,
never caps. Quantitative core is deterministic (frozen stamp); the optional local-Ollama narrative is
advisory, never numeric, and excluded from the determinism gate. Source data, the historical packages,
accepted packages, and SQLite are never mutated (DB opened read-only for a schema+counts inventory).

Run:
    PYTHONPATH=src python3 -m construction_financial_review.cli forecast-history-informed --project tropical \
        [--frozen-stamp YYYYMMDD_HHMMSS] [--out-root DIR] [--with-llm]
"""
from __future__ import annotations

import tempfile
from collections import Counter, OrderedDict
from datetime import datetime
from pathlib import Path

from ..common.hashing import sha256_file
from ..common.io import read_jsonl, write_json, write_jsonl
from ..common.safety import safety_scan
from ..forecast_intelligence import db_inventory
from . import (gcgr_proportionality, history_actual_validation, history_io, history_mapping,
               history_monthly_distribution, history_probability_adjustments, history_recommendations,
               history_reliability, history_signals, validation as fhi_validation)

DATA_FILES = (
    "historical_forecast_signal_by_budget_code.jsonl",
    "historical_forecast_monthly_curve_by_budget_code.jsonl",
    "historical_vs_actual_validation_by_budget_code.jsonl",
    "historical_assumption_reliability_by_budget_code.jsonl",
    "history_informed_forecast_adjustment_by_budget_code.jsonl",
    "history_informed_monthly_distribution_by_budget_code.jsonl",
    "history_informed_probability_adjustments_by_budget_code.jsonl",
    "forecast_history_informed_recommendations.jsonl",
    "historical_forecast_data_quality_warnings.jsonl",
    "project_history_informed_summary.json",
    "top_history_validated_assumptions.json",
    "top_history_contradicted_assumptions.json",
    "top_increasing_historical_exposures.json",
    "top_zero_remaining_candidates.json",
)

# Analytic audit files derived purely from inputs (deterministic; included in the determinism diff).
AUDIT_DATA_FILES = (
    "audit/history_mapping_audit.json",
    "audit/history_vs_actual_reconciliation.json",
    "audit/history_curve_shape_audit.json",
    "audit/gcgr_proportionality_audit.json",
)

WATCH_CODES = ("15-16-100", "03-01-025", "20-18-110")
TOP_N = 25


def _warn(project_key, key, cost_code, wtype, severity, message):
    return OrderedDict([("project_key", project_key), ("budget_code_key", key),
                        ("cost_code", cost_code), ("warning_type", wtype),
                        ("severity", severity), ("message", message)])


# --------------------------------------------------------------------------- pure deterministic build

def _build_collections(inputs: dict, project_key: str) -> dict:
    history_rows = inputs["history_rows"]
    index = inputs["index"]
    context_by = inputs["context_by"]
    intel = inputs["intel"]
    monthly = inputs["monthly"]
    probability = inputs["probability"]
    fhi_cfg = (inputs.get("_cfg") or {}).get("forecast_history_informed") or {}
    half_life = fhi_cfg.get("history_recency_half_life_months", 6)

    mapping_by_cc = history_mapping.build_mapping(history_rows, index)
    by_cc = history_mapping.group_history_by_cost_code(history_rows)
    reference_month = max((r.get("snapshot_month") for r in history_rows if r.get("snapshot_month")),
                          default=None)
    current_keys = set(index["keys"])

    signals, curves, validations, reliabilities = [], [], [], []
    adjustments, distributions, prob_adj, recs, warnings = [], [], [], [], []
    curve_shape_audit, recon_audit = [], []

    for cc, rows in by_cc.items():
        mp = mapping_by_cc[cc]
        key = mp.get("budget_code_key")
        signal = history_signals.build_signal(cc, rows, mp, project_key)
        signals.append(signal)
        curves.extend(history_signals.build_curve_rows(cc, rows, mp, project_key))
        v = history_actual_validation.build_validation(cc, rows, mp, context_by, intel, project_key)
        validations.append(v)
        rel = history_reliability.build_reliability(signal, v, intel, key, reference_month,
                                                    half_life, project_key)
        reliabilities.append(rel)
        adj = history_recommendations.build_adjustment(
            signal, v, rel, (intel.get("recommendations") or {}).get(key), context_by.get(key),
            fhi_cfg, project_key)
        adjustments.append(adj)
        dist = history_monthly_distribution.build_distribution(
            signal, v, rel, (monthly.get("monthly") or {}).get(key), fhi_cfg, project_key)
        distributions.append(dist)
        padj = history_probability_adjustments.build_probability_adjustment(
            signal, v, rel, (probability.get("sim_inputs") or {}).get(key),
            (probability.get("overrun") or {}).get(key), project_key)
        prob_adj.append(padj)
        recs.append(_recommendation_row(signal, v, rel, adj, project_key))
        curve_shape_audit.append(OrderedDict([
            ("cost_code", cc), ("budget_code_key", key),
            ("latest_curve_shape_class", signal.get("latest_curve_shape_class")),
            ("historical_pattern_class", signal.get("historical_pattern_class")),
            ("forecast_snapshot_count", signal.get("forecast_snapshot_count")),
        ]))
        recon_audit.append(OrderedDict([
            ("cost_code", cc), ("budget_code_key", key),
            ("historical_forecast_month", v.get("historical_forecast_month")),
            ("historical_forecasted_remaining_in_window", v.get("historical_forecasted_remaining_in_window")),
            ("cost_entries_actual_cost_in_window", v.get("cost_entries_actual_cost_in_window")),
            ("absolute_variance", v.get("absolute_variance")),
            ("validation_class", v.get("validation_class")),
        ]))
        warnings.extend(_code_warnings(cc, mp, project_key))

    # sort everything deterministically
    skey = lambda r: (r.get("budget_code_key") or "", r.get("cost_code") or "")  # noqa: E731
    signals.sort(key=skey); validations.sort(key=skey); reliabilities.sort(key=skey)
    adjustments.sort(key=skey); distributions.sort(key=skey); prob_adj.sort(key=skey)
    recs.sort(key=skey); curves.sort(key=lambda r: (r.get("budget_code_key") or "",
                                                     r.get("cost_code") or "", r.get("period_month") or ""))
    curve_shape_audit.sort(key=skey); recon_audit.sort(key=skey)

    # explicit watch-code presence reports (refinement: verify before reporting absent)
    presence = [history_mapping.check_code_presence(cc, history_rows, index, current_keys)
                for cc in WATCH_CODES]
    for pr in presence:
        if pr["absent_everywhere"]:
            warnings.append(_warn(project_key, None, pr["cost_code"], "code_absent_all_sources", "low",
                                  f"{pr['cost_code']} absent from cash-flow + GC/GR history, canonical "
                                  "BudgetDetails, and current forecast packages (verified)."))
    warnings.sort(key=lambda w: (w.get("cost_code") or "", w.get("warning_type") or ""))

    gcgr_audit = gcgr_proportionality.build_audit(inputs, mapping_by_cc, project_key)
    mapping_audit = OrderedDict([
        ("project_key", project_key),
        ("mapping_status_counts", dict(Counter(s["mapping_status"] for s in signals))),
        ("watch_code_presence", presence),
        ("by_cost_code", list(mapping_by_cc.values())),
    ])

    tops = _tops(signals, validations, reliabilities)
    summary = _summary(project_key, inputs, signals, validations, reliabilities, reference_month)

    out = {
        "historical_forecast_signal_by_budget_code.jsonl": signals,
        "historical_forecast_monthly_curve_by_budget_code.jsonl": curves,
        "historical_vs_actual_validation_by_budget_code.jsonl": validations,
        "historical_assumption_reliability_by_budget_code.jsonl": reliabilities,
        "history_informed_forecast_adjustment_by_budget_code.jsonl": adjustments,
        "history_informed_monthly_distribution_by_budget_code.jsonl": distributions,
        "history_informed_probability_adjustments_by_budget_code.jsonl": prob_adj,
        "forecast_history_informed_recommendations.jsonl": recs,
        "historical_forecast_data_quality_warnings.jsonl": warnings,
        "project_history_informed_summary.json": summary,
        "top_history_validated_assumptions.json": tops["validated"],
        "top_history_contradicted_assumptions.json": tops["contradicted"],
        "top_increasing_historical_exposures.json": tops["increasing"],
        "top_zero_remaining_candidates.json": tops["zero"],
        "audit/history_mapping_audit.json": mapping_audit,
        "audit/history_vs_actual_reconciliation.json": recon_audit,
        "audit/history_curve_shape_audit.json": curve_shape_audit,
        "audit/gcgr_proportionality_audit.json": gcgr_audit,
    }
    return out


def _recommendation_row(signal, v, rel, adj, project_key):
    return OrderedDict([
        ("project_key", project_key),
        ("budget_code_key", signal.get("budget_code_key")),
        ("cost_code", signal.get("cost_code")),
        ("mapping_status", signal.get("mapping_status")),
        ("historical_pattern_class", signal.get("historical_pattern_class")),
        ("validation_class", v.get("validation_class")),
        ("reliability_band", rel.get("reliability_band")),
        ("overall_history_reliability_score", rel.get("overall_history_reliability_score")),
        ("history_informed_direction", adj.get("history_informed_direction")),
        ("history_informed_adjusted_final_cost", adj.get("history_informed_adjusted_final_cost")),
        ("confidence_delta", adj.get("confidence_delta")),
        ("uncertainty_delta", adj.get("uncertainty_delta")),
        ("do_not_auto_apply", True),
        ("requires_human_acceptance", True),
    ])


def _code_warnings(cc, mp, project_key):
    out = []
    key = mp.get("budget_code_key")
    if mp.get("duplicate_cost_code_warning"):
        out.append(_warn(project_key, key, cc, "duplicate_cost_code", "medium",
                         f"{cc} appears with multiple descriptions: {mp.get('distinct_descriptions')}"))
    if mp.get("mapping_status") == "unmapped_absent_from_budget_details":
        out.append(_warn(project_key, key, cc, "unmapped_historical_code", "medium",
                         f"{cc} not present in canonical BudgetDetails; signal emitted unmapped."))
    if mp.get("mapping_status") == "cost_code_multi_category_rollup":
        out.append(_warn(project_key, key, cc, "multi_category_rollup", "low",
                         f"{cc} spans canonical categories {mp.get('candidate_budget_code_keys')}; "
                         "not force-mapped to a single category."))
    if mp.get("description_sensitive_review"):
        out.append(_warn(project_key, key, cc, "description_sensitive_10xx", "low",
                         f"{cc} is description-sensitive (GR vs non-GR); review before mapping."))
    return out


def _tops(signals, validations, reliabilities):
    rel_by = {(r["budget_code_key"], r["cost_code"]): r for r in reliabilities}
    val_by = {(v["budget_code_key"], v["cost_code"]): v for v in validations}

    def rel_score(s):
        r = rel_by.get((s["budget_code_key"], s["cost_code"]))
        return float(r["overall_history_reliability_score"]) if r else 0.0

    def vclass(s):
        v = val_by.get((s["budget_code_key"], s["cost_code"]))
        return v["validation_class"] if v else None

    def override(s):
        v = val_by.get((s["budget_code_key"], s["cost_code"]))
        return float(v["actual_trend_override_score"]) if v and v.get("actual_trend_override_score") else 0.0

    validated = sorted([s for s in signals if (vclass(s) or "").startswith("validated")],
                       key=lambda s: (-rel_score(s), s["cost_code"]))[:TOP_N]
    contradicted = sorted([s for s in signals if (vclass(s) or "").startswith("contradicted")],
                          key=lambda s: (-override(s), s["cost_code"]))[:TOP_N]
    increasing = sorted([s for s in signals if s.get("historical_pattern_class") == "increasing_exposure"],
                        key=lambda s: (float(s.get("historical_forecast_slope") or 0) * -1, s["cost_code"]))[:TOP_N]
    zero = sorted([s for s in signals
                   if s.get("historical_pattern_class") in ("stable_zero", "inactive")
                   and vclass(s) == "validated_zero_inactive"],
                  key=lambda s: (-float(s.get("zero_remaining_persistence_score") or 0), s["cost_code"]))[:TOP_N]
    pick = lambda lst: [OrderedDict([(k, s.get(k)) for k in  # noqa: E731
                                     ("budget_code_key", "cost_code", "historical_pattern_class",
                                      "latest_curve_shape_class", "historical_remaining_forecast_latest",
                                      "historical_forecast_slope", "zero_remaining_persistence_score")]
                                    + [("validation_class", vclass(s)),
                                       ("reliability_score", rel_score(s))]) for s in lst]
    return {"validated": pick(validated), "contradicted": pick(contradicted),
            "increasing": pick(increasing), "zero": pick(zero)}


def _summary(project_key, inputs, signals, validations, reliabilities, reference_month):
    return OrderedDict([
        ("project_key", project_key),
        ("reference_snapshot_month", reference_month),
        ("historical_cost_codes_analyzed", len(signals)),
        ("mapping_status_counts", dict(Counter(s["mapping_status"] for s in signals))),
        ("pattern_class_counts", dict(Counter(s["historical_pattern_class"] for s in signals))),
        ("validation_class_counts", dict(Counter(v["validation_class"] for v in validations))),
        ("reliability_band_counts", dict(Counter(r["reliability_band"] for r in reliabilities))),
        ("zero_remaining_validated_candidates",
         sum(1 for v in validations if v["validation_class"] == "validated_zero_inactive")),
        ("contradicted_assumptions",
         sum(1 for v in validations if (v["validation_class"] or "").startswith("contradicted"))),
        ("increasing_exposure_codes",
         sum(1 for s in signals if s["historical_pattern_class"] == "increasing_exposure")),
        ("count_reconciliation", inputs["count_reconciliation"]),
        ("source_packages", OrderedDict([
            ("cash_flow", inputs["cashflow_dir"].name if inputs["cashflow_dir"] else None),
            ("gcgr", inputs["gcgr_dir"].name if inputs["gcgr_dir"] else None),
            ("context", inputs["context_pkg"].name),
            ("intelligence", inputs["intelligence_pkg"].name),
            ("monthly", inputs["monthly_pkg"].name if inputs["monthly_pkg"] else None),
            ("probability", inputs["probability_pkg"].name if inputs["probability_pkg"] else None),
        ])),
        ("posture", "Historical forecast is prior-assumption evidence, never actual cost, never a cap. "
                    "CostEntries/Sage incurred cost is the primary reality check. All outputs are "
                    "advisory and require human acceptance; no accepted package is mutated."),
        ("requires_human_acceptance", True),
    ])


# --------------------------------------------------------------------------- write + orchestrate

def _write_collections(out: Path, collections: dict):
    for fname in DATA_FILES + AUDIT_DATA_FILES:
        payload = collections[fname]
        (out / fname).parent.mkdir(parents=True, exist_ok=True)
        if fname.endswith(".jsonl"):
            write_jsonl(out / fname, payload)
        else:
            write_json(out / fname, payload)


def _determinism_check(inputs, project_key) -> OrderedDict:
    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        p1, p2 = Path(d1), Path(d2)
        c1 = _build_collections(inputs, project_key)
        c2 = _build_collections(inputs, project_key)
        _write_collections(p1, c1)
        _write_collections(p2, c2)
        per_file, ok = [], True
        for fname in DATA_FILES + AUDIT_DATA_FILES:
            h1, h2 = sha256_file(p1 / fname), sha256_file(p2 / fname)
            same = h1 == h2
            ok = ok and same
            per_file.append(OrderedDict([("file", fname), ("sha256", h1), ("identical", same)]))
    return OrderedDict([
        ("performed", True), ("quantitative_core_byte_identical", ok),
        ("llm_excluded_from_byte_diff", True), ("diff_result", "pass" if ok else "fail"),
        ("per_file", per_file),
    ])


def _after_hashes(inputs) -> OrderedDict:
    before = inputs["source_hashes_before"]
    after = history_io.source_hashes(inputs["cashflow_dir"], inputs["gcgr_dir"])
    unchanged = before == after
    return OrderedDict([("before", before), ("after", after), ("unchanged", unchanged)])


def _source_files(inputs) -> OrderedDict:
    return OrderedDict([
        ("historical_cash_flow_package", inputs["cashflow_dir"].name if inputs["cashflow_dir"] else None),
        ("historical_gcgr_package", inputs["gcgr_dir"].name if inputs["gcgr_dir"] else None),
        ("forecast_context_package", inputs["context_pkg"].name),
        ("forecast_intelligence_package", inputs["intelligence_pkg"].name),
        ("forecast_monthly_package", inputs["monthly_pkg"].name if inputs["monthly_pkg"] else None),
        ("forecast_probability_package", inputs["probability_pkg"].name if inputs["probability_pkg"] else None),
        ("mutation_posture", "all inputs read-only; no source/Excel/SQLite/accepted-package mutation; "
                             "no live external calls (localhost Ollama only under --with-llm)"),
    ])


def _meta(command, inputs, stamp, generated_ts):
    return OrderedDict([
        ("generator", "construction_financial_review.forecast_history_informed."
                      "generate_forecast_history_informed_package"),
        ("command", command), ("package_stamp", stamp),
        ("generated_timestamp_local", generated_ts),
        ("project_key", inputs["project_key"]),
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
        ("manifest_title", "Forecast History-Informed Evidence Package — Tropical World Nursery"),
        ("manifest_version", "1.0.0"),
        ("project", OrderedDict([("project_key", project_key),
                                 ("project_name", "Tropical World Nursery Senior Living Facility"),
                                 ("job_reference", "23-435-01"), ("forecast_period", "2026-June")])),
        ("generation", meta), ("output_files", files),
        ("validation_status", OrderedDict([("passed", validation["passed"]),
                                           ("checks", validation["checks"])])),
        ("conclusion", conclusion),
    ])


def generate(project_key, cfg, data_root=None, frozen_stamp=None, out_root=None,
             with_llm=False, llm_model=None) -> dict:
    data_root = Path(data_root or cfg["default_data_root"])
    inputs = history_io.load_inputs(cfg, data_root, project_key)
    inputs["_cfg"] = cfg

    stamp = frozen_stamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    generated_ts = frozen_stamp if frozen_stamp else datetime.now().isoformat(timespec="seconds")
    out_base = Path(out_root) if out_root else data_root
    out = out_base / f"forecast_history_informed_package_tropical_{stamp}"
    out.mkdir(parents=True, exist_ok=False)
    (out / "audit").mkdir(exist_ok=True)
    (out / "llm").mkdir(exist_ok=True)

    collections = _build_collections(inputs, project_key)
    _write_collections(out, collections)
    determinism = _determinism_check(inputs, project_key)

    narratives, receipts, ollama_status = _run_llm(with_llm, cfg, llm_model,
                                                   collections["forecast_history_informed_recommendations.jsonl"],
                                                   generated_ts)
    write_jsonl(out / "llm" / "history_informed_narratives.jsonl", narratives)
    write_jsonl(out / "llm" / "history_informed_narrative_receipts.jsonl", receipts)

    command = (f"python3 -m construction_financial_review.cli forecast-history-informed "
               f"--project {project_key}" + (" --with-llm" if with_llm else ""))
    meta = _meta(command, inputs, stamp, generated_ts)

    audit = OrderedDict([
        ("history_mapping_audit", collections["audit/history_mapping_audit.json"]),
        ("history_vs_actual_reconciliation", collections["audit/history_vs_actual_reconciliation.json"]),
        ("history_curve_shape_audit", collections["audit/history_curve_shape_audit.json"]),
        ("gcgr_proportionality_audit", collections["audit/gcgr_proportionality_audit.json"]),
        ("source_hashes_before_after", _after_hashes(inputs)),
    ])
    write_json(out / "audit" / "source_hashes_before_after.json", audit["source_hashes_before_after"])
    write_json(out / "audit" / "historical_source_files_used.json", _source_files(inputs))
    db_inv = db_inventory.inventory(cfg, project_key)
    write_json(out / "audit" / "db_inventory.json", db_inv)
    write_json(out / "input_inventory.json", OrderedDict([("generation", meta),
                                                          ("source_files", _source_files(inputs))]))
    _write_readme(out, project_key, meta, inputs, collections)
    _write_schema(out)

    data_files = sorted(p for p in out.rglob("*") if p.is_file()
                        and p.name not in ("manifest.json", "validation_report.json"))
    safety = safety_scan(data_files)
    write_json(out / "audit" / "safety_scan_report.json", safety)
    validation = fhi_validation.build_validation(out, inputs, collections, audit, determinism, safety,
                                                 meta, bool(with_llm and ollama_status == "available"),
                                                 receipts)
    write_json(out / "validation_report.json", validation)
    conclusion = ("forecast_history_informed_ready" if validation["passed"]
                  else "forecast_history_informed_not_ready")
    write_json(out / "manifest.json", _manifest(out, project_key, meta, conclusion, validation))

    summary = collections["project_history_informed_summary.json"]
    return {"output_package": str(out), "validation_passed": validation["passed"],
            "safety_passed": safety["passed"], "determinism_passed": determinism["diff_result"] == "pass",
            "source_hashes_unchanged": audit["source_hashes_before_after"]["unchanged"],
            "llm_status": ollama_status, "llm_narratives_generated": len(narratives),
            "historical_cost_codes_analyzed": summary["historical_cost_codes_analyzed"],
            "zero_remaining_validated_candidates": summary["zero_remaining_validated_candidates"],
            "contradicted_assumptions": summary["contradicted_assumptions"]}


def _run_llm(with_llm, cfg, llm_model, recommendations, generated_ts):
    """Advisory only: short qualitative notes for the top reviewable codes. Never numeric."""
    if not with_llm:
        return [], [], "disabled"
    try:
        from ..forecast_accuracy.llm.client import OllamaClient
        from ..forecast_accuracy.llm import narrate
    except Exception:
        return [], [], "unavailable"
    llm_cfg = cfg.get("llm") or {}
    model = llm_model or llm_cfg.get("model", "qwen2.5:14b")
    client = OllamaClient(model=model, endpoint=llm_cfg.get("endpoint", "http://localhost:11434"),
                          temperature=float(llm_cfg.get("temperature", 0)),
                          seed=int(llm_cfg.get("seed", 7)), timeout=float(llm_cfg.get("timeout_seconds", 60)))
    up, _present = client.available()
    if not up:
        return [], [], "unavailable"
    backend = narrate.make_backend(client) if hasattr(narrate, "make_backend") else None
    narratives, receipts = [], []
    review = [r for r in recommendations
              if r.get("history_informed_direction") in ("defer_to_actuals_review", "suggest_increase_review")][:15]
    for r in review:
        facts = OrderedDict([
            ("budget_code_key", r.get("budget_code_key")), ("cost_code", r.get("cost_code")),
            ("historical_pattern_class", r.get("historical_pattern_class")),
            ("validation_class", r.get("validation_class")),
            ("reliability_band", r.get("reliability_band")),
            ("history_informed_direction", r.get("history_informed_direction")),
        ])
        try:
            nrow, rrow = narrate.narrate_one(facts, backend, model)
            narratives.append(nrow)
            receipts.append(rrow)
        except Exception:
            continue
    return narratives, receipts, "available"


def _write_readme(out, project_key, meta, inputs, collections):
    s = collections["project_history_informed_summary.json"]
    md = [
        f"# forecast_history_informed_package_tropical ({meta['package_stamp']})",
        "",
        "Additive historical-forecast-assumption evidence for Tropical World Nursery "
        f"({project_key} / 23-435-01 / 2026-June). Mines prior cash-flow + GC/GR forecasts, validates "
        "each against CostEntries/Sage actual cost, and surfaces ADVISORY recommendations, "
        "confidence/uncertainty shifts and monthly-shape signals. It does NOT replace or mutate any "
        "accepted package.",
        "",
        f"- Historical cost codes analyzed: {s['historical_cost_codes_analyzed']}.",
        f"- Mapping status: {s['mapping_status_counts']}.",
        f"- Validation classes: {s['validation_class_counts']}.",
        f"- Zero-remaining validated candidates: {s['zero_remaining_validated_candidates']}; "
        f"contradicted assumptions: {s['contradicted_assumptions']}; "
        f"increasing-exposure codes: {s['increasing_exposure_codes']}.",
        "",
        "**Posture.** Historical forecast is prior-assumption evidence — never actual cost, never a cap. "
        "CostEntries/Sage incurred cost is the primary reality check. Actual cost to date is the only "
        "hard floor; nothing is capped above any reference. The local LLM is advisory only (no numeric "
        "output) and excluded from the determinism gate. Every row requires human acceptance.",
        "",
        "See `historical_forecast_signal_by_budget_code.jsonl` (per-code remaining-forecast pattern + "
        "curve shape), `historical_vs_actual_validation_by_budget_code.jsonl` (prior assumption vs "
        "CostEntries actuals), `historical_assumption_reliability_by_budget_code.jsonl`, "
        "`history_informed_forecast_adjustment_by_budget_code.jsonl` (advisory, do-not-auto-apply), and "
        "`audit/gcgr_proportionality_audit.json` (GC-fee taper hypothesis). Quant core is deterministic "
        "(`validation_report.json` `determinism`); `audit/source_hashes_before_after.json` proves the "
        "historical packages were not mutated.",
        "",
    ]
    (out / "README.md").write_text("\n".join(md), encoding="utf-8")


def _write_schema(out):
    md = [
        "# Forecast History-Informed Evidence Package — Schema",
        "",
        "Money is Decimal-string (2dp); scores/weights are 4dp Decimal strings in [0,1]. Historical "
        "amounts are quantized at our JSON boundary; they are PRIOR-ASSUMPTION evidence, never actuals.",
        "",
        "## Key files",
        "- `historical_forecast_signal_by_budget_code.jsonl` — per historical cost code: mapping status/"
        "confidence, per-snapshot remaining-forecast latest/min/max/mean/stddev/slope, pattern class, "
        "latest curve-shape class, persistence/stability/volatility/signal-strength scores.",
        "- `historical_forecast_monthly_curve_by_budget_code.jsonl` — latest snapshot's monthly forecast "
        "curve (period_month, amount, curve_weight, curve_shape_class, source lineage).",
        "- `historical_vs_actual_validation_by_budget_code.jsonl` — prior remaining forecast vs CostEntries "
        "actual cost in the post-snapshot window: variance, inactivity, recent burns, escalation, "
        "credits, actual-trend override score, validation_class/confidence. CostEntries are truth.",
        "- `historical_assumption_reliability_by_budget_code.jsonl` — persistence/recency/stability/"
        "actual-validation/contradiction/schedule/invoice scores → overall reliability + band + reasons.",
        "- `history_informed_forecast_adjustment_by_budget_code.jsonl` — ADVISORY direction + adjustment "
        "(weighted by reliability; floored at actuals; never capped above any reference; do_not_auto_apply).",
        "- `history_informed_monthly_distribution_by_budget_code.jsonl` — advisory curve-shape monthly "
        "weight suggestions (schedule/actual-trend/invoice/history-curve), do_not_auto_apply.",
        "- `history_informed_probability_adjustments_by_budget_code.jsonl` — advisory sigma multiplier / "
        "tail-shift suggestions (tighten when validated, widen when contradicted); never edits the "
        "probability package.",
        "- `forecast_history_informed_recommendations.jsonl` + `top_*` rollups + "
        "`project_history_informed_summary.json` — reviewer-facing rollups.",
        "- `audit/*` — history_mapping_audit (incl. watch-code presence: 15-16-100 / 03-01-025 / "
        "20-18-110), history_vs_actual_reconciliation, history_curve_shape_audit, "
        "gcgr_proportionality_audit (GC-fee taper hypothesis; proportionality reported confirmed only "
        "when validated), source_hashes_before_after (no-mutation proof), db_inventory (schema+counts), "
        "safety_scan_report, historical_source_files_used. `llm/*` advisory only, excluded from determinism.",
        "",
        "## Rules",
        "- Historical forecast values are NEVER written as actual cost and NEVER used as a hard cap.",
        "- CostEntries/Sage incurred cost is the primary reality check; actual cost to date is the only "
        "hard floor; nothing is capped above ERP/budget/commitment/owner SOV/pay-app/prior forecast.",
        "- Cost-code-only history maps to canonical BudgetDetails only; multi-category codes are rollups "
        "(never force-mapped); absent codes are reported explicitly; duplicate same-sheet codes keep "
        "source-row + description lineage.",
        "- Every recommendation is advisory (`do_not_auto_apply`, `requires_human_acceptance`); no "
        "accepted intelligence/monthly/probability package is mutated.",
        "- Deterministic: same frozen stamp => byte-identical quantitative core + analytic audit files.",
        "",
    ]
    (out / "SCHEMA.md").write_text("\n".join(md), encoding="utf-8")


def run(project_key, cfg, data_root=None, frozen_stamp=None, out_root=None, with_llm=False,
        llm_model=None) -> int:
    import json
    res = generate(project_key, cfg, data_root=data_root, frozen_stamp=frozen_stamp, out_root=out_root,
                   with_llm=with_llm, llm_model=llm_model)
    print(json.dumps(OrderedDict([("status", "ok" if res["validation_passed"] else "validation_failed"),
                                  *res.items()]), indent=2))
    return 0 if res["validation_passed"] else 1
