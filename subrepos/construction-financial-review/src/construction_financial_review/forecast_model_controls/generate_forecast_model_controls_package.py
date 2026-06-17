"""Generate the operator forecast-model-controls package for Tropical World Nursery.

Loads the forecast-model-control file (committed dormant config, or a ``--forecast-model-control-file``
override), resolves each control's window + value constraint + model shape + manual inputs into a
controlled monthly forecast, maps it to a canonical budget code, enforces the actuals floor + window +
manual + duplicate-conflict + acceptance gates, and emits an auditable package: per-control rows,
resolved references, application disposition, a monthly-reconciliation preview, a deterministic
probability/plausibility assessment, a human-review queue, conflicts, warnings, and fail-closed audits.
Read-only against source packages; never mutates source Excel, accepted packages, or SQLite; no live
external calls. Deterministic under a frozen stamp.

Run:
    PYTHONPATH=src python3 -m construction_financial_review.cli forecast-model-controls --project tropical \
        [--frozen-stamp YYYYMMDD_HHMMSS] [--out-root DIR] [--forecast-model-control-file PATH]
"""
from __future__ import annotations

import tempfile
from collections import Counter, OrderedDict
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from ..common import run_lineage
from ..common.hashing import sha256_file
from ..common.io import read_jsonl, write_json, write_jsonl
from ..common.money import D, dec, money_str
from ..common.safety import safety_scan
from ..schedule_analysis.schedule_mapping import build_canonical_index
from . import integration, probability_assessment
from . import validation as fmc_validation

SUBPROJECT_ROOT = Path(__file__).resolve().parents[3]
ZERO = Decimal("0")
CENTS = Decimal("0.01")

DATA_FILES = (
    "model_controls_by_budget_code.jsonl",
    "model_control_applications_by_budget_code.jsonl",
    "model_control_resolved_targets_by_budget_code.jsonl",
    "model_control_monthly_preview_by_budget_code.jsonl",
    "model_control_probability_assessment_by_budget_code.jsonl",
    "model_control_review_queue.jsonl",
    "model_control_conflicts.jsonl",
    "model_control_warnings.jsonl",
    "project_forecast_model_controls_summary.json",
)
AUDIT_DATA_FILES = (
    "audit/control_mapping_audit.json",
    "audit/target_source_resolution_audit.json",
    "audit/window_resolution_audit.json",
    "audit/actuals_floor_audit.json",
    "audit/no_hidden_cap_audit.json",
    "audit/model_shape_audit.json",
    "audit/monthly_reconciliation_preview_audit.json",
    "audit/probability_anchor_policy_audit.json",
    "audit/combined_actuals_plus_forecast_target_reconciliation_audit.json",
)


# --------------------------------------------------------------------------- discovery + inputs

def _latest_dir(data_root: Path, pattern: str):
    matches = sorted(p for p in data_root.glob(pattern) if p.is_dir())
    return matches[-1] if matches else None


def _discover(cfg: dict, data_root: Path, project_key: str):
    """Return (discovery, context_lineage).

    Context is resolved via the shared run-lineage resolver: explicit context pin (debug) -> active
    full-fresh run state (CFR_RUN_LINEAGE_STATE) -> latest-glob. It NEVER prefers the stale
    cfg["forecast_context_package"] named config (which caused model controls to consume a stale context),
    even in standalone mode. intelligence/monthly/probability/prior_comprehensive stay on latest-glob.
    """
    ctx, ctx_lineage = run_lineage.resolve_upstream(
        "context", data_root=data_root, project_key=project_key,
        override_stamp=cfg.get("_pinned_context_stamp"))
    discovery = {
        "context": ctx,
        "intelligence": _latest_dir(data_root, "forecast_accuracy_next_package_tropical_*"),
        "monthly": _latest_dir(data_root, "forecast_monthly_package_tropical_*"),
        "probability": _latest_dir(data_root, "forecast_probability_package_tropical_*"),
        "prior_comprehensive": _latest_dir(data_root, "forecast_comprehensive_package_tropical_*"),
    }
    return discovery, ctx_lineage


def _active_months(monthly_pkg: Path) -> list:
    if not monthly_pkg:
        return []
    fpath = monthly_pkg / "monthly_forecast_by_budget_code.jsonl"
    if not fpath.exists():
        return []
    return sorted({r["forecast_month"] for r in read_jsonl(fpath) if r.get("forecast_month")})


