"""Activity-level forecast features (Phase 4) and per-budget-code schedule rollup (Phase 5).

Approved refinement: ``total_float <= 0`` is a critical/longest-path *proxy only*. Risk
**escalation** keys on **negative** float (``< 0``) on **open** work — never zero float alone.
Schedule percent-complete is duration progress, never cost progress.
"""
from __future__ import annotations

from collections import OrderedDict
from typing import Optional

from ..common.money import D, dec
from . import schedule_io, schedule_mapping

# --- deterministic materiality thresholds (documented in docs/workflow/06) -------------------
MATERIAL_OPEN_ACTIVITY_COUNT = 3          # >= 3 open activities is material
MATERIAL_REMAINING_DURATION_DAYS = 14     # >= 14 8h-days of remaining work is material

# remaining_work_status values
RW_NONE = "no_schedule_evidence"
RW_COMPLETE = "complete"
RW_MINOR = "minor_remaining_work"
RW_MATERIAL = "material_remaining_work"
RW_AMBIGUOUS = "unmapped_or_ambiguous"

# schedule_risk_level values
RISK_NONE = "none"
RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"
RISK_CRITICAL = "critical"


def _f(activity: dict) -> Optional[float]:
    v = schedule_io.total_float_days(activity)
    return None if v is None else float(v)


def build_activity_features(activities: list[dict], decisions_by_objid: dict) -> list[dict]:
    """One feature row per schedule activity (Phase 4)."""
    rows = []
    for a in activities:
        objid = a.get("activity_object_id")
        d = decisions_by_objid.get(objid, {})
        status = schedule_io.normalize_status(a.get("status"))
        codes = a.get("activity_codes") or {}
        dates = a.get("dates") or {}
        durations = a.get("durations") or {}
        progress = a.get("progress") or {}
        constraints = a.get("constraints") or {}
        tf = schedule_io.total_float_days(a)
        tf_f = None if tf is None else float(tf)
        open_work = not status["is_completed"]
        is_neg = tf_f is not None and tf_f < 0
        is_crit_proxy = tf_f is not None and tf_f <= 0
        mapping_status = d.get("mapping_status", schedule_mapping.STATUS_NA)
        mapped_key = d.get("mapped_budget_code_key")

        # forecast_use priority
        if not d.get("schedule_cost_code"):
            forecast_use = "not_used"
        elif mapping_status in (schedule_mapping.STATUS_AMBIGUOUS, schedule_mapping.STATUS_INVALID):
            forecast_use = "mapping_review"
        elif status["is_completed"]:
            forecast_use = "alignment_check"
        elif schedule_io.remaining_start(a) and schedule_io.remaining_finish(a):
            forecast_use = "cashflow_timing"
        else:
            forecast_use = "remaining_exposure_review"

        rows.append(OrderedDict([
            ("activity_id", a.get("activity_id")),
            ("activity_object_id", objid),
            ("activity_code", d.get("schedule_cost_code")),
            ("activity_name", a.get("activity_name")),
            ("wbs_code", a.get("wbs_code")),
            ("wbs_name", a.get("wbs_name")),
            ("activity_type", a.get("activity_type")),
            ("status", a.get("status")),
            ("is_completed", status["is_completed"]),
            ("is_in_progress", status["is_in_progress"]),
            ("is_not_started", status["is_not_started"]),
            ("is_milestone", schedule_io.is_milestone(a.get("activity_type"))),
            ("is_loe_or_summary", schedule_io.is_loe_or_summary(a.get("activity_type"))),
            ("start_date", schedule_io._dates(a).get("start")),
            ("finish_date", dates.get("finish")),
            ("actual_start", dates.get("actual_start")),
            ("actual_finish", dates.get("actual_finish")),
            ("remaining_start", dates.get("remaining_early_start")),
            ("remaining_finish", dates.get("remaining_early_finish")),
            ("original_duration_days", durations.get("original_duration_days_8h")),
            ("remaining_duration_days", durations.get("remaining_duration_days_8h")),
            ("percent_complete", progress.get("activity_percent_complete")),
            ("duration_percent_complete", progress.get("duration_percent_complete")),
            ("physical_percent_complete", progress.get("physical_percent_complete")),
            ("total_float_days", tf),
            ("free_float_days", schedule_io._float(a).get("free_float_days_8h")),
            ("is_negative_float", is_neg),
            ("is_zero_or_negative_float_proxy", is_crit_proxy),
            ("is_critical_or_longest_path", is_crit_proxy),  # proxy: total_float <= 0
            ("primary_constraint_type", constraints.get("primary_constraint_type")),
            ("primary_constraint_date", constraints.get("primary_constraint_date")),
            ("predecessor_count", schedule_io.predecessor_count(a)),
            ("successor_count", schedule_io.successor_count(a)),
            ("has_open_start", schedule_io.predecessor_count(a) == 0),
            ("has_open_finish", schedule_io.successor_count(a) == 0),
            ("schedule_cost_code", d.get("schedule_cost_code")),
            ("schedule_cost_code_family", d.get("schedule_cost_code_family")),
            ("mapped_budget_code_key", mapped_key),
            ("schedule_mapping_status", mapping_status),
            ("schedule_mapping_confidence", d.get("mapping_confidence", "none")),
            ("candidate_budget_code_keys", d.get("candidate_budget_code_keys", [])),
            ("is_open", open_work),
            ("forecast_use", forecast_use),
            ("notes", d.get("notes")),
        ]))
    rows.sort(key=lambda r: (r["activity_id"] or ""))
    return rows


