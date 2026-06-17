"""Generate the operator staffing-plan forecast package for Tropical World Nursery.

Discovers + validates the extracted staffing JSON package, resolves each source cost code to a canonical
``.LAB`` budget-code key (LAB-only numeric; the family is date-context only), and emits an auditable
package: the per-code BRIDGE (actual / accepted final+CTC / plan-implied final+CTC / deltas), BOTH the
plan-implied and current-CTC-reconciled monthly forecasts, a mapping review queue, conflicts (incl. a
stale-CTC class), warnings, and fail-closed audits. Read-only against the source package and all accepted
packages; never mutates source Excel, the staffing JSON package, accepted packages, or SQLite; no live
external calls. Deterministic under a frozen stamp.

Run:
    PYTHONPATH=src python3 -m construction_financial_review.cli forecast-staffing-plan --project tropical \
        [--frozen-stamp YYYYMMDD_HHMMSS] [--out-root DIR]
"""
from __future__ import annotations

import tempfile
from collections import Counter, OrderedDict
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from ..common import lineage
from ..common.hashing import sha256_file
from ..common.io import read_jsonl, write_json, write_jsonl
from ..common.money import D, money_str
from ..common.safety import safety_scan
from ..schedule_analysis.schedule_mapping import build_canonical_index
from . import integration
from . import validation as sp_validation

SUBPROJECT_ROOT = Path(__file__).resolve().parents[3]
ZERO = Decimal("0")

DATA_FILES = (
    "staffing_plan_source_inventory.json",
    "staffing_plan_assignments_normalized.jsonl",
    "staffing_plan_mapping_by_cost_code.jsonl",
    "staffing_plan_mapping_review_queue.jsonl",
    "staffing_plan_monthly_by_budget_code.jsonl",
    "staffing_plan_monthly_by_cost_code.jsonl",
    "staffing_plan_monthly_project_forecast.jsonl",
    "staffing_plan_summary_by_budget_code.jsonl",
    "staffing_plan_summary_by_person.jsonl",
    "staffing_plan_conflicts.jsonl",
    "staffing_plan_warnings.jsonl",
    "project_staffing_plan_summary.json",
)
AUDIT_DATA_FILES = (
    "audit/mapping_audit.json",
    "audit/monthly_reconciliation_audit.json",
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
        "cost_frequency": _latest_dir(data_root, "forecast_cost_frequency_package_tropical_*"),
    }


def _horizon_end(monthly_pkg: Path) -> str | None:
    if not monthly_pkg:
        return None
    fpath = monthly_pkg / "monthly_forecast_by_budget_code.jsonl"
    if not fpath.exists():
        return None
    months = {r.get("forecast_month") for r in read_jsonl(fpath) if r.get("forecast_month")}
    return max(months) if months else None


def _freq_basis(cost_freq_pkg: Path) -> dict:
    if not cost_freq_pkg:
        return {}
    fpath = cost_freq_pkg / "cost_frequency_by_budget_code.jsonl"
    if not fpath.exists():
        return {}
    return {r["budget_code_key"]: r.get("effective_frequency_class")
            for r in read_jsonl(fpath) if r.get("budget_code_key")}


