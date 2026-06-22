"""Deterministic schedule version-over-version comparison."""

from __future__ import annotations

import json
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
    finish_drifts: list[float] = []
    for act_id in common:
        fa = from_by_id[act_id]
        ta = to_by_id[act_id]
        keys = ("finish_date", "start_date", "duration_original", "percent_complete", "cost_code")
        if any(fa.get(k) != ta.get(k) for k in keys):
            changed += 1

    rel_from = {_rel_key(r) for r in from_relationships}
    rel_to = {_rel_key(r) for r in to_relationships}
    rel_added = len(rel_to - rel_from)
    rel_removed = len(rel_from - rel_to)
    rel_union = rel_from | rel_to
    logic_churn = (rel_added + rel_removed) / len(rel_union) if rel_union else 0.0

    summary = {
        "added_activity_ids": sorted(added)[:50],
        "removed_activity_ids": sorted(removed)[:50],
        "changed_activity_count": changed,
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
        "logic_churn_rate": f"{logic_churn:.4f}",
        "wbs_churn_count": 0,
        "calendar_churn_count": 0,
        "code_churn_count": 0,
        "finish_drift_days": str(sum(finish_drifts)) if finish_drifts else None,
    }


def _rel_key(rel: dict[str, Any]) -> str:
    return f"{rel.get('predecessor_activity_id')}|{rel.get('successor_activity_id')}|{rel.get('relationship_type')}"