def _schedule_by_key(intel_pkg: Path) -> tuple:
    """Per-code schedule fields + project-level latest finish (best effort)."""
    schedule, latest_project, present = {}, None, False
    if not intel_pkg:
        return schedule, {"schedule_present": False, "latest_project_schedule_date": None}
    for fname in ("remaining_work_evidence_by_budget_code.jsonl",
                  "schedule_forecast_evidence_by_budget_code.jsonl"):
        fp = intel_pkg / fname
        if not fp.exists():
            continue
        for r in read_jsonl(fp):
            key = r.get("budget_code_key")
            if not key:
                continue
            fin = r.get("latest_schedule_finish")
            entry = schedule.setdefault(key, {})
            if fin:
                present = True
                entry["latest_schedule_finish"] = fin
                entry.setdefault("latest_remaining_finish", fin)
                if latest_project is None or fin > latest_project:
                    latest_project = fin
    return schedule, {"schedule_present": present, "latest_project_schedule_date": latest_project}


def _prior_prob_keys(prob_pkg: Path) -> set:
    keys = set()
    if not prob_pkg:
        return keys
    for fp in sorted(prob_pkg.glob("*by_budget_code.jsonl")):
        for r in read_jsonl(fp):
            key = r.get("budget_code_key")
            if key and any(k in r for k in ("simulated_p50", "p50", "integrated_p50")):
                keys.add(key)
    return keys


def load_inputs(cfg: dict, data_root: Path, project_key: str, stamp: str, stamp_iso: str | None,
                override_path: str | None) -> "OrderedDict":
    discovery, context_lineage = _discover(cfg, data_root, project_key)
    ctx = discovery["context"]
    budget_codes = list(read_jsonl(ctx / "canonical" / "budget_codes.jsonl"))
    canonical_keys = set(build_canonical_index(budget_codes)["keys"])

    context_rows = list(read_jsonl(ctx / "summaries" / "budget_code_forecast_context.jsonl"))
    actuals_by_key, amounts_by_key, burn_by_key = {}, {}, {}
    for r in context_rows:
        key = r.get("budget_code_key")
        if not key:
            continue
        actuals_by_key[key] = D((r.get("actuals") or {}).get("actual_cost_all_source_to_date"))
        amounts_by_key[key] = r.get("budget_amounts") or {}
        burn_by_key[key] = (r.get("burn") or {}).get("avg_monthly_burn")

    rec_by_key, model_final_by_key, model_ctc_by_key = {}, {}, {}
    if discovery["intelligence"]:
        recf = discovery["intelligence"] / "forecast_recommendations_by_budget_code.jsonl"
        if recf.exists():
            for r in read_jsonl(recf):
                key = r.get("budget_code_key")
                if not key:
                    continue
                rec_by_key[key] = r
                model_final_by_key[key] = dec(r.get("recommended_final_cost"))
                model_ctc_by_key[key] = dec(r.get("recommended_cost_to_complete"))

    prior_final_by_key = {}
    if discovery["prior_comprehensive"]:
        pf = discovery["prior_comprehensive"] / "integrated_final_cost_recommendations.jsonl"
        if pf.exists():
            prior_final_by_key = {r["budget_code_key"]: r.get("integrated_recommended_final_cost")
                                  for r in read_jsonl(pf) if r.get("budget_code_key")}

    ref_ctx = integration.build_ref_ctx(
        canonical_keys, amounts_by_key, rec_by_key, prior_final_by_key,
        context_package_path=str(ctx),
        intelligence_package_path=str(discovery["intelligence"]) if discovery["intelligence"] else None,
        prior_comprehensive_package_path=(str(discovery["prior_comprehensive"])
                                          if discovery["prior_comprehensive"] else None),
        prior_is_current_run=False)

    schedule_by_key, project_schedule = _schedule_by_key(discovery["intelligence"])
    calendar_months = _active_months(discovery["monthly"])
    prior_prob_keys = _prior_prob_keys(discovery["probability"])

    bundle = integration.prepare(cfg, SUBPROJECT_ROOT, canonical_keys, actuals_by_key, ref_ctx,
                                 schedule_by_key, project_schedule, calendar_months, model_final_by_key,
                                 model_ctc_by_key, project_key, stamp_iso, override_path)

    source_files = []
    for p in (ctx, discovery["intelligence"], discovery["monthly"], discovery["probability"],
              discovery["prior_comprehensive"]):
        if p:
            source_files.extend(sorted(p.rglob("*.jsonl"))[:160])
    cf = Path(bundle["load_result"]["control_file"])
    if cf.exists():
        source_files.append(cf)

    return OrderedDict([
        ("project_key", project_key), ("discovery", discovery), ("stamp", stamp),
        ("context_lineage", context_lineage),
        ("amounts_by_key", amounts_by_key), ("burn_by_key", burn_by_key),
        ("prior_prob_keys", prior_prob_keys), ("calendar_months", calendar_months),
        ("project_schedule", project_schedule),
        ("within_pct", dec(cfg.get("materiality_percent")) or Decimal("0.10")),
        ("override_path", override_path), ("bundle", bundle),
        ("source_files", source_files[:400]), ("source_hashes_before", _source_hashes(source_files[:400])),
    ])


