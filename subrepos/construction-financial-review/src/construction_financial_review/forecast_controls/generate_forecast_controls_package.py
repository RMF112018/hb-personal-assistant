"""Generate the operator forecast-controls package for Tropical World Nursery.

Loads the operator control file, maps each control to a canonical budget code, resolves precedence
(accepted > pending) into applied decisions, and emits an auditable package: per-control rows,
application disposition, a monthly-adjustment preview (zero post-stop months, redistribute the allowed
remaining cost), a human-review queue, warnings, and fail-closed audits. Read-only against source
packages; never mutates source Excel, accepted packages, or SQLite; no live external calls. Deterministic
under a frozen stamp.

Run:
    PYTHONPATH=src python3 -m construction_financial_review.cli forecast-controls --project tropical \
        [--frozen-stamp YYYYMMDD_HHMMSS] [--out-root DIR]
"""
from __future__ import annotations

import tempfile
from collections import Counter, OrderedDict
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from ..common.hashing import sha256_file
from ..common.io import read_jsonl, write_json, write_jsonl
from ..common.money import D, dec, money_str
from ..common.safety import safety_scan
from ..schedule_analysis.schedule_mapping import build_canonical_index
from . import apply, integration
from . import validation as fctl_validation

SUBPROJECT_ROOT = Path(__file__).resolve().parents[3]
ZERO = Decimal("0")

DATA_FILES = (
    "forecast_controls_by_budget_code.jsonl",
    "forecast_controls_application_by_budget_code.jsonl",
    "forecast_controls_monthly_adjustments_by_budget_code.jsonl",
    "forecast_controls_review_queue.jsonl",
    "forecast_controls_warnings.jsonl",
    "project_forecast_controls_summary.json",
)
AUDIT_DATA_FILES = (
    "audit/control_mapping_audit.json",
    "audit/control_application_audit.json",
    "audit/actuals_floor_audit.json",
    "audit/no_hidden_cap_audit.json",
)


# --------------------------------------------------------------------------- discovery + inputs

def _latest_dir(data_root: Path, pattern: str):
    matches = sorted(p for p in data_root.glob(pattern) if p.is_dir())
    return matches[-1] if matches else None


def _discover(cfg: dict, data_root: Path) -> dict:
    ctx = None
    named = cfg.get("forecast_context_package")
    if named and (data_root / named).is_dir():
        ctx = data_root / named
    ctx = ctx or _latest_dir(data_root, "forecast_context_package_tropical_*")
    if not ctx:
        raise SystemExit(f"ERROR: required context package not found under {data_root}")
    return {
        "context": ctx,
        "intelligence": _latest_dir(data_root, "forecast_accuracy_next_package_tropical_*"),
        "monthly": _latest_dir(data_root, "forecast_monthly_package_tropical_*"),
    }


def _monthly_baseline(monthly_pkg: Path) -> dict:
    """Per-key baseline month rows + blended weights from a discovered monthly package (best effort)."""
    if not monthly_pkg:
        return {}
    fpath = monthly_pkg / "monthly_forecast_by_budget_code.jsonl"
    dpath = monthly_pkg / "remaining_work_monthly_distribution_by_budget_code.jsonl"
    if not fpath.exists():
        return {}
    rows_by_key = {}
    for r in read_jsonl(fpath):
        rows_by_key.setdefault(r["budget_code_key"], []).append(r)
    blended_by_key = {}
    if dpath.exists():
        for d in read_jsonl(dpath):
            blended_by_key[d["budget_code_key"]] = OrderedDict(
                (w["month"], D(w["weight"])) for w in (d.get("monthly_distribution_weights") or []))
    baseline = {}
    for key, rows in rows_by_key.items():
        rows = sorted(rows, key=lambda r: r["forecast_month"])
        months = [r["forecast_month"] for r in rows]
        blended = blended_by_key.get(key) or OrderedDict((m, Decimal("1")) for m in months)
        baseline[key] = {"month_costs": rows, "blended": OrderedDict((m, blended.get(m, ZERO)) for m in months)}
    return baseline