def load_inputs(cfg: dict, data_root: Path, project_key: str, stamp_iso: str | None) -> "OrderedDict":
    discovery = _discover(cfg, data_root)
    ctx = discovery["context"]
    budget_codes = list(read_jsonl(ctx / "canonical" / "budget_codes.jsonl"))
    canonical_index = build_canonical_index(budget_codes)

    context_rows = list(read_jsonl(ctx / "summaries" / "budget_code_forecast_context.jsonl"))
    actuals_by_key, monthly_actuals_by_key = {}, {}
    for r in context_rows:
        k = r.get("budget_code_key")
        if not k:
            continue
        actuals = r.get("actuals") or {}
        actuals_by_key[k] = D(actuals.get("actual_cost_all_source_to_date"))
        monthly_actuals_by_key[k] = actuals.get("monthly_actuals") or []

    rec_by_key = {}
    if discovery["intelligence"]:
        recf = discovery["intelligence"] / "forecast_recommendations_by_budget_code.jsonl"
        if recf.exists():
            rec_by_key = {r["budget_code_key"]: r for r in read_jsonl(recf) if r.get("budget_code_key")}

    horizon_end = _horizon_end(discovery["monthly"])
    freq_basis = _freq_basis(discovery["cost_frequency"])

    bundle = integration.prepare(
        cfg, SUBPROJECT_ROOT, data_root, budget_codes, actuals_by_key, rec_by_key, project_key,
        stamp_iso=stamp_iso, monthly_actuals_by_key=monthly_actuals_by_key,
        forecast_horizon_end=horizon_end, freq_basis_by_key=freq_basis)

    source_files = []
    pkg_path = bundle["discovery"].get("package_path")
    if pkg_path:
        source_files.extend(sorted(Path(pkg_path).rglob("*"))[:200])
    mf = Path(bundle["mapping_load"]["mapping_file"])
    if mf.exists():
        source_files.append(mf)

    return OrderedDict([
        ("project_key", project_key), ("discovery", discovery),
        ("canonical_index", canonical_index), ("horizon_end", horizon_end),
        ("bundle", bundle), ("source_files", source_files[:400]),
        ("source_hashes_before", _source_hashes(source_files[:400])),
    ])


def _source_hashes(files) -> "OrderedDict":
    return OrderedDict((str(p), sha256_file(p) if Path(p).is_file() else None) for p in files)


# --------------------------------------------------------------------------- pure build

def _build_collections(inputs: dict, project_key: str) -> dict:
    bundle = inputs["bundle"]
    discovery_src = bundle["discovery"]
    parsed = discovery_src.get("parsed") or {}
    mapping_results = bundle["mapping_results"]
    resolved = bundle["resolved"]
    map_by_cc = {m["source_cost_code"]: m for m in mapping_results}

    # source inventory
    source_inventory = OrderedDict([
        ("project_key", project_key),
        ("source_package_name", discovery_src.get("package_name")),
        ("source_package_path", discovery_src.get("package_path")),
        ("source_validation_passed", discovery_src.get("source_validation_passed")),
        ("source_hashes_verified", discovery_src.get("source_hashes_verified")),
        ("manifest_counts_match", discovery_src.get("manifest_counts_match")),
        ("monthly_totals_reconcile", discovery_src.get("monthly_totals_reconcile")),
        ("monthly_reconciliation_detail", discovery_src.get("monthly_reconciliation_detail")),
        ("manifest", parsed.get("manifest")),
        ("mapping_file", bundle["mapping_load"]["mapping_file"]),
        ("mapping_present", bundle["mapping_load"]["present"]),
        ("note", "read-only ingestion; the source Excel and staffing JSON package are never mutated"),
    ])

    # enriched normalized assignments (source rows + mapping annotation; source not mutated)
    assignments = []
    for r in parsed.get("normalized") or []:
        m = map_by_cc.get(r.get("cost_code"), {})
        row = OrderedDict(r)
        row["numeric_target_budget_code_key"] = m.get("numeric_target_budget_code_key")
        row["mapping_status"] = m.get("mapping_status")
        row["applied_numeric"] = bool(m.get("applied_numeric"))
        assignments.append(row)
    assignments.sort(key=lambda r: (r.get("cost_code") or "", str(r.get("assignment_id") or "")))

    # monthly by cost code (source + mapping annotation)
    monthly_cc = []
    for r in parsed.get("monthly_by_cost_code") or []:
        m = map_by_cc.get(r.get("cost_code"), {})
        row = OrderedDict(r)
        row["numeric_target_budget_code_key"] = m.get("numeric_target_budget_code_key")
        row["mapping_status"] = m.get("mapping_status")
        row["applied_numeric"] = bool(m.get("applied_numeric"))
        monthly_cc.append(row)
    monthly_cc.sort(key=lambda r: r.get("cost_code") or "")

    # project monthly forecast (source + applied-numeric-only rollup)
    applied_by_month = OrderedDict()
    for d in resolved["by_key"].values():
        for m, v in d["implied_monthly"].items():
            applied_by_month[m] = applied_by_month.get(m, ZERO) + v
    project_rows = []
    for r in parsed.get("project_forecast") or []:
        mo = r.get("month")
        project_rows.append(OrderedDict([
            ("project_key", project_key), ("month", mo),
            ("source_staffing_forecast_amount", money_str(D(r.get("forecast_amount")))),
            ("applied_numeric_staffing_forecast_amount", money_str(applied_by_month.get(mo, ZERO))),
        ]))
    project_rows.sort(key=lambda r: r["month"] or "")

    # summary by person (source passthrough)
    person_rows = sorted((OrderedDict(r) for r in parsed.get("summary_by_person") or []),
                         key=lambda r: str(r.get("person_name") or r.get("person_display_name") or ""))

    summary = _project_summary(project_key, discovery_src, resolved, mapping_results)

    audits = _audits(project_key, resolved, mapping_results)

    out = {
        "staffing_plan_source_inventory.json": source_inventory,
        "staffing_plan_assignments_normalized.jsonl": assignments,
        "staffing_plan_mapping_by_cost_code.jsonl": sorted(mapping_results,
                                                           key=lambda r: r["source_cost_code"]),
        "staffing_plan_mapping_review_queue.jsonl": resolved["review_queue"],
        "staffing_plan_monthly_by_budget_code.jsonl": resolved["monthly_by_budget_code"],
        "staffing_plan_monthly_by_cost_code.jsonl": monthly_cc,
        "staffing_plan_monthly_project_forecast.jsonl": project_rows,
        "staffing_plan_summary_by_budget_code.jsonl": resolved["summary_by_budget_code"],
        "staffing_plan_summary_by_person.jsonl": person_rows,
        "staffing_plan_conflicts.jsonl": resolved["conflicts"],
        "staffing_plan_warnings.jsonl": resolved["warnings"],
        "project_staffing_plan_summary.json": summary,
    }
    out.update(audits)
    return out