def _source_hashes(files) -> "OrderedDict":
    return OrderedDict((str(p), sha256_file(p) if Path(p).exists() else None) for p in files)


# --------------------------------------------------------------------------- pure build

def _preview_row(project_key, key, decision) -> "OrderedDict":
    actual = decision["actual_cost_to_date"]
    target = decision["controlled_final_cost"]
    remaining = decision["controlled_remaining"]
    alloc = decision["monthly_allocation"] or OrderedDict()
    rows = [OrderedDict([("forecast_month", m), ("recommended_month_cost", money_str(v))])
            for m, v in alloc.items()]
    alloc_sum = sum((D(r["recommended_month_cost"]) for r in rows), ZERO)
    preview = bool(rows)
    reconciles = (preview and abs(alloc_sum - remaining) <= CENTS
                  and abs((D(actual) + alloc_sum) - D(target)) <= CENTS)
    return OrderedDict([
        ("project_key", project_key), ("budget_code_key", key), ("control_id", decision["control_id"]),
        ("value_constraint_policy", decision["value_constraint_policy"]),
        ("model_type", decision["model_type"]), ("monthly_vector_source", decision["monthly_vector_source"]),
        ("forecast_start_basis", decision["schedule_start_basis"]),
        ("forecast_end_basis", decision["schedule_end_basis"]),
        ("actual_cost_to_date", money_str(actual)), ("controlled_final_cost", money_str(target)),
        ("controlled_remaining", money_str(remaining)),
        ("active_forecast_months", list(decision["active_months"])),
        ("active_forecast_month_count", len(decision["active_months"])),
        ("monthly_preview_available", preview), ("monthly_allocation", rows),
        ("allocation_sum", money_str(alloc_sum)),
        ("cent_residual", money_str(remaining - alloc_sum) if preview else None),
        ("reconciles_to_target", bool(reconciles)),
        ("changes_deterministic_final", decision["changes_deterministic_final"]),
    ])


