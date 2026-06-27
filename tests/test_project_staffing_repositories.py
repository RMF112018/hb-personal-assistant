"""Phase 2a staffing repository tests (CRUD, soft-delete, redaction, idempotency)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from hb_assistant.construction.forecast.staffing.repositories import (
    AbsenceOverrideRepository,
    HolidayCalendarRepository,
    StaffingAssumptionsRepository,
    StaffingConfigRepository,
    StaffingCostCodeRepository,
    StaffingTemplateRepository,
    normalize_name,
)
from hb_assistant.store.migrator import SQLiteMigrator

_CAL_ID = "holcal-company_default_2026_2040"


def _db(td: str) -> str:
    path = Path(td) / "staffing.db"
    SQLiteMigrator(db_path=str(path)).apply()
    return str(path)


def _assert_no_raw(obj: dict) -> None:
    for forbidden in ("raw_json", "run_id", "source_path", "source_sha256"):
        assert forbidden not in obj, forbidden


def test_normalize_name() -> None:
    assert normalize_name("  John   Smith ") == "john smith"
    assert normalize_name("") is None
    assert normalize_name(None) is None


def test_holiday_calendar_read_seeded() -> None:
    with tempfile.TemporaryDirectory() as td:
        repo = HolidayCalendarRepository(db_path=_db(td))
        cals = repo.list_calendars()
        assert len(cals) == 1
        assert cals[0]["calendar_key"] == "company_default_2026_2040"
        _assert_no_raw(cals[0])
        assert _CAL_ID in repo.calendar_ids()
        dates = repo.get_dates(_CAL_ID)
        assert len(dates) == 150
        dates_2026 = repo.get_dates(_CAL_ID, year_range=(2026, 2026))
        assert len(dates_2026) == 10


def test_assumptions_defaults_and_upsert() -> None:
    with tempfile.TemporaryDirectory() as td:
        repo = StaffingAssumptionsRepository(db_path=_db(td))
        default = repo.get("tropical")
        assert default["persisted"] is False
        assert default["hours_per_business_day"] == "8.00"
        assert default["full_time_hours_per_week"] == "40.00"
        saved = repo.upsert("tropical", hours_per_business_day="7.50", holiday_calendar_id=_CAL_ID)
        assert saved["persisted"] is True
        assert saved["hours_per_business_day"] == "7.50"
        assert saved["business_days_per_week"] == "5.00"  # untouched default
        assert saved["holiday_calendar_id"] == _CAL_ID
        # second upsert merges over stored values
        again = repo.upsert("tropical", business_days_per_week="4.00")
        assert again["hours_per_business_day"] == "7.50"
        assert again["business_days_per_week"] == "4.00"


def _config_row(**over: object) -> dict:
    row = {
        "project_key": "tropical",
        "role_title": "Superintendent",
        "person_name": "  Jane  Doe ",
        "employment_type": "Full Time",
        "cost_code": "01-100",
        "rate_unit": "weekly",
        "lab_rate": "2500.00",
        "start_date": "2026-07-01",
        "finish_date": "2026-12-31",
    }
    row.update(over)
    return row


def test_config_crud_and_soft_delete() -> None:
    with tempfile.TemporaryDirectory() as td:
        repo = StaffingConfigRepository(db_path=_db(td))
        created = repo.create(_config_row())
        cid = created["staffing_config_id"]
        assert created["person_name_normalized"] == "jane doe"
        assert created["active_status"] == "active"
        assert created["override_fields_json"] == []  # decoded to list
        _assert_no_raw(created)

        assert repo.get(cid)["role_title"] == "Superintendent"
        assert len(repo.list("tropical")) == 1

        patched = repo.patch(cid, {"role_title": "Project Manager", "person_name": "Bob  Roe"})
        assert patched["role_title"] == "Project Manager"
        assert patched["person_name_normalized"] == "bob roe"

        validated = repo.set_validation(cid, status="invalid", errors=[{"code": "x"}])
        assert validated["validation_status"] == "invalid"
        assert validated["validation_errors_json"] == [{"code": "x"}]

        deactivated = repo.deactivate(cid)
        assert deactivated["active_status"] == "deactivated"
        assert deactivated["deactivated_utc"] is not None
        assert repo.list("tropical", active_only=True) == []
        assert len(repo.list("tropical", active_only=False)) == 1


def test_absence_crud() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _db(td)
        cfg = StaffingConfigRepository(db_path=db).create(_config_row())
        repo = AbsenceOverrideRepository(db_path=db)
        created = repo.create(
            {
                "project_key": "tropical",
                "staffing_config_id": cfg["staffing_config_id"],
                "start_date": "2026-08-01",
                "finish_date": "2026-08-05",
                "absence_hours": "40.00",
            }
        )
        aid = created["absence_override_id"]
        _assert_no_raw(created)
        assert len(repo.list("tropical")) == 1
        repo.patch(aid, {"absence_hours": "16.00"})
        assert repo.get(aid)["absence_hours"] == "16.00"
        repo.deactivate(aid)
        assert repo.list("tropical", active_only=True) == []


def test_template_versions_monotonic() -> None:
    with tempfile.TemporaryDirectory() as td:
        repo = StaffingTemplateRepository(db_path=_db(td))
        tpl = repo.create_template(template_key="super-fl", template_name="FL Superintendent")
        tid = tpl["template_id"]
        assert tpl["current_version_id"] is None
        v1 = repo.add_version(tid, cost_code="01-100", default_role_title="Super", default_lab_rate="2400")
        v2 = repo.add_version(tid, cost_code="01-100", default_lab_rate="2500")
        assert v1["version_number"] == 1
        assert v2["version_number"] == 2
        assert repo.get(tid)["current_version_id"] == v2["template_version_id"]
        assert len(repo.list_versions(tid)) == 2
        assert repo.get_current_version(tid)["default_lab_rate"] == "2500"
        _assert_no_raw(v1)
        repo.deactivate(tid)
        assert repo.list(active_only=True) == []


def test_cost_codes_crud() -> None:
    with tempfile.TemporaryDirectory() as td:
        repo = StaffingCostCodeRepository(db_path=_db(td))
        created = repo.create(
            {"project_key": "tropical", "cost_code": "01-900", "cost_code_description": "Staffing"}
        )
        assert created["source_scope"] == "project_staffing"
        _assert_no_raw(created)
        assert len(repo.list(project_key="tropical")) == 1
        repo.deactivate(created["staffing_cost_code_id"])
        assert repo.list(project_key="tropical", active_only=True) == []