def _project_summary(project_key, discovery_src, resolved, mapping_results) -> "OrderedDict":
    by_key = resolved["by_key"]
    delta_ctc_total = sum((d["plan_implied_remaining_cost"] - d["accepted_cost_to_complete"]
                           for d in by_key.values() if d["accepted_cost_to_complete"] is not None), ZERO)
    return OrderedDict([
        ("project_key", project_key),
        ("source_package_name", discovery_src.get("package_name")),
        ("plan_cost_code_count", resolved["counts"]["plan_cost_codes"]),
        ("applied_numeric_code_count", resolved["counts"]["applied_numeric_codes"]),
        ("applied_budget_codes", resolved["applied_budget_codes"]),
        ("mapping_status_counts", resolved["counts"]),
        ("applied_plan_remaining_total", resolved["applied_total"]),
        ("applied_delta_vs_accepted_ctc_total", money_str(delta_ctc_total)),
        ("codes_requiring_operator_acceptance",
         sorted(k for k, d in by_key.items() if d["requires_operator_acceptance"])),
        ("review_queue_count", len(resolved["review_queue"])),
        ("conflict_count", len(resolved["conflicts"])),
        ("conflict_class_counts", dict(Counter(c["conflict_class"] for c in resolved["conflicts"]))),
        ("warning_count", len(resolved["warnings"])),
        ("requires_human_acceptance", True),
        ("note", "staffing dollars are LAB-only; .LBN/.MAT receive date-context evidence only. Plan-implied "
                 "final-cost changes are advisory until operator acceptance; actuals are the only floor."),
    ])


