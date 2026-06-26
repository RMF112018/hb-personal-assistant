"""Shared schedule file parsing types and format detection."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


class ScheduleImportError(RuntimeError):
    """Raised when schedule import is misconfigured or input is invalid."""

    def __init__(
        self,
        code: str,
        *,
        message: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.payload = payload or {}
        super().__init__(message or code)


@dataclass
class ParsedScheduleBundle:
    schedule_id: str
    schedule_name: str | None = None
    data_date: str | None = None
    planned_start: str | None = None
    scheduled_finish: str | None = None
    procore_project_id: str | None = None
    source_project_id: str | None = None
    source_project_name: str | None = None
    source_project_short_name: str | None = None
    source_project_metadata_json: str | None = None
    activities: list[dict[str, Any]] = field(default_factory=list)
    relationships: list[dict[str, Any]] = field(default_factory=list)
    wbs_nodes: list[dict[str, Any]] = field(default_factory=list)
    calendars: list[dict[str, Any]] = field(default_factory=list)
    code_assignments: list[dict[str, Any]] = field(default_factory=list)
    udf_values: list[dict[str, Any]] = field(default_factory=list)
    validation_findings: list[dict[str, str]] = field(default_factory=list)
    cost_loaded_hints: list[dict[str, Any]] = field(default_factory=list)
    schedule_options: dict[str, Any] = field(default_factory=dict)
    source_capabilities: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedScheduleFile:
    source_file_id: str
    filename: str
    source_type: str
    source_format: str
    source_vendor: str | None = None
    file_role: str = "unknown"
    byte_size: int = 0
    sha256: str | None = None
    parse_status: str = "parsed"
    parser_name: str | None = None
    parser_version: str | None = None
    parser_coverage: dict[str, Any] = field(default_factory=dict)
    detected_project_count: int = 0
    detected_activity_count: int = 0
    detected_relationship_count: int = 0
    detected_baseline_project_count: int = 0
    warnings: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ParsedScheduleEntity:
    role: str
    source_format: str
    source_file_id: str | None = None
    project_object_id: str | None = None
    project_id: str | None = None
    project_name: str | None = None
    original_project_object_id: str | None = None
    baseline_type_name: str | None = None
    baseline_type_object_id: str | None = None
    data_date: str | None = None
    planned_start: str | None = None
    scheduled_finish: str | None = None
    activities: list[dict[str, Any]] = field(default_factory=list)
    relationships: list[dict[str, Any]] = field(default_factory=list)
    wbs_nodes: list[dict[str, Any]] = field(default_factory=list)
    calendars: list[dict[str, Any]] = field(default_factory=list)
    code_assignments: list[dict[str, Any]] = field(default_factory=list)
    udf_values: list[dict[str, Any]] = field(default_factory=list)
    source_options: dict[str, Any] = field(default_factory=dict)
    source_capabilities: dict[str, Any] = field(default_factory=dict)
    parser_coverage: dict[str, Any] = field(default_factory=dict)
    warnings: list[dict[str, Any]] = field(default_factory=list)

    def to_bundle(self) -> ParsedScheduleBundle:
        return ParsedScheduleBundle(
            schedule_id=self.project_id or self.project_object_id or "imported-schedule",
            schedule_name=self.project_name,
            data_date=self.data_date,
            planned_start=self.planned_start,
            scheduled_finish=self.scheduled_finish,
            procore_project_id=self.project_object_id,
            source_project_id=self.project_id,
            source_project_name=self.project_name,
            source_project_short_name=self.project_id,
            source_project_metadata_json=None,
            activities=list(self.activities),
            relationships=list(self.relationships),
            wbs_nodes=list(self.wbs_nodes),
            calendars=list(self.calendars),
            code_assignments=list(self.code_assignments),
            udf_values=list(self.udf_values),
            validation_findings=[
                {"code": str(w.get("code") or "parser_warning"), "message": str(w.get("message") or w)}
                for w in self.warnings
            ],
            schedule_options=dict(self.source_options),
            source_capabilities=dict(self.source_capabilities),
        )


@dataclass
class ParsedSchedulePackage:
    package_id: str
    package_mode: str
    files: list[ParsedScheduleFile] = field(default_factory=list)
    schedule_entities: list[ParsedScheduleEntity] = field(default_factory=list)
    selected_current_entity: ParsedScheduleEntity | None = None
    baseline_entities: list[ParsedScheduleEntity] = field(default_factory=list)
    package_capabilities: dict[str, Any] = field(default_factory=dict)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    manifest: dict[str, Any] = field(default_factory=dict)


def safe_basename(filename: str) -> str:
    base = os.path.basename(str(filename or "").strip()) or "upload"
    return base.replace("/", "_").replace("\\", "_").replace("..", "_")


def sniff_xml_source_format(data: bytes) -> str:
    """Detect P6 APIBusinessObjects vs Microsoft Project 2007 XML from content."""
    head = data[:8192].decode("utf-8", errors="ignore").lower()
    if "schemas.microsoft.com/project" in head:
        return "ms_project_xml"
    if "apibusinessobjects" in head or "xmlns=\"http://xmlns.oracle.com/primavera/p6" in head:
        return "primavera_pmxml"
    # Default XML uploads to P6 parser; invalid/unknown XML fails at parse time.
    return "primavera_pmxml"


def detect_source(filename: str, data: bytes | None = None) -> tuple[str, str]:
    lower = safe_basename(filename).lower()
    if lower.endswith(".xml") or lower.endswith(".pmxml"):
        if data:
            return "xml", sniff_xml_source_format(data)
        return "xml", "primavera_pmxml"
    if lower.endswith(".xer"):
        return "xer", "primavera_xer"
    if lower.endswith(".csv"):
        return "csv", "csv"
    raise ScheduleImportError(
        "unsupported_schedule_format",
        message="unsupported schedule file type (expected .xml, .xer, or .csv)",
    )
