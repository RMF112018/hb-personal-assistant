"""Deterministic schedule version-over-version comparison."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from statistics import mean, median
from typing import Any


def compute_version_diff(
    *,
    project_key: str,
    from_version: str,
    to_version: str,
    from_activities: list[dict[str, Any]],
    to_activities: list[dict[str, Any]],
    from_relationships: list[dict[str, Any]],
    to_relationships: list[dict[str, Any]],
) -> dict[str, Any]:
    from_by_id = {str(a["activity_id"]): a for a in from_activities if a.get("activity_id")}
    to_by_id = {str(a["activity_id"]): a for a in to_activities if a.get("activity_id")}

    from_ids = set(from_by_id)
    to_ids = set(to_by_id)
    added = to_ids - from_ids
    removed = from_ids - to_ids
    common = from_ids & to_ids

    changed = 0
    changed_ids: list[str] = []
    finish_drifts: list[float] = []
    start_drifts: list[float] = []
    milestone_finish_drifts: list[float] = []
    near_term_changed: list[str] = []
    constraint_changed = 0
    calendar_changed = 0
    wbs_changed = 0
    code_changed = 0
    for act_id in common:
        fa = from_by_id[act_id]
        ta = to_by_id[act_id]
        keys = (
            "finish_date",
            "start_date",
            "duration_original",
            "percent_complete",
            "cost_code",
            "constraint_type",
            "constraint_date",
            "calendar_id",
            "wbs_id",
            "wbs_code",
        )
        if any(fa.get(k) != ta.get(k) for k in keys):
            changed += 1
            changed_ids.append(act_id)
            if _is_near_term(ta):
                near_term_changed.append(act_id)
        if fa.get("constraint_type") != ta.get("constraint_type") or fa.get("constraint_date") != ta.get("constraint_date"):
            constraint_changed += 1
        if fa.get("calendar_id") != ta.get("calendar_id"):
            calendar_changed += 1
        if fa.get("wbs_id") != ta.get("wbs_id") or fa.get("wbs_code") != ta.get("wbs_code"):
            wbs_changed += 1
        if fa.get("cost_code") != ta.get("cost_code"):
            code_changed += 1
        finish_drift = _date_delta_days(fa.get("finish_date"), ta.get("finish_date"))
        if finish_drift is not None:
            finish_drifts.append(finish_drift)
            if _truthy(ta.get("is_milestone")):
                milestone_finish_drifts.append(finish_drift)
        start_drift = _date_delta_days(fa.get("start_date"), ta.get("start_date"))
        if start_drift is not None:
            start_drifts.append(start_drift)

    rel_from = {_rel_key(r) for r in from_relationships}
    rel_to = {_rel_key(r) for r in to_relationships}
    rel_added = len(rel_to - rel_from)
    rel_removed = len(rel_from - rel_to)
    rel_union = rel_from | rel_to
    logic_churn = (rel_added + rel_removed) / len(rel_union) if rel_union else 0.0
    rel_type_changed, lag_changed = _relationship_change_counts(from_relationships, to_relationships)

    summary = {
        "added_activity_ids": sorted(added)[:50],
        "removed_activity_ids": sorted(removed)[:50],
        "changed_activity_count": changed,
        "changed_activity_ids": sorted(changed_ids)[:100],
        "near_term_changed_activity_ids": sorted(near_term_changed)[:100],
        "finish_drift": _stats(finish_drifts),
        "start_drift": _stats(start_drifts),
    }

    return {
        "project_key": project_key,
        "from_schedule_version_key": from_version,
        "to_schedule_version_key": to_version,
        "diff_type": "activity_id_aligned",
        "summary_json": json.dumps(summary),
        "activity_added_count": len(added),
        "activity_removed_count": len(removed),
        "activity_changed_count": changed,
        "relationship_added_count": rel_added,
        "relationship_removed_count": rel_removed,
        "relationship_type_changed_count": rel_type_changed,
        "lag_changed_count": lag_changed,
        "logic_churn_rate": f"{logic_churn:.4f}",
        "wbs_churn_count": wbs_changed,
        "calendar_churn_count": calendar_changed,
        "code_churn_count": code_changed,
        "constraint_changed_count": constraint_changed,
        "finish_drift_days": str(round(sum(finish_drifts), 4)) if finish_drifts else None,
        "finish_drift_mean_days": _stat_value(finish_drifts, "mean"),
        "finish_drift_median_days": _stat_value(finish_drifts, "median"),
        "finish_drift_max_days": _stat_value(finish_drifts, "max"),
        "start_drift_mean_days": _stat_value(start_drifts, "mean"),
        "milestone_finish_drift_mean_days": _stat_value(milestone_finish_drifts, "mean"),
    }


def _rel_key(rel: dict[str, Any]) -> str:
    return f"{rel.get('predecessor_activity_id')}|{rel.get('successor_activity_id')}|{rel.get('relationship_type')}"


def _rel_pair_key(rel: dict[str, Any]) -> str:
    return f"{rel.get('predecessor_activity_id')}|{rel.get('successor_activity_id')}"


def _relationship_change_counts(
    from_relationships: list[dict[str, Any]],
    to_relationships: list[dict[str, Any]],
) -> tuple[int, int]:
    from_by_pair = {_rel_pair_key(r): r for r in from_relationships}
    to_by_pair = {_rel_pair_key(r): r for r in to_relationships}
    rel_type_changed = 0
    lag_changed = 0
    for pair in set(from_by_pair) & set(to_by_pair):
        fr = from_by_pair[pair]
        tr = to_by_pair[pair]
        if fr.get("relationship_type") != tr.get("relationship_type"):
            rel_type_changed += 1
        if str(fr.get("lag_value") or "") != str(tr.get("lag_value") or ""):
            lag_changed += 1
    return rel_type_changed, lag_changed


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


def _date_delta_days(from_value: Any, to_value: Any) -> float | None:
    from_date = _parse_date(from_value)
    to_date = _parse_date(to_value)
    if from_date is None or to_date is None:
        return None
    return float((to_date - from_date).days)


def _stat_value(values: list[float], kind: str) -> str | None:
    if not values:
        return None
    if kind == "mean":
        return str(round(mean(values), 4))
    if kind == "median":
        return str(round(median(values), 4))
    if kind == "max":
        return str(round(max(values), 4))
    return None


def _stats(values: list[float]) -> dict[str, str | None]:
    return {
        "mean_days": _stat_value(values, "mean"),
        "median_days": _stat_value(values, "median"),
        "max_days": _stat_value(values, "max"),
        "count": str(len(values)),
    }


def _is_near_term(activity: dict[str, Any]) -> bool:
    finish = _parse_date(activity.get("finish_date"))
    if finish is None:
        return False
    return abs((finish - datetime.now(timezone.utc).date()).days) <= 60


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}
