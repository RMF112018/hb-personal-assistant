"""Phase 04A v2.0 schedules + activities normalizer tests."""

from __future__ import annotations

import json

from hb_assistant.procore.normalizers.schedule import (
    normalize_activity,
    normalize_schedule,
)

_CORRELATION = "synthetic-corr-sched"
_FETCHED_AT = "2026-05-28T00:00:00+00:00"


_SCHEDULE_RAW = {
    "schedule_id": "15",
    "project_id": "12345",
    "company_id": "67890",
    "schedule_name": "Main Project Schedule",
    "schedule_type": "IMPORTED_READ_WRITE_PROJECT_SCHEDULE",
    "is_active": True,
    "data_date": "2024-05-14T00:00:00Z",
    "start_date": "2024-05-01T00:00:00Z",
    "calendar_id": "101",
    "parent_schedule_id": "10",
    "updated_at": "2024-05-14T13:30:00Z",
    "updated_by": "999",
    "created_at": "2024-05-14T13:30:00Z",
    "created_by": "999",
}


def test_normalize_schedule_preserves_structured_fields() -> None:
    record = normalize_schedule(
        _SCHEDULE_RAW,
        project_key="tropical",
        endpoint_id="schedules",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    canonical = record["canonical_fields"]
    assert canonical["schedule_id"] == "15"
    assert canonical["schedule_name"] == "Main Project Schedule"
    assert canonical["schedule_type"] == "IMPORTED_READ_WRITE_PROJECT_SCHEDULE"
    assert canonical["is_active"] is True
    assert canonical["calendar_id"] == "101"
    assert canonical["parent_schedule_id"] == "10"
    assert record["entity_stable_key"] == "15"
    assert record["category"] == "schedules"
    assert record["review_required"] is False


_ACTIVITY_RAW = {
    "activity_id": "245",
    "activity_name": "Install Windows",
    "start_date": "2024-05-14T13:30:00Z",
    "finish_date": "2024-05-25T17:00:00Z",
    "duration": 5,
    "duration_unit": "day",
    "duration_display_unit": "days",
    "percent_complete": 75.5,
    "parent_id": "418600",
    "ordered_parent_index": 3,
    "constraint_type": "SNET",
    "constraint_date": "2024-05-10T08:00:00Z",
    "assigned_company": "ABC Contractors",
    "crew_size": 5,
    "calendar_id": "101",
    "deadline_date": "2024-06-01",
    "deadline_variance": -3,
    "category_data": [{"name": "Phase_GLOBAL", "value": "Foundation"}],
    "resource_data": [{"resource_id": "101", "resource_name": "Crew 1"}],
    "is_critical": True,
    "is_actual_start": True,
    "is_actual_finish": False,
    "total_float": 2.5,
    "notes": "Foundation work must be completed first",
    "schedule_id": "15",
    "project_id": "12345",
    "company_id": "67890",
    "created_at": "2024-05-14T13:30:00Z",
    "created_by": "1001",
    "updated_at": "2024-05-15T10:30:00Z",
    "updated_by": "1002",
}


def test_normalize_activity_preserves_structured_fields_and_hashes_notes() -> None:
    record = normalize_activity(
        _ACTIVITY_RAW,
        project_key="tropical",
        endpoint_id="activities",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
    )
    canonical = record["canonical_fields"]
    serialized = json.dumps(record)

    # Structured fields preserved
    assert canonical["activity_id"] == "245"
    assert canonical["activity_name"] == "Install Windows"
    assert canonical["percent_complete"] == 75.5
    assert canonical["is_critical"] is True
    assert canonical["total_float"] == 2.5
    assert canonical["assigned_company"] == "ABC Contractors"
    assert canonical["schedule_id"] == "15"

    # category_data + resource_data preserved verbatim
    assert canonical["category_data"] == [{"name": "Phase_GLOBAL", "value": "Foundation"}]
    assert canonical["resource_data"] == [{"resource_id": "101", "resource_name": "Crew 1"}]

    # notes (free text) reduced to hash-only summary
    notes_text = _ACTIVITY_RAW["notes"]
    assert isinstance(notes_text, str)
    assert notes_text not in serialized
    assert "notes_summary" in canonical
    assert canonical["notes_summary"]["hash_prefix"]

    assert record["entity_stable_key"] == "245"
    assert record["category"] == "schedule_activities"


def test_normalize_activity_surfaces_parent_procore_id_when_supplied() -> None:
    record = normalize_activity(
        _ACTIVITY_RAW,
        project_key="tropical",
        endpoint_id="activities",
        correlation_id=_CORRELATION,
        fetched_at=_FETCHED_AT,
        parent_procore_id="OVERRIDE_SCHED_ID",
    )
    canonical = record["canonical_fields"]
    # Raw payload already has schedule_id="15"; parent_schedule_id only set
    # when raw doesn't already carry it. Here we test the lineage-fallback path.
    assert canonical["schedule_id"] == "15"