def _audits(project_key, resolved, mapping_results) -> dict:
    by_key = resolved["by_key"]
    floor_rows = [OrderedDict([("budget_code_key", k),
                               ("actual_cost_to_date", money_str(d["actual_cost_to_date"])),
                               ("plan_implied_final_cost", money_str(d["plan_implied_final_cost"])),
                               ("floor_respected", d["plan_implied_final_cost"] >= d["actual_cost_to_date"])])
                  for k, d in sorted(by_key.items())]
    return {
        "audit/mapping_audit.json": OrderedDict([
            ("project_key", project_key),
            ("by_mapping_status", dict(Counter(m["mapping_status"] for m in mapping_results))),
            ("numeric_target_is_lab_only", all(
                (m.get("numeric_target_budget_code_key") or ".LAB").endswith(".LAB")
                for m in mapping_results if m.get("applied_numeric"))),
            ("date_context_family_recorded", all(bool(m.get("date_context_target_budget_code_keys"))
                                                 for m in mapping_results if m.get("applied_numeric"))),
            ("mapping_rows", mapping_results),
            ("rule", "numeric staffing dollars apply only to a uniquely-resolved .LAB key confirmed by an "
                     "accepted operator override; .LBN/.MAT are date-context only; nothing fabricated")]),
        "audit/monthly_reconciliation_audit.json": OrderedDict([
            ("project_key", project_key),
            ("reconciliation_failures", resolved["reconciliation_failures"]),
            ("all_reconciled", not resolved["reconciliation_failures"]),
            ("per_code", [OrderedDict([
                ("budget_code_key", k),
                ("plan_implied_remaining_cost", money_str(d["plan_implied_remaining_cost"])),
                ("implied_monthly_sum", money_str(sum(d["implied_monthly"].values(), ZERO))),
                ("accepted_cost_to_complete",
                 money_str(d["accepted_cost_to_complete"]) if d["accepted_cost_to_complete"] is not None else None),
                ("ctc_reconciled_monthly_sum",
                 money_str(sum(d["ctc_reconciled_monthly"].values(), ZERO)) if d["ctc_reconciled_monthly"]
                 is not None else None)])
                for k, d in sorted(by_key.items())]),
            ("rule", "plan-implied monthly Σ == plan source total; ctc-reconciled monthly Σ == accepted CTC")]),
        "audit/actuals_floor_audit.json": OrderedDict([
            ("project_key", project_key),
            ("all_floors_respected", all(r["floor_respected"] for r in floor_rows)),
            ("floor_violations", resolved["floor_violations"]),
            ("per_code", floor_rows),
            ("rule", "staffing-plan implied final cost may never fall below actual cost to date")]),
        "audit/no_hidden_cap_audit.json": OrderedDict([
            ("project_key", project_key),
            ("no_hidden_cap", True),
            ("rule", "the staffing-plan implied final cost is actual + plan remaining; it is never reduced "
                     "by any reference (budget / projected / owner SOV / ERP / prior forecast); only "
                     "floored at actuals"),
            ("note", "plan-implied final-cost changes are advisory and require explicit operator acceptance")]),
    }


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
    cfg, _ctx_pkg, ctx_lineage = lineage.pin_context_into_cfg(cfg, data_root, project_key)
    stamp = frozen_stamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    generated_ts = frozen_stamp if frozen_stamp else datetime.now().isoformat(timespec="seconds")
    stamp_iso = frozen_stamp or generated_ts

    inputs = load_inputs(cfg, data_root, project_key, stamp_iso)
    bundle = inputs["bundle"]
    # fail closed before writing anything if the plan is unsafe
    integration.assert_integration_safe(cfg, bundle)

    out_base = Path(out_root) if out_root else data_root
    out = out_base / f"forecast_staffing_plan_package_tropical_{stamp}"
    out.mkdir(parents=True, exist_ok=False)
    (out / "audit").mkdir(exist_ok=True)

    collections = _build_collections(inputs, project_key)
    _write_collections(out, collections)
    determinism = _determinism_check(inputs, project_key)

    command = f"python3 -m construction_financial_review.cli forecast-staffing-plan --project {project_key}"
    meta = OrderedDict([
        ("generator", "construction_financial_review.forecast_staffing_plan."
                      "generate_forecast_staffing_plan_package"),
        ("command", command), ("package_stamp", stamp), ("generated_timestamp_local", generated_ts),
        ("project_key", project_key)])

    after = _source_hashes(inputs["source_files"])
    src_audit = OrderedDict([("before", inputs["source_hashes_before"]), ("after", after),
                             ("unchanged", inputs["source_hashes_before"] == after)])
    write_json(out / "audit" / "source_hashes_before_after.json", src_audit)
    write_json(out / "input_inventory.json", OrderedDict([
        ("generation", meta),
        ("context_lineage", ctx_lineage),
        ("staffing_source_package", bundle["discovery"].get("package_path")),
        ("mapping_file", bundle["mapping_load"]["mapping_file"]),
        ("discovery", OrderedDict([(k, str(v) if v else None) for k, v in inputs["discovery"].items()]))]))
    _write_readme(out, project_key, meta, collections)
    _write_schema(out)

    data_files = sorted(p for p in out.rglob("*") if p.is_file()
                        and p.name not in ("manifest.json", "validation_report.json"))
    safety = safety_scan(data_files)
    write_json(out / "audit" / "safety_scan_report.json", safety)

    audit = OrderedDict([
        ("mapping_audit", collections["audit/mapping_audit.json"]),
        ("monthly_reconciliation_audit", collections["audit/monthly_reconciliation_audit.json"]),
        ("actuals_floor_audit", collections["audit/actuals_floor_audit.json"]),
        ("no_hidden_cap_audit", collections["audit/no_hidden_cap_audit.json"]),
        ("source_hashes_before_after", src_audit)])
    validation = sp_validation.build_validation(out, bundle["discovery"], bundle["mapping_load"],
                                                bundle["resolved"], collections, audit, determinism,
                                                safety, meta, src_audit["unchanged"])
    write_json(out / "validation_report.json", validation)
    conclusion = "forecast_staffing_plan_ready" if validation["passed"] else "forecast_staffing_plan_not_ready"
    write_json(out / "manifest.json", _manifest(out, project_key, meta, conclusion, validation))

    return {"output_package": str(out), "validation_passed": validation["passed"],
            "safety_passed": safety["passed"], "determinism_passed": determinism["diff_result"] == "pass",
            "source_hashes_unchanged": src_audit["unchanged"],
            "source_package": validation["source_package"],
            "plan_cost_code_count": validation["plan_cost_code_count"],
            "applied_numeric_code_count": validation["applied_numeric_code_count"],
            "applied_budget_codes": validation["applied_budget_codes"],
            "mapping_status_counts": validation["mapping_status_counts"],
            "conflict_count": validation["conflict_count"],
            "review_queue_count": validation["review_queue_count"]}