def _classify_remaining_work(open_count: int, remaining_duration: D) -> str:
    if open_count == 0:
        return RW_COMPLETE
    material = (open_count >= MATERIAL_OPEN_ACTIVITY_COUNT
               or remaining_duration >= D(MATERIAL_REMAINING_DURATION_DAYS))
    return RW_MATERIAL if material else RW_MINOR


def _risk_level(remaining_status: str, neg_float_open: int) -> str:
    """Schedule-only risk level. Critical is reserved for the alignment stage (needs $ exposure)."""
    if remaining_status == RW_NONE:
        return RISK_NONE
    if remaining_status == RW_AMBIGUOUS:
        return RISK_LOW
    if remaining_status == RW_COMPLETE:
        return RISK_NONE
    if remaining_status == RW_MATERIAL:
        return RISK_HIGH if neg_float_open > 0 else RISK_MEDIUM
    # minor remaining work
    return RISK_LOW


def build_budget_rollup(budget_codes: list[dict], features: list[dict], project_key: str) -> list[dict]:
    """One rollup row per canonical budget key (Phase 5), whether schedule evidence exists or not."""
    # Index mapped features by their assigned key; ambiguous features by each candidate key.
    mapped_by_key: dict[str, list] = {}
    ambiguous_by_key: dict[str, list] = {}
    for f in features:
        if f["schedule_mapping_status"] == schedule_mapping.STATUS_MAPPED and f["mapped_budget_code_key"]:
            mapped_by_key.setdefault(f["mapped_budget_code_key"], []).append(f)
        elif f["schedule_mapping_status"] == schedule_mapping.STATUS_AMBIGUOUS:
            for k in f.get("candidate_budget_code_keys", []):
                ambiguous_by_key.setdefault(k, []).append(f)

    rows = []
    for bc in budget_codes:
        key = bc.get("budget_code_key")
        mapped = mapped_by_key.get(key, [])
        ambiguous = ambiguous_by_key.get(key, [])

        open_feats = [f for f in mapped if f["is_open"]]
        completed = [f for f in mapped if f["is_completed"]]
        in_prog = [f for f in mapped if f["is_in_progress"]]
        not_started = [f for f in mapped if f["is_not_started"]]
        milestones = [f for f in mapped if f["is_milestone"]]
        remaining_duration = D(0)
        for f in open_feats:
            remaining_duration += D(f.get("remaining_duration_days"))

        floats_open = [float(f["total_float_days"]) for f in open_feats if f["total_float_days"] is not None]
        neg_float_open = sum(1 for v in floats_open if v < 0)
        crit_proxy_open = sum(1 for v in floats_open if v <= 0)

        if mapped:
            remaining_status = _classify_remaining_work(len(open_feats), remaining_duration)
            mapping_status = "mapped"
            mapping_conf = "high"
        elif ambiguous:
            remaining_status = RW_AMBIGUOUS
            mapping_status = "ambiguous"
            mapping_conf = "low"
        else:
            remaining_status = RW_NONE
            mapping_status = "none"
            mapping_conf = "none"

        risk_flags = []
        if remaining_status == RW_MATERIAL:
            risk_flags.append("material_remaining_work")
        if neg_float_open > 0:
            risk_flags.append("negative_float_remaining_work")
        if crit_proxy_open > 0:
            risk_flags.append("critical_or_longest_path_proxy_remaining_work")
        if remaining_status == RW_AMBIGUOUS:
            risk_flags.append("schedule_mapping_ambiguous")

        def _dmin(vals):
            vals = [v for v in vals if v]
            return min(vals) if vals else None

        def _dmax(vals):
            vals = [v for v in vals if v]
            return max(vals) if vals else None

        starts = [schedule_io.normalize_date(f["start_date"]) for f in mapped]
        finishes = [schedule_io.normalize_date(f["finish_date"]) for f in mapped]
        rem_starts = [schedule_io.normalize_date(f["remaining_start"]) for f in open_feats]
        rem_finishes = [schedule_io.normalize_date(f["remaining_finish"]) for f in open_feats]

        # average total float over open mapped features (Decimal, 2dp)
        avg_float = None
        if floats_open:
            total = D(0)
            for v in floats_open:
                total += dec(v)
            avg_float = str((total / D(len(floats_open))).quantize(D("0.01")))

        cashflow_usable = bool(mapped and open_feats and any(
            schedule_io.normalize_date(f["remaining_start"]) and schedule_io.normalize_date(f["remaining_finish"])
            for f in open_feats))

        rows.append(OrderedDict([
            ("project_key", project_key),
            ("budget_code_key", key),
            ("sub_job", bc.get("sub_job")),
            ("cost_code", bc.get("cost_code")),
            ("category", bc.get("category")),
            ("budget_code_description", bc.get("budget_code_description")),
            ("schedule_mapping_status", mapping_status),
            ("schedule_mapping_confidence", mapping_conf),
            ("mapped_activity_count", len(mapped)),
            ("ambiguous_candidate_activity_count", len(ambiguous)),
            ("completed_activity_count", len(completed)),
            ("in_progress_activity_count", len(in_prog)),
            ("not_started_activity_count", len(not_started)),
            ("open_activity_count", len(open_feats)),
            ("milestone_activity_count", len(milestones)),
            ("earliest_activity_start", _dmin(starts)),
            ("latest_activity_finish", _dmax(finishes)),
            ("earliest_remaining_start", _dmin(rem_starts)),
            ("latest_remaining_finish", _dmax(rem_finishes)),
            ("remaining_duration_days", str(remaining_duration.quantize(D("0.01")))),
            ("minimum_total_float_days", min(floats_open) if floats_open else None),
            ("average_total_float_days", avg_float),
            ("negative_float_activity_count", neg_float_open),
            ("critical_or_longest_path_activity_count", crit_proxy_open),
            ("constraint_count", sum(1 for f in mapped if f["primary_constraint_type"])),
            ("open_start_count", sum(1 for f in mapped if f["has_open_start"])),
            ("open_finish_count", sum(1 for f in mapped if f["has_open_finish"])),
            ("schedule_remaining_work_status", remaining_status),
            ("schedule_risk_level", _risk_level(remaining_status, neg_float_open)),
            ("schedule_risk_flags", risk_flags),
            ("cashflow_timing_usable", cashflow_usable),
            ("notes", None),
        ]))
    rows.sort(key=lambda r: r["budget_code_key"])
    return rows