def _build_collections(inputs: dict, project_key: str) -> dict:
    bundle = inputs["bundle"]
    load_result, resolved = bundle["load_result"], bundle["resolved"]
    mapping_results = bundle["mapping_results"]
    stamp = inputs["stamp"]
    amounts_by_key, burn_by_key = inputs["amounts_by_key"], inputs["burn_by_key"]
    prior_prob_keys, within_pct = inputs["prior_prob_keys"], inputs["within_pct"]

    map_by_id = {m["control_id"]: m for m in mapping_results}
    app_by_id = {a["control_id"]: a for a in resolved["applications"]}
    rt_by_id = {r["control_id"]: r for r in resolved["resolved_targets"]}

    control_rows = []
    for c in load_result["controls"]:
        m = map_by_id.get(c["control_id"], {})
        a = app_by_id.get(c["control_id"], {})
        rt = rt_by_id.get(c["control_id"], {})
        row = OrderedDict(c)
        row["mapped_budget_code_key"] = m.get("mapped_budget_code_key")
        row["mapping_status"] = m.get("mapping_status")
        row["resolved_reference_value"] = rt.get("resolved_reference_value")
        row["controlled_final_cost"] = rt.get("controlled_final_cost")
        row["application_status"] = a.get("application_status")
        row["applied"] = a.get("applied", False)
        row["disposition"] = a.get("disposition")
        control_rows.append(row)
    control_rows.sort(key=lambda r: (r.get("mapped_budget_code_key") or "", r.get("control_id") or ""))

    resolved_targets = []
    for r in resolved["resolved_targets"]:
        row = OrderedDict(r)
        row["resolved_at_package_stamp"] = stamp
        resolved_targets.append(row)

    previews = [_preview_row(project_key, key, d) for key, d in resolved["by_key"].items()]
    previews.sort(key=lambda r: (r["budget_code_key"] or "", r["control_id"] or ""))

    prob_rows = []
    for key, d in resolved["by_key"].items():
        if d["changes_deterministic_final"]:
            prob_rows.append(probability_assessment.assess(
                project_key, d, amounts_by_key.get(key), key in prior_prob_keys,
                burn_by_key.get(key), within_pct))
    prob_rows.sort(key=lambda r: (r["budget_code_key"] or "", r["control_id"] or ""))

    summary = OrderedDict([
        ("project_key", project_key), ("control_file", load_result["control_file"]),
        ("control_file_is_override", load_result["control_file_is_override"]),
        ("control_count", load_result["control_count"]), ("acceptance_counts", resolved["counts"]),
        ("applied_control_count", len(resolved["by_key"])),
        ("controlled_budget_codes", resolved["controlled_budget_codes"]),
        ("value_changing_count", sum(1 for d in resolved["by_key"].values() if d["changes_deterministic_final"])),
        ("timing_or_shape_only_count", sum(1 for d in resolved["by_key"].values() if not d["changes_deterministic_final"])),
        ("review_queue_count", len(resolved["review_queue"])), ("conflict_count", len(resolved["conflicts"])),
        ("warning_count", len(resolved["warnings"])), ("floor_conflict_count", len(resolved["floor_conflicts"])),
        ("mapping_status_counts", dict(Counter(m["mapping_status"] for m in mapping_results))),
        ("model_type_counts", dict(Counter(d["model_type"] for d in resolved["by_key"].values()))),
        ("requires_human_acceptance", True),
        ("note", "forecast model controls configure window, model shape, value constraints, and manual "
                 "values per code; only accepted controls apply, CostEntries actuals are the only floor, "
                 "and no reference is ever a hidden cap unless explicitly accepted"),
    ])

    out = {
        "model_controls_by_budget_code.jsonl": control_rows,
        "model_control_applications_by_budget_code.jsonl": resolved["applications"],
        "model_control_resolved_targets_by_budget_code.jsonl": resolved_targets,
        "model_control_monthly_preview_by_budget_code.jsonl": previews,
        "model_control_probability_assessment_by_budget_code.jsonl": prob_rows,
        "model_control_review_queue.jsonl": resolved["review_queue"],
        "model_control_conflicts.jsonl": resolved["conflicts"],
        "model_control_warnings.jsonl": resolved["warnings"],
        "project_forecast_model_controls_summary.json": summary,
    }
    out.update(_build_audits(inputs, project_key, mapping_results, resolved, previews, prob_rows))
    return out