def _manifest(out, project_key, meta, conclusion, validation):
    files = []
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name != "manifest.json":
            rows = sum(1 for _ in read_jsonl(p)) if p.suffix == ".jsonl" else None
            files.append(OrderedDict([("path", str(p.relative_to(out))), ("size_bytes", p.stat().st_size),
                                      ("row_count", rows), ("sha256", sha256_file(p))]))
    return OrderedDict([
        ("package_name", out.name),
        ("manifest_title", "Operator Staffing Plan Forecast Package — Tropical World Nursery"),
        ("manifest_version", "1.0.0"),
        ("project", OrderedDict([("project_key", project_key),
                                 ("project_name", "Tropical World Nursery Senior Living Facility"),
                                 ("job_reference", "23-435-01"), ("forecast_period", "2026-June")])),
        ("generation", meta), ("output_files", files),
        ("validation_status", OrderedDict([("passed", validation["passed"]),
                                           ("checks", validation["checks"])])),
        ("conclusion", conclusion)])


def _write_readme(out, project_key, meta, collections):
    s = collections["project_staffing_plan_summary.json"]
    md = [
        f"# forecast_staffing_plan_package_tropical ({meta['package_stamp']})",
        "",
        "Operator-supplied planned-staffing forecast layer for Tropical World Nursery "
        f"({project_key} / 23-435-01 / 2026-June). Ingests the extracted staffing JSON package, resolves "
        "each source cost code to a canonical `.LAB` budget-code key (LAB-only numeric; the "
        "`.LAB`/`.LBN`/`.MAT` family is date-context only), and emits the per-code bridge, BOTH the "
        "plan-implied and current-CTC-reconciled monthly forecasts, a mapping review queue, conflicts, "
        "warnings, and fail-closed audits. It does NOT mutate the source Excel, the staffing JSON "
        "package, accepted packages, or SQLite, and makes no live external calls.",
        "",
        f"- Source package: `{s['source_package_name']}`.",
        f"- Plan cost codes: {s['plan_cost_code_count']}; applied numeric `.LAB` codes: "
        f"{s['applied_numeric_code_count']} {s['applied_budget_codes']}.",
        f"- Mapping status: {s['mapping_status_counts']}.",
        f"- Applied plan remaining total: {s['applied_plan_remaining_total']}; Σ delta vs accepted CTC: "
        f"{s['applied_delta_vs_accepted_ctc_total']}.",
        f"- Codes requiring operator acceptance: {s['codes_requiring_operator_acceptance']}.",
        f"- Review-queue items: {s['review_queue_count']}; conflicts: {s['conflict_count']} "
        f"{s['conflict_class_counts']}.",
        "",
        "**Posture.** Staffing dollars are LAB-only — 100% of a mapped cost code's monthly staffing "
        "forecast applies to the resolved `.LAB` key (allocation 1.0000); no dollars go to `.LBN`/`.MAT`. "
        "A code applies numerically only when the cost_code + canonical role/description family resolves "
        "to exactly one `.LAB` AND an operator override has accepted the mapping. Ambiguous / unmapped / "
        "pending codes are review-only.",
        "",
        "**No hidden stale CTC.** For every mapped code the package reports BOTH the plan-implied monthly "
        "forecast (operator plan dollars) and the current-CTC-reconciled monthly forecast (accepted CTC "
        "over the same plan shape), the implied remaining / implied final cost, the deltas vs accepted "
        "CTC and final cost, and a `requires_operator_acceptance` flag. Plan-driven final-cost changes "
        "are advisory until accepted. CostEntries actuals are truth; actual cost to date is the only "
        "floor; no reference is ever a cap.",
        "",
    ]
    (out / "README.md").write_text("\n".join(md), encoding="utf-8")


