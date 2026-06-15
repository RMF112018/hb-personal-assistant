"""Generate the deterministic cost-frequency / billing-cadence evidence package for Tropical World Nursery.

Classifies each canonical code's cost-incurrence cadence from real CostEntries, recognizes the configured
weekly internal-staffing codes, computes weekday-normalized staffing daily rates from the latest COMPLETE
actual month, revalidates cadence against the most recent actuals, and emits advisory monthly phasing
(staffing projections are scaled to the accepted cost-to-complete, preserving the weekday shape — never
changing any accepted final cost). Quant core is deterministic (frozen stamp + data-derived window); the
optional local-Ollama narrative is advisory, never numeric, and excluded from the determinism gate.
Inputs are read-only; no source / accepted package / SQLite is mutated.

Run:
    PYTHONPATH=src python3 -m construction_financial_review.cli forecast-cost-frequency --project tropical \
        [--frozen-stamp YYYYMMDD_HHMMSS] [--out-root DIR] [--with-llm]
"""
from __future__ import annotations

import tempfile
from collections import Counter, OrderedDict
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from ..common.hashing import sha256_file
from ..common.io import read_jsonl, write_json, write_jsonl
from ..common.money import D, money_str
from ..common.safety import safety_scan
from ..forecast_intelligence import db_inventory
from . import (
    daily_rate,
    frequency_detect,
    frequency_io,
    frequency_revalidation,
    staffing_codes,
    weekday_calendar,
)
from . import monthly_frequency_phasing as phasing
from . import validation as fcf_validation

CONTRACT_VERSION = "1.0.0"

DATA_FILES = (
    "cost_frequency_by_budget_code.jsonl",
    "cost_entry_cadence_observations_by_budget_code.jsonl",
    "internal_staffing_daily_rate_by_budget_code.jsonl",
    "weekday_calendar_by_forecast_month.jsonl",
    "frequency_revalidation_by_budget_code.jsonl",
    "frequency_adjusted_monthly_phasing_by_budget_code.jsonl",
    "frequency_adjusted_monthly_project_forecast.jsonl",
    "cadence_change_warnings.jsonl",
    "forecast_cost_frequency_recommendations.jsonl",
    "project_cost_frequency_summary.json",
)
AUDIT_DATA_FILES = (
    "audit/frequency_detection_audit.json",
    "audit/staffing_code_policy_audit.json",
)
ZERO = Decimal("0")
STAFFING_PLAN_GLOB = "forecast_staffing_plan_package_tropical_*"


def _load_staffing_plan(data_root: Path) -> dict:
    """Read the latest staffing-plan package bridge (read-only). Returns {budget_code_key: summary_row}.

    The operator staffing plan is a stronger forward-looking timing source than historical cadence for
    the mapped .LAB codes; cadence classification is preserved here for diagnostics.
    """
    matches = sorted(p for p in Path(data_root).glob(STAFFING_PLAN_GLOB) if p.is_dir())
    if not matches:
        return {}
    fpath = matches[-1] / "staffing_plan_summary_by_budget_code.jsonl"
    if not fpath.exists():
        return {}
    return {r["budget_code_key"]: r for r in read_jsonl(fpath) if r.get("budget_code_key")}


# --------------------------------------------------------------------------- pure deterministic build

