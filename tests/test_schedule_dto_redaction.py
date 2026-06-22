"""Schedule DTO redaction leak tests."""

from __future__ import annotations

from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks
from hb_assistant.construction.analytics.schedule_dto import (
    ScheduleActivityDTO,
    ScheduleImportPreviewDTO,
    ScheduleMappingRunDTO,
    ScheduleVersionSummaryDTO,
)


def test_schedule_dtos_have_no_redaction_leaks() -> None:
    payloads = [
        ScheduleImportPreviewDTO(
            import_id="abc",
            display_label="Test Schedule",
            source_type="xml",
            source_format="primavera_pmxml",
            source_filename="schedule.xml",
            file_sha256="a" * 64,
            byte_count=100,
            activity_count=2,
            relationship_count=1,
            wbs_count=1,
            calendar_count=1,
            code_count=0,
            udf_count=0,
            cost_loaded_status="not_cost_loaded",
            validation_findings=[],
            schedule_name="Test",
            data_date="2026-06-01",
            planned_start="2026-01-01",
            scheduled_finish="2026-12-31",
            requires_column_mapping=False,
        ).public(),
        ScheduleVersionSummaryDTO(
            schedule_version_key="tropical|S1|2026-06-01",
            project_key="tropical",
            source_type="xml",
            source_format="primavera_pmxml",
            display_label="schedule.xml",
            data_date="2026-06-01",
            planned_start=None,
            scheduled_finish=None,
            activity_count=2,
            relationship_count=1,
            cost_loaded_status="not_cost_loaded",
            imported_at="2026-06-22T00:00:00+00:00",
            quality_finding_count=0,
        ).public(),
        ScheduleActivityDTO(
            activity_id="A1",
            activity_name="Foundation",
            wbs_code="01.01",
            start_date="2026-01-01",
            finish_date="2026-01-31",
            duration_original="20",
            activity_status=None,
            is_critical=False,
            total_float=None,
            cost_code="15-16-110",
            percent_complete="50",
        ).public(),
        ScheduleMappingRunDTO(
            mapping_run_id="map-1",
            project_key="tropical",
            schedule_version_key="tropical|S1|d",
            operator_objective="association_only",
            mapping_status="in_review",
            cost_loaded_status_at_start="not_cost_loaded",
            created_at="2026-06-22T00:00:00+00:00",
            approved_at=None,
            distribution_label=None,
        ).public(),
    ]
    for p in payloads:
        assert find_redaction_leaks(p) == []