def load_inputs(cfg: dict, data_root: Path, project_key: str, stamp_iso: str | None) -> "OrderedDict":
    discovery = _discover(cfg, data_root)
    ctx = discovery["context"]
    budget_codes = list(read_jsonl(ctx / "canonical" / "budget_codes.jsonl"))
    canonical_keys = set(build_canonical_index(budget_codes)["keys"])

    context_rows = list(read_jsonl(ctx / "summaries" / "budget_code_forecast_context.jsonl"))
    actuals_by_key = {r["budget_code_key"]: D((r.get("actuals") or {}).get("actual_cost_all_source_to_date"))
                      for r in context_rows if r.get("budget_code_key")}

    rec_by_key = {}
    if discovery["intelligence"]:
        recf = discovery["intelligence"] / "forecast_recommendations_by_budget_code.jsonl"
        if recf.exists():
            rec_by_key = {r["budget_code_key"]: r for r in read_jsonl(recf) if r.get("budget_code_key")}

    bundle = integration.prepare(cfg, SUBPROJECT_ROOT, canonical_keys, actuals_by_key, project_key, stamp_iso)
    monthly_baseline = _monthly_baseline(discovery["monthly"])

    source_files = []
    for p in (ctx, discovery["intelligence"], discovery["monthly"]):
        if p:
            source_files.extend(sorted(p.rglob("*.jsonl"))[:200])
    cf = Path(bundle["load_result"]["control_file"])
    if cf.exists():
        source_files.append(cf)

    return OrderedDict([
        ("project_key", project_key), ("discovery", discovery),
        ("canonical_keys", canonical_keys), ("actuals_by_key", actuals_by_key),
        ("rec_by_key", rec_by_key), ("monthly_baseline", monthly_baseline),
        ("bundle", bundle), ("source_files", source_files[:400]),
        ("source_hashes_before", _source_hashes(source_files[:400])),
    ])


def _source_hashes(files) -> "OrderedDict":
    return OrderedDict((str(p), sha256_file(p) if Path(p).exists() else None) for p in files)


# --------------------------------------------------------------------------- pure build

def _monthly_adjustment_row(project_key, key, decision, rec, baseline) -> "OrderedDict":
    actual = D(rec.get("actual_cost_all_source_to_date"))
    model_rec_ctc = D(rec.get("recommended_cost_to_complete"))
    model_worst_ctc = D(rec.get("worst_credible_cost_to_complete"))
    model_final = D(rec.get("recommended_final_cost"))
    applied_rec_ctc, applied_worst_ctc, dollar = apply.effective_ctc(
        model_rec_ctc, model_worst_ctc, actual, decision)
    applied_final = actual + applied_rec_ctc

    preview, before, after, zeroed = False, [], [], []
    if baseline:
        base_reconcile = {
            "month_costs": baseline["month_costs"], "blended": baseline["blended"],
            "actual": actual, "recommended_final_cost": model_final,
            "worst_credible_final_cost": actual + model_worst_ctc,
            "recommended_cost_to_complete": model_rec_ctc,
            "worst_credible_cost_to_complete": model_worst_ctc,
            "current_projected_cost": dec(rec.get("current_projected_cost")),
            "revised_budget": dec(rec.get("revised_budget")),
            "monthly_forecast_basis": "model_monthly_baseline",
        }
        reshaped = apply.reshape_reconcile(base_reconcile, decision)
        before = [OrderedDict([("forecast_month", mc["forecast_month"]),
                               ("recommended_month_cost", mc["recommended_month_cost"])])
                  for mc in baseline["month_costs"]]
        after = [OrderedDict([("forecast_month", mc["forecast_month"]),
                              ("recommended_month_cost", mc["recommended_month_cost"])])
                 for mc in reshaped["month_costs"]]
        stop = decision.get("stop_month")
        zeroed = [mc["forecast_month"] for mc in reshaped["month_costs"]
                  if stop and mc["forecast_month"] > stop]
        preview = True

    return OrderedDict([
        ("project_key", project_key), ("budget_code_key", key), ("control_id", decision["control_id"]),
        ("control_type", decision["control_type"]), ("acceptance_status", decision["acceptance_status"]),
        ("stop_month", decision.get("stop_month")),
        ("actual_cost_to_date", money_str(actual)),
        ("model_recommended_cost_to_complete", money_str(model_rec_ctc)),
        ("applied_recommended_cost_to_complete", money_str(applied_rec_ctc)),
        ("model_recommended_final_cost", money_str(model_final)),
        ("applied_recommended_final_cost", money_str(applied_final)),
        ("dollars_remain_model_derived", bool(decision.get("dollars_model_derived"))),
        ("monthly_preview_available", preview),
        ("months_zeroed_after_stop", zeroed),
        ("before_month_costs", before), ("after_month_costs", after),
        ("note", "stop-date redistributes the model cost-to-complete through the stop window; "
                 "total remaining cost is model-derived unless an accepted amount is provided"),
    ])


