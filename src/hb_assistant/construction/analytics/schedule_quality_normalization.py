"""Normalization helpers for schedule quality metrics."""

from __future__ import annotations

from typing import Any

RELATIONSHIP_TYPE_ALIASES: dict[str, str] = {
    "FINISH TO START": "FS",
    "FINISH-TO-START": "FS",
    "FINISH TO FINISH": "FF",
    "FINISH-TO-FINISH": "FF",
    "START TO START": "SS",
    "START-TO-START": "SS",
    "START TO FINISH": "SF",
    "START-TO-FINISH": "SF",
    "FS": "FS",
    "FF": "FF",
    "SS": "SS",
    "SF": "SF",
}

DEFAULT_HOURS_PER_DAY = 8.0


def normalize_relationship_type(raw: Any) -> str:
    label = str(raw or "FS").strip().upper()
    if label in {"FS", "FF", "SS", "SF"}:
        return label
    return RELATIONSHIP_TYPE_ALIASES.get(label, "UNKNOWN")


def relationship_type_distribution(rels: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"FS": 0, "FF": 0, "SS": 0, "SF": 0, "UNKNOWN": 0}
    for rel in rels:
        norm = normalize_relationship_type(rel.get("relationship_type"))
        counts[norm] = counts.get(norm, 0) + 1
    total = len(rels)
    non_fs = total - counts.get("FS", 0)
    return {
        **counts,
        "total": total,
        "non_fs_count": non_fs,
        "non_fs_ratio": round(non_fs / total, 4) if total else 0.0,
    }


def calendar_hours_per_day(calendars: list[dict[str, Any]], calendar_id: Any) -> float:
    if calendar_id is None:
        return DEFAULT_HOURS_PER_DAY
    for cal in calendars:
        if str(cal.get("calendar_id")) != str(calendar_id):
            continue
        for key in ("hours_per_day", "standard_hours_per_day", "work_hours_per_day"):
            try:
                val = cal.get(key)
                if val is not None and float(val) > 0:
                    return float(val)
            except (TypeError, ValueError):
                continue
    return DEFAULT_HOURS_PER_DAY


def normalize_duration_days(
    *,
    duration_value: Any,
    duration_unit: Any,
    hours_per_day: float = DEFAULT_HOURS_PER_DAY,
    source_format: str | None = None,
) -> float | None:
    try:
        raw = float(duration_value)
    except (TypeError, ValueError):
        return None
    default_unit = "h" if source_format == "primavera_xer" else "d"
    unit = str(duration_unit or default_unit).strip().lower()
    if unit in {"d", "day", "days"}:
        return raw
    if unit in {"h", "hr", "hour", "hours"}:
        hpd = hours_per_day if hours_per_day > 0 else DEFAULT_HOURS_PER_DAY
        return raw / hpd
    if unit in {"w", "wk", "week", "weeks"}:
        return raw * 5.0
    if unit in {"m", "mo", "month", "months"}:
        return raw * 22.0
    return raw


def is_logic_excluded_activity(act: dict[str, Any]) -> tuple[bool, str | None]:
    activity_type = str(act.get("activity_type") or "").lower()
    if act.get("is_milestone"):
        return True, "milestone"
    if "summary" in activity_type or activity_type in {"wbs_summary", "loe"}:
        return True, "summary_or_loe"
    name = str(act.get("activity_name") or "").lower()
    if "project start" in name or name.startswith("start milestone"):
        return True, "project_start_boundary"
    if "project finish" in name or name.endswith("finish milestone"):
        return True, "project_finish_boundary"
    return False, None


def cost_resource_posture(import_meta: dict[str, Any] | None) -> str:
    if not import_meta:
        return "unknown"
    status = str(import_meta.get("cost_loaded_status") or "not_cost_loaded")
    if status == "verified":
        return "cost_loaded"
    if status == "possible":
        return "partially_resource_loaded"
    if status == "unreconciled":
        return "partially_resource_loaded"
    if status == "not_cost_loaded":
        return "not_cost_loaded"
    return "unknown"