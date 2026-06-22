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
    activities: list[dict[str, Any]] = field(default_factory=list)
    relationships: list[dict[str, Any]] = field(default_factory=list)
    wbs_nodes: list[dict[str, Any]] = field(default_factory=list)
    calendars: list[dict[str, Any]] = field(default_factory=list)
    code_assignments: list[dict[str, Any]] = field(default_factory=list)
    udf_values: list[dict[str, Any]] = field(default_factory=list)
    validation_findings: list[dict[str, str]] = field(default_factory=list)
    cost_loaded_hints: list[dict[str, Any]] = field(default_factory=list)
    schedule_options: dict[str, Any] = field(default_factory=dict)


def safe_basename(filename: str) -> str:
    base = os.path.basename(str(filename or "").strip()) or "upload"
    return base.replace("/", "_").replace("\\", "_").replace("..", "_")


def detect_source(filename: str) -> tuple[str, str]:
    lower = safe_basename(filename).lower()
    if lower.endswith(".xml") or lower.endswith(".pmxml"):
        return "xml", "primavera_pmxml"
    if lower.endswith(".xer"):
        return "xer", "primavera_xer"
    if lower.endswith(".csv"):
        return "csv", "csv"
    raise ScheduleImportError(
        "unsupported_schedule_format",
        message="unsupported schedule file type (expected .xml, .xer, or .csv)",
    )