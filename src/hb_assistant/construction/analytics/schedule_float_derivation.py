"""Derive finish float from P6 exported remaining early/late dates (not full CPM recalc)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

FINISH_FLOAT_TYPE = "finish float = late finish - early finish"
FLOAT_BASIS = "remaining_late_finish_minus_remaining_early_finish"
DEFAULT_HOURS_PER_DAY = 8.0


def parse_schedule_options(fields: dict[str, str]) -> dict[str, Any]:
    threshold_raw = fields.get("CriticalActivityFloatThreshold")
    threshold = 0.0
    if threshold_raw is not None and str(threshold_raw).strip() != "":
        try:
            threshold = float(threshold_raw)
        except ValueError:
            threshold = 0.0
    calc_finish = fields.get("CalculateFloatBasedOnFinishDate")
    return {
        "compute_total_float_type": fields.get("ComputeTotalFloatType"),
        "critical_activity_path_type": fields.get("CriticalActivityPathType"),
        "critical_activity_float_threshold": threshold,
        "calculate_float_based_on_finish_date": _truthy_int(calc_finish),
    }


def merge_schedule_options(
    base: dict[str, Any] | None, override: dict[str, Any] | None
) -> dict[str, Any]:
    out: dict[str, Any] = dict(base or {})
    for key, val in (override or {}).items():
        if val is not None and val != "":
            out[key] = val
    return out


def _truthy_int(value: str | None) -> int:
    return 1 if (value or "").strip().lower() in {"true", "1", "y", "yes"} else 0


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value or not str(value).strip():
        return None
    raw = str(value).strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _hours_per_day(calendar_id: str | None, calendars_by_id: dict[str, dict[str, Any]]) -> float:
    if not calendar_id:
        return DEFAULT_HOURS_PER_DAY
    cal = calendars_by_id.get(str(calendar_id), {})
    raw = cal.get("hours_per_day")
    if raw is None:
        return DEFAULT_HOURS_PER_DAY
    try:
        val = float(raw)
        return val if val > 0 else DEFAULT_HOURS_PER_DAY
    except (TypeError, ValueError):
        return DEFAULT_HOURS_PER_DAY


def supports_finish_float_derivation(options: dict[str, Any] | None) -> bool:
    raw = (options or {}).get("compute_total_float_type") or ""
    return FINISH_FLOAT_TYPE in str(raw).lower()


def derive_finish_float(
    activity: dict[str, Any],
    *,
    options: dict[str, Any] | None,
    calendars_by_id: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return derived float fields; empty dict when not derivable."""
    if not supports_finish_float_derivation(options):
        return {}

    early_finish = activity.get("remaining_early_finish") or activity.get("remaining_finish")
    late_finish = activity.get("remaining_late_finish")
    early_dt = _parse_iso_datetime(early_finish)
    late_dt = _parse_iso_datetime(late_finish)
    if early_dt is None or late_dt is None:
        return {}

    hours = (late_dt - early_dt).total_seconds() / 3600.0
    hpd = _hours_per_day(activity.get("calendar_id"), calendars_by_id or {})
    days = hours / hpd

    out: dict[str, Any] = {
        "derived_total_float_hours": f"{hours:.4f}".rstrip("0").rstrip("."),
        "derived_total_float_days": f"{days:.4f}".rstrip("0").rstrip("."),
        "derived_float_basis": FLOAT_BASIS,
    }

    path_type = str((options or {}).get("critical_activity_path_type") or "").strip().lower()
    threshold = float((options or {}).get("critical_activity_float_threshold") or 0.0)
    if path_type == "critical float":
        out["derived_is_critical_by_float_threshold"] = 1 if days <= threshold else 0
    else:
        out["derived_is_critical_by_float_threshold"] = None

    return out


def apply_derived_float_to_activities(
    activities: list[dict[str, Any]],
    *,
    options: dict[str, Any] | None,
    calendars: list[dict[str, Any]] | None = None,
) -> None:
    calendars_by_id = {
        str(c.get("calendar_id")): c for c in (calendars or []) if c.get("calendar_id")
    }
    for act in activities:
        if act.get("explicit_total_float_hours") is not None:
            continue
        derived = derive_finish_float(act, options=options, calendars_by_id=calendars_by_id)
        act.update(derived)