def _build_collections(inputs: dict, project_key: str) -> dict:
    cfg_fcf = (inputs.get("_cfg") or {}).get("forecast_cost_frequency") or {}
    window = inputs["window"]
    months = window["months"]
    boundary = window["latest_complete_month_boundary"]
    context_by, rec_by, txn_by = inputs["context_by"], inputs["rec_by"], inputs["txn_dates_by"]
    staffing_plan_by = inputs.get("staffing_plan_by_key") or {}

    freq_rows, obs_rows, rate_rows, reval_rows = [], [], [], []
    phasing_rows, recs, warnings = [], [], []
    project_month_proj = OrderedDict((m, ZERO) for m in months)

    for bc in sorted(inputs["budget_codes"], key=lambda r: r["budget_code_key"]):
        key = bc["budget_code_key"]
        cost_code, category = bc.get("cost_code"), bc.get("category")
        is_staffing = staffing_codes.is_internal_staffing_code(key, cfg_fcf)
        ctx = context_by.get(key, {})
        monthly_actuals = (ctx.get("actuals") or {}).get("monthly_actuals") or []
        txn_dates = txn_by.get(key, [])

        detected = frequency_detect.classify(monthly_actuals, txn_dates, boundary, cfg_fcf, is_staffing)
        reval = frequency_revalidation.revalidate(detected, cfg_fcf, boundary, is_staffing,
                                                  project_key, key, cost_code)
        effective = "weekly_internal_staffing" if is_staffing \
            else reval["revalidated_effective_frequency_class"]
        cadence_source = "configured" if is_staffing else detected["cadence_source"]

        rate = daily_rate.compute(monthly_actuals, boundary, cfg_fcf, project_key, key, cost_code, category)
        ctc = (rec_by.get(key) or {}).get("recommended_cost_to_complete")
        prow = phasing.phasing_row(project_key, key, cost_code, category, is_staffing, effective,
                                   detected["frequency_confidence"], months, rate.get("daily_rate"), ctc)
        phasing_rows.append(prow)
        cadence_material = effective in ("weekly_internal_staffing", "weekly_observed")
        sp_row = staffing_plan_by.get(key)
        staffing_plan_present = bool(sp_row)

        # accumulate the project-level staffing projection (scaled to CTC; timing only)
        if is_staffing and rate.get("daily_rate") is not None:
            raw = phasing.staffing_projection(rate["daily_rate"], months)
            scaled, _, _ = phasing.scale_to_ctc(raw, ctc)
            for m in months:
                project_month_proj[m] += scaled[m]
            rate_rows.append(rate)

        freq_rows.append(OrderedDict([
            ("project_key", project_key),
            ("budget_code_key", key),
            ("cost_code", cost_code),
            ("category", category),
            ("is_internal_staffing_code", is_staffing),
            ("configured_frequency_override", "weekly_internal_staffing" if is_staffing else None),
            ("observed_frequency_class", detected["observed_frequency_class"]),
            ("effective_frequency_class", effective),
            ("cadence_source", cadence_source),
            ("frequency_confidence", detected["frequency_confidence"]),
            ("months_observed", detected["months_observed"]),
            ("recent_months_observed", detected["recent_months_observed"]),
            ("entry_count_by_month", detected["entry_count_by_month"]),
            ("transaction_level_costentries_available",
             detected["transaction_level_costentries_available"]),
            ("monthly_aggregate_fallback_used", detected["monthly_aggregate_fallback_used"]),
            ("latest_complete_month", rate.get("latest_complete_month")),
            ("latest_complete_month_actual_cost", rate.get("latest_complete_month_actual_cost")),
            ("latest_complete_month_weekdays", rate.get("latest_complete_month_weekdays")),
            ("daily_rate", rate.get("daily_rate") if is_staffing else None),
            ("daily_rate_basis", rate.get("daily_rate_basis") if is_staffing else "non_staffing_code"),
            ("daily_rate_confidence", rate.get("daily_rate_confidence") if is_staffing else "n/a"),
            ("cadence_change_detected", reval["cadence_change_detected"]),
            ("cadence_change_basis", reval["cadence_change_basis"]),
            ("cadence_materially_changed_monthly_phasing", cadence_material),
            ("staffing_projection_scaled_to_ctc", prow["staffing_projection_scaled_to_ctc"]),
            ("recommended_monthly_phasing_basis", prow["recommended_monthly_phasing_basis"]),
            ("staffing_plan_present", staffing_plan_present),
            ("forward_looking_timing_source",
             "operator_staffing_plan" if staffing_plan_present
             else ("cost_frequency_cadence" if cadence_material else "model_default")),
            ("staffing_plan_supersedes_cadence_for_future_months", staffing_plan_present),
            ("cadence_classification_preserved_for_diagnostics", True),
            ("requires_human_acceptance", True),
        ]))
        obs_rows.append(frequency_detect.observation_row(project_key, key, cost_code, category, detected))
        reval_rows.append(reval)
        if reval["cadence_change_detected"]:
            warnings.append(OrderedDict([
                ("project_key", project_key), ("budget_code_key", key), ("cost_code", cost_code),
                ("warning_type", "cadence_change"), ("severity", "low"),
                ("message", reval["cadence_change_basis"]),
                ("documented_observed_frequency_class", reval["documented_observed_frequency_class"]),
                ("revalidated_effective_frequency_class",
                 reval["revalidated_effective_frequency_class"]),
            ]))
        if is_staffing and rate.get("rate_volatility_flag"):
            warnings.append(OrderedDict([
                ("project_key", project_key), ("budget_code_key", key), ("cost_code", cost_code),
                ("warning_type", "staffing_rate_volatility"), ("severity", "low"),
                ("message", f"{cost_code} latest-complete daily rate {rate.get('daily_rate')} diverges "
                            f">25% from trailing-6mo {rate.get('trailing_6mo_daily_rate')}."),
            ]))
        recs.append(OrderedDict([
            ("project_key", project_key), ("budget_code_key", key), ("cost_code", cost_code),
            ("is_internal_staffing_code", is_staffing),
            ("effective_frequency_class", effective),
            ("recommended_monthly_phasing_basis", prow["recommended_monthly_phasing_basis"]),
            ("cadence_change_detected", reval["cadence_change_detected"]),
            ("staffing_plan_supersedes_cadence", staffing_plan_present),
            ("do_not_change_accepted_final_cost", True),
            ("requires_human_acceptance", True),
        ]))

    skey = lambda r: (r.get("budget_code_key") or "", r.get("cost_code") or "")  # noqa: E731
    for lst in (freq_rows, obs_rows, rate_rows, reval_rows, phasing_rows, recs):
        lst.sort(key=skey)
    warnings.sort(key=lambda w: (w.get("cost_code") or "", w.get("warning_type") or ""))

    weekday_cal = weekday_calendar.calendar_rows(months, project_key)
    project_forecast = [OrderedDict([
        ("project_key", project_key), ("forecast_month", m),
        ("weekday_count", weekday_calendar.weekdays_in_month(m)),
        ("internal_staffing_scaled_monthly_projection", money_str(project_month_proj[m])),
    ]) for m in months]

    detection_audit = OrderedDict([
        ("project_key", project_key),
        ("forecast_window", window),
        ("transaction_level_costentries_available", inputs["transaction_level_available"]),
        ("observed_frequency_class_counts",
         dict(Counter(r["observed_frequency_class"] for r in freq_rows))),
        ("effective_frequency_class_counts",
         dict(Counter(r["effective_frequency_class"] for r in freq_rows))),
        ("cadence_source_counts", dict(Counter(r["cadence_source"] for r in freq_rows))),
        ("monthly_aggregate_fallback_codes",
         [r["budget_code_key"] for r in freq_rows if r["monthly_aggregate_fallback_used"]]),
    ])
    policy_audit = staffing_codes.policy_audit(cfg_fcf, set(inputs["index"]["keys"]), project_key)

    summary = _summary(project_key, inputs, freq_rows, rate_rows, warnings, project_forecast)

    return {
        "cost_frequency_by_budget_code.jsonl": freq_rows,
        "cost_entry_cadence_observations_by_budget_code.jsonl": obs_rows,
        "internal_staffing_daily_rate_by_budget_code.jsonl": rate_rows,
        "weekday_calendar_by_forecast_month.jsonl": weekday_cal,
        "frequency_revalidation_by_budget_code.jsonl": reval_rows,
        "frequency_adjusted_monthly_phasing_by_budget_code.jsonl": phasing_rows,
        "frequency_adjusted_monthly_project_forecast.jsonl": project_forecast,
        "cadence_change_warnings.jsonl": warnings,
        "forecast_cost_frequency_recommendations.jsonl": recs,
        "project_cost_frequency_summary.json": summary,
        "audit/frequency_detection_audit.json": detection_audit,
        "audit/staffing_code_policy_audit.json": policy_audit,
    }


