"""Staffing → DB-native monthly output (Phase 6).

Computes the staffing contribution to a DB-native forecast result entirely in hb_assistant (reusing
the Phase-2 proration + attribution), then merges it into the engine result dict so staffing rows
flow into the monthly cells, the operator matrix, and the totals/KPIs — with **zero CFR change**.

The merge preserves the engine's exact reconciliation invariants: per-code forecast cells sum to
that code's cost-to-complete; one matrix row per budget code; matrix totals = Σ rows; month totals
= Σ cells; header cost-to-complete = Σ all forecast cells. Staffing forecast/actual cells live on
synthetic budget_code_keys (``staffing:{config_id}:{category}`` for labor, ``staffing-materials:
{cost_code}:MAT`` for materials) so they coexist with budget-code rows.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from hb_assistant.procore.normalizers.financial import parse_amount

from . import attribution, template_resolution, validation
from .proration import business_day_units, holiday_duration_map
from .repositories import (
    AbsenceOverrideRepository,
    HolidayCalendarRepository,
    StaffingActualsRepository,
    StaffingAssumptionsRepository,
    StaffingConfigRepository,
    StaffingTemplateRepository,
)

_CENT = Decimal("0.01")
_LABOR = ("LAB", "LBN")


def _money(value: Decimal) -> str:
    return str(value.quantize(_CENT))


def _rate(value: Any) -> Decimal | None:
    canon = parse_amount(value)
    if canon is None:
        return None
    try:
        d = Decimal(canon)
    except (InvalidOperation, ValueError):
        return None
    return d if d > 0 else None


def _in_window(month: str, start: str | None, end: str | None) -> bool:
    return bool(start and end and start <= month <= end)


def _quantity(units: Decimal, rate_unit: str, hpd: Decimal, bdw: Decimal) -> Decimal:
    if rate_unit == "hourly":
        return units * hpd
    if rate_unit == "weekly":
        return units / bdw if bdw else Decimal("0")
    return units  # daily


def _absence_units_by_month(
    absences: list[dict[str, Any]], row: dict[str, Any], holiday_dates: dict[str, str], hpd: Decimal
) -> dict[str, Decimal]:
    """Full-Time absence reduction: business-day units to subtract per month for this row."""
    if row.get("employment_type") != "Full Time" or hpd <= 0:
        return {}
    person = row.get("person_name_normalized")
    out: dict[str, Decimal] = {}
    for ab in absences:
        if ab.get("staffing_config_id"):
            if ab["staffing_config_id"] != row.get("staffing_config_id"):
                continue
        elif not (person and ab.get("person_name_normalized") == person):
            continue
        hours = _rate(ab.get("absence_hours"))
        if hours is None:
            continue
        span = business_day_units(ab.get("start_date"), ab.get("finish_date"), holiday_dates=holiday_dates)
        span_total = sum(span.values(), Decimal("0"))
        if span_total <= 0:
            continue
        absence_days = hours / hpd
        for month, units in span.items():
            share = (units / span_total) * absence_days
            out[month] = out.get(month, Decimal("0")) + share
    return out


def build_staffing_output(db_path: str, project_key: str, window: dict[str, Any]) -> dict[str, Any]:
    """Compute the staffing forecast contribution. Returns status + (when valid) lines/cells/rows."""
    config_repo = StaffingConfigRepository(db_path=db_path)
    rows = config_repo.list(project_key, active_only=True)
    if not rows:
        return {"status": "empty"}

    assumptions = StaffingAssumptionsRepository(db_path=db_path).get(project_key)
    absences = AbsenceOverrideRepository(db_path=db_path).list(project_key, active_only=True)
    templates = StaffingTemplateRepository(db_path=db_path)
    holidays = HolidayCalendarRepository(db_path=db_path)
    holiday_dates = (
        holiday_duration_map(holidays.get_dates(assumptions["holiday_calendar_id"]))
        if assumptions.get("holiday_calendar_id")
        else {}
    )

    # resolve effective rows + validate (blocking)
    effective: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for row in rows:
        tv = templates.get_current_version(row["template_id"]) if row.get("template_id") else None
        try:
            eff, _i, _o = template_resolution.resolve_effective_row(row, tv)
        except template_resolution.TemplateResolutionError as exc:
            eff = row
            errors.append({"field": "template", "code": "template_resolution_failed",
                           "message": str(exc), "staffing_config_id": row.get("staffing_config_id")})
        effective.append(eff)
        errors.extend(validation.validate_row(eff))
    errors.extend(validation.validate_project(effective, absences))
    errors.extend(validation.validate_assumptions(assumptions, valid_calendar_ids=holidays.calendar_ids()))
    if errors:
        return {"status": "invalid", "errors": errors}

    # make sure actuals are projected + attributed
    attribution.rebuild(db_path, project_key)
    actuals_repo = StaffingActualsRepository(db_path=db_path)

    fm_start, fm_end = window.get("forecast_start_month"), window.get("forecast_end_month")
    am_start, am_through = window.get("actuals_start_month"), window.get("actuals_through_month")
    has_window = all(window.get(f) for f in
                     ("forecast_start_month", "forecast_end_month",
                      "actuals_start_month", "actuals_through_month"))
    hpd = _rate(assumptions.get("hours_per_business_day")) or Decimal("8")
    bdw = _rate(assumptions.get("business_days_per_week")) or Decimal("5")

    cells: list[dict[str, Any]] = []
    lines: list[dict[str, Any]] = []
    matrix_rows: list[dict[str, Any]] = []
    staffing_rows: list[dict[str, Any]] = []

    # attributed labor actuals by (staffing_config_id, category, month)
    actual_by_key: dict[tuple[str, str, str], Decimal] = {}
    for a in actuals_repo.list(project_key):
        if a.get("attribution_status") != "matched_rule" or not a.get("staffing_config_id"):
            continue
        if a.get("category") not in _LABOR:
            continue
        month = a.get("accounting_month")
        if not (has_window and _in_window(month, am_start, am_through)):
            continue
        k = (a["staffing_config_id"], a["category"], month)
        actual_by_key[k] = actual_by_key.get(k, Decimal("0")) + (_rate(a.get("amount")) or Decimal("0"))

    for eff in effective:
        cid = eff["staffing_config_id"]
        absence_units = _absence_units_by_month(absences, eff, holiday_dates, hpd)
        units_by_month = business_day_units(eff["start_date"], eff["finish_date"], holiday_dates=holiday_dates)
        for cat in _LABOR:
            rate = _rate(eff.get("lab_rate" if cat == "LAB" else "lbn_rate"))
            key = f"staffing:{cid}:{cat}"
            ctd = Decimal("0")
            forecast_cells: list[tuple[str, Decimal]] = []
            if has_window:
                for month, units in units_by_month.items():
                    if not _in_window(month, fm_start, fm_end) or rate is None:
                        continue
                    eligible = units - absence_units.get(month, Decimal("0"))
                    if eligible < 0:
                        eligible = Decimal("0")
                    cost = (rate * _quantity(eligible, eff.get("rate_unit") or "daily", hpd, bdw)).quantize(_CENT)
                    if cost > 0:
                        forecast_cells.append((month, cost))
                for month in sorted({am for (c, ca, am) in actual_by_key if c == cid and ca == cat}):
                    amt = actual_by_key[(cid, cat, month)]
                    ctd += amt
                    cells.append(_cell(key, month, amt, actual=True))
            ftc = sum((c for _m, c in forecast_cells), Decimal("0"))
            if not has_window:
                # no operator window: emit a single forecast line for the full assignment, no cells
                full = _full_assignment_cost(units_by_month, rate, eff, hpd, bdw)
                if full <= 0:
                    continue
                ftc = full
            elif ftc <= 0 and ctd <= 0:
                continue
            for month, cost in forecast_cells:
                cells.append(_cell(key, month, cost, actual=False))
            lines.append(_line(key, eff.get("cost_code"), cat, ctd + ftc, ftc))
            if has_window:
                matrix_rows.append(_matrix_row(key, eff, cat, ctd, ftc))
                staffing_rows.append(_staffing_row(key, eff, cat, ctd + ftc))

    # MAT materials summary (actuals only, never person-attributed)
    if has_window:
        for m in actuals_repo.mat_summary(project_key):
            amt = _rate(m.get("actual_amount"))
            if amt is None or amt <= 0:
                continue
            key = f"staffing-materials:{m['cost_code']}:MAT"
            first = m.get("first_month")
            month = first if _in_window(first, am_start, am_through) else am_through
            cells.append(_cell(key, month, amt, actual=True))
            lines.append(_line(key, m["cost_code"], "MAT", amt, Decimal("0")))
            matrix_rows.append(_matrix_row_materials(key, m["cost_code"], amt))
            staffing_rows.append(_mat_staffing_row(key, m["cost_code"], amt))

    return {
        "status": "ok" if (lines or cells) else "empty",
        "lines": lines, "monthly": cells, "matrix_rows": matrix_rows, "staffing": staffing_rows,
        "effective": effective, "assumptions": assumptions,
    }


def _full_assignment_cost(units_by_month, rate, eff, hpd, bdw) -> Decimal:
    if rate is None:
        return Decimal("0")
    total_units = sum(units_by_month.values(), Decimal("0"))
    return (rate * _quantity(total_units, eff.get("rate_unit") or "daily", hpd, bdw)).quantize(_CENT)


def _cell(key: str, month: str, value: Decimal, *, actual: bool) -> dict[str, Any]:
    return {
        "budget_code_key": key, "month": month, "value": _money(value),
        "is_actual": 1 if actual else 0,
        "value_type": "actual" if actual else "forecast",
        "source_status": "source_actual" if actual else "calculated_forecast",
    }


def _line(key: str, cost_code: str | None, category: str, final: Decimal, ctc: Decimal) -> dict[str, Any]:
    return {
        "budget_code_key": key, "cost_code": cost_code, "category": category,
        "forecast_final_cost": _money(final), "forecast_cost_to_complete": _money(ctc),
        "variance_to_budget": _money(-final), "confidence": "medium",
        "method_code": "staffing_basis", "row_status": "ok", "reason_codes": [],
    }


def _matrix_row(key: str, eff: dict[str, Any], category: str, ctd: Decimal, ftc: Decimal) -> dict[str, Any]:
    eac = ctd + ftc
    return {
        "budget_code_key": key, "budget_code": None, "cost_code": eff.get("cost_code"),
        "cost_type": category, "projected_budget_display": "0.00",
        "projected_budget_display_source": "staffing",
        "projected_budget_calculation_basis": "0.00", "projected_budget_calculation_source": "staffing",
        "projected_budget_source_warning": None,
        "completed_to_date": _money(ctd), "forecast_to_complete": _money(ftc),
        "estimated_at_completion": _money(eac), "variance_to_budget": _money(-eac),
        "confidence": "medium", "method_code": "staffing_basis", "reason_codes": [],
        "sort_key": key, "row_type": "staffing_labor", "staffing_config_id": eff.get("staffing_config_id"),
        "role_title": eff.get("role_title"), "person_name": eff.get("person_name"),
        "employee_name_normalized": eff.get("person_name_normalized"),
        "source_budget_code_key": None, "attribution_status": "matched_rule" if ctd > 0 else "forecast_only",
    }


def _matrix_row_materials(key: str, cost_code: str, amt: Decimal) -> dict[str, Any]:
    return {
        "budget_code_key": key, "budget_code": None, "cost_code": cost_code, "cost_type": "MAT",
        "projected_budget_display": "0.00", "projected_budget_display_source": "staffing",
        "projected_budget_calculation_basis": "0.00", "projected_budget_calculation_source": "staffing",
        "projected_budget_source_warning": None,
        "completed_to_date": _money(amt), "forecast_to_complete": "0.00",
        "estimated_at_completion": _money(amt), "variance_to_budget": _money(-amt),
        "confidence": "medium", "method_code": "staffing_materials", "reason_codes": [],
        "sort_key": key, "row_type": "staffing_materials", "staffing_config_id": None,
        "role_title": "Materials", "person_name": None, "employee_name_normalized": None,
        "source_budget_code_key": None, "attribution_status": "not_applicable",
    }


def _staffing_row(key: str, eff: dict[str, Any], category: str, cost: Decimal) -> dict[str, Any]:
    return {"budget_code_key": key, "role": eff.get("role_title"), "month": None,
            "headcount": None, "cost_amount": _money(cost),
            "staffing_config_id": eff.get("staffing_config_id"), "category": category}


def _mat_staffing_row(key: str, cost_code: str, amt: Decimal) -> dict[str, Any]:
    return {"budget_code_key": key, "role": "Materials", "month": None, "headcount": None,
            "cost_amount": _money(amt), "category": "MAT", "cost_code": cost_code}


def merge_staffing_into_result(result: dict[str, Any], staffing: dict[str, Any]) -> dict[str, Any]:
    """Augment a DB-native engine result dict with staffing rows + recomputed totals/summary."""
    if staffing.get("status") != "ok":
        return result
    result = dict(result)
    result["forecast_lines"] = list(result.get("forecast_lines") or ()) + staffing["lines"]
    result["monthly"] = list(result.get("monthly") or ()) + staffing["monthly"]
    result["staffing"] = staffing["staffing"]

    if staffing["matrix_rows"]:
        result["monthly_table_rows"] = list(result.get("monthly_table_rows") or ()) + staffing["matrix_rows"]
        result["monthly_table_totals"] = _recompute_totals(
            result["monthly_table_rows"], result["monthly"]
        )

    result["summary"] = _recompute_summary(result.get("summary") or {}, staffing["lines"])
    return result


def _d(v: Any) -> Decimal:
    try:
        return Decimal(str(v)) if v not in (None, "") else Decimal("0")
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _recompute_totals(rows: list[dict[str, Any]], cells: list[dict[str, Any]]) -> dict[str, Any]:
    pb = ctd = ftc = eac = var = Decimal("0")
    for r in rows:
        pb += _d(r.get("projected_budget_display"))
        ctd += _d(r.get("completed_to_date"))
        ftc += _d(r.get("forecast_to_complete"))
        eac += _d(r.get("estimated_at_completion"))
        var += _d(r.get("variance_to_budget"))
    month_values: dict[str, Decimal] = {}
    for c in cells:
        month_values[c["month"]] = month_values.get(c["month"], Decimal("0")) + _d(c.get("value"))
    return {
        "month_values": {m: _money(v) for m, v in sorted(month_values.items())},
        "projected_budget_total": _money(pb), "completed_to_date_total": _money(ctd),
        "forecast_to_complete_total": _money(ftc), "estimated_at_completion_total": _money(eac),
        "variance_to_budget_total": _money(var),
    }


def _recompute_summary(summary: dict[str, Any], staffing_lines: list[dict[str, Any]]) -> dict[str, Any]:
    out = dict(summary)
    add_final = sum((_d(ln["forecast_final_cost"]) for ln in staffing_lines), Decimal("0"))
    add_ctc = sum((_d(ln["forecast_cost_to_complete"]) for ln in staffing_lines), Decimal("0"))
    final = _d(summary.get("total_forecast_final_cost")) + add_final
    ctc = _d(summary.get("total_cost_to_complete")) + add_ctc
    revised = _d(summary.get("total_revised_budget"))
    out["total_forecast_final_cost"] = _money(final)
    out["total_cost_to_complete"] = _money(ctc)
    out["variance_to_budget"] = _money(final - revised)
    return out