def _write_schema(out):
    md = [
        "# Operator Staffing Plan Forecast Package — Schema",
        "",
        "Money is Decimal-string (2dp) or null; allocation shares are 4dp. Staffing dollars are LAB-only.",
        "",
        "## Key files",
        "- `staffing_plan_source_inventory.json` — discovered source package, its validation status, hash "
        "verification, and monthly-total reconciliation.",
        "- `staffing_plan_assignments_normalized.jsonl` — source assignments + resolved "
        "`numeric_target_budget_code_key` / `mapping_status` (source not mutated).",
        "- `staffing_plan_mapping_by_cost_code.jsonl` — per cost code: numeric `.LAB` target, "
        "date-context `.LAB`/`.LBN`/`.MAT` targets, `mapping_status`, `applied_numeric`, allocation share.",
        "- `staffing_plan_mapping_review_queue.jsonl` — ambiguous / unmapped / pending / acceptance-"
        "required rows for operator review.",
        "- `staffing_plan_monthly_by_budget_code.jsonl` — per `.LAB` code: "
        "`staffing_plan_implied_monthly_forecast` (plan dollars) AND "
        "`current_ctc_reconciled_monthly_forecast` (accepted CTC over the plan shape), + acceptance flag.",
        "- `staffing_plan_summary_by_budget_code.jsonl` — the BRIDGE: actual, accepted final + CTC, plan "
        "implied final + remaining, `delta_vs_current_accepted_ctc`, `delta_vs_current_accepted_final_cost`, "
        "recommendation + acceptance status, and both monthly vectors.",
        "- `staffing_plan_monthly_by_cost_code.jsonl` / `staffing_plan_monthly_project_forecast.jsonl` / "
        "`staffing_plan_summary_by_person.jsonl` — source rollups (annotated; applied-numeric project total).",
        "- `staffing_plan_conflicts.jsonl` — staffing_plan_conflicts_with_current_accepted_ctc, "
        "..._changes_final_cost_materially, ..._conflicts_with_recent_actual_burn, "
        "..._conflicts_with_cost_frequency, ..._unmapped_cost_code, ..._ambiguous_mapping, "
        "..._ends_before_forecast_horizon, ..._monthly_total_reconciliation_failure.",
        "- `staffing_plan_warnings.jsonl`, `project_staffing_plan_summary.json`.",
        "- `audit/*` — mapping, monthly_reconciliation, actuals_floor, no_hidden_cap, "
        "source_hashes_before_after, safety_scan.",
        "",
        "## Rules",
        "- Numeric staffing dollars apply only to a uniquely-resolved `.LAB` key confirmed by an accepted "
        "operator override; `.LBN`/`.MAT` are date-context only; no split is ever fabricated.",
        "- The package never compresses a stale accepted CTC into the plan window: plan-implied and "
        "CTC-reconciled forecasts are both emitted, deltas surfaced, and acceptance required when material.",
        "- Actual cost to date is the only hard floor; no reference is ever a cap; final-cost changes are "
        "advisory until operator acceptance.",
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
