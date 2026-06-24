"""Baseline-dependent schedule-quality evidence helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from .schedule_quality_normalization import is_logic_excluded_activity

MAX_BASELINE_SAMPLE_IDS = 10

STATUS_DATE_METADATA_FIELDS = (
    "data_date",
    "status_date",
    "schedule_data_date",
    "source_data_date",
)


@dataclass(frozen=True)
class ParsedScheduleDate:
    value: date | None
    raw: str | None
    parsed: bool
    reason: str | None = None


def _raw_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_schedule_date(value: Any) -> ParsedScheduleDate:
    text = _raw_text(value)
    if text is None:
        return ParsedScheduleDate(value=None, raw=None, parsed=False, reason="missing")
    normalized = text.replace("Z", "+00:00")
    candidates = (normalized, normalized[:10])
    for candidate in candidates:
        try:
            parsed_dt = datetime.fromisoformat(candidate)
            return ParsedScheduleDate(value=parsed_dt.date(), raw=text, parsed=True)
        except ValueError:
            try:
                return ParsedScheduleDate(
                    value=date.fromisoformat(candidate),
                    raw=text,
                    parsed=True,
                )
            except ValueError:
                continue
    return ParsedScheduleDate(value=None, raw=text, parsed=False, reason="invalid")


def resolve_status_date(
    *,
    ctx_data_date: Any,
    import_meta: dict[str, Any] | None,
    schedule_version_key: str | None,
) -> dict[str, Any]:
    candidates: list[tuple[str, Any]] = [("ctx.data_date", ctx_data_date)]
    meta = import_meta or {}
    candidates.extend(
        (f"import_meta.{field}", meta.get(field)) for field in STATUS_DATE_METADATA_FIELDS
    )
    if schedule_version_key:
        parts = str(schedule_version_key).split("|")
        candidates.append(("schedule_version_key", parts[2] if len(parts) >= 3 else None))

    invalid: list[dict[str, str | None]] = []
    for source, raw in candidates:
        parsed = parse_schedule_date(raw)
        if parsed.parsed:
            return {
                "status_date": parsed.value.isoformat() if parsed.value else None,
                "status_date_raw": parsed.raw,
                "status_date_source": source,
                "status_date_parse_success": True,
                "status_date_missing_reason": None,
                "invalid_status_date_candidates": invalid,
            }
        if parsed.raw is not None:
            invalid.append({"source": source, "raw": parsed.raw, "reason": parsed.reason})

    reason = "invalid_status_date" if invalid else "missing_status_date"
    return {
        "status_date": None,
        "status_date_raw": None,
        "status_date_source": None,
        "status_date_parse_success": False,
        "status_date_missing_reason": reason,
        "invalid_status_date_candidates": invalid,
    }


def _sample(activity: dict[str, Any], *, reason: str | None = None) -> dict[str, Any]:
    item = {
        "activity_id": activity.get("activity_id"),
        "activity_name": activity.get("activity_name"),
        "baseline_finish": activity.get("baseline_finish"),
        "actual_finish": activity.get("actual_finish"),
        "activity_status": activity.get("activity_status"),
    }
    if reason:
        item["reason"] = reason
    return item


def is_completed_by_status_date(activity: dict[str, Any], status_date: date) -> bool:
    actual_finish = parse_schedule_date(activity.get("actual_finish"))
    if actual_finish.parsed and actual_finish.value is not None:
        return actual_finish.value <= status_date
    if actual_finish.raw is not None:
        return False

    status = str(activity.get("activity_status") or "").strip().lower()
    if status in {"tk_complete", "complete", "completed", "finished"}:
        return True
    try:
        percent_complete = float(activity.get("percent_complete"))
    except (TypeError, ValueError):
        return False
    return percent_complete >= 100.0


def compute_baseline_quality_evidence(
    *,
    activities: list[dict[str, Any]],
    ctx_data_date: Any = None,
    import_meta: dict[str, Any] | None = None,
    schedule_version_key: str | None = None,
) -> dict[str, Any]:
    status = resolve_status_date(
        ctx_data_date=ctx_data_date,
        import_meta=import_meta,
        schedule_version_key=schedule_version_key,
    )
    status_date = date.fromisoformat(status["status_date"]) if status["status_date"] else None
    baseline_source = (import_meta or {}).get("baseline_source")

    eligible: list[dict[str, Any]] = []
    excluded_count = 0
    exclusion_reasons: dict[str, int] = {}
    baseline_start_count = 0
    baseline_finish_count = 0
    target_start_count = 0
    target_finish_count = 0
    planned_finish_count = 0
    actual_finish_count = 0
    completed_activity_count = 0
    incomplete_activity_count = 0
    invalid_baseline_finish_count = 0
    due_activities: list[dict[str, Any]] = []
    missed: list[dict[str, Any]] = []
    completed_due: list[dict[str, Any]] = []

    for activity in activities:
        excluded, reason = is_logic_excluded_activity(activity)
        if excluded:
            excluded_count += 1
            key = reason or "excluded"
            exclusion_reasons[key] = exclusion_reasons.get(key, 0) + 1
            continue
        eligible.append(activity)
        if _raw_text(activity.get("baseline_start")):
            baseline_start_count += 1
        if _raw_text(activity.get("baseline_finish")):
            baseline_finish_count += 1
        if _raw_text(activity.get("target_start")):
            target_start_count += 1
        if _raw_text(activity.get("target_finish")):
            target_finish_count += 1
        if _raw_text(activity.get("planned_finish")):
            planned_finish_count += 1
        if _raw_text(activity.get("actual_finish")):
            actual_finish_count += 1

        if status_date and is_completed_by_status_date(activity, status_date):
            completed_activity_count += 1
        else:
            incomplete_activity_count += 1

        baseline_finish = parse_schedule_date(activity.get("baseline_finish"))
        if baseline_finish.raw is not None and not baseline_finish.parsed:
            invalid_baseline_finish_count += 1
        if (
            status_date
            and baseline_finish.parsed
            and baseline_finish.value is not None
            and baseline_finish.value <= status_date
        ):
            due_activities.append(activity)
            if is_completed_by_status_date(activity, status_date):
                completed_due.append(activity)
            else:
                reason = "not_complete_by_status_date"
                actual_finish = parse_schedule_date(activity.get("actual_finish"))
                if actual_finish.parsed and actual_finish.value and actual_finish.value > status_date:
                    reason = "actual_finish_after_status_date"
                missed.append(_sample(activity, reason=reason))

    missing: list[str] = []
    if not activities:
        missing.append("no activities in canonical store")
    if status_date is None:
        missing.append(status["status_date_missing_reason"] or "missing status date")
    if baseline_finish_count == 0:
        missing.append("missing baseline finish dates")
    if status_date is not None and baseline_finish_count > 0 and not due_activities:
        missing.append("baseline due denominator is zero")

    thresholds = {
        "profile_thresholds_defined": False,
        "threshold_status_available": False,
        "metric_interpretation": "reported_indicator_no_profile_threshold",
    }
    denominator_definition = (
        "eligible activities with true baseline_finish on or before status_date"
    )
    evidence = {
        "total_activity_count": len(activities),
        "eligible_activity_count": len(eligible),
        "excluded_activity_count": excluded_count,
        "exclusion_reasons": exclusion_reasons,
        "baseline_start_count": baseline_start_count,
        "baseline_finish_count": baseline_finish_count,
        "target_start_count": target_start_count,
        "target_finish_count": target_finish_count,
        "planned_finish_count": planned_finish_count,
        "non_baseline_date_fields": {
            "target_start_count": target_start_count,
            "target_finish_count": target_finish_count,
            "planned_finish_count": planned_finish_count,
            "used_as_baseline_proxy": False,
        },
        "actual_finish_count": actual_finish_count,
        "completed_activity_count": completed_activity_count,
        "incomplete_activity_count": incomplete_activity_count,
        "invalid_baseline_finish_count": invalid_baseline_finish_count,
        "baseline_due_activity_count": len(due_activities),
        "missed_due_activity_count": len(missed),
        "completed_due_activity_count": len(completed_due),
        "denominator_definition": denominator_definition,
        "baseline_source": baseline_source,
        "true_baseline_finish_dates_available": baseline_finish_count > 0,
        "only_target_or_planned_dates_available": baseline_finish_count == 0
        and (target_finish_count > 0 or planned_finish_count > 0),
        "missed_tasks_measurable": status_date is not None
        and baseline_finish_count > 0
        and len(due_activities) > 0,
        "bei_measurable": status_date is not None
        and baseline_finish_count > 0
        and len(due_activities) > 0,
        "cpli_prerequisites_available": False,
        "missing_prerequisites": missing,
        "caveats": [
            "target/planned dates are counted as non-baseline evidence only",
            "CPLI requires CPM critical-path length evidence and is not calculated here",
        ],
        "missed_activity_samples": missed[:MAX_BASELINE_SAMPLE_IDS],
        "completed_due_activity_samples": [
            _sample(activity) for activity in completed_due[:MAX_BASELINE_SAMPLE_IDS]
        ],
        **status,
        **thresholds,
    }
    return evidence