def _summary(project_key, inputs, freq_rows, rate_rows, warnings, project_forecast) -> OrderedDict:
    staffing_rows = [r for r in freq_rows if r["is_internal_staffing_code"]]
    rates = [D(r["daily_rate"]) for r in rate_rows if r.get("daily_rate") is not None]
    return OrderedDict([
        ("project_key", project_key),
        ("forecast_window", inputs["window"]),
        ("canonical_codes_analyzed", len(freq_rows)),
        ("internal_staffing_codes_recognized", len(staffing_rows)),
        ("transaction_level_costentries_available", inputs["transaction_level_available"]),
        ("observed_frequency_class_counts",
         dict(Counter(r["observed_frequency_class"] for r in freq_rows))),
        ("effective_frequency_class_counts",
         dict(Counter(r["effective_frequency_class"] for r in freq_rows))),
        ("codes_with_cadence_change", sum(1 for r in freq_rows if r["cadence_change_detected"])),
        ("staffing_daily_rate_summary", OrderedDict([
            ("rated_staffing_codes", len(rates)),
            ("min_daily_rate", str(min(rates)) if rates else None),
            ("max_daily_rate", str(max(rates)) if rates else None),
        ])),
        ("internal_staffing_scaled_project_forecast_by_month", project_forecast),
        ("posture", "Cadence is timing/shape evidence from CostEntries (accounting truth). It never "
                    "creates or changes any accepted final cost; staffing projections are scaled to the "
                    "accepted cost-to-complete, preserving weekday shape. All rows require human "
                    "acceptance."),
        ("package_contract", OrderedDict([
            ("contract_version", CONTRACT_VERSION),
            ("consumable_by", "forecast_comprehensive"),
            ("primary_artifacts", [
                "cost_frequency_by_budget_code.jsonl",
                "frequency_adjusted_monthly_phasing_by_budget_code.jsonl",
                "internal_staffing_daily_rate_by_budget_code.jsonl",
                "weekday_calendar_by_forecast_month.jsonl",
            ]),
            ("phasing_weight_key", "monthly_phasing_weights[].weight (per forecast_month, sums to 1)"),
            ("effective_class_field", "effective_frequency_class"),
            ("timing_only_guarantee", "do_not_change_accepted_final_cost == true on every phasing row"),
        ])),
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
    after = frequency_io.source_hashes(inputs["source_files"])
    return OrderedDict([("before", before), ("after", after), ("unchanged", before == after)])


def _source_files_audit(inputs) -> OrderedDict:
    return OrderedDict([
        ("forecast_context_package", inputs["context_pkg"].name),
        ("accepted_forecast_intelligence_package", inputs["accepted_pkg"].name),
        ("schedule_package", inputs["schedule_pkg"].name if inputs["schedule_pkg"] else None),
        ("input_files", [p.name for p in inputs["source_files"]]),
        ("mutation_posture", "all inputs read-only; no source/Excel/SQLite/accepted-package mutation; "
                             "no live external calls (localhost Ollama only under --with-llm)"),
    ])


def _meta(command, inputs, stamp, generated_ts) -> OrderedDict:
    return OrderedDict([
        ("generator", "construction_financial_review.forecast_cost_frequency."
                      "generate_forecast_cost_frequency_package"),
        ("command", command), ("package_stamp", stamp),
        ("generated_timestamp_local", generated_ts),
        ("project_key", inputs["project_key"]),
        ("contract_version", CONTRACT_VERSION),
    ])


def _manifest(out, project_key, meta, conclusion, validation) -> OrderedDict:
    files = []
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name != "manifest.json":
            rows = sum(1 for _ in read_jsonl(p)) if p.suffix == ".jsonl" else None
            files.append(OrderedDict([("path", str(p.relative_to(out))), ("size_bytes", p.stat().st_size),
                                      ("row_count", rows), ("sha256", sha256_file(p))]))
    return OrderedDict([
        ("package_name", out.name),
        ("manifest_title", "Cost-Frequency / Billing-Cadence Evidence Package — Tropical World Nursery"),
        ("manifest_version", "1.0.0"),
        ("contract_version", CONTRACT_VERSION),
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
    inputs = frequency_io.load_inputs(cfg, data_root, project_key)
    inputs["_cfg"] = cfg
    inputs["staffing_plan_by_key"] = _load_staffing_plan(data_root)

    stamp = frozen_stamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    generated_ts = frozen_stamp if frozen_stamp else datetime.now().isoformat(timespec="seconds")
    out_base = Path(out_root) if out_root else data_root
    out = out_base / f"forecast_cost_frequency_package_tropical_{stamp}"
    out.mkdir(parents=True, exist_ok=False)
    (out / "audit").mkdir(exist_ok=True)
    (out / "llm").mkdir(exist_ok=True)

    collections = _build_collections(inputs, project_key)
    _write_collections(out, collections)
    determinism = _determinism_check(inputs, project_key)

    narratives, receipts, ollama_status = _run_llm(with_llm, cfg, llm_model,
                                                   collections["forecast_cost_frequency_recommendations.jsonl"],
                                                   generated_ts)
    write_jsonl(out / "llm" / "cost_frequency_narratives.jsonl", narratives)
    write_jsonl(out / "llm" / "cost_frequency_narrative_receipts.jsonl", receipts)

    command = (f"python3 -m construction_financial_review.cli forecast-cost-frequency "
               f"--project {project_key}" + (" --with-llm" if with_llm else ""))
    meta = _meta(command, inputs, stamp, generated_ts)

    audit = OrderedDict([
        ("frequency_detection_audit", collections["audit/frequency_detection_audit.json"]),
        ("staffing_code_policy_audit", collections["audit/staffing_code_policy_audit.json"]),
        ("source_hashes_before_after", _after_hashes(inputs)),
    ])
    write_json(out / "audit" / "source_hashes_before_after.json", audit["source_hashes_before_after"])
    write_json(out / "audit" / "source_files_used.json", _source_files_audit(inputs))
    write_json(out / "audit" / "staffing_plan_consumption.json", OrderedDict([
        ("project_key", project_key),
        ("staffing_plan_present", bool(inputs["staffing_plan_by_key"])),
        ("staffing_plan_budget_codes", sorted(inputs["staffing_plan_by_key"].keys())),
        ("rule", "for mapped staffing .LAB codes the operator staffing plan is the forward-looking "
                 "timing source (stronger than historical cadence); cadence classification is preserved "
                 "as diagnostic and the accepted final cost is never changed by this slice"),
    ]))
    db_inv = db_inventory.inventory(cfg, project_key)
    write_json(out / "audit" / "db_inventory.json", db_inv)
    write_json(out / "input_inventory.json", OrderedDict([("generation", meta),
                                                          ("forecast_window", inputs["window"]),
                                                          ("source_files", _source_files_audit(inputs))]))
    _write_readme(out, project_key, meta, collections)
    _write_schema(out)

    data_files = sorted(p for p in out.rglob("*") if p.is_file()
                        and p.name not in ("manifest.json", "validation_report.json"))
    safety = safety_scan(data_files)
    write_json(out / "audit" / "safety_scan_report.json", safety)
    validation = fcf_validation.build_validation(out, inputs, collections, audit, determinism, safety,
                                                meta, bool(with_llm and ollama_status == "available"),
                                                receipts)
    write_json(out / "validation_report.json", validation)
    conclusion = ("forecast_cost_frequency_ready" if validation["passed"]
                  else "forecast_cost_frequency_not_ready")
    write_json(out / "manifest.json", _manifest(out, project_key, meta, conclusion, validation))

    summary = collections["project_cost_frequency_summary.json"]
    return {"output_package": str(out), "validation_passed": validation["passed"],
            "safety_passed": safety["passed"], "determinism_passed": determinism["diff_result"] == "pass",
            "source_hashes_unchanged": audit["source_hashes_before_after"]["unchanged"],
            "llm_status": ollama_status, "llm_narratives_generated": len(narratives),
            "canonical_codes_analyzed": summary["canonical_codes_analyzed"],
            "internal_staffing_codes_recognized": summary["internal_staffing_codes_recognized"],
            "codes_with_cadence_change": summary["codes_with_cadence_change"],
            "forecast_window": f'{inputs["window"]["forecast_start_month"]}..'
                               f'{inputs["window"]["forecast_end_month"]}'}


def _run_llm(with_llm, cfg, llm_model, recommendations, generated_ts):
    """Advisory only: short qualitative notes for staffing / cadence-change codes. Never numeric."""
    if not with_llm:
        return [], [], "disabled"
    try:
        from ..forecast_accuracy.llm import narrate
        from ..forecast_accuracy.llm.client import OllamaClient
    except Exception:
        return [], [], "unavailable"
    llm_cfg = cfg.get("llm") or {}
    model = llm_model or llm_cfg.get("model", "qwen2.5:14b")
    client = OllamaClient(model=model, endpoint=llm_cfg.get("endpoint", "http://localhost:11434"),
                          temperature=float(llm_cfg.get("temperature", 0)),
                          seed=int(llm_cfg.get("seed", 7)), timeout=float(llm_cfg.get("timeout_seconds", 60)))
    up, _present = client.available() if hasattr(client, "available") else (False, False)
    if not up:
        return [], [], "unavailable"
    backend = narrate.make_backend(client) if hasattr(narrate, "make_backend") else None
    narratives, receipts = [], []
    review = [r for r in recommendations
              if r.get("is_internal_staffing_code") or r.get("cadence_change_detected")][:15]
    for r in review:
        facts = OrderedDict([
            ("budget_code_key", r.get("budget_code_key")), ("cost_code", r.get("cost_code")),
            ("effective_frequency_class", r.get("effective_frequency_class")),
            ("recommended_monthly_phasing_basis", r.get("recommended_monthly_phasing_basis")),
            ("cadence_change_detected", r.get("cadence_change_detected")),
        ])
        try:
            nrow, rrow = narrate.narrate_one(facts, backend, model)
            narratives.append(nrow)
            receipts.append(rrow)
        except Exception:
            continue
    return narratives, receipts, "available"


def _write_readme(out, project_key, meta, collections):
    s = collections["project_cost_frequency_summary.json"]
    w = s["forecast_window"]
    md = [
        f"# forecast_cost_frequency_package_tropical ({meta['package_stamp']})",
        "",
        "Deterministic cost-frequency / billing-cadence evidence for Tropical World Nursery "
        f"({project_key} / 23-435-01 / 2026-June). Classifies each canonical code's incurrence cadence "
        "from real CostEntries (transaction dates + per-month entry counts), recognizes the configured "
        "weekly internal-staffing codes, computes weekday-normalized staffing daily rates from the "
        "latest COMPLETE actual month, revalidates cadence against recent actuals, and emits ADVISORY "
        "monthly phasing.",
        "",
        f"- Forecast window: {w['forecast_start_month']}..{w['forecast_end_month']} "
        f"(latest complete month boundary {w['latest_complete_month_boundary']}).",
        f"- Canonical codes analyzed: {s['canonical_codes_analyzed']}; internal staffing codes "
        f"recognized: {s['internal_staffing_codes_recognized']}.",
        f"- Effective cadence classes: {s['effective_frequency_class_counts']}.",
        f"- Codes with a cadence change surfaced: {s['codes_with_cadence_change']}.",
        "",
        "**Posture.** CostEntries/Sage incurred cost is accounting truth. Cadence is timing/shape "
        "evidence only — it never creates or changes any accepted final cost. Staffing projections are "
        "scaled to the accepted cost-to-complete, preserving the weekday shape. The local LLM is "
        "advisory only (no numeric output) and excluded from the determinism gate. Every row requires "
        "human acceptance.",
        "",
        "**Consumed by `forecast_comprehensive`** via the stable package contract in "
        "`project_cost_frequency_summary.json` (`package_contract`, `contract_version`): the per-code "
        "`effective_frequency_class` + `monthly_phasing_weights` in "
        "`frequency_adjusted_monthly_phasing_by_budget_code.jsonl`, staffing daily rates, and the "
        "weekday calendar. The same pure phasing logic is already wired into `forecast_monthly`.",
        "",
    ]
    (out / "README.md").write_text("\n".join(md), encoding="utf-8")


def _write_schema(out):
    md = [
        "# Cost-Frequency / Billing-Cadence Evidence Package — Schema",
        "",
        "Money is Decimal-string (2dp); weights/rates are Decimal strings. Cadence is PRIOR timing "
        "evidence from CostEntries — never an actual, never a cap, never a change to any accepted final "
        "cost.",
        "",
        "## Key files",
        "- `cost_frequency_by_budget_code.jsonl` — per canonical code: staffing flag, configured "
        "override, observed + effective cadence class, cadence source (configured/observed/inferred), "
        "confidence, months/recent-months observed, per-month entry counts, transaction-level "
        "availability + monthly-aggregate-fallback flags, latest-complete-month + weekday-normalized "
        "daily rate (staffing), cadence-change flag/basis, whether cadence materially changed phasing, "
        "whether the staffing projection was scaled to CTC, recommended phasing basis.",
        "- `cost_entry_cadence_observations_by_budget_code.jsonl` — the entry-count cadence evidence.",
        "- `internal_staffing_daily_rate_by_budget_code.jsonl` — staffing daily rates + trailing "
        "3/6-month weekday-normalized comparison + volatility flag.",
        "- `weekday_calendar_by_forecast_month.jsonl` — weekday (Mon-Fri) count per forecast month.",
        "- `frequency_revalidation_by_budget_code.jsonl` — documented vs most-recent cadence; "
        "cadence-change detection.",
        "- `frequency_adjusted_monthly_phasing_by_budget_code.jsonl` — advisory normalized monthly "
        "phasing weights (weekday-normalized for staffing/weekly; even for monthly/twice; none "
        "otherwise) + staffing raw vs scaled-to-CTC projection. `do_not_change_accepted_final_cost`.",
        "- `frequency_adjusted_monthly_project_forecast.jsonl` — project-level staffing scaled "
        "projection by month (timing only).",
        "- `cadence_change_warnings.jsonl`, `forecast_cost_frequency_recommendations.jsonl`, "
        "`project_cost_frequency_summary.json` (carries the consumable `package_contract`).",
        "- `audit/*` — frequency_detection_audit, staffing_code_policy_audit (found/missing), "
        "source_hashes_before_after (no-mutation proof), source_files_used, db_inventory, "
        "safety_scan_report. `llm/*` advisory only, excluded from determinism.",
        "",
        "## Rules",
        "- CostEntries/Sage incurred cost is the only actual-cost source; cadence never becomes an "
        "actual and never changes any accepted final cost (timing/shape only).",
        "- Configured weekly internal-staffing override is the authoritative effective cadence.",
        "- Staffing daily rate = latest COMPLETE month actual cost / weekdays in that month; the partial "
        "current month is never the rate basis.",
        "- Staffing forecast = daily rate x weekdays per forecast month, scaled to accepted CTC "
        "(weekday shape preserved).",
        "- No staff-change events are fabricated (future-ready placeholder only).",
        "- Deterministic: same frozen stamp + data-derived window => byte-identical quantitative core.",
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