def _build_collections(inputs: dict, project_key: str) -> dict:
    bundle = inputs["bundle"]
    load_result, resolved = bundle["load_result"], bundle["resolved"]
    mapping_results = bundle["mapping_results"]
    rec_by, baseline = inputs["rec_by_key"], inputs["monthly_baseline"]

    map_by_id = {m["control_id"]: m for m in mapping_results}
    app_by_id = {a["control_id"]: a for a in resolved["applications"]}

    control_rows = []
    for c in load_result["controls"]:
        m = map_by_id.get(c["control_id"], {})
        a = app_by_id.get(c["control_id"], {})
        row = OrderedDict(c)
        row["mapped_budget_code_key"] = m.get("mapped_budget_code_key")
        row["mapping_status"] = m.get("mapping_status")
        row["disposition"] = a.get("disposition")
        row["applied"] = a.get("applied", False)
        control_rows.append(row)
    control_rows.sort(key=lambda r: (r.get("mapped_budget_code_key") or "", r.get("control_id") or ""))

    adjustments = []
    for key, decision in resolved["by_key"].items():
        adjustments.append(_monthly_adjustment_row(project_key, key, decision,
                                                   rec_by.get(key, {}), baseline.get(key)))
    adjustments.sort(key=lambda r: (r["budget_code_key"] or "", r["control_id"] or ""))

    summary = OrderedDict([
        ("project_key", project_key),
        ("control_file", load_result["control_file"]),
        ("control_count", load_result["control_count"]),
        ("acceptance_counts", resolved["counts"]),
        ("applied_control_count", len(resolved["by_key"])),
        ("controlled_budget_codes", resolved["controlled_budget_codes"]),
        ("timing_only_count", sum(1 for d in resolved["by_key"].values()
                                  if d.get("timing_applied") and not d.get("dollar_applied"))),
        ("dollar_applied_count", sum(1 for d in resolved["by_key"].values() if d.get("dollar_applied"))),
        ("dollars_model_derived_count", sum(1 for d in resolved["by_key"].values()
                                            if d.get("dollars_model_derived"))),
        ("review_queue_count", len(resolved["review_queue"])),
        ("warning_count", len(resolved["warnings"])),
        ("mapping_status_counts", dict(Counter(m["mapping_status"] for m in mapping_results))),
        ("requires_human_acceptance", True),
        ("note", "operator controls are explicit human decisions; pending posture-changing controls are "
                 "queued only; CostEntries actuals are truth and actual cost to date is the only floor"),
    ])

    floor_violations = resolved["floor_violations"]
    dollar_apps = [a for a in resolved["applications"] if a["dollar_applied"]]
    audits = {
        "audit/control_mapping_audit.json": OrderedDict([
            ("project_key", project_key),
            ("by_mapping_status", dict(Counter(m["mapping_status"] for m in mapping_results))),
            ("ambiguous", [m["control_id"] for m in mapping_results if m["mapping_status"] == "ambiguous_cost_code"]),
            ("invented", [m["control_id"] for m in mapping_results
                          if m["mapping_status"] == "invented_budget_code_key"]),
            ("mapping_rows", mapping_results),
            ("rule", "explicit budget_code_key must be canonical; cost_code resolves only when unique")]),
        "audit/control_application_audit.json": OrderedDict([
            ("project_key", project_key),
            ("by_disposition", dict(Counter(a["disposition"] for a in resolved["applications"]))),
            ("applied_count", len(resolved["by_key"])),
            ("lineage_complete", all(a.get("control_id") and ("disposition" in a)
                                     for a in resolved["applications"])),
            ("superseded", resolved["superseded"]),
            ("controlled_budget_codes", resolved["controlled_budget_codes"])]),
        "audit/actuals_floor_audit.json": OrderedDict([
            ("project_key", project_key),
            ("all_floors_respected", not floor_violations),
            ("floor_violations", floor_violations),
            ("rule", "no accepted control may set final cost below actual cost to date; "
                     "actual cost to date is the only hard floor")]),
        "audit/no_hidden_cap_audit.json": OrderedDict([
            ("project_key", project_key),
            ("no_hidden_cap", all(a["acceptance_status"] == "accepted" for a in dollar_apps)),
            ("dollar_changes", [OrderedDict([("control_id", a["control_id"]),
                                             ("budget_code_key", a["budget_code_key"]),
                                             ("acceptance_status", a["acceptance_status"]),
                                             ("source", a["source"])]) for a in dollar_apps]),
            ("rule", "any dollar change must be tied to an explicit accepted operator control with a "
                     "source/reason; stop-date timing without an accepted amount keeps dollars model-derived")]),
    }

    out = {
        "forecast_controls_by_budget_code.jsonl": control_rows,
        "forecast_controls_application_by_budget_code.jsonl": resolved["applications"],
        "forecast_controls_monthly_adjustments_by_budget_code.jsonl": adjustments,
        "forecast_controls_review_queue.jsonl": resolved["review_queue"],
        "forecast_controls_warnings.jsonl": resolved["warnings"],
        "project_forecast_controls_summary.json": summary,
    }
    out.update(audits)
    return out