def _build_audits(inputs, project_key, mapping_results, resolved, previews, prob_rows) -> dict:
    applied_apps = [a for a in resolved["applications"] if a["applied"]]
    rt_rows = resolved["resolved_targets"]
    no_hidden = all(a["acceptance_status"] == "accepted" for a in applied_apps)

    floor_rows = [OrderedDict([
        ("control_id", rt["control_id"]), ("budget_code_key", rt["budget_code_key"]),
        ("actuals_floor", rt["actual_cost_to_date"]), ("controlled_final_cost", rt["controlled_final_cost"]),
        ("controlled_remaining", rt["controlled_remaining"]), ("floor_status", rt["floor_status"]),
        ("application_status", rt["application_status"])]) for rt in rt_rows]

    window_rows = [OrderedDict([
        ("control_id", d["control_id"]), ("budget_code_key", d["budget_code_key"]),
        ("forecast_start_policy", d["forecast_start_policy"]), ("forecast_end_policy", d["forecast_end_policy"]),
        ("resolved_start_date", d["resolved_start_date"]), ("resolved_end_date", d["resolved_end_date"]),
        ("schedule_start_basis", d["schedule_start_basis"]), ("schedule_end_basis", d["schedule_end_basis"]),
        ("active_months", d["active_months"])]) for d in resolved["by_key"].values()]

    shape_rows = [OrderedDict([
        ("control_id", d["control_id"]), ("budget_code_key", d["budget_code_key"]),
        ("model_type", d["model_type"]), ("monthly_vector_source", d["monthly_vector_source"]),
        ("controlled_remaining", money_str(d["controlled_remaining"])),
        ("active_month_count", len(d["active_months"]))]) for d in resolved["by_key"].values()]

    preview_audit = [OrderedDict([
        ("control_id", p["control_id"]), ("budget_code_key", p["budget_code_key"]),
        ("controlled_remaining", p["controlled_remaining"]), ("monthly_allocation_sum", p["allocation_sum"]),
        ("cent_residual", p["cent_residual"]), ("active_forecast_window", p["active_forecast_months"]),
        ("reconciles_to_target", p["reconciles_to_target"])]) for p in previews]

    return {
        "audit/control_mapping_audit.json": OrderedDict([
            ("project_key", project_key),
            ("by_mapping_status", dict(Counter(m["mapping_status"] for m in mapping_results))),
            ("ambiguous", [m["control_id"] for m in mapping_results if m["mapping_status"] == "ambiguous_cost_code"]),
            ("invented", [m["control_id"] for m in mapping_results if m["mapping_status"] == "invented_budget_code_key"]),
            ("mapping_rows", mapping_results),
            ("rule", "explicit budget_code_key must be canonical; cost_code resolves only when unique")]),
        "audit/target_source_resolution_audit.json": OrderedDict([
            ("project_key", project_key),
            ("by_reference_source", dict(Counter(rt.get("reference_source") for rt in rt_rows))),
            ("present_count", sum(1 for rt in rt_rows if rt["resolved_reference_value"] is not None)),
            ("missing", [rt["control_id"] for rt in rt_rows
                         if rt["resolved_reference_value"] is None and rt["reference_source"]]),
            ("aliases_used", [OrderedDict([("control_id", rt["control_id"]), ("alias_used", rt["alias_used"])])
                              for rt in rt_rows if rt.get("alias_used")]),
            ("resolution_rows", rt_rows),
            ("rule", "each reference resolves to a TOTAL value with lineage; projected_budget aliases "
                     "projected_costs unless a distinct field disagrees; prior_comprehensive must be a prior "
                     "package (never the current run)")]),
        "audit/window_resolution_audit.json": OrderedDict([
            ("project_key", project_key),
            ("project_schedule", inputs["project_schedule"]),
            ("by_end_basis", dict(Counter(d["schedule_end_basis"] for d in resolved["by_key"].values()))),
            ("window_rows", window_rows),
            ("rule", "end order: explicit -> code-mapped schedule date -> project schedule final date -> "
                     "existing horizon fallback (only when entire schedule dataset is missing); unmapped "
                     "codes never degrade the window")]),
        "audit/actuals_floor_audit.json": OrderedDict([
            ("project_key", project_key), ("all_floors_respected", not resolved["floor_conflicts"]),
            ("floor_conflicts", resolved["floor_conflicts"]), ("floor_rows", floor_rows),
            ("rule", "no accepted control may set final cost below actual cost to date; actuals are the only "
                     "hard floor and are never reduced")]),
        "audit/no_hidden_cap_audit.json": OrderedDict([
            ("project_key", project_key), ("no_hidden_cap", no_hidden),
            ("dollar_changes", [OrderedDict([
                ("control_id", a["control_id"]), ("budget_code_key", a["budget_code_key"]),
                ("acceptance_status", a["acceptance_status"]), ("accepted_by", a["accepted_by"]),
                ("accepted_at", a["accepted_at"]), ("reason", a["reason"]),
                ("value_constraint_policy", a["value_constraint_policy"]),
                ("constraint_applied", a["constraint_applied"]),
                ("controlled_final_cost", a["controlled_final_cost"])])
                for a in applied_apps if a["changes_deterministic_final"]]),
            ("rule", "no budget/commitment/pay-app/probability/history value sets final cost unless tied to "
                     "an accepted control; a not_to_exceed that binds is disclosed as an operator constraint, "
                     "never a silent cap")]),
        "audit/model_shape_audit.json": OrderedDict([
            ("project_key", project_key),
            ("by_model_type", dict(Counter(d["model_type"] for d in resolved["by_key"].values()))),
            ("shape_rows", shape_rows),
            ("rule", "deterministic normalized monthly shape vectors; manual_monthly uses operator values "
                     "directly; existing_model defers to the blended model in the monthly package")]),
        "audit/monthly_reconciliation_preview_audit.json": OrderedDict([
            ("project_key", project_key),
            ("all_previews_reconcile", all(p["reconciles_to_target"] for p in previews) if previews else True),
            ("preview_rows", preview_audit),
            ("rule", "controlled remaining is allocated across the active window (last month absorbs the cent "
                     "residual); sum == controlled remaining and actual + sum == controlled final")]),
        "audit/probability_anchor_policy_audit.json": OrderedDict([
            ("project_key", project_key),
            ("probability_control_policy", "anchor_when_available_else_provisional_assessment"),
            ("status_counts", dict(Counter(r["probability_status"] for r in prob_rows))),
            ("assessment_counts", dict(Counter(r["manual_value_assessment"] for r in prob_rows))),
            ("rule", "value-changing controlled codes anchor to a prior accepted probability row when present; "
                     "otherwise a deterministic provisional plausibility assessment is emitted (numeric "
                     "probabilities null) — missing prior probability never fails the deterministic run")]),
        "audit/combined_actuals_plus_forecast_target_reconciliation_audit.json": OrderedDict([
            ("project_key", project_key), ("controlled_keys", resolved["controlled_budget_codes"]),
            ("targets", [OrderedDict([
                ("budget_code_key", d["budget_code_key"]),
                ("controlled_final_cost", money_str(d["controlled_final_cost"])),
                ("actual_cost_to_date", money_str(d["actual_cost_to_date"])),
                ("controlled_remaining", money_str(d["controlled_remaining"]))])
                for d in resolved["by_key"].values()]),
            ("boundary_rule", "combined CSV uses CostEntries actuals before the current forecast month and "
                              "forecast from the current month forward; for controlled keys the current-month "
                              "combined cell = current-month actuals-to-date + current-month remaining forecast "
                              "(counted once) so sum(month columns) == controlled final cost"),
            ("note", "enforced in forecast_comprehensive + forecast_actuals; this standalone audit documents "
                     "the policy and the per-key controlled finals")]),
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
             with_llm=False, llm_model=None, control_file=None) -> dict:
    data_root = Path(data_root or cfg["default_data_root"])
    stamp = frozen_stamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    generated_ts = frozen_stamp if frozen_stamp else datetime.now().isoformat(timespec="seconds")
    stamp_iso = frozen_stamp or generated_ts

    inputs = load_inputs(cfg, data_root, project_key, stamp, stamp_iso, control_file)

    out_base = Path(out_root) if out_root else data_root
    out = out_base / f"forecast_model_controls_package_tropical_{stamp}"
    out.mkdir(parents=True, exist_ok=False)
    (out / "audit").mkdir(exist_ok=True)

    collections = _build_collections(inputs, project_key)
    _write_collections(out, collections)
    determinism = _determinism_check(inputs, project_key)

    command = f"python3 -m construction_financial_review.cli forecast-model-controls --project {project_key}"
    meta = OrderedDict([
        ("generator",
         "construction_financial_review.forecast_model_controls.generate_forecast_model_controls_package"),
        ("command", command), ("package_stamp", stamp), ("generated_timestamp_local", generated_ts),
        ("project_key", project_key)])

    after = _source_hashes(inputs["source_files"])
    src_audit = OrderedDict([("before", inputs["source_hashes_before"]), ("after", after),
                             ("unchanged", inputs["source_hashes_before"] == after)])
    write_json(out / "audit" / "source_hashes_before_after.json", src_audit)
    lr = inputs["bundle"]["load_result"]
    context_lineage_consistent = run_lineage.lineage_consistent([inputs["context_lineage"]])
    write_json(out / "input_inventory.json", OrderedDict([
        ("generation", meta), ("control_file", lr["control_file"]),
        ("control_file_is_override", lr["control_file_is_override"]),
        ("control_file_present", lr["present"]),
        ("context_lineage", inputs["context_lineage"]),
        ("forecast_model_controls_context_lineage_consistent", bool(context_lineage_consistent)),
        ("discovery", OrderedDict([(k, str(v) if v else None) for k, v in inputs["discovery"].items()]))]))
    _write_readme(out, project_key, meta, collections)
    _write_schema(out)

    data_files = sorted(p for p in out.rglob("*") if p.is_file()
                        and p.name not in ("manifest.json", "validation_report.json"))
    safety = safety_scan(data_files)
    write_json(out / "audit" / "safety_scan_report.json", safety)

    audit = OrderedDict([
        ("control_mapping_audit", collections["audit/control_mapping_audit.json"]),
        ("target_source_resolution_audit", collections["audit/target_source_resolution_audit.json"]),
        ("window_resolution_audit", collections["audit/window_resolution_audit.json"]),
        ("actuals_floor_audit", collections["audit/actuals_floor_audit.json"]),
        ("no_hidden_cap_audit", collections["audit/no_hidden_cap_audit.json"]),
        ("model_shape_audit", collections["audit/model_shape_audit.json"]),
        ("monthly_reconciliation_preview_audit", collections["audit/monthly_reconciliation_preview_audit.json"]),
        ("probability_anchor_policy_audit", collections["audit/probability_anchor_policy_audit.json"]),
        ("source_hashes_before_after", src_audit)])
    validation = fmc_validation.build_validation(out, lr, inputs["bundle"]["resolved"], collections,
                                                 audit, determinism, safety, meta, src_audit["unchanged"],
                                                 context_lineage_consistent=context_lineage_consistent)
    write_json(out / "validation_report.json", validation)
    conclusion = "forecast_model_controls_ready" if validation["passed"] else "forecast_model_controls_not_ready"
    write_json(out / "manifest.json", _manifest(out, project_key, meta, conclusion, validation))

    return {"output_package": str(out), "validation_passed": validation["passed"],
            "safety_passed": safety["passed"], "determinism_passed": determinism["diff_result"] == "pass",
            "source_hashes_unchanged": src_audit["unchanged"], "control_count": validation["control_count"],
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
        ("manifest_title", "Operator Forecast Model Controls Package — Tropical World Nursery"),
        ("manifest_version", "1.0.0"),
        ("project", OrderedDict([("project_key", project_key),
                                 ("project_name", "Tropical World Nursery Senior Living Facility"),
                                 ("job_reference", "23-435-01"), ("forecast_period", "2026-June")])),
        ("generation", meta), ("output_files", files),
        ("validation_status", OrderedDict([("passed", validation["passed"]),
                                           ("checks", validation["checks"])])),
        ("conclusion", conclusion)])


