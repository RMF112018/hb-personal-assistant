"""Detailed schedule diff fact generation and severity classification."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import date, datetime
from typing import Any

SEVERITY_ORDER = {
    "critical": 5,
    "major": 4,
    "moderate": 3,
    "minor": 2,
    "informational": 1,
}

IMPACT_LEVEL_ORDER = {
    "critical": 1,
    "high": 2,
    "medium": 3,
    "low": 4,
    "informational": 5,
}


def classify_date_drift(day_delta: int | None, *, critical_path: bool = False) -> str:
    if day_delta is None or day_delta == 0:
        return "informational"
    magnitude = abs(int(day_delta))
    later = int(day_delta) > 0
    if later and magnitude > 10:
        return "critical"
    if later and magnitude >= 6:
        return "major"
    if later and magnitude >= 3:
        return "moderate"
    if magnitude >= 1:
        return "minor" if not critical_path else "moderate"
    return "informational"


def classify_change(
    *,
    change_domain: str,
    change_type: str,
    field_name: str | None = None,
    day_delta: int | None = None,
    critical_path: bool = False,
    open_end: bool = False,
) -> tuple[str, bool]:
    if day_delta is not None:
        severity = classify_date_drift(day_delta, critical_path=critical_path)
    elif change_domain == "relationship":
        severity = "major" if critical_path else "moderate"
    elif change_domain == "activity" and change_type in {"added", "removed"}:
        severity = "major" if critical_path or open_end else "moderate"
    elif change_domain == "wbs":
        severity = "moderate"
    elif field_name in {"activity_name", "calendar_id", "calendar_name", "cost_code"}:
        severity = "informational"
    else:
        severity = "minor"
    requires_attention = SEVERITY_ORDER[severity] >= SEVERITY_ORDER["major"] or open_end
    return severity, requires_attention


def build_detail_facts(
    *,
    diff_id: int,
    project_key: str,
    from_version: str,
    to_version: str,
    schedule_identity_key: str | None,
    identity_safe: bool,
    comparison_type: str,
    from_activities: list[dict[str, Any]],
    to_activities: list[dict[str, Any]],
    from_relationships: list[dict[str, Any]],
    to_relationships: list[dict[str, Any]],
    from_wbs: list[dict[str, Any]] | None = None,
    to_wbs: list[dict[str, Any]] | None = None,
    from_calendars: list[dict[str, Any]] | None = None,
    to_calendars: list[dict[str, Any]] | None = None,
    from_codes: list[dict[str, Any]] | None = None,
    to_codes: list[dict[str, Any]] | None = None,
    from_udfs: list[dict[str, Any]] | None = None,
    to_udfs: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    from_by_id = {str(a.get("activity_id")): a for a in from_activities if a.get("activity_id")}
    to_by_id = {str(a.get("activity_id")): a for a in to_activities if a.get("activity_id")}
    from_ids = set(from_by_id)
    to_ids = set(to_by_id)

    for activity_id in sorted(to_ids - from_ids):
        rows.append(
            _row(
                diff_id=diff_id,
                project_key=project_key,
                from_version=from_version,
                to_version=to_version,
                schedule_identity_key=schedule_identity_key,
                identity_safe=identity_safe,
                comparison_type=comparison_type,
                change_domain="activity",
                change_type="added",
                activity=to_by_id[activity_id],
                entity_key=activity_id,
            )
        )
    for activity_id in sorted(from_ids - to_ids):
        rows.append(
            _row(
                diff_id=diff_id,
                project_key=project_key,
                from_version=from_version,
                to_version=to_version,
                schedule_identity_key=schedule_identity_key,
                identity_safe=identity_safe,
                comparison_type=comparison_type,
                change_domain="activity",
                change_type="removed",
                activity=from_by_id[activity_id],
                entity_key=activity_id,
            )
        )

    activity_fields = (
        "activity_name",
        "activity_status",
        "planned_start",
        "planned_finish",
        "start_date",
        "finish_date",
        "actual_start",
        "actual_finish",
        "duration_original",
        "duration_remaining",
        "duration_actual",
        "total_float",
        "derived_total_float_days",
        "explicit_total_float_days",
        "is_critical",
        "is_longest_path",
        "is_milestone",
        "wbs_id",
        "wbs_code",
        "wbs_path",
        "calendar_id",
        "calendar_name",
        "activity_type",
    )
    date_fields = {
        "planned_start",
        "planned_finish",
        "start_date",
        "finish_date",
        "actual_start",
        "actual_finish",
    }
    for activity_id in sorted(from_ids & to_ids):
        before = from_by_id[activity_id]
        after = to_by_id[activity_id]
        for field in activity_fields:
            if _clean(before.get(field)) == _clean(after.get(field)):
                continue
            day_delta = _date_delta_days(before.get(field), after.get(field)) if field in date_fields else None
            rows.append(
                _row(
                    diff_id=diff_id,
                    project_key=project_key,
                    from_version=from_version,
                    to_version=to_version,
                    schedule_identity_key=schedule_identity_key,
                    identity_safe=identity_safe,
                    comparison_type=comparison_type,
                    change_domain="activity",
                    change_type="date_drift" if day_delta is not None else "changed",
                    activity=after,
                    entity_key=activity_id,
                    field_name=field,
                    from_value=before.get(field),
                    to_value=after.get(field),
                    day_delta=day_delta,
                )
            )

    rows.extend(
        _relationship_rows(
            diff_id=diff_id,
            project_key=project_key,
            from_version=from_version,
            to_version=to_version,
            schedule_identity_key=schedule_identity_key,
            identity_safe=identity_safe,
            comparison_type=comparison_type,
            from_relationships=from_relationships,
            to_relationships=to_relationships,
            from_activities=from_by_id,
            to_activities=to_by_id,
        )
    )
    rows.extend(
        _generic_rows(
            diff_id=diff_id,
            project_key=project_key,
            from_version=from_version,
            to_version=to_version,
            schedule_identity_key=schedule_identity_key,
            identity_safe=identity_safe,
            comparison_type=comparison_type,
            change_domain="wbs",
            key_fields=("wbs_id",),
            label_fields=("wbs_name", "wbs_code", "parent_wbs_id", "wbs_path"),
            from_rows=from_wbs or [],
            to_rows=to_wbs or [],
        )
    )
    rows.extend(
        _generic_rows(
            diff_id=diff_id,
            project_key=project_key,
            from_version=from_version,
            to_version=to_version,
            schedule_identity_key=schedule_identity_key,
            identity_safe=identity_safe,
            comparison_type=comparison_type,
            change_domain="calendar",
            key_fields=("calendar_id",),
            label_fields=("calendar_name", "calendar_type", "hours_per_day", "days_per_week", "is_default"),
            from_rows=from_calendars or [],
            to_rows=to_calendars or [],
        )
    )
    rows.extend(
        _generic_rows(
            diff_id=diff_id,
            project_key=project_key,
            from_version=from_version,
            to_version=to_version,
            schedule_identity_key=schedule_identity_key,
            identity_safe=identity_safe,
            comparison_type=comparison_type,
            change_domain="activity_code",
            key_fields=("activity_id", "code_type"),
            label_fields=("code_value", "code_description"),
            from_rows=from_codes or [],
            to_rows=to_codes or [],
        )
    )
    rows.extend(
        _generic_rows(
            diff_id=diff_id,
            project_key=project_key,
            from_version=from_version,
            to_version=to_version,
            schedule_identity_key=schedule_identity_key,
            identity_safe=identity_safe,
            comparison_type=comparison_type,
            change_domain="udf",
            key_fields=("activity_id", "udf_type_name"),
            label_fields=("udf_data_type", "udf_value"),
            from_rows=from_udfs or [],
            to_rows=to_udfs or [],
        )
    )
    return rows


def summarize_detail_facts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "total_change_count": len(rows),
        "added_activity_count": 0,
        "removed_activity_count": 0,
        "changed_activity_count": 0,
        "relationship_added_count": 0,
        "relationship_removed_count": 0,
        "relationship_changed_count": 0,
        "wbs_change_count": 0,
        "date_drift_count": 0,
        "critical_severity_count": 0,
        "major_severity_count": 0,
        "moderate_severity_count": 0,
        "minor_severity_count": 0,
        "informational_count": 0,
        "requires_attention_count": 0,
        "domain_counts": {},
    }
    for row in rows:
        domain = str(row.get("change_domain") or "")
        change_type = str(row.get("change_type") or "")
        severity = str(row.get("severity") or "informational")
        summary["domain_counts"][domain] = int(summary["domain_counts"].get(domain, 0)) + 1
        if domain == "activity" and change_type == "added":
            summary["added_activity_count"] += 1
        elif domain == "activity" and change_type == "removed":
            summary["removed_activity_count"] += 1
        elif domain == "activity":
            summary["changed_activity_count"] += 1
        if domain == "relationship" and change_type == "logic_added":
            summary["relationship_added_count"] += 1
        elif domain == "relationship" and change_type == "logic_removed":
            summary["relationship_removed_count"] += 1
        elif domain == "relationship":
            summary["relationship_changed_count"] += 1
        if domain == "wbs":
            summary["wbs_change_count"] += 1
        if change_type == "date_drift":
            summary["date_drift_count"] += 1
        if severity == "critical":
            summary["critical_severity_count"] += 1
        elif severity == "major":
            summary["major_severity_count"] += 1
        elif severity == "moderate":
            summary["moderate_severity_count"] += 1
        elif severity == "minor":
            summary["minor_severity_count"] += 1
        else:
            summary["informational_count"] += 1
        if int(row.get("requires_attention") or 0):
            summary["requires_attention_count"] += 1
    return summary


def impact_level_for_score(score: int) -> str:
    if score >= 75:
        return "critical"
    if score >= 40:
        return "high"
    if score >= 20:
        return "medium"
    if score >= 5:
        return "low"
    return "informational"


def score_impact_detail(row: dict[str, Any]) -> int:
    severity = str(row.get("severity") or "informational")
    score = {
        "critical": 25,
        "major": 12,
        "moderate": 6,
        "minor": 2,
    }.get(severity, 0)
    if int(row.get("requires_attention") or 0):
        score += 10
    domain = str(row.get("change_domain") or "")
    change_type = str(row.get("change_type") or "")
    if domain == "relationship" or change_type.startswith("logic_"):
        score += 5
    day_delta = _int_or_none(row.get("day_delta"))
    if day_delta is not None:
        magnitude = abs(day_delta)
        if magnitude > 10:
            score += 15
        elif magnitude >= 6:
            score += 8
        elif magnitude >= 3:
            score += 4
    if domain == "activity" and change_type == "removed":
        score += 8
    if _is_milestone_detail(row) and day_delta is not None and day_delta > 0:
        score += 15
    if int(row.get("is_critical_path_related") or 0):
        score += 15
    return score


def build_impact_rollups(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    normalized = [dict(row) for row in rows]
    rollups: list[dict[str, Any]] = []
    rollups.append(_rollup("summary", "all", "All schedule changes", normalized))
    rollups.extend(_grouped_rollups("wbs", normalized, _wbs_rollup_key))
    rollups.extend(_grouped_rollups("attention", [r for r in normalized if int(r.get("requires_attention") or 0)], _attention_rollup_key))
    rollups.extend(_grouped_rollups("severity", normalized, _severity_rollup_key))
    rollups.extend(_grouped_rollups("change_domain", normalized, _domain_rollup_key))
    logic_rows = [
        r
        for r in normalized
        if str(r.get("change_domain") or "") == "relationship"
        or str(r.get("change_type") or "").startswith("logic_")
    ]
    rollups.extend(_grouped_rollups("logic", logic_rows, _logic_rollup_key))
    milestone_rows = [r for r in normalized if _is_milestone_detail(r)]
    rollups.extend(_grouped_rollups("milestone", milestone_rows, _activity_rollup_key))
    critical_rows = [r for r in normalized if int(r.get("is_critical_path_related") or 0)]
    rollups.extend(_grouped_rollups("critical_path", critical_rows, _activity_rollup_key))
    near_critical_rows = [r for r in normalized if _is_near_critical_float_detail(r)]
    rollups.extend(_grouped_rollups("near_critical", near_critical_rows, _activity_rollup_key))
    return sorted(
        rollups,
        key=lambda r: (
            IMPACT_LEVEL_ORDER.get(str(r.get("impact_level") or "informational"), 99),
            -int(r.get("impact_score") or 0),
            str(r.get("rollup_type") or ""),
            str(r.get("rollup_label") or ""),
        ),
    )


def _grouped_rollups(
    rollup_type: str,
    rows: list[dict[str, Any]],
    key_func: Any,
) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    labels: dict[str, str] = {}
    for row in rows:
        key, label = key_func(row)
        if not key:
            continue
        groups[key].append(row)
        labels[key] = label
    return [_rollup(rollup_type, key, labels[key], group) for key, group in groups.items()]


def _rollup(
    rollup_type: str,
    rollup_key: str,
    rollup_label: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    first = rows[0] if rows else {}
    severities = defaultdict(int)
    activity_ids = {
        str(row.get("activity_id") or "")
        for row in rows
        if str(row.get("activity_id") or "").strip()
    }
    day_deltas = [_int_or_none(row.get("day_delta")) for row in rows]
    day_deltas = [d for d in day_deltas if d is not None]
    score = sum(score_impact_detail(row) for row in rows)
    for row in rows:
        severities[str(row.get("severity") or "informational")] += 1
    domain_changes = [str(row.get("change_domain") or "") for row in rows]
    change_types = [str(row.get("change_type") or "") for row in rows]
    wbs_code = _first_nonempty(row.get("wbs_code") for row in rows)
    wbs_name = _first_nonempty(row.get("wbs_name") for row in rows)
    activity_id = _first_nonempty(row.get("activity_id") for row in rows)
    activity_name = _first_nonempty(row.get("activity_name") for row in rows)
    evidence = {
        "basis": "schedule_version_diff_detail_facts",
        "detail_count": len(rows),
        "availability": _rollup_availability_note(rollup_type),
        "score_model": "phase4_v1",
    }
    normalized_key = _normalize_rollup_key(rollup_key)
    comparison_type = str(first.get("comparison_type") or "manual")
    return {
        "rollup_id": _impact_rollup_id(
            first.get("diff_id"),
            rollup_type,
            normalized_key,
            comparison_type,
        ),
        "diff_id": int(first.get("diff_id") or 0),
        "project_key": first.get("project_key"),
        "from_schedule_version_key": first.get("from_schedule_version_key"),
        "to_schedule_version_key": first.get("to_schedule_version_key"),
        "schedule_identity_key": first.get("schedule_identity_key"),
        "comparison_type": comparison_type,
        "identity_safe": int(first.get("identity_safe") or 0),
        "rollup_type": rollup_type,
        "rollup_key": normalized_key,
        "rollup_label": rollup_label,
        "wbs_code": wbs_code,
        "wbs_name": wbs_name,
        "activity_id": activity_id if rollup_type in {"activity", "milestone", "critical_path", "near_critical"} else None,
        "activity_name": activity_name if rollup_type in {"activity", "milestone", "critical_path", "near_critical"} else None,
        "milestone_activity_id": activity_id if rollup_type == "milestone" else None,
        "milestone_name": activity_name if rollup_type == "milestone" else None,
        "activity_count": len(activity_ids),
        "change_count": len(rows),
        "critical_count": int(severities["critical"]),
        "major_count": int(severities["major"]),
        "moderate_count": int(severities["moderate"]),
        "minor_count": int(severities["minor"]),
        "informational_count": int(severities["informational"]),
        "date_drift_count": sum(1 for t in change_types if t == "date_drift"),
        "logic_change_count": sum(1 for t in change_types if t.startswith("logic_")),
        "relationship_change_count": sum(1 for d in domain_changes if d == "relationship"),
        "activity_added_count": sum(1 for d, t in zip(domain_changes, change_types) if d == "activity" and t == "added"),
        "activity_removed_count": sum(1 for d, t in zip(domain_changes, change_types) if d == "activity" and t == "removed"),
        "requires_attention_count": sum(1 for row in rows if int(row.get("requires_attention") or 0)),
        "max_day_delta": max(day_deltas, key=abs) if day_deltas else None,
        "net_day_delta": sum(day_deltas) if day_deltas else None,
        "max_later_day_delta": max((d for d in day_deltas if d > 0), default=None),
        "max_earlier_day_delta": min((d for d in day_deltas if d < 0), default=None),
        "impact_score": str(score),
        "impact_level": impact_level_for_score(score),
        "requires_attention": 1 if any(int(row.get("requires_attention") or 0) for row in rows) else 0,
        "evidence_json": json.dumps(evidence, sort_keys=True, default=str),
    }


def _impact_rollup_id(diff_id: Any, rollup_type: str, rollup_key: str, comparison_type: str) -> str:
    basis = json.dumps(
        {
            "diff_id": str(diff_id or ""),
            "rollup_type": rollup_type,
            "rollup_key": rollup_key,
            "comparison_type": comparison_type,
        },
        sort_keys=True,
    )
    return "sir_" + hashlib.sha256(basis.encode("utf-8")).hexdigest()[:24]


def _normalize_rollup_key(value: Any) -> str:
    return " ".join(str(value or "unknown").strip().lower().split())


def _wbs_rollup_key(row: dict[str, Any]) -> tuple[str | None, str]:
    key = _first_nonempty((row.get("wbs_code"), row.get("wbs_name")))
    if not key:
        return None, ""
    name = str(row.get("wbs_name") or "").strip()
    code = str(row.get("wbs_code") or "").strip()
    return key, " / ".join(part for part in (code, name) if part) or key


def _attention_rollup_key(row: dict[str, Any]) -> tuple[str | None, str]:
    severity = str(row.get("severity") or "informational")
    domain = str(row.get("change_domain") or "unknown")
    return f"{severity}|{domain}", f"{severity} {domain}"


def _severity_rollup_key(row: dict[str, Any]) -> tuple[str | None, str]:
    severity = str(row.get("severity") or "informational")
    return severity, severity


def _domain_rollup_key(row: dict[str, Any]) -> tuple[str | None, str]:
    domain = str(row.get("change_domain") or "unknown")
    return domain, domain


def _logic_rollup_key(row: dict[str, Any]) -> tuple[str | None, str]:
    key = _first_nonempty((row.get("wbs_code"), row.get("activity_id"), row.get("entity_key")))
    label = _first_nonempty((row.get("wbs_name"), row.get("activity_name"), row.get("entity_label"), key))
    return key, label or str(key)


def _activity_rollup_key(row: dict[str, Any]) -> tuple[str | None, str]:
    key = _first_nonempty((row.get("activity_id"), row.get("entity_key")))
    label = _first_nonempty((row.get("activity_name"), row.get("entity_label"), key))
    return key, label or str(key)


def _is_milestone_detail(row: dict[str, Any]) -> bool:
    field = str(row.get("field_name") or "").lower()
    if field not in {"is_milestone", "activity_type"}:
        return False
    values = " ".join(str(row.get(k) or "").lower() for k in ("from_value", "to_value"))
    return "milestone" in values or values.strip() in {"0 1", "false true", "no yes"}


def _is_near_critical_float_detail(row: dict[str, Any]) -> bool:
    if str(row.get("field_name") or "") not in {
        "total_float",
        "derived_total_float_days",
        "explicit_total_float_days",
    }:
        return False
    values = [_int_or_none(row.get("from_value")), _int_or_none(row.get("to_value"))]
    return any(value is not None and value <= 10 for value in values)


def _rollup_availability_note(rollup_type: str) -> str:
    if rollup_type == "milestone":
        return "generated_only_from_explicit_milestone_detail_facts"
    if rollup_type in {"critical_path", "near_critical"}:
        return "generated_only_from_persisted_critical_or_float_detail_facts"
    return "available"


def _first_nonempty(values: Any) -> str | None:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return None


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None


def _relationship_rows(
    *,
    diff_id: int,
    project_key: str,
    from_version: str,
    to_version: str,
    schedule_identity_key: str | None,
    identity_safe: bool,
    comparison_type: str,
    from_relationships: list[dict[str, Any]],
    to_relationships: list[dict[str, Any]],
    from_activities: dict[str, dict[str, Any]],
    to_activities: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    from_by_pair = {_rel_pair_key(r): r for r in from_relationships}
    to_by_pair = {_rel_pair_key(r): r for r in to_relationships}
    for key in sorted(set(to_by_pair) - set(from_by_pair)):
        rel = to_by_pair[key]
        rows.append(_rel_row(diff_id, project_key, from_version, to_version, schedule_identity_key, identity_safe, comparison_type, "logic_added", rel, to_activities))
    for key in sorted(set(from_by_pair) - set(to_by_pair)):
        rel = from_by_pair[key]
        rows.append(_rel_row(diff_id, project_key, from_version, to_version, schedule_identity_key, identity_safe, comparison_type, "logic_removed", rel, from_activities))
    for key in sorted(set(from_by_pair) & set(to_by_pair)):
        before = from_by_pair[key]
        after = to_by_pair[key]
        for field in ("relationship_type", "lag_value", "lag_unit"):
            if _clean(before.get(field)) != _clean(after.get(field)):
                rows.append(
                    _rel_row(
                        diff_id,
                        project_key,
                        from_version,
                        to_version,
                        schedule_identity_key,
                        identity_safe,
                        comparison_type,
                        "logic_changed",
                        after,
                        to_activities,
                        field_name=field,
                        from_value=before.get(field),
                        to_value=after.get(field),
                    )
                )
    return rows


def _rel_row(
    diff_id: int,
    project_key: str,
    from_version: str,
    to_version: str,
    schedule_identity_key: str | None,
    identity_safe: bool,
    comparison_type: str,
    change_type: str,
    rel: dict[str, Any],
    activities: dict[str, dict[str, Any]],
    *,
    field_name: str | None = None,
    from_value: Any = None,
    to_value: Any = None,
) -> dict[str, Any]:
    pred = str(rel.get("predecessor_activity_id") or "")
    succ = str(rel.get("successor_activity_id") or "")
    critical = _is_critical(activities.get(pred) or {}) or _is_critical(activities.get(succ) or {})
    return _row(
        diff_id=diff_id,
        project_key=project_key,
        from_version=from_version,
        to_version=to_version,
        schedule_identity_key=schedule_identity_key,
        identity_safe=identity_safe,
        comparison_type=comparison_type,
        change_domain="relationship",
        change_type=change_type,
        entity_key=f"{pred}|{succ}",
        predecessor_activity_id=pred,
        successor_activity_id=succ,
        field_name=field_name,
        from_value=from_value,
        to_value=to_value,
        critical_path=critical,
        evidence={"relationship_type": rel.get("relationship_type"), "lag_value": rel.get("lag_value"), "lag_unit": rel.get("lag_unit")},
    )


def _generic_rows(
    *,
    diff_id: int,
    project_key: str,
    from_version: str,
    to_version: str,
    schedule_identity_key: str | None,
    identity_safe: bool,
    comparison_type: str,
    change_domain: str,
    key_fields: tuple[str, ...],
    label_fields: tuple[str, ...],
    from_rows: list[dict[str, Any]],
    to_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    from_by_key = {_generic_key(row, key_fields): row for row in from_rows if _generic_key(row, key_fields)}
    to_by_key = {_generic_key(row, key_fields): row for row in to_rows if _generic_key(row, key_fields)}
    for key in sorted(set(to_by_key) - set(from_by_key)):
        out.append(_row(diff_id=diff_id, project_key=project_key, from_version=from_version, to_version=to_version, schedule_identity_key=schedule_identity_key, identity_safe=identity_safe, comparison_type=comparison_type, change_domain=change_domain, change_type="added", entity_key=key, entity_label=_label(to_by_key[key]), activity_id=to_by_key[key].get("activity_id"), wbs_code=to_by_key[key].get("wbs_code")))
    for key in sorted(set(from_by_key) - set(to_by_key)):
        out.append(_row(diff_id=diff_id, project_key=project_key, from_version=from_version, to_version=to_version, schedule_identity_key=schedule_identity_key, identity_safe=identity_safe, comparison_type=comparison_type, change_domain=change_domain, change_type="removed", entity_key=key, entity_label=_label(from_by_key[key]), activity_id=from_by_key[key].get("activity_id"), wbs_code=from_by_key[key].get("wbs_code")))
    for key in sorted(set(from_by_key) & set(to_by_key)):
        before = from_by_key[key]
        after = to_by_key[key]
        for field in label_fields:
            if _clean(before.get(field)) != _clean(after.get(field)):
                out.append(_row(diff_id=diff_id, project_key=project_key, from_version=from_version, to_version=to_version, schedule_identity_key=schedule_identity_key, identity_safe=identity_safe, comparison_type=comparison_type, change_domain=change_domain, change_type="changed", entity_key=key, entity_label=_label(after), activity_id=after.get("activity_id"), wbs_code=after.get("wbs_code"), wbs_name=after.get("wbs_name"), field_name=field, from_value=before.get(field), to_value=after.get(field)))
    return out


def _row(
    *,
    diff_id: int,
    project_key: str,
    from_version: str,
    to_version: str,
    schedule_identity_key: str | None,
    identity_safe: bool,
    comparison_type: str,
    change_domain: str,
    change_type: str,
    entity_key: Any = None,
    entity_label: Any = None,
    activity: dict[str, Any] | None = None,
    activity_id: Any = None,
    activity_name: Any = None,
    wbs_code: Any = None,
    wbs_name: Any = None,
    predecessor_activity_id: Any = None,
    successor_activity_id: Any = None,
    field_name: str | None = None,
    from_value: Any = None,
    to_value: Any = None,
    day_delta: int | None = None,
    critical_path: bool | None = None,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    activity = activity or {}
    activity_id = activity_id if activity_id is not None else activity.get("activity_id")
    activity_name = activity_name if activity_name is not None else activity.get("activity_name")
    wbs_code = wbs_code if wbs_code is not None else activity.get("wbs_code")
    wbs_name = wbs_name if wbs_name is not None else activity.get("wbs_name")
    critical = bool(critical_path if critical_path is not None else _is_critical(activity))
    open_end = _is_open_ended(activity)
    severity, requires_attention = classify_change(
        change_domain=change_domain,
        change_type=change_type,
        field_name=field_name,
        day_delta=day_delta,
        critical_path=critical,
        open_end=open_end,
    )
    payload = {
        "diff_id": diff_id,
        "project_key": project_key,
        "from_schedule_version_key": from_version,
        "to_schedule_version_key": to_version,
        "schedule_identity_key": schedule_identity_key,
        "identity_safe": 1 if identity_safe else 0,
        "comparison_type": comparison_type,
        "change_domain": change_domain,
        "change_type": change_type,
        "entity_key": _string(entity_key),
        "entity_label": _string(entity_label if entity_label is not None else activity_name),
        "wbs_code": _string(wbs_code),
        "wbs_name": _string(wbs_name),
        "activity_id": _string(activity_id),
        "activity_name": _string(activity_name),
        "predecessor_activity_id": _string(predecessor_activity_id),
        "successor_activity_id": _string(successor_activity_id),
        "field_name": field_name,
        "from_value": _string(from_value),
        "to_value": _string(to_value),
        "numeric_delta": _numeric_delta(from_value, to_value),
        "day_delta": day_delta,
        "severity": severity,
        "significance_score": str(SEVERITY_ORDER[severity]),
        "is_critical_path_related": 1 if critical else 0,
        "is_open_end_related": 1 if open_end else 0,
        "requires_attention": 1 if requires_attention else 0,
        "evidence_json": json.dumps(evidence or {"basis": "normalized_schedule_tables"}, sort_keys=True, default=str),
    }
    stable = "|".join(
        str(payload.get(key) or "")
        for key in (
            "diff_id",
            "change_domain",
            "change_type",
            "entity_key",
            "activity_id",
            "predecessor_activity_id",
            "successor_activity_id",
            "field_name",
        )
    )
    payload["detail_id"] = "sddf-" + hashlib.sha256(stable.encode()).hexdigest()
    return payload


def _date_delta_days(from_value: Any, to_value: Any) -> int | None:
    from_date = _parse_date(from_value)
    to_date = _parse_date(to_value)
    if from_date is None or to_date is None:
        return None
    return (to_date - from_date).days


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    for candidate in (text.replace("Z", "+00:00"), text[:10]):
        try:
            return datetime.fromisoformat(candidate).date()
        except ValueError:
            try:
                return date.fromisoformat(candidate)
            except ValueError:
                continue
    return None


def _rel_pair_key(rel: dict[str, Any]) -> str:
    return f"{rel.get('predecessor_activity_id')}|{rel.get('successor_activity_id')}"


def _generic_key(row: dict[str, Any], fields: tuple[str, ...]) -> str:
    return "|".join(str(row.get(field) or "") for field in fields).strip("|")


def _label(row: dict[str, Any]) -> str | None:
    for field in ("activity_name", "wbs_name", "calendar_name", "code_value", "udf_type_name"):
        if row.get(field):
            return str(row[field])
    return None


def _is_critical(activity: dict[str, Any]) -> bool:
    return any(
        str(activity.get(field) or "").strip().lower() in {"1", "true", "yes", "y"}
        for field in (
            "is_critical",
            "derived_is_critical_by_float_threshold",
            "source_critical_flag",
            "source_longest_path_flag",
        )
    )


def _is_open_ended(activity: dict[str, Any]) -> bool:
    return not activity.get("start_date") or not activity.get("finish_date")


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _numeric_delta(from_value: Any, to_value: Any) -> str | None:
    try:
        return str(round(float(to_value) - float(from_value), 4))
    except (TypeError, ValueError):
        return None