# --------------------------------------------------------------------------- write + orchestrate

def _write_collections(out: Path, collections: dict):
    for fname in DATA_FILES + AUDIT_DATA_FILES:
        payload = collections[fname]
        (out / fname).parent.mkdir(parents=True, exist_ok=True)
        if fname.endswith(".jsonl"):
            write_jsonl(out / fname, payload)
        else:
            write_json(out / fname, payload)


def _determinism_check(inputs, project_key) -> "OrderedDict":
    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        p1, p2 = Path(d1), Path(d2)
        _write_collections(p1, _build_collections(inputs, project_key))
        _write_collections(p2, _build_collections(inputs, project_key))
        per_file, ok = [], True
        for fname in DATA_FILES + AUDIT_DATA_FILES:
            h1, h2 = sha256_file(p1 / fname), sha256_file(p2 / fname)
            same = h1 == h2
            ok = ok and same
            per_file.append(OrderedDict([("file", fname), ("sha256", h1), ("identical", same)]))
    return OrderedDict([("performed", True), ("quantitative_core_byte_identical", ok),
                        ("diff_result", "pass" if ok else "fail"), ("per_file", per_file)])


def generate(project_key, cfg, data_root=None, frozen_stamp=None, out_root=None,
             with_llm=False, llm_model=None) -> dict:
    data_root = Path(data_root or cfg["default_data_root"])
    stamp = frozen_stamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    generated_ts = frozen_stamp if frozen_stamp else datetime.now().isoformat(timespec="seconds")
    stamp_iso = frozen_stamp or generated_ts

    inputs = load_inputs(cfg, data_root, project_key, stamp_iso)

    out_base = Path(out_root) if out_root else data_root
    out = out_base / f"forecast_controls_package_tropical_{stamp}"
    out.mkdir(parents=True, exist_ok=False)
    (out / "audit").mkdir(exist_ok=True)

    collections = _build_collections(inputs, project_key)
    _write_collections(out, collections)
    determinism = _determinism_check(inputs, project_key)

    command = f"python3 -m construction_financial_review.cli forecast-controls --project {project_key}"
    meta = OrderedDict([
        ("generator", "construction_financial_review.forecast_controls.generate_forecast_controls_package"),
        ("command", command), ("package_stamp", stamp), ("generated_timestamp_local", generated_ts),
        ("project_key", project_key)])

    after = _source_hashes(inputs["source_files"])
    src_audit = OrderedDict([("before", inputs["source_hashes_before"]), ("after", after),
                             ("unchanged", inputs["source_hashes_before"] == after)])
    write_json(out / "audit" / "source_hashes_before_after.json", src_audit)
    write_json(out / "input_inventory.json", OrderedDict([
        ("generation", meta),
        ("control_file", inputs["bundle"]["load_result"]["control_file"]),
        ("control_file_present", inputs["bundle"]["load_result"]["present"]),
        ("discovery", OrderedDict([("context", str(inputs["discovery"]["context"])),
                                   ("intelligence", str(inputs["discovery"]["intelligence"]) if inputs["discovery"]["intelligence"] else None),
                                   ("monthly", str(inputs["discovery"]["monthly"]) if inputs["discovery"]["monthly"] else None)]))]))
    _write_readme(out, project_key, meta, collections, inputs)
    _write_schema(out)

    data_files = sorted(p for p in out.rglob("*") if p.is_file()
                        and p.name not in ("manifest.json", "validation_report.json"))
    safety = safety_scan(data_files)
    write_json(out / "audit" / "safety_scan_report.json", safety)

    audit = OrderedDict([
        ("control_mapping_audit", collections["audit/control_mapping_audit.json"]),
        ("control_application_audit", collections["audit/control_application_audit.json"]),
        ("actuals_floor_audit", collections["audit/actuals_floor_audit.json"]),
        ("no_hidden_cap_audit", collections["audit/no_hidden_cap_audit.json"]),
        ("source_hashes_before_after", src_audit)])
    validation = fctl_validation.build_validation(out, inputs["bundle"]["load_result"],
                                                  inputs["bundle"]["resolved"], collections, audit,
                                                  determinism, safety, meta, src_audit["unchanged"])
    write_json(out / "validation_report.json", validation)
    conclusion = "forecast_controls_ready" if validation["passed"] else "forecast_controls_not_ready"
    write_json(out / "manifest.json", _manifest(out, project_key, meta, conclusion, validation))

    return {"output_package": str(out), "validation_passed": validation["passed"],
            "safety_passed": safety["passed"], "determinism_passed": determinism["diff_result"] == "pass",
            "source_hashes_unchanged": src_audit["unchanged"],
            "control_count": validation["control_count"],
            "applied_control_count": validation["applied_control_count"],
            "controlled_budget_codes": validation["controlled_budget_codes"],
            "acceptance_counts": validation["acceptance_counts"]}


