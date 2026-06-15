"""Priority 5 — schedule cost-loading readiness audit.

Determines whether the schedule is good enough to influence cost phasing / confidence, and where it is
not. Schedule never overrides actuals and never creates actual cost — readiness only determines a
use-posture. Emits one audit object plus data gaps.
"""
from __future__ import annotations

from collections import Counter, OrderedDict

from ..common.money import D


def _cfg(cfg):
    return (cfg or {}).get("forecast_improvement_audit") or {}


def _frac(num, den):
    return round(num / den, 4) if den else 0.0


def build(inputs: dict, cfg: dict):
    """Return (audit_obj, gaps)."""
    fia = _cfg(cfg)
    project_key = inputs["project_key"]
    acts = inputs["schedule_activities"]
    canonical_count = len(inputs["budget_by_key"])
    gaps = []

    if not acts:
        gaps.append(OrderedDict([
            ("project_key", project_key), ("improvement", "priority_5_schedule_readiness"),
            ("gap_type", "schedule_package_absent"),
            ("detail", "no schedule activities present; schedule readiness unsupported")]))
        return OrderedDict([("project_key", project_key), ("schedule_present", False),
                            ("recommended_posture", "schedule_not_usable")]), gaps

    n = len(acts)
    data_dates = {a.get("data_date") for a in acts if a.get("data_date")}
    mapped = 0
    has_dates = 0
    has_pct = 0
    has_logic = 0
    cost_loaded = 0
    mapped_keys = set()
    high_risk_unmapped = 0
    conf_counter = Counter()
    for a in acts:
        conf = (a.get("budget_code_mapping_confidence") or "none")
        conf_counter[conf] += 1
        cands = a.get("candidate_budget_code_keys") or []
        is_mapped = conf not in ("none", None, "") and bool(cands)
        if is_mapped:
            mapped += 1
            mapped_keys.update(cands)
        dates = a.get("dates") or {}
        if (dates.get("start") or dates.get("planned_start")) and (dates.get("finish") or dates.get("planned_finish")):
            has_dates += 1
        prog = a.get("progress") or {}
        if prog.get("activity_percent_complete") is not None:
            has_pct += 1
        if (a.get("predecessors") or []) or (a.get("successors") or []):
            has_logic += 1
        raw = a.get("raw_xml_fields") or {}
        if D(raw.get("PlannedLaborCost")) > 0 or D(raw.get("AtCompletionLaborCost")) > 0 \
                or D(raw.get("PlannedNonLaborCost")) > 0:
            cost_loaded += 1
        rel = a.get("forecast_relevance") or {}
        if rel.get("is_active_work") and rel.get("is_cost_mappable") and not is_mapped:
            high_risk_unmapped += 1

    mapped_frac = _frac(mapped, n)
    cost_loaded_frac = _frac(cost_loaded, n)
    date_frac = _frac(has_dates, n)
    pct_frac = _frac(has_pct, n)
    logic_frac = _frac(has_logic, n)
    code_coverage = _frac(len(mapped_keys & set(inputs["budget_by_key"])), canonical_count)

    drive_map = float(fia.get("schedule_drive_mapped_fraction", 0.6))
    drive_cost = float(fia.get("schedule_drive_cost_loaded_fraction", 0.5))
    inform_map = float(fia.get("schedule_inform_mapped_fraction", 0.2))
    if mapped_frac >= drive_map and cost_loaded_frac >= drive_cost:
        posture = "schedule_can_drive_phasing"
    elif mapped_frac >= inform_map:
        posture = "schedule_can_inform_phasing_only"
    elif date_frac >= 0.5:
        posture = "schedule_context_only"
    else:
        posture = "schedule_not_usable"

    if mapped_frac < inform_map:
        gaps.append(OrderedDict([
            ("project_key", project_key), ("improvement", "priority_5_schedule_readiness"),
            ("gap_type", "schedule_budget_code_mapping_sparse"),
            ("detail", f"only {mapped}/{n} activities map to a budget code "
                       f"(mapping_confidence mostly 'none'); posture limited to {posture}")]))
    if cost_loaded == 0:
        gaps.append(OrderedDict([
            ("project_key", project_key), ("improvement", "priority_5_schedule_readiness"),
            ("gap_type", "schedule_not_cost_loaded"),
            ("detail", "no activity carries resource/cost loading; schedule cannot drive cost phasing")]))

    audit = OrderedDict([
        ("project_key", project_key), ("schedule_present", True),
        ("schedule_data_date", sorted(data_dates)[-1] if data_dates else None),
        ("activity_count", n),
        ("mapped_activity_count", mapped),
        ("unmapped_activity_count", n - mapped),
        ("mapped_fraction", mapped_frac),
        ("mapping_confidence_distribution", OrderedDict(
            (k, conf_counter[k]) for k in sorted(conf_counter))),
        ("distinct_mapped_budget_codes", len(mapped_keys & set(inputs["budget_by_key"]))),
        ("budget_code_coverage_fraction", code_coverage),
        ("date_completeness_fraction", date_frac),
        ("percent_complete_completeness_fraction", pct_frac),
        ("logic_completeness_fraction", logic_frac),
        ("cost_loading_presence_fraction", cost_loaded_frac),
        ("high_risk_unmapped_active_scopes", high_risk_unmapped),
        ("recommended_posture", posture),
        ("posture_basis", "mapped_fraction + cost_loading_fraction vs configured thresholds"),
        ("schedule_overrides_actuals", False),
        ("schedule_creates_actual_cost", False),
        ("requires_human_acceptance", True),
    ])
    return audit, gaps
