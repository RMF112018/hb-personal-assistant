"""Normalization helpers for schedule quality metrics."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

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

LagConversionStatus = Literal["known_unit", "assumed_days", "unparseable"]


@dataclass(frozen=True)
class LagNormalizationResult:
    normalized_days: Decimal | None
    source_unit_label: str | None
    conversion_status: LagConversionStatus


_DAY_UNITS = {"d", "day", "days"}
_HOUR_UNITS = {"h", "hr", "hrs", "hour", "hours"}
_MINUTE_UNITS = {"m", "min", "mins", "minute", "minutes"}
_MINUTE_TENTH_UNITS = {
    "minute_tenth",
    "minute_tenths",
    "tenths_of_minute",
    "tenth_of_minute",
    "msp_link_lag",
}
_WEEK_UNITS = {"w", "wk", "wks", "week", "weeks"}
_MONTH_UNITS = {"mo", "month", "months"}


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _hours_per_day_decimal(hours_per_day: Decimal | float | int | None) -> Decimal:
    parsed = _decimal_or_none(hours_per_day)
    if parsed is None or parsed <= 0:
        return Decimal(str(DEFAULT_HOURS_PER_DAY))
    return parsed


def normalize_lag_result(
    lag_value: object,
    lag_unit: object | None,
    *,
    hours_per_day: Decimal | float | int | None = None,
) -> LagNormalizationResult:
    raw = _decimal_or_none(lag_value)
    unit_label = str(lag_unit).strip().lower() if lag_unit is not None else None
    if unit_label == "":
        unit_label = None
    if raw is None:
        return LagNormalizationResult(
            normalized_days=None,
            source_unit_label=unit_label,
            conversion_status="unparseable",
        )

    hpd = _hours_per_day_decimal(hours_per_day)
    if unit_label in _DAY_UNITS:
        days = raw
    elif unit_label in _HOUR_UNITS:
        days = raw / hpd
    elif unit_label in _MINUTE_UNITS:
        days = raw / Decimal("60") / hpd
    elif unit_label in _MINUTE_TENTH_UNITS:
        days = raw / Decimal("10") / Decimal("60") / hpd
    elif unit_label in _WEEK_UNITS:
        days = raw * Decimal("5.0")
    elif unit_label in _MONTH_UNITS:
        days = raw * Decimal("22.0")
    else:
        return LagNormalizationResult(
            normalized_days=raw,
            source_unit_label=unit_label,
            conversion_status="assumed_days",
        )
    return LagNormalizationResult(
        normalized_days=days,
        source_unit_label=unit_label,
        conversion_status="known_unit",
    )


def normalize_lag_days(
    lag_value: object,
    lag_unit: object | None,
    *,
    hours_per_day: Decimal | float | int | None = None,
) -> Decimal | None:
    return normalize_lag_result(
        lag_value,
        lag_unit,
        hours_per_day=hours_per_day,
    ).normalized_days


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
