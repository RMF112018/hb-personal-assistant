"""Generate the schedule-integrated forecast package for Tropical World Nursery.

Reads the P6/XER-derived schedule package plus the latest forecast context, crosswalk-v2
analysis, and (optional) mapping-discrepancy workpaper, and writes ONE new timestamped output
package under the forecast data root. Schedule data is timing/remaining-work/sequencing/risk
evidence only — never accounting actual cost, never an independent cost driver.

Run via the CLI:
    PYTHONPATH=src python3 -m construction_financial_review.cli \
        schedule-integrate-forecast --project tropical
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
from ..common.money import D, dec, money_str
from ..common.safety import safety_scan
from ..common.validation import all_files_parse
from . import cashflow, forecast_integration, schedule_io, schedule_mapping, schedule_rollup

SUBPROJECT_ROOT = Path(__file__).resolve().parents[2]
GENERATOR_NAME = "construction_financial_review.schedule_analysis.generate_schedule_integrated_forecast"

CONCLUSION_READY = "schedule_integrated_forecast_ready"
CONCLUSION_REVIEW = "schedule_integrated_forecast_ready_with_review_items"
CONCLUSION_NOT_READY = "schedule_integrated_forecast_not_ready"


# ---------------------------------------------------------------------------
# Generation metadata (read-only git)
# ---------------------------------------------------------------------------

def _git(args: list[str]) -> Optional[str]:
    try:
        out = subprocess.run(["git", *args], cwd=str(SUBPROJECT_ROOT),
                             capture_output=True, text=True, timeout=15)
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return None


def _generation_metadata(command: str, packages: dict, stamp: str, generated_ts: str) -> OrderedDict:
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
        ("selected_input_packages", OrderedDict([
            ("schedule_package", str(packages.get("schedule_package")) if packages.get("schedule_package") else None),
            ("context_package", str(packages.get("context_package")) if packages.get("context_package") else None),
            ("analysis_v2_package", str(packages.get("analysis_v2_package")) if packages.get("analysis_v2_package") else None),
            ("mapping_workpaper_package", str(packages.get("mapping_workpaper_package")) if packages.get("mapping_workpaper_package") else None),
        ])),
        ("package_selection_notes", packages.get("selection", [])),
    ])


# ---------------------------------------------------------------------------
# Inventories / health (Phase 2)
# ---------------------------------------------------------------------------

def _jsonl_count(path: Path) -> int:
    return sum(1 for _ in read_jsonl(path)) if path.exists() else 0


def build_schedule_package_inventory(schedule_pkg: Path, manifest: dict) -> OrderedDict:
    files = []
    for p in sorted(schedule_pkg.iterdir()):
        if not p.is_file():
            continue
        rows = _jsonl_count(p) if p.suffix == ".jsonl" else None
        files.append(OrderedDict([
            ("file", p.name),
            ("size_bytes", p.stat().st_size),
            ("jsonl_row_count", rows),
        ]))
    md = manifest.get("metadata", {})
    return OrderedDict([
        ("schedule_package_path", str(schedule_pkg)),
        ("file_count", len(files)),
        ("files", files),
        ("record_counts", manifest.get("record_counts", {})),
        ("project_id", md.get("project_id")),
        ("project_name", md.get("project_name")),
        ("data_date", md.get("data_date")),
        ("planned_start_date", md.get("planned_start_date")),
        ("scheduled_finish_date", md.get("scheduled_finish_date")),
        ("source_files", md.get("source_files")),
    ])


def build_schedule_health(manifest: dict, validation: dict, activities: list[dict],
                          decisions: list[dict], canonical_index: dict) -> OrderedDict:
    md = manifest.get("metadata", {})
    counts = manifest.get("record_counts", {})
    status_counts = manifest.get("activity_status_counts", {})
    type_counts = manifest.get("activity_type_counts", {})

    with_cc = sum(1 for d in decisions if d["schedule_cost_code"])
    without_cc = len(decisions) - with_cc
    mapped = sum(1 for d in decisions if d["mapping_status"] == schedule_mapping.STATUS_MAPPED)
    ambiguous = sum(1 for d in decisions if d["mapping_status"] == schedule_mapping.STATUS_AMBIGUOUS)
    invalid = sum(1 for d in decisions if d["mapping_status"] == schedule_mapping.STATUS_INVALID)
    neg_float = sum(1 for a in activities
                    if schedule_io.total_float_days(a) is not None
                    and float(schedule_io.total_float_days(a)) < 0)
    zero_or_neg = sum(1 for a in activities
                      if schedule_io.total_float_days(a) is not None
                      and float(schedule_io.total_float_days(a)) <= 0)
    open_neg_float = sum(1 for a in activities
                         if schedule_io.is_open(a.get("status"))
                         and schedule_io.total_float_days(a) is not None
                         and float(schedule_io.total_float_days(a)) < 0)
    missing_dates = sum(1 for a in activities
                        if not normalize_date((a.get("dates") or {}).get("start")))
    no_pred = sum(1 for a in activities if schedule_io.predecessor_count(a) == 0)
    no_succ = sum(1 for a in activities if schedule_io.successor_count(a) == 0)

    distinct_sched_cc = sorted({d["schedule_cost_code"] for d in decisions if d["schedule_cost_code"]})

    return OrderedDict([
        ("project_id", md.get("project_id")),
        ("project_name", md.get("project_name")),
        ("data_date", md.get("data_date")),
        ("planned_start_date", md.get("planned_start_date")),
        ("scheduled_finish_date", md.get("scheduled_finish_date")),
        ("source_files", md.get("source_files")),
        ("validation_status", OrderedDict([
            ("validation_warning_count", validation.get("summary", {}).get("validation_warning_count")),
            ("duplicate_activity_ids", validation.get("duplicate_activity_ids")),
            ("relationship_link_issue_count", validation.get("relationship_link_issue_count")),
        ])),
        ("activity_counts", OrderedDict([
            ("total_activities", counts.get("activities")),
            ("completed", status_counts.get("Completed")),
            ("in_progress", status_counts.get("In Progress")),
            ("not_started", status_counts.get("Not Started")),
            ("milestones", (type_counts.get("Start Milestone", 0) + type_counts.get("Finish Milestone", 0))),
            ("level_of_effort", type_counts.get("Level of Effort")),
            ("activities_with_cost_code", with_cc),
            ("activities_without_cost_code", without_cc),
            ("activities_missing_start_date", missing_dates),
        ])),
        ("relationship_counts", OrderedDict([
            ("total_relationships", counts.get("relationships")),
            ("activities_with_no_predecessors", no_pred),
            ("activities_with_no_successors", no_succ),
        ])),
        ("float_health", OrderedDict([
            ("negative_total_float_activities", neg_float),
            ("zero_or_negative_total_float_activities", zero_or_neg),
            ("open_work_negative_float_activities", open_neg_float),
            ("note", "total_float <= 0 is a critical/longest-path proxy only; "
                     "risk escalation uses negative float (< 0) on open work."),
        ])),
        ("cost_code_mapping_readiness", OrderedDict([
            ("distinct_schedule_cost_codes", len(distinct_sched_cc)),
            ("activities_mapped_unique_budget_key", mapped),
            ("activities_ambiguous_multi_category", ambiguous),
            ("activities_cost_code_not_in_canonical", invalid),
            ("canonical_budget_code_keys", len(canonical_index["keys"])),
            ("canonical_distinct_cost_codes", len(canonical_index["by_cost_code"])),
            ("mapping_level", "cost_code_to_budget_key (category-level ambiguity preserved)"),
        ])),
    ])


# ---------------------------------------------------------------------------
# Risk register (Phase 7) + review items (Phase 12)
# ---------------------------------------------------------------------------

def build_schedule_risk_register(project_key: str, alignment_by_key: dict, rollup_by_key: dict,
                                 integrated_by_key: dict, crosswalk_rows: list[dict]) -> list[dict]:
    risks = []
    n = 0

    def _add(budget_key, rtype, severity, sched_ev, fin_ev, materiality_passed, action,
             requires_review, activity_ids, notes):
        nonlocal n
        n += 1
        risks.append(OrderedDict([
            ("risk_id", f"SR-{n:04d}"),
            ("project_key", project_key),
            ("budget_code_key", budget_key),
            ("risk_type", rtype),
            ("severity", severity),
            ("schedule_evidence", sched_ev),
            ("financial_evidence", fin_ev),
            ("materiality_passed", materiality_passed),
            ("recommended_action", action),
            ("requires_human_review", requires_review),
            ("supporting_activity_ids", activity_ids),
            ("notes", notes),
        ]))

    for key in sorted(alignment_by_key):
        al = alignment_by_key[key]
        ru = rollup_by_key.get(key, {})
        flags = set(al.get("schedule_alignment_flags", []))
        material = ru.get("schedule_remaining_work_status") == schedule_rollup.RW_MATERIAL
        neg = (ru.get("negative_float_activity_count") or 0) > 0
        exhaustion = "schedule_open_work_with_forecast_exhaustion" in flags
        sched_ev = OrderedDict([
            ("remaining_work_status", ru.get("schedule_remaining_work_status")),
            ("open_activity_count", ru.get("open_activity_count")),
            ("remaining_duration_days", ru.get("remaining_duration_days")),
            ("negative_float_activity_count", ru.get("negative_float_activity_count")),
        ])
        fin_ev = OrderedDict([
            ("current_projected_cost", al.get("current_projected_cost")),
            ("actual_cost_all_source_to_date", al.get("actual_cost_all_source_to_date")),
            ("existing_forecast_action", al.get("existing_forecast_action")),
        ])

        if exhaustion and neg and material:
            _add(key, "schedule_critical_remaining_work", "critical", sched_ev, fin_ev, True,
                 "Escalate: material remaining work + negative float + forecast exhaustion.", True, [],
                 "Negative-float open work with actuals >= 90% of projected.")
        elif exhaustion:
            _add(key, "schedule_open_work_with_forecast_exhaustion", "high", sched_ev, fin_ev, True,
                 "Review forecast adequacy: actuals near projected with material remaining work.", True, [], None)
        if "owner_complete_but_schedule_open" in flags:
            _add(key, "schedule_open_work_after_owner_complete", "high", sched_ev, fin_ev, material,
                 "Reconcile owner ~100% complete against open schedule work.", True, [], None)
        if "procore_complete_but_schedule_open" in flags:
            _add(key, "schedule_open_work_after_procore_complete", "medium", sched_ev, fin_ev, material,
                 "Reconcile Procore completion against open schedule work.", True, [], None)
        if neg and material and not exhaustion:
            _add(key, "schedule_negative_float_remaining_work", "high", sched_ev, fin_ev, True,
                 "Negative float on material remaining work; confirm cost exposure.", True, [], None)
        elif neg and not material:
            _add(key, "schedule_negative_float_remaining_work", "medium", sched_ev, fin_ev, False,
                 "Negative float present but remaining work immaterial.", True, [], None)
        if "schedule_complete_but_costs_trailing" in flags:
            _add(key, "schedule_complete_but_actuals_trailing", "low", sched_ev, fin_ev, True,
                 "Schedule complete while actuals trail projected; confirm remaining cost.", True, [], None)
        if "schedule_open_work_with_no_payapp_evidence" in flags:
            _add(key, "schedule_open_work_with_forecast_exhaustion" if exhaustion else "financial_budget_without_schedule_evidence",
                 "medium" if material else "low", sched_ev, fin_ev, material,
                 "Open schedule work with no owner/Procore pay-app evidence.", True, [], None)
        if ru.get("schedule_mapping_status") == "ambiguous":
            _add(key, "schedule_mapping_gap", "informational", sched_ev, fin_ev, False,
                 "Schedule cost code maps to multiple canonical categories; manual budget-key selection needed.",
                 True, [], None)

    # Activity-level mapping gaps from the crosswalk (cost codes not in canonical universe).
    for cx in crosswalk_rows:
        if cx["mapping_status"] == schedule_mapping.STATUS_INVALID:
            _add(None, "schedule_activity_without_budget_mapping", "informational",
                 OrderedDict([("schedule_cost_code", cx["schedule_cost_code"]),
                              ("activity_count", cx["activity_count"])]),
                 OrderedDict(), False,
                 "Schedule cost code absent from canonical BudgetDetails; cannot create a forecast row.",
                 True, cx["activity_ids"][:25], cx.get("notes"))

    risks.sort(key=lambda r: (r["budget_code_key"] or "~", r["risk_id"]))
    # Re-id after sort for stable ordering.
    for i, r in enumerate(risks, 1):
        r["risk_id"] = f"SR-{i:04d}"
    return risks


def build_review_items(project_key: str, crosswalk_rows: list[dict], rollup_by_key: dict,
                       alignment_by_key: dict, cashflow_by_key: dict, no_cost_code_count: int) -> list[dict]:
    items = []
    n = 0

    def _add(priority, rtype, budget_key, sched_cc, activity_ids, reason, action, source_files, notes):
        nonlocal n
        n += 1
        items.append(OrderedDict([
            ("review_item_id", f"SRI-{n:04d}"),
            ("priority", priority),
            ("review_type", rtype),
            ("budget_code_key", budget_key),
            ("schedule_cost_code", sched_cc),
            ("activity_ids", activity_ids),
            ("reason", reason),
            ("recommended_human_action", action),
            ("source_files", source_files),
            ("notes", notes),
        ]))

    for cx in crosswalk_rows:
        if cx["mapping_status"] == schedule_mapping.STATUS_AMBIGUOUS:
            material = any(rollup_by_key.get(k, {}).get("schedule_remaining_work_status") == schedule_rollup.RW_MATERIAL
                           for k in cx["candidate_budget_code_keys"])
            _add("high" if material else "medium", "schedule_budget_mapping", None, cx["schedule_cost_code"],
                 cx["activity_ids"][:25],
                 f"Cost code {cx['schedule_cost_code']} maps to {len(cx['candidate_budget_code_keys'])} canonical "
                 f"categories: {cx['candidate_budget_code_keys']}.",
                 "Select the correct budget category (or split) for these activities.",
                 ["schedule_to_budget_code_crosswalk.jsonl"], cx.get("notes"))
        elif cx["mapping_status"] == schedule_mapping.STATUS_INVALID:
            _add("medium", "schedule_budget_mapping", None, cx["schedule_cost_code"], cx["activity_ids"][:25],
                 f"Cost code {cx['schedule_cost_code']} not present in canonical BudgetDetails.",
                 "Confirm whether this scope belongs to an existing budget code.",
                 ["schedule_to_budget_code_crosswalk.jsonl"], cx.get("notes"))

    for key in sorted(alignment_by_key):
        al = alignment_by_key[key]
        flags = set(al.get("schedule_alignment_flags", []))
        if "owner_complete_but_schedule_open" in flags or "procore_complete_but_schedule_open" in flags:
            _add("high", "schedule_financial_alignment", key, None, [],
                 "Owner/Procore evidence indicates completion while schedule shows open work.",
                 "Reconcile completion evidence with remaining schedule scope.",
                 ["schedule_forecast_alignment_by_budget_code.jsonl"], None)
        if "schedule_critical_remaining_work" in flags:
            _add("high", "schedule_remaining_exposure", key, None, [],
                 "Negative-float material remaining work; potential cost exposure.",
                 "Review cost-to-complete against critical remaining scope.",
                 ["schedule_forecast_alignment_by_budget_code.jsonl"], None)

    # Cash-flow gaps: positive exposure but could not allocate (missing remaining dates).
    for key, rows in cashflow_by_key.items():
        if rows and rows[0]["allocation_method"] == cashflow.ALLOC_NOT_ALLOCATED \
                and D(rows[0]["remaining_forecast_exposure_total"]) > 0 \
                and rollup_by_key.get(key, {}).get("open_activity_count"):
            _add("medium", "cashflow_timing_review", key, None, [],
                 "Positive remaining exposure but mapped open activities lack usable remaining dates.",
                 "Confirm remaining activity dates to enable cash-flow timing.",
                 ["schedule_cashflow_timing_curve.jsonl"], None)

    if no_cost_code_count:
        _add("low", "schedule_logic_quality", None, None, [],
             f"{no_cost_code_count} schedule activities have no cost code (milestones/summary/admin).",
             "No action unless any should be financially mapped.",
             ["schedule_activity_forecast_features.jsonl"], None)

    items.sort(key=lambda r: ({"critical": 0, "high": 1, "medium": 2, "low": 3}[r["priority"]],
                              r["review_item_id"]))
    for i, r in enumerate(items, 1):
        r["review_item_id"] = f"SRI-{i:04d}"
    return items


# ---------------------------------------------------------------------------
# Main generation
# ---------------------------------------------------------------------------

def generate(project_key: str, cfg: dict, data_root: Optional[Path] = None,
             frozen_stamp: Optional[str] = None, out_root: Optional[Path] = None) -> dict:
    data_root = Path(data_root or cfg["default_data_root"])
    packages = schedule_io.discover_packages(data_root, cfg)
    for required in ("schedule_package", "context_package", "analysis_v2_package"):
        if not packages.get(required):
            raise SystemExit(f"ERROR: required {required} not found under {data_root}")

    schedule_pkg = packages["schedule_package"]
    context_pkg = packages["context_package"]
    analysis_pkg = packages["analysis_v2_package"]
    workpaper_pkg = packages["mapping_workpaper_package"]

    stamp = frozen_stamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    generated_ts = frozen_stamp if frozen_stamp else datetime.now().isoformat(timespec="seconds")
    out_base = Path(out_root) if out_root else data_root
    out = out_base / f"schedule_integrated_forecast_package_tropical_{stamp}"
    out.mkdir(parents=True, exist_ok=False)
    (out / "audit").mkdir(exist_ok=True)
    command = f"python3 -m construction_financial_review.cli schedule-integrate-forecast --project {project_key}"

    # ---- Load inputs -------------------------------------------------------
    manifest = schedule_io.read_schedule_manifest(schedule_pkg)
    validation = schedule_io.read_schedule_validation(schedule_pkg)
    activities = list(schedule_io.iter_activities(schedule_pkg))
    relationships = list(schedule_io.iter_relationships(schedule_pkg))
    budget_codes = list(read_jsonl(context_pkg / "canonical" / "budget_codes.jsonl"))
    context_rows = list(read_jsonl(context_pkg / "summaries" / "budget_code_forecast_context.jsonl"))
    context_by_key = {r["budget_code_key"]: r for r in context_rows}
    recs = list(read_jsonl(analysis_pkg / "forecast_recommendations_by_budget_code.jsonl"))
    v2_risks = list(read_jsonl(analysis_pkg / "forecast_risk_register.jsonl"))
    workpaper_rows = []
    if workpaper_pkg and (workpaper_pkg / "budget_code_scope_reconciliation.jsonl").exists():
        workpaper_rows = list(read_jsonl(workpaper_pkg / "budget_code_scope_reconciliation.jsonl"))

    # ---- Map + roll up -----------------------------------------------------
    index = schedule_mapping.build_canonical_index(budget_codes)
    decisions = schedule_mapping.map_activities(activities, index)
    decisions_by_objid = {d["activity_object_id"]: d for d in decisions}
    crosswalk_rows = schedule_mapping.aggregate_crosswalk(decisions)
    features = schedule_rollup.build_activity_features(activities, decisions_by_objid)
    rollup = schedule_rollup.build_budget_rollup(budget_codes, features, project_key)
    rollup_by_key = {r["budget_code_key"]: r for r in rollup}

    # ---- Integrate forecast (Phases 6, 9) ----------------------------------
    integrated, alignment = [], []
    for rec in recs:
        key = rec["budget_code_key"]
        ru = rollup_by_key.get(key, {})
        integrated.append(forecast_integration.integrate_recommendation(rec, ru))
        alignment.append(forecast_integration.build_alignment_row(rec, ru, context_by_key.get(key), project_key))
    integrated.sort(key=lambda r: r["budget_code_key"])
    alignment.sort(key=lambda r: r["budget_code_key"])
    integrated_by_key = {r["budget_code_key"]: r for r in integrated}
    alignment_by_key = {r["budget_code_key"]: r for r in alignment}

    # ---- Cash-flow timing (Phase 8) ----------------------------------------
    mapped_open_by_key: dict[str, list] = {}
    for f in features:
        if f["schedule_mapping_status"] == schedule_mapping.STATUS_MAPPED and f["is_open"] and f["mapped_budget_code_key"]:
            mapped_open_by_key.setdefault(f["mapped_budget_code_key"], []).append(f)
    cashflow_rows, cashflow_by_key = [], {}
    for rec in integrated:
        key = rec["budget_code_key"]
        exposure = cashflow.remaining_forecast_exposure(
            rec.get("current_projected_cost"), rec.get("actual_cost_all_source_to_date"),
            rec.get("schedule_integrated_recommended_projected_cost"))
        rows = cashflow.allocate_budget_code(key, project_key, exposure, mapped_open_by_key.get(key, []))
        cashflow_by_key[key] = rows
        cashflow_rows.extend(rows)
    cashflow_rows.sort(key=lambda r: (r["budget_code_key"], r["month"] or "~"))

    # ---- Risk + review (Phases 7, 10, 12) ----------------------------------
    no_cc = sum(1 for d in decisions if not d["schedule_cost_code"])
    sched_risks = build_schedule_risk_register(project_key, alignment_by_key, rollup_by_key,
                                               integrated_by_key, crosswalk_rows)
    review_items = build_review_items(project_key, crosswalk_rows, rollup_by_key, alignment_by_key,
                                      cashflow_by_key, no_cc)

    integrated_risks = []
    for r in v2_risks:
        rr = OrderedDict(r)
        rr["risk_source"] = "v2_baseline"
        rr["original_risk_id"] = r.get("risk_id")
        rr["schedule_integrated_severity"] = r.get("severity")
        integrated_risks.append(rr)
    for r in sched_risks:
        rr = OrderedDict(r)
        rr["risk_source"] = "schedule_integration"
        rr["original_risk_id"] = None
        rr["schedule_integrated_severity"] = r.get("severity")
        integrated_risks.append(rr)

    # ---- Inventories -------------------------------------------------------
    pkg_inventory = build_schedule_package_inventory(schedule_pkg, manifest)
    health = build_schedule_health(manifest, validation, activities, decisions, index)

    activity_inventory = [OrderedDict([
        ("activity_id", a.get("activity_id")),
        ("activity_name", a.get("activity_name")),
        ("activity_type", a.get("activity_type")),
        ("status", a.get("status")),
        ("wbs_code", a.get("wbs_code")),
        ("wbs_name", a.get("wbs_name")),
        ("is_milestone", schedule_io.is_milestone(a.get("activity_type"))),
        ("schedule_cost_code", decisions_by_objid.get(a.get("activity_object_id"), {}).get("schedule_cost_code")),
        ("mapping_status", decisions_by_objid.get(a.get("activity_object_id"), {}).get("mapping_status")),
        ("total_float_days", schedule_io.total_float_days(a)),
        ("remaining_duration_days", (a.get("durations") or {}).get("remaining_duration_days_8h")),
    ]) for a in activities]
    activity_inventory.sort(key=lambda r: (r["activity_id"] or ""))

    relationship_inventory = [OrderedDict([
        ("relationship_object_id", r.get("relationship_object_id")),
        ("predecessor_activity_id", r.get("predecessor_activity_id")),
        ("successor_activity_id", r.get("successor_activity_id")),
        ("relationship_type", r.get("relationship_type")),
        ("lag", r.get("lag")),
    ]) for r in relationships]
    relationship_inventory.sort(key=lambda r: (r["relationship_object_id"] or 0))

    milestone_summary = [OrderedDict([
        ("activity_id", a.get("activity_id")),
        ("activity_name", a.get("activity_name")),
        ("activity_type", a.get("activity_type")),
        ("status", a.get("status")),
        ("finish_date", (a.get("dates") or {}).get("finish")),
        ("total_float_days", schedule_io.total_float_days(a)),
    ]) for a in activities if schedule_io.is_milestone(a.get("activity_type"))]
    milestone_summary.sort(key=lambda r: (r["finish_date"] or "~", r["activity_id"] or ""))

    evidence_alignment = [OrderedDict([
        ("project_key", project_key),
        ("budget_code_key", a["budget_code_key"]),
        ("actual_cost_all_source_to_date", a["actual_cost_all_source_to_date"]),
        ("owner_latest_percent_complete", a["owner_latest_percent_complete"]),
        ("procore_latest_completed_to_date", a["procore_latest_completed_to_date"]),
        ("schedule_remaining_work_status", a["schedule_remaining_work_status"]),
        ("schedule_open_activity_count", a["schedule_open_activity_count"]),
        ("schedule_forecast_implication", a["schedule_forecast_implication"]),
        ("schedule_alignment_flags", a["schedule_alignment_flags"]),
    ]) for a in alignment]

    # ---- Adjustment trace (audit) ------------------------------------------
    adj_trace = [OrderedDict([
        ("budget_code_key", r["budget_code_key"]),
        ("base_forecast_action", r.get("forecast_action")),
        ("schedule_integrated_forecast_action", r.get("schedule_integrated_forecast_action")),
        ("action_changed_by_schedule", r.get("action_changed_by_schedule")),
        ("schedule_forecast_implication", r.get("schedule_forecast_implication")),
        ("schedule_remaining_work_status", r.get("schedule_remaining_work_status")),
        ("confidence_before_schedule", r.get("confidence_before_schedule")),
        ("confidence_after_schedule", r.get("confidence_after_schedule")),
        ("schedule_review_notes", r.get("schedule_review_notes")),
    ]) for r in integrated if r.get("action_changed_by_schedule") or r.get("schedule_risk_flags")]
    adj_trace.sort(key=lambda r: r["budget_code_key"])

    # ---- Write data artifacts ---------------------------------------------
    write_json(out / "schedule_package_inventory.json", pkg_inventory)
    write_json(out / "schedule_health_summary.json", health)
    write_jsonl(out / "schedule_activity_inventory.jsonl", activity_inventory)
    write_jsonl(out / "schedule_relationship_inventory.jsonl", relationship_inventory)
    write_jsonl(out / "schedule_milestone_summary.jsonl", milestone_summary)
    write_jsonl(out / "schedule_to_budget_code_crosswalk.jsonl", crosswalk_rows)
    write_jsonl(out / "schedule_budget_code_rollup.jsonl", rollup)
    write_jsonl(out / "schedule_activity_forecast_features.jsonl", features)
    write_jsonl(out / "schedule_forecast_alignment_by_budget_code.jsonl", alignment)
    write_jsonl(out / "schedule_risk_register.jsonl", sched_risks)
    write_jsonl(out / "schedule_cashflow_timing_curve.jsonl", cashflow_rows)
    write_jsonl(out / "schedule_mapping_review_items.jsonl", review_items)
    write_jsonl(out / "forecast_recommendations_schedule_integrated.jsonl", integrated)
    write_jsonl(out / "forecast_risk_register_schedule_integrated.jsonl", integrated_risks)
    write_jsonl(out / "evidence_alignment_schedule_integrated.jsonl", evidence_alignment)
    write_jsonl(out / "audit" / "forecast_adjustment_trace.jsonl", adj_trace)
    write_json(out / "audit" / "schedule_health_snapshot.json", health)

    # ---- Summaries ---------------------------------------------------------
    action_changes = Counter()
    blocked_decreases, strengthened_reviews, material_keys, neg_float_keys, exhaustion_keys = [], [], [], [], []
    for r in integrated:
        if r.get("action_changed_by_schedule"):
            action_changes[f"{r.get('forecast_action')} -> {r.get('schedule_integrated_forecast_action')}"] += 1
        if "schedule_blocks_decrease" in (r.get("schedule_risk_flags") or []):
            blocked_decreases.append(r["budget_code_key"])
        if r.get("schedule_forecast_implication") == forecast_integration.IMPL_STRENGTHENS_REVIEW:
            strengthened_reviews.append(r["budget_code_key"])
        ru = rollup_by_key.get(r["budget_code_key"], {})
        if ru.get("schedule_remaining_work_status") == schedule_rollup.RW_MATERIAL:
            material_keys.append(r["budget_code_key"])
        if (ru.get("negative_float_activity_count") or 0) > 0:
            neg_float_keys.append(r["budget_code_key"])
        if "schedule_open_work_with_forecast_exhaustion" in (r.get("schedule_risk_flags") or []):
            exhaustion_keys.append(r["budget_code_key"])

    cashflow_alloc_rows = [r for r in cashflow_rows if r["allocation_method"] != cashflow.ALLOC_NOT_ALLOCATED]
    review_counts = Counter(i["priority"] for i in review_items)

    conclusion = CONCLUSION_REVIEW if review_items else CONCLUSION_READY

    integration_summary = OrderedDict([
        ("project_key", project_key),
        ("conclusion", conclusion),
        ("schedule_package_path", str(schedule_pkg)),
        ("schedule_data_date", manifest.get("metadata", {}).get("data_date")),
        ("scheduled_finish_date", manifest.get("metadata", {}).get("scheduled_finish_date")),
        ("total_activities", len(activities)),
        ("activity_status_counts", manifest.get("activity_status_counts", {})),
        ("total_relationships", len(relationships)),
        ("cost_code_mapped_activity_count",
         sum(1 for d in decisions if d["mapping_status"] == schedule_mapping.STATUS_MAPPED)),
        ("ambiguous_activity_count",
         sum(1 for d in decisions if d["mapping_status"] == schedule_mapping.STATUS_AMBIGUOUS)),
        ("unmapped_activity_count",
         sum(1 for d in decisions if d["mapping_status"] in (schedule_mapping.STATUS_NA, schedule_mapping.STATUS_INVALID))),
        ("mapped_budget_key_count", len({d["mapped_budget_code_key"] for d in decisions if d.get("mapped_budget_code_key")})),
        ("budget_codes_material_remaining_work", len(material_keys)),
        ("budget_codes_schedule_blocked_decrease", blocked_decreases),
        ("budget_codes_schedule_strengthened_review", strengthened_reviews),
        ("budget_codes_forecast_exhaustion_with_open_work", exhaustion_keys),
        ("budget_codes_negative_float_remaining_work", neg_float_keys),
        ("cashflow_timing_rows_generated", len(cashflow_alloc_rows)),
        ("forecast_action_changes", dict(action_changes)),
        ("manual_review_item_counts_by_priority", dict(review_counts)),
        ("manual_review_item_total", len(review_items)),
    ])
    write_json(out / "schedule_integration_summary.json", integration_summary)
    _write_summaries(out, project_key, integration_summary, integrated, alignment_by_key,
                     rollup_by_key, material_keys, neg_float_keys, blocked_decreases, review_items)

    # ---- Audit: source files / validation snapshots ------------------------
    source_files_used = OrderedDict([
        ("schedule_package", str(schedule_pkg)),
        ("context_package", str(context_pkg)),
        ("analysis_v2_package", str(analysis_pkg)),
        ("mapping_workpaper_package", str(workpaper_pkg) if workpaper_pkg else None),
        ("mapping_workpaper_present", bool(workpaper_pkg)),
        ("baseline_recommendation_file", "forecast_recommendations_by_budget_code.jsonl (crosswalk_v2)"),
    ])
    write_json(out / "audit" / "source_files_used.json", source_files_used)
    write_json(out / "audit" / "source_validation_snapshot.json", OrderedDict([
        ("schedule_validation_summary", validation.get("summary", {})),
        ("schedule_validation_warnings", validation.get("validation_warnings", [])),
        ("context_recommendation_rows", len(recs)),
        ("canonical_budget_codes", len(budget_codes)),
        ("workpaper_reconciliation_rows", len(workpaper_rows)),
    ]))
    write_json(out / "audit" / "schedule_cost_code_mapping_snapshot.json", OrderedDict([
        ("crosswalk_row_count", len(crosswalk_rows)),
        ("status_counts", dict(Counter(c["mapping_status"] for c in crosswalk_rows))),
        ("distinct_cost_codes", len({c["schedule_cost_code"] for c in crosswalk_rows if c["schedule_cost_code"]})),
        ("mapped_budget_keys", sorted({c["mapped_budget_code_key"] for c in crosswalk_rows if c["mapped_budget_code_key"]})),
    ]))

    # ---- README / SCHEMA ---------------------------------------------------
    meta = _generation_metadata(command, packages, stamp, generated_ts)
    _write_readme(out, project_key, meta, integration_summary)
    _write_schema(out)
    write_json(out / "input_inventory.json", _input_inventory(meta, schedule_pkg, context_pkg, analysis_pkg, workpaper_pkg))

    # ---- Validation + safety + manifest ------------------------------------
    data_files = sorted(p for p in out.rglob("*") if p.is_file()
                        and p.name not in ("manifest.json", "validation_report.json"))
    safety = safety_scan(data_files)
    write_json(out / "audit" / "safety_scan_report.json", safety)

    validation_report = _build_validation_report(out, integrated, recs, budget_codes, cashflow_by_key,
                                                 crosswalk_rows, index, safety, conclusion, meta)
    write_json(out / "validation_report.json", validation_report)

    manifest_out = _build_manifest(out, project_key, meta, conclusion, validation_report)
    write_json(out / "manifest.json", manifest_out)

    return {
        "output_package": str(out),
        "conclusion": conclusion,
        "integration_summary": integration_summary,
        "validation_passed": validation_report["passed"],
        "safety_passed": safety["passed"],
    }


def _input_inventory(meta, schedule_pkg, context_pkg, analysis_pkg, workpaper_pkg) -> OrderedDict:
    return OrderedDict([
        ("generation", meta),
        ("inputs", OrderedDict([
            ("schedule_package", str(schedule_pkg)),
            ("forecast_context_package", str(context_pkg)),
            ("forecast_analysis_crosswalk_v2_package", str(analysis_pkg)),
            ("mapping_discrepancy_workpaper_package", str(workpaper_pkg) if workpaper_pkg else None),
        ])),
    ])


def _build_validation_report(out, integrated, recs, budget_codes, cashflow_by_key, crosswalk_rows,
                             index, safety, conclusion, meta) -> OrderedDict:
    canonical_keys = index["keys"]
    integrated_keys = [r["budget_code_key"] for r in integrated]
    one_per_key = len(integrated_keys) == len(canonical_keys) == len(set(integrated_keys))
    all_keys_canonical = all(k in canonical_keys for k in integrated_keys)
    # No schedule-only numeric increase: integrated projected never exceeds the v2 recommendation.
    base_by_key = {r["budget_code_key"]: r for r in recs}
    no_schedule_increase = True
    for r in integrated:
        base = base_by_key.get(r["budget_code_key"], {})
        bi = dec(base.get("recommended_projected_cost"))
        si = dec(r.get("schedule_integrated_recommended_projected_cost"))
        if bi is not None and si is not None and si > bi:
            no_schedule_increase = False
            break
    # Schedule blocked decreases where applicable (every decrease that was material -> review).
    blocked_ok = all(
        r.get("schedule_integrated_forecast_action") != "decrease_forecast"
        for r in integrated
        if "schedule_blocks_decrease" in (r.get("schedule_risk_flags") or []))
    # Cash-flow allocation ties.
    cashflow_ok = True
    for key, rows in cashflow_by_key.items():
        exposure = dec(rows[0]["remaining_forecast_exposure_total"]) if rows else Decimal("0")
        if not cashflow.allocation_ties(rows, exposure or Decimal("0")):
            cashflow_ok = False
            break
    no_fuzzy = all(c["mapping_method"] != "fuzzy" for c in crosswalk_rows)
    mapped_in_canonical = all(
        c["mapped_budget_code_key"] in canonical_keys
        for c in crosswalk_rows if c["mapped_budget_code_key"])

    parse = all_files_parse([p for p in out.rglob("*") if p.suffix in (".json", ".jsonl")])

    checks = OrderedDict([
        ("output_files_parse", parse["_all_passed"]),
        ("one_recommendation_row_per_canonical_key", one_per_key),
        ("all_recommendation_keys_canonical", all_keys_canonical),
        ("schedule_did_not_create_numeric_increase", no_schedule_increase),
        ("schedule_blocked_decreases_where_material", blocked_ok),
        ("cashflow_allocation_ties_to_exposure", cashflow_ok),
        ("no_fuzzy_mapping_method", no_fuzzy),
        ("mapped_budget_keys_in_canonical", mapped_in_canonical),
        ("safety_scan_passed", safety["passed"]),
    ])
    passed = all(bool(v) for v in checks.values())
    return OrderedDict([
        ("generated_timestamp_local", meta["generated_timestamp_local"]),
        ("package_stamp", meta["package_stamp"]),
        ("checks", checks),
        ("recommendation_row_count", len(integrated)),
        ("canonical_budget_code_count", len(canonical_keys)),
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
            files.append(OrderedDict([
                ("path", str(rel)),
                ("size_bytes", p.stat().st_size),
                ("row_count", rows),
                ("sha256", sha256_file(p)),
            ]))
    return OrderedDict([
        ("package_name", out.name),
        ("project", OrderedDict([
            ("project_key", project_key),
            ("project_name", "Tropical World Nursery Senior Living Facility"),
            ("job_reference", "23-435-01"),
            ("forecast_period", "2026-June"),
        ])),
        ("generation", meta),
        ("output_files", files),
        ("validation_status", OrderedDict([
            ("passed", validation_report["passed"]),
            ("checks", validation_report["checks"]),
        ])),
        ("conclusion", conclusion),
    ])


def _write_summaries(out, project_key, summary, integrated, alignment_by_key, rollup_by_key,
                     material_keys, neg_float_keys, blocked_decreases, review_items):
    def _top(keys, n=10):
        return keys[:n]

    def _bullets(keys, n=10):
        top = _top(keys, n)
        return [f"- {k}" for k in top] if top else ["- none"]

    review_md = [
        "# Schedule-Integrated Forecast — Reviewer Summary",
        "",
        f"Project: Tropical World Nursery Senior Living Facility ({project_key} / 23-435-01 / 2026-June)",
        f"Baseline: crosswalk_v2 recommendations. Conclusion: **{summary['conclusion']}**.",
        "",
        "## What changed from the prior forecast analysis",
        "Schedule evidence is applied as timing/remaining-work/risk only. It never sets a number, "
        "creates an increase, or creates a decrease. Action changes:",
        "",
        f"- Forecast action changes caused by schedule: `{summary['forecast_action_changes'] or 'none'}`",
        f"- Budget codes where schedule blocked a decrease: {blocked_decreases or 'none'}",
        f"- Budget codes where schedule strengthened review_required: "
        f"{summary['budget_codes_schedule_strengthened_review'] or 'none'}",
        "",
        "## Top budget codes with material remaining schedule work",
        *_bullets(material_keys),
        "",
        "## Top budget codes with negative-float remaining work",
        *_bullets(neg_float_keys),
        "",
        "## Top budget codes with forecast exhaustion + open schedule work",
        *_bullets(summary['budget_codes_forecast_exhaustion_with_open_work']),
        "",
        "## Cash-flow timing",
        f"- Allocated month-rows generated: {summary['cashflow_timing_rows_generated']} "
        "(duration-weighted, confidence capped at medium).",
        "",
        "## Manual schedule review items",
        f"- Total: {summary['manual_review_item_total']} "
        f"(by priority: {summary['manual_review_item_counts_by_priority']})",
        "",
        "## Known limitations",
        "- Schedule supplies cost code but not budget category; cost codes spanning multiple "
        "categories remain ambiguous (no forced mapping).",
        "- Activities without a cost code are not financially mapped.",
        "- Critical/longest-path is a `total_float <= 0` proxy; escalation uses negative float on open work.",
        "",
    ]
    (out / "forecast_review_summary_schedule_integrated.md").write_text("\n".join(review_md), encoding="utf-8")

    exec_md = [
        "# Schedule-Integrated Forecast — Executive Summary",
        "",
        f"Project: Tropical World Nursery Senior Living Facility ({project_key} / 23-435-01 / 2026-June)",
        "",
        "Schedule data is used strictly as **timing and risk evidence** — not as actual cost and not "
        "as an independent cost driver. No recommended final cost was set by the schedule.",
        "",
        f"- Total forecast adjustment changes vs prior package: schedule changed "
        f"{sum(summary['forecast_action_changes'].values()) if summary['forecast_action_changes'] else 0} "
        "budget-code actions (review-strengthening / decrease-blocking only).",
        f"- Added schedule review items: {summary['manual_review_item_total']}.",
        f"- Budget codes with material remaining schedule work: {summary['budget_codes_material_remaining_work']}.",
        f"- Forecast-exhaustion + open schedule work: "
        f"{len(summary['budget_codes_forecast_exhaustion_with_open_work'])} budget code(s).",
        "",
        "## Most important schedule-driven forecast risks",
        *_bullets(summary['budget_codes_forecast_exhaustion_with_open_work'] + neg_float_keys, 8),
        "",
        "## Recommended human review priorities",
        "1. Reconcile any owner/Procore completion that conflicts with open schedule work.",
        "2. Resolve ambiguous schedule cost-code -> budget category selections.",
        "3. Confirm remaining cost-to-complete where negative float coincides with material remaining work.",
        "",
    ]
    (out / "executive_forecast_summary_schedule_integrated.md").write_text("\n".join(exec_md), encoding="utf-8")


def _write_readme(out, project_key, meta, summary):
    md = [
        f"# schedule_integrated_forecast_package_tropical ({meta['package_stamp']})",
        "",
        "Schedule-integrated forecast review for Tropical World Nursery Senior Living Facility "
        f"({project_key} / 23-435-01 / 2026-June).",
        "",
        "Schedule data is **timing / remaining-work / sequencing / risk** evidence only. It never "
        "becomes accounting actual cost, never independently earns value, and never by itself sets a "
        "recommended final cost. Baseline recommendations come from the crosswalk_v2 analysis package.",
        "",
        f"- Conclusion: **{summary['conclusion']}**",
        f"- Schedule data date: {summary['schedule_data_date']}; scheduled finish: {summary['scheduled_finish_date']}",
        f"- Activities: {summary['total_activities']}; relationships: {summary['total_relationships']}",
        f"- Mapped activities: {summary['cost_code_mapped_activity_count']}; "
        f"ambiguous: {summary['ambiguous_activity_count']}; unmapped: {summary['unmapped_activity_count']}",
        f"- Manual review items: {summary['manual_review_item_total']}",
        "",
        "See `SCHEMA.md` for the file-by-file field reference and `validation_report.json` for the "
        "validation gate results. Generation metadata (git branch/HEAD/dirty, command, selected inputs) "
        "is recorded in `input_inventory.json` and `manifest.json`.",
        "",
    ]
    (out / "README.md").write_text("\n".join(md), encoding="utf-8")


def _write_schema(out):
    md = [
        "# Schedule-Integrated Forecast Package — Schema",
        "",
        "Money is Decimal-string (2dp). Float days are 8h-day values from the schedule. JSONL is "
        "deterministically sorted by primary key.",
        "",
        "## Files",
        "- `schedule_package_inventory.json` — schedule package files, sizes, record counts, metadata.",
        "- `schedule_health_summary.json` — activity/relationship/float/mapping health.",
        "- `schedule_activity_inventory.jsonl` — one compact row per schedule activity.",
        "- `schedule_relationship_inventory.jsonl` — one row per logic relationship.",
        "- `schedule_milestone_summary.jsonl` — milestone activities.",
        "- `schedule_to_budget_code_crosswalk.jsonl` — cost code -> budget_code_key mapping decisions "
        "(canonical authority; extractor candidates are supporting evidence only).",
        "- `schedule_budget_code_rollup.jsonl` — one row per canonical budget key; remaining-work status + risk.",
        "- `schedule_activity_forecast_features.jsonl` — one row per activity with full forecast features.",
        "- `schedule_forecast_alignment_by_budget_code.jsonl` — schedule vs actual/owner/Procore alignment.",
        "- `schedule_risk_register.jsonl` — schedule-derived risks.",
        "- `schedule_cashflow_timing_curve.jsonl` — duration-weighted remaining-exposure timing (timing only).",
        "- `schedule_mapping_review_items.jsonl` — manual review items.",
        "- `forecast_recommendations_schedule_integrated.jsonl` — v2 recommendations + schedule fields (one per canonical key).",
        "- `forecast_risk_register_schedule_integrated.jsonl` — v2 risks preserved + schedule risks appended.",
        "- `evidence_alignment_schedule_integrated.jsonl` — compact evidence/alignment per budget key.",
        "- `schedule_integration_summary.json`, `forecast_review_summary_schedule_integrated.md`, "
        "`executive_forecast_summary_schedule_integrated.md` — summaries.",
        "- `audit/` — source files used, validation snapshots, health snapshot, cost-code mapping snapshot, "
        "forecast adjustment trace, safety scan.",
        "",
        "## Key rules",
        "- `actuals_near_projected` (forecast exhaustion) = actual >= 0.90 * current_projected_cost.",
        "- Material remaining work = >= 3 open activities OR >= 14 remaining 8h-days.",
        "- `total_float <= 0` = critical/longest-path proxy only; escalation uses negative float (< 0) on open work.",
        "- Cash-flow allocation confidence capped at `medium`; ambiguous/unmapped stays `not_allocated`.",
        "",
    ]
    (out / "SCHEMA.md").write_text("\n".join(md), encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------

def run(project_key: str, cfg: dict, data_root: Optional[str] = None,
        frozen_stamp: Optional[str] = None, out_root: Optional[str] = None) -> int:
    result = generate(project_key, cfg, Path(data_root) if data_root else None,
                      frozen_stamp, Path(out_root) if out_root else None)
    print(json.dumps({
        "status": "ok",
        "output_package": result["output_package"],
        "conclusion": result["conclusion"],
        "validation_passed": result["validation_passed"],
        "safety_passed": result["safety_passed"],
    }, indent=2))
    return 0 if result["validation_passed"] else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog=GENERATOR_NAME)
    ap.add_argument("--project", default="tropical")
    ap.add_argument("--data-root", default=None)
    ap.add_argument("--frozen-stamp", default=None)
    ap.add_argument("--out-root", default=None)
    args = ap.parse_args(argv)
    cfg_path = SUBPROJECT_ROOT / "config" / "projects" / f"{args.project}.json"
    cfg = read_json(cfg_path)
    return run(args.project, cfg, args.data_root, args.frozen_stamp, args.out_root)


if __name__ == "__main__":
    sys.exit(main())
