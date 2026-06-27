"""Phase 2a staffing validation tests (field-specific blocking codes + overlaps)."""

from __future__ import annotations

from hb_assistant.construction.forecast.staffing.validation import (
    validate_absence,
    validate_assumptions,
    validate_project,
    validate_row,
    validation_result,
)


def _row(**over: object) -> dict:
    row = {
        "staffing_config_id": "cfg1",
        "role_title": "Superintendent",
        "person_name_normalized": "jane doe",
        "employment_type": "Full Time",
        "cost_code": "01-100",
        "rate_unit": "weekly",
        "lab_rate": "2500.00",
        "lbn_rate": "",
        "mat_rate": None,
        "start_date": "2026-07-01",
        "finish_date": "2026-12-31",
    }
    row.update(over)
    return row


def _codes(errors: list[dict]) -> set[str]:
    return {e["code"] for e in errors}


def test_valid_row_has_no_errors() -> None:
    assert validate_row(_row()) == []


def test_each_blocking_field_code() -> None:
    assert "role_title_missing" in _codes(validate_row(_row(role_title="")))
    assert "employment_type_invalid" in _codes(validate_row(_row(employment_type="Contractor")))
    assert "cost_code_missing" in _codes(validate_row(_row(cost_code="")))
    assert "rate_unit_invalid" in _codes(validate_row(_row(rate_unit="monthly")))
    assert "start_date_invalid" in _codes(validate_row(_row(start_date="not-a-date")))
    assert "finish_date_invalid" in _codes(validate_row(_row(finish_date="")))
    assert "finish_before_start" in _codes(
        validate_row(_row(start_date="2026-12-31", finish_date="2026-07-01"))
    )
    assert "rate_negative" in _codes(validate_row(_row(lab_rate="-5.00")))
    assert "rate_invalid" in _codes(validate_row(_row(lab_rate="abc")))


def test_all_rates_blank_or_zero_blocks() -> None:
    errors = validate_row(_row(lab_rate="0.00", lbn_rate="", mat_rate=None))
    assert "all_rates_blank_or_zero" in _codes(errors)


def test_one_valid_rate_is_not_blocked() -> None:
    # mat zero + lbn blank but lab positive -> not blocked (non-blocking case stays valid)
    assert validate_row(_row(lab_rate="100.00", lbn_rate="", mat_rate="0.00")) == []


def test_assumptions_validation() -> None:
    base = {
        "hours_per_business_day": "8.00",
        "business_days_per_week": "5.00",
        "full_time_hours_per_week": "40.00",
        "holiday_calendar_id": "holcal-x",
    }
    assert validate_assumptions(base, valid_calendar_ids={"holcal-x"}) == []
    bad_cal = validate_assumptions(base, valid_calendar_ids={"other"})
    assert "holiday_calendar_invalid" in _codes(bad_cal)
    bad_hours = validate_assumptions({**base, "hours_per_business_day": "0"})
    assert "assumption_not_positive" in _codes(bad_hours)


def test_absence_validation() -> None:
    ok = {
        "staffing_config_id": "cfg1",
        "start_date": "2026-08-01",
        "finish_date": "2026-08-05",
        "absence_hours": "40.00",
    }
    assert validate_absence(ok) == []
    both = validate_absence({**ok, "person_name": "Jane Doe"})
    assert "absence_target_ambiguous" in _codes(both)
    neither = validate_absence(
        {"start_date": "2026-08-01", "finish_date": "2026-08-05", "absence_hours": "8"}
    )
    assert "absence_target_ambiguous" in _codes(neither)
    bad_hours = validate_absence({**ok, "absence_hours": "0"})
    assert "absence_hours_not_positive" in _codes(bad_hours)


def test_project_person_overlap() -> None:
    a = _row(staffing_config_id="a", person_name_normalized="jane doe", cost_code="01-100")
    b = _row(
        staffing_config_id="b",
        person_name_normalized="jane doe",
        cost_code="02-200",
        start_date="2026-09-01",
        finish_date="2027-01-31",
    )
    errors = validate_project([a, b])
    assert "person_overlap" in _codes(errors)


def test_project_tbd_overlap() -> None:
    named = _row(staffing_config_id="a", person_name_normalized="jane doe")
    tbd = _row(staffing_config_id="b", person_name_normalized=None)
    errors = validate_project([named, tbd])
    assert "tbd_overlap" in _codes(errors)


def test_project_no_overlap_when_disjoint() -> None:
    a = _row(staffing_config_id="a", start_date="2026-01-01", finish_date="2026-03-31")
    b = _row(
        staffing_config_id="b",
        person_name_normalized="jane doe",
        start_date="2026-06-01",
        finish_date="2026-09-30",
    )
    assert validate_project([a, b]) == []


def test_validation_result_rollup() -> None:
    assert validation_result([]) == {"status": "valid", "errors": []}
    rolled = validation_result([{"field": "x", "code": "y", "message": "z"}])
    assert rolled["status"] == "invalid"
    assert len(rolled["errors"]) == 1