def _manifest(out, project_key, meta, conclusion, validation):
    files = []
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name != "manifest.json":
            rows = sum(1 for _ in read_jsonl(p)) if p.suffix == ".jsonl" else None
            files.append(OrderedDict([("path", str(p.relative_to(out))), ("size_bytes", p.stat().st_size),
                                      ("row_count", rows), ("sha256", sha256_file(p))]))
    return OrderedDict([
        ("package_name", out.name),
        ("manifest_title", "Operator Forecast Controls Package — Tropical World Nursery"),
        ("manifest_version", "1.0.0"),
        ("project", OrderedDict([("project_key", project_key),
                                 ("project_name", "Tropical World Nursery Senior Living Facility"),
                                 ("job_reference", "23-435-01"), ("forecast_period", "2026-June")])),
        ("generation", meta), ("output_files", files),
        ("validation_status", OrderedDict([("passed", validation["passed"]),
                                           ("checks", validation["checks"])])),
        ("conclusion", conclusion)])


def _write_readme(out, project_key, meta, collections, inputs):
    s = collections["project_forecast_controls_summary.json"]
    md = [
        f"# forecast_controls_package_tropical ({meta['package_stamp']})",
        "",
        "Operator-controlled forecast stop-date / closeout-constraint layer for Tropical World Nursery "
        f"({project_key} / 23-435-01 / 2026-June). Loads the operator control file, maps each control to "
        "a canonical budget code, resolves precedence (accepted > pending), and emits applied decisions, "
        "a monthly-adjustment preview, a human-review queue, warnings, and fail-closed audits. It does "
        "NOT mutate source Excel, accepted packages, or SQLite, and makes no live external calls.",
        "",
        f"- Control file: `{s['control_file']}`.",
        f"- Controls: {s['control_count']} ({s['acceptance_counts']}); applied: {s['applied_control_count']} "
        f"(timing-only {s['timing_only_count']}, dollar {s['dollar_applied_count']}, "
        f"dollars-model-derived {s['dollars_model_derived_count']}).",
        f"- Controlled budget codes: {s['controlled_budget_codes']}.",
        f"- Review-queue items: {s['review_queue_count']}; warnings: {s['warning_count']}; "
        f"mapping: {s['mapping_status_counts']}.",
        "",
        "**Posture.** Controls are explicit operator decisions with source, reason, and acceptance "
        "metadata — never model truth. A posture-changing control (post-stop zeroing or a dollar change) "
        "applies ONLY when human-accepted; pending controls surface in the review queue without changing "
        "the forecast. CostEntries/Sage incurred cost is accounting truth and actual cost to date is the "
        "only hard floor — no hidden caps. When a stop-date control has no accepted remaining/final "
        "amount, the model cost-to-complete is redistributed through the stop window and the dollar total "
        "is flagged as still model-derived.",
        "",
        "**Precedence.** When multiple controls target one budget code, the accepted control is applied "
        "and pending controls are recorded as superseded (latest control_id wins within a tier). "
        "Stop dates use month-level proration with `zero_after_stop_month` (the stop month is kept; "
        "months strictly after it are zeroed).",
        "",
    ]
    (out / "README.md").write_text("\n".join(md), encoding="utf-8")