def _write_readme(out, project_key, meta, collections):
    s = collections["project_forecast_model_controls_summary.json"]
    md = [
        f"# forecast_model_controls_package_tropical ({meta['package_stamp']})",
        "",
        "Operator forecast-model-control layer for Tropical World Nursery "
        f"({project_key} / 23-435-01 / 2026-June). Each control configures the forecast model for one "
        "canonical budget code: its forecast window (start/end), model shape (linear / S-curve / bell / "
        "manual), an optional value constraint (equal-to / cap / floor / explicit final / explicit "
        "remaining against a selected reference), and optional manual total or monthly inputs. Final-value "
        "pinning is one subsection of this contract. It maps each control to a canonical budget code, "
        "enforces the actuals floor + window + manual + duplicate-conflict + acceptance gates, and emits "
        "applied decisions, resolved references, a monthly-reconciliation preview, a deterministic "
        "probability/plausibility assessment, a human-review queue, conflicts, warnings, and fail-closed "
        "audits. It does NOT mutate source Excel, accepted packages, or SQLite, and makes no live external "
        "calls.",
        "",
        f"- Control file: `{s['control_file']}`" + (" (override)" if s["control_file_is_override"] else " (committed)") + ".",
        f"- Controls: {s['control_count']} ({s['acceptance_counts']}); applied: {s['applied_control_count']} "
        f"(value-changing {s['value_changing_count']}, timing/shape-only {s['timing_or_shape_only_count']}).",
        f"- Controlled budget codes: {s['controlled_budget_codes']}.",
        f"- Model types: {s['model_type_counts']}; review-queue: {s['review_queue_count']}; "
        f"conflicts: {s['conflict_count']}; warnings: {s['warning_count']}.",
        "",
        "**Posture.** A model control is an explicit operator decision, never model truth and never a hidden "
        "cap. It applies ONLY when `acceptance_status = accepted`; pending controls surface in the review "
        "queue without changing the forecast. CostEntries/Sage incurred cost is accounting truth and actual "
        "cost to date is the only hard floor — a controlled final below actuals is rejected and integration "
        "fails closed. A `not_to_exceed` constraint that binds is disclosed as an operator constraint, never "
        "a silent cap.",
        "",
        "**Probability is degraded, not fatal.** When a control changes the deterministic final value, the "
        "comprehensive consumer anchors probability to a prior accepted probability row when one exists; "
        "otherwise this package emits a deterministic provisional plausibility assessment (numeric "
        "probabilities null) — a missing prior probability row never kills the deterministic run.",
        "",
    ]
    (out / "README.md").write_text("\n".join(md), encoding="utf-8")


