"""Phase 04B schedule-activity enrichment projection.

Turns schedule activities into schedule intelligence: critical-path flag, total
float risk, deadline-variance classification, constraint risk, percent-complete
(trend derivable from the generic history snapshots), the activity hierarchy, the
schedule-to-activity link, and assigned company / resource / category edges.
Activities have no dedicated V7 tables, so everything lands in the cross-cutting
enrichment tables. Reads the raw payload directly (mirrors ``project_submittal``);
reuses ``procore_enrichment``. Schedule version / data-date history is captured by
the generic history path (``record_procore_history_for_record``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from .procore_enrichment import emit_action_signal, emit_record_edge, extract_company_refs

# Constraint types that do not constrain the schedule (the scheduler default).
_SOFT_CONSTRAINTS = {"", "asap", "as_soon_as_possible"}
# Hard mandatory constraints — elevated risk.
_HARD_CONSTRAINTS = {"mso", "mfo", "must_start_on", "must_finish_on"}
# Scalar fields carried as primary-signal metadata (all non-PII).
_META_FIELDS = (
    "schedule_id", "percent_complete", "total_float", "deadline_variance",
    "constraint_type", "constraint_date", "is_critical",
)


def _record_key(project_key: str, endpoint_id: str, parent: Optional[str], record_id: Any) -> str:
    return "|".join([project_key, endpoint_id, parent or "", str(record_id)])


def _num(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _float_band(total_float: Optional[float]) -> str:
    if total_float is None:
        return "unknown"
    if total_float <= 0:
        return "zero_or_negative"
    if total_float <= 5:
        return "low"
    return "ample"


def _variance_class(variance: Optional[float]) -> str:
    if variance is None:
        return "unknown"
    if variance < 0:
        return "late"
    if variance == 0:
        return "on_time"
    return "ahead"


def project_activity(
    raw: Mapping[str, Any], *, project_key: str, sync_run_id: Optional[str] = None,
    now_utc: str, db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    if not isinstance(raw, dict) or raw.get("activity_id") in (None, ""):
        return {"projected": False}
    activity_id = str(raw["activity_id"])
    activity_rk = _record_key(project_key, "activities", None, activity_id)
    signals: List[str] = []

    # schedule-to-activity + hierarchy edges
    schedule_id = raw.get("schedule_id")
    if schedule_id not in (None, ""):
        emit_record_edge(
            project_key=project_key, from_record_key=activity_rk,
            to_record_key=_record_key(project_key, "schedules", None, schedule_id),
            edge_type="in_schedule", source_endpoint_id="activities", now_utc=now_utc, db_path=db_path,
        )
    parent_id = raw.get("parent_id")
    if parent_id not in (None, ""):
        emit_record_edge(
            project_key=project_key, from_record_key=activity_rk,
            to_record_key=_record_key(project_key, "activities", None, parent_id),
            edge_type="child_of_activity", source_endpoint_id="activities", now_utc=now_utc, db_path=db_path,
        )

    # assigned company (string name or dict ref)
    assigned = raw.get("assigned_company")
    company_arg = [{"name": assigned}] if isinstance(assigned, str) else assigned
    for k in extract_company_refs(company_arg, now_utc=now_utc, db_path=db_path):
        emit_record_edge(project_key=project_key, from_record_key=activity_rk, edge_type="assigned_company",
                         source_endpoint_id="activities", to_entity_key=k, now_utc=now_utc, db_path=db_path)

    # resource + category edges (record -> synthetic-record, label kept in metadata)
    for res in raw.get("resource_data") or []:
        if isinstance(res, dict) and res.get("resource_id") not in (None, ""):
            emit_record_edge(
                project_key=project_key, from_record_key=activity_rk,
                to_record_key=_record_key(project_key, "schedule-resources", None, res["resource_id"]),
                edge_type="resource", source_endpoint_id="activities",
                metadata={"resource_name": res.get("resource_name")}, now_utc=now_utc, db_path=db_path,
            )
    for cat in raw.get("category_data") or []:
        if isinstance(cat, dict) and (cat.get("name") or cat.get("value")):
            emit_record_edge(
                project_key=project_key, from_record_key=activity_rk,
                to_record_key=_record_key(project_key, "schedule-categories", None,
                                          f"{cat.get('name')}:{cat.get('value')}"),
                edge_type="category", source_endpoint_id="activities",
                metadata={"name": cat.get("name"), "value": cat.get("value")}, now_utc=now_utc, db_path=db_path,
            )

    # ---- action signals ----------------------------------------------------
    total_float = _num(raw.get("total_float"))
    variance = _num(raw.get("deadline_variance"))
    constraint = str(raw.get("constraint_type") or "").strip().lower()
    meta = {f: raw.get(f) for f in _META_FIELDS if raw.get(f) is not None}
    meta["float_band"] = _float_band(total_float)
    meta["deadline_variance_class"] = _variance_class(variance)
    primary_emitted = False

    def _sig(signal_type: str, importance: str, reason_codes: Optional[List[str]] = None) -> None:
        nonlocal primary_emitted
        attach = meta if not primary_emitted else None
        emit_action_signal(project_key=project_key, record_key=activity_rk, endpoint_id="activities",
                           signal_type=signal_type, importance=importance, reason_codes=reason_codes,
                           metadata=attach, now_utc=now_utc, db_path=db_path)
        primary_emitted = True
        signals.append(signal_type)

    if raw.get("is_critical"):
        _sig("activity_critical", "high")
    if total_float is not None and total_float <= 0:
        _sig("activity_zero_float", "high", reason_codes=[_float_band(total_float)])
    if variance is not None and variance < 0:
        _sig("activity_deadline_variance", "high", reason_codes=[_variance_class(variance)])
    if constraint and constraint not in _SOFT_CONSTRAINTS:
        _sig("activity_constrained", "high" if constraint in _HARD_CONSTRAINTS else "medium",
             reason_codes=[constraint])

    return {"projected": True, "record_key": activity_rk, "signals": signals}


__all__ = ["project_activity"]
