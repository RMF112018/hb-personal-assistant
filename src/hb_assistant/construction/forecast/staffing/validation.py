"""Field-specific staffing validation (Phase 2a).

Returns coded, field-scoped errors (``{field, code, message}``) for a resolved/effective staffing
row, the project assumptions, absence overrides, and project-level overlaps. Only **blocking**
conditions (SOW 4.3) are emitted here; non-blocking conditions (unmatched/uncertain attribution,
MAT actuals, missing budget row, one blank rate when others are valid) are intentionally not
raised. This module makes **no** reference to ``forecast_cost_entries`` data — actuals-aware rules
arrive in Phase 2b.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from hb_assistant.procore.normalizers.financial import parse_amount

EMPLOYMENT_TYPES = frozenset({"Hourly", "Part Time", "Full Time", "Intern"})
RATE_UNITS = frozenset({"hourly", "daily", "weekly"})
_RATE_FIELDS = ("lab_rate", "lbn_rate", "mat_rate")


def _err(field: str, code: str, message: str, **extra: Any) -> dict[str, Any]:
    out = {"field": field, "code": code, "message": message}
    out.update(extra)
    return out


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _classify_rate(value: Any) -> str:
    """One of: blank, zero, positive, negative, invalid."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return "blank"
    canon = parse_amount(value)
    if canon is None:
        return "invalid"
    try:
        amount = Decimal(canon)
    except (InvalidOperation, ValueError):
        return "invalid"
    if amount < 0:
        return "negative"
    if amount == 0:
        return "zero"
    return "positive"


def validate_row(effective_row: dict[str, Any]) -> list[dict[str, Any]]:
    """Blocking field errors for a single (effective) staffing row."""
    errors: list[dict[str, Any]] = []

    if not (effective_row.get("role_title") or "").strip():
        errors.append(_err("role_title", "role_title_missing", "Role/title is required."))

    employment = effective_row.get("employment_type")
    if employment not in EMPLOYMENT_TYPES:
        errors.append(
            _err("employment_type", "employment_type_invalid", "Invalid employment type.")
        )

    if not (effective_row.get("cost_code") or "").strip():
        errors.append(_err("cost_code", "cost_code_missing", "Cost code is required."))

    if effective_row.get("rate_unit") not in RATE_UNITS:
        errors.append(_err("rate_unit", "rate_unit_invalid", "Invalid rate unit."))

    start = _parse_date(effective_row.get("start_date"))
    finish = _parse_date(effective_row.get("finish_date"))
    if start is None:
        errors.append(_err("start_date", "start_date_invalid", "Invalid or missing start date."))
    if finish is None:
        errors.append(_err("finish_date", "finish_date_invalid", "Invalid or missing finish date."))
    if start is not None and finish is not None and finish < start:
        errors.append(
            _err("finish_date", "finish_before_start", "Finish date is before start date.")
        )

    classes = {field: _classify_rate(effective_row.get(field)) for field in _RATE_FIELDS}
    for field, cls in classes.items():
        if cls == "negative":
            errors.append(_err(field, "rate_negative", "Rate cannot be negative."))
        elif cls == "invalid":
            errors.append(_err(field, "rate_invalid", "Rate is not a valid amount."))
    if all(classes[f] in ("blank", "zero") for f in _RATE_FIELDS):
        # 2a: blocking. Phase 2b relaxes this when matching actuals exist for the row.
        errors.append(
            _err("rates", "all_rates_blank_or_zero", "At least one LAB/LBN/MAT rate is required.")
        )

    return errors


def validate_assumptions(
    assumptions: dict[str, Any], *, valid_calendar_ids: set[str] | None = None
) -> list[dict[str, Any]]:
    """Blocking errors for project staffing assumptions."""
    errors: list[dict[str, Any]] = []
    for field in ("hours_per_business_day", "business_days_per_week", "full_time_hours_per_week"):
        canon = parse_amount(assumptions.get(field))
        if canon is None or Decimal(canon) <= 0:
            errors.append(_err(field, "assumption_not_positive", f"{field} must be positive."))
    calendar_id = assumptions.get("holiday_calendar_id")
    if (
        calendar_id is not None
        and valid_calendar_ids is not None
        and calendar_id not in valid_calendar_ids
    ):
        errors.append(
            _err("holiday_calendar_id", "holiday_calendar_invalid", "Unknown holiday calendar.")
        )
    return errors


def validate_absence(absence: dict[str, Any]) -> list[dict[str, Any]]:
    """Blocking errors for a single absence override."""
    errors: list[dict[str, Any]] = []
    start = _parse_date(absence.get("start_date"))
    finish = _parse_date(absence.get("finish_date"))
    if start is None:
        errors.append(_err("start_date", "start_date_invalid", "Invalid or missing start date."))
    if finish is None:
        errors.append(_err("finish_date", "finish_date_invalid", "Invalid or missing finish date."))
    if start is not None and finish is not None and finish < start:
        errors.append(
            _err("finish_date", "finish_before_start", "Finish date is before start date.")
        )
    hours = parse_amount(absence.get("absence_hours"))
    if hours is None or Decimal(hours) <= 0:
        errors.append(_err("absence_hours", "absence_hours_not_positive", "Absence hours must be positive."))
    has_config = bool(absence.get("staffing_config_id"))
    has_person = bool((absence.get("person_name") or "").strip())
    if has_config == has_person:
        errors.append(
            _err(
                "target",
                "absence_target_ambiguous",
                "Specify exactly one of staffing row or person.",
            )
        )
    return errors


def _overlaps(a_start: date, a_finish: date, b_start: date, b_finish: date) -> bool:
    return a_start <= b_finish and b_start <= a_finish


def validate_project(
    effective_rows: list[dict[str, Any]], absences: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    """Project-level overlap errors (SOW 2.11) plus per-absence validity."""
    errors: list[dict[str, Any]] = []
    dated: list[tuple[dict[str, Any], date, date]] = []
    for row in effective_rows:
        start = _parse_date(row.get("start_date"))
        finish = _parse_date(row.get("finish_date"))
        if start is not None and finish is not None and finish >= start:
            dated.append((row, start, finish))

    for i in range(len(dated)):
        row_a, sa, fa = dated[i]
        for j in range(i + 1, len(dated)):
            row_b, sb, fb = dated[j]
            if not _overlaps(sa, fa, sb, fb):
                continue
            person_a = row_a.get("person_name_normalized")
            person_b = row_b.get("person_name_normalized")
            ids = sorted(
                [row_a.get("staffing_config_id", ""), row_b.get("staffing_config_id", "")]
            )
            if person_a and person_b and person_a == person_b:
                errors.append(
                    _err(
                        "dates",
                        "person_overlap",
                        "Same person assigned to overlapping active rows.",
                        related_ids=ids,
                    )
                )
            elif (
                # one TBD placeholder + one named row, same role + cost code
                (person_a is None) ^ (person_b is None)
                and row_a.get("role_title") == row_b.get("role_title")
                and row_a.get("cost_code") == row_b.get("cost_code")
            ):
                errors.append(
                    _err(
                        "person",
                        "tbd_overlap",
                        "TBD placeholder overlaps a named row for the same role and cost code.",
                        related_ids=ids,
                    )
                )

    for absence in absences or []:
        errors.extend(validate_absence(absence))
    return errors


def validation_result(errors: list[dict[str, Any]]) -> dict[str, Any]:
    """Roll errors into a persistable ``{status, errors}`` shape for the config repository."""
    return {"status": "invalid" if errors else "valid", "errors": errors}