def _write_schema(out):
    md = [
        "# Operator Forecast Model Controls Package — Schema",
        "",
        "Money is Decimal-string (2dp) or null; `manual_monthly_values` is an ordered `{YYYY-MM: amount}` "
        "map. A value/model change applies only when `acceptance_status = accepted`.",
        "",
        "## Capabilities (per accepted control)",
        "- **Window:** `forecast_start_policy` (current_month_start | explicit_date | schedule_activity_start "
        "| earliest_remaining_start) + `forecast_end_policy` (latest_project_schedule_date | explicit_date | "
        "schedule_activity_finish | latest_schedule_finish | existing_forecast_horizon).",
        "- **Value constraint:** `value_constraint_policy` (none | equal_to_reference | "
        "not_to_exceed_reference | not_less_than_reference | explicit_final_value | explicit_remaining_value) "
        "against a `reference_source`.",
        "- **Model shape:** `model_type` (existing_model | linear | linear_ascending | linear_descending | "
        "front_loaded_s_curve | back_loaded_s_curve | bell_curve | manual_total | manual_monthly; alias "
        "`belle` -> `bell_curve`).",
        "- **Manual:** `manual_total` requires one of `manual_final_cost`/`manual_remaining_cost`; "
        "`manual_monthly` requires `manual_monthly_values`.",
        "",
        "## Reference value sources",
        "- `explicit_user_amount`, `original_budget`, `revised_budget`, `projected_budget` (alias of "
        "`projected_costs`), `projected_cost`, `committed_cost`, `accepted_intelligence_final`, "
        "`prior_comprehensive_integrated_final` (prior package only — never the current run).",
        "",
        "## Key files",
        "- `model_controls_by_budget_code.jsonl`, `model_control_applications_by_budget_code.jsonl`, "
        "`model_control_resolved_targets_by_budget_code.jsonl`, "
        "`model_control_monthly_preview_by_budget_code.jsonl`, "
        "`model_control_probability_assessment_by_budget_code.jsonl`, `model_control_review_queue.jsonl`, "
        "`model_control_conflicts.jsonl`, `model_control_warnings.jsonl`, "
        "`project_forecast_model_controls_summary.json`.",
        "- `audit/` — control mapping, target-source resolution, window resolution, actuals floor, "
        "no-hidden-cap, model shape, monthly reconciliation, probability-anchor policy, combined-CSV target "
        "reconciliation, `source_hashes_before_after.json` (input files unchanged before/after), and "
        "`safety_scan_report.json` (output safety scan, must pass).",
        "",
        "## Rules",
        "- Explicit `budget_code_key` must be canonical; a `cost_code`-only control resolves only when "
        "unique, else ambiguous and fails closed.",
        "- Only accepted controls apply; pending/rejected are documented, never applied.",
        "- The controlled final may never fall below actual cost to date (only hard floor).",
        "- Two accepted controls that disagree for one code fail closed (no latest-wins).",
        "- No hidden caps; a binding not_to_exceed is disclosed as an operator constraint.",
        "- Probability is degraded-not-fatal: anchor when a prior accepted row exists, else a provisional "
        "evidence-scored assessment; numeric probabilities are null for provisional assessments.",
        "- Deterministic: same frozen stamp + same inputs => byte-identical quantitative core + audits.",
        "",
    ]
    (out / "SCHEMA.md").write_text("\n".join(md), encoding="utf-8")


def run(project_key, cfg, data_root=None, frozen_stamp=None, out_root=None, with_llm=False,
        llm_model=None, control_file=None) -> int:
    import json
    res = generate(project_key, cfg, data_root=data_root, frozen_stamp=frozen_stamp, out_root=out_root,
                   with_llm=with_llm, llm_model=llm_model, control_file=control_file)
    print(json.dumps(OrderedDict([("status", "ok" if res["validation_passed"] else "validation_failed"),
                                  *res.items()]), indent=2))
    return 0 if res["validation_passed"] else 1
