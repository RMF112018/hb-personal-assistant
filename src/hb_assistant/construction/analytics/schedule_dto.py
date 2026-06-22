"""Redacted DTOs for Schedule Intelligence API responses."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ScheduleImportPreviewDTO:
    import_id: str
    display_label: str
    source_type: str
    source_format: str
    source_filename: str
    file_sha256: str
    byte_count: int
    activity_count: int
    relationship_count: int
    wbs_count: int
    calendar_count: int
    code_count: int
    udf_count: int
    cost_loaded_status: str
    validation_findings: list[dict[str, str]]
    schedule_name: str | None
    data_date: str | None
    planned_start: str | None
    scheduled_finish: str | None
    requires_column_mapping: bool
    project_key: str | None = None
    project_display_name: str | None = None

    def public(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ScheduleVersionSummaryDTO:
    schedule_version_key: str
    project_key: str
    source_type: str
    source_format: str
    display_label: str
    data_date: str | None
    planned_start: str | None
    scheduled_finish: str | None
    activity_count: int
    relationship_count: int
    cost_loaded_status: str
    imported_at: str
    quality_finding_count: int
    quality_status: str = "not_evaluated"
    quality_score: str | None = None
    quality_grade: str | None = None
    quality_profile: str | None = None
    project_display_name: str | None = None
    completion_posture: str | None = None
    evaluated_at: str | None = None

    def public(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ScheduleActivityDTO:
    activity_id: str
    activity_name: str | None
    wbs_code: str | None
    start_date: str | None
    finish_date: str | None
    duration_original: str | None
    activity_status: str | None
    is_critical: bool | None
    total_float: str | None
    cost_code: str | None
    percent_complete: str | None

    def public(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ScheduleMappingRunDTO:
    mapping_run_id: str
    project_key: str
    schedule_version_key: str
    operator_objective: str
    mapping_status: str
    cost_loaded_status_at_start: str | None
    created_at: str
    approved_at: str | None
    distribution_label: str | None

    def public(self) -> dict[str, Any]:
        return asdict(self)


OPERATOR_OBJECTIVES = (
    "association_only",
    "simplified_duration_distribution",
    "true_cost_loading",
    "existing_cost_loaded_review",
)

DISTRIBUTION_LABELS = {
    "simplified_duration_distribution": "analytical_distribution",
    "true_cost_loading": "true_cost_loaded",
    "association_only": None,
    "existing_cost_loaded_review": "cost_loaded_review",
}