def _write_schema(out):
    md = [
        "# Operator Forecast Controls Package — Schema",
        "",
        "Money is Decimal-string (2dp) or null. Controls are advisory operator decisions; posture changes "
        "apply only when `acceptance_status = accepted`.",
        "",
        "## Key files",
        "- `forecast_controls_by_budget_code.jsonl` — every operator control (normalized) joined to its "
        "mapped canonical `budget_code_key`, `mapping_status`, and `disposition`.",
        "- `forecast_controls_application_by_budget_code.jsonl` — per-control resolution: applied / "
        "timing_applied / dollar_applied / dollars_remain_model_derived, stop_month, accepted amounts, "
        "actuals floor, disposition, superseded_by, lineage.",
        "- `forecast_controls_monthly_adjustments_by_budget_code.jsonl` — per applied decision: model vs "
        "applied cost-to-complete + final cost, months zeroed after the stop, and a before/after monthly "
        "vector preview (when a monthly package is discoverable).",
        "- `forecast_controls_review_queue.jsonl` — pending / superseded / unmapped / floor-violation "
        "controls for human review (priority + reason).",
        "- `forecast_controls_warnings.jsonl` — model-derived-dollars, mapping-failure, and floor warnings.",
        "- `project_forecast_controls_summary.json` — counts + controlled budget codes.",
        "- `audit/control_mapping_audit.json`, `audit/control_application_audit.json`, "
        "`audit/actuals_floor_audit.json`, `audit/no_hidden_cap_audit.json`, "
        "`audit/source_hashes_before_after.json`, `audit/safety_scan_report.json`.",
        "",
        "## Control types",
        "- `closeout_stop_date`, `forecast_stop_date`, `inactive_after_date` — timing/stop-date controls.",
        "- `remaining_cost_allowance`, `accepted_final_cost_override` — dollar controls (accepted only).",
        "- `monthly_distribution_override` — timing reshape (accepted only); `watch_only` — monitor, no change.",
        "",
        "## Rules",
        "- Explicit `budget_code_key` must be canonical; a `cost_code`-only control resolves only when "
        "unique, else it is ambiguous and fails closed.",
        "- Posture-changing controls apply only when accepted; pending controls are queued, not applied.",
        "- Accepted final/remaining cost may never fall below actual cost to date (only hard floor).",
        "- No hidden caps: any dollar change is tied to an explicit accepted operator control.",
        "- Deterministic: same frozen stamp + same inputs => byte-identical quantitative core + audits.",
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
