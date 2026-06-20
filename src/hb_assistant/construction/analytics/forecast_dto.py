"""Read-only, redacted DTOs for the forecast package browser (Implementation Phase 1).

These dataclasses are the boundary between on-disk forecast package internals and the
user-facing UI. Redaction here is *structural*, not cosmetic: each DTO exposes only
business-facing fields (a friendly ``display_label``, an opaque ``package_id``, cost
codes, costs, statuses) and deliberately OMITS filesystem paths, raw run stamps,
package directory names, CLI commands, and Python module names. Because those fields
do not exist on the DTOs, the raw values cannot reach the client.

``find_redaction_leaks`` is a defensive self-check used by tests to prove a serialized
payload contains none of the forbidden dev-internals.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

# --- friendly type labels (business-facing) ----------------------------------

TYPE_LABELS: dict[str, str] = {
    "comprehensive": "Comprehensive forecast",
    "accuracy": "Forecast accuracy",
    "accuracy_next": "Forecast accuracy (next-gen)",
    "intelligence": "Forecast intelligence",
    "monthly": "Monthly forecast",
    "probability": "Probability validation",
    "history_informed": "History-informed forecast",
    "cost_frequency": "Cost-frequency cadence",
    "controls": "Forecast controls",
    "model_controls": "Forecast model controls",
    "staffing_plan": "Staffing plan",
    "context": "Forecast context",
    "analysis": "Forecast analysis",
    "schedule_integrated": "Schedule-integrated forecast",
    "actuals_erp_crosscheck": "Actuals vs ERP cross-check",
    "mapping_workpaper": "Mapping discrepancy workpaper",
    "db_json_export": "Data export",
}

_MONTHS = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)


def friendly_datetime_from_stamp(stamp: str | None) -> str | None:
    """Convert a raw ``YYYYMMDD_HHMMSS`` package stamp to a friendly date label.

    The raw stamp itself is never emitted to the UI; only this friendly form is.
    """
    if not stamp:
        return None
    try:
        dt = datetime.strptime(stamp, "%Y%m%d_%H%M%S")
    except (ValueError, TypeError):
        return None
    hour = dt.hour % 12 or 12
    ampm = "AM" if dt.hour < 12 else "PM"
    return f"{_MONTHS[dt.month - 1]} {dt.day}, {dt.year} {hour}:{dt.minute:02d} {ampm}"


# --- DTOs ---------------------------------------------------------------------


@dataclass(frozen=True)
class ProjectDTO:
    project_key: str
    project_name: str | None = None
    job_reference: str | None = None

    def public(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PeriodDTO:
    period: str
    package_count: int = 0

    def public(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PackageDTO:
    package_id: str
    package_type: str
    display_label: str
    status: str  # validated | attention | invalid | unsupported
    project_key: str | None = None
    period: str | None = None
    job_reference: str | None = None
    generated_display: str | None = None
    validation_total: int = 0
    validation_passed: int = 0
    validation_failed: int = 0
    output_file_count: int = 0

    def public(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ValidationDTO:
    package_id: str
    status: str
    total_checks: int
    passed: int
    failed: int
    failed_checks: list[str] = field(default_factory=list)  # humanized check labels

    def public(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ManifestFileDTO:
    file_name: str  # basename only — never a path or directory name
    kind: str  # csv | jsonl | json | md | other
    row_count: int | None = None
    size_bytes: int | None = None

    def public(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ManifestDTO:
    package_id: str
    package_type: str
    display_label: str
    project_key: str | None
    period: str | None
    job_reference: str | None
    generated_display: str | None
    manifest_version: str | None
    output_file_count: int
    files: list[ManifestFileDTO] = field(default_factory=list)

    def public(self) -> dict[str, Any]:
        return {
            "package_id": self.package_id,
            "package_type": self.package_type,
            "display_label": self.display_label,
            "project_key": self.project_key,
            "period": self.period,
            "job_reference": self.job_reference,
            "generated_display": self.generated_display,
            "manifest_version": self.manifest_version,
            "output_file_count": self.output_file_count,
            "files": [f.public() for f in self.files],
        }


@dataclass(frozen=True)
class PackageSummaryDTO:
    package_id: str
    package_type: str
    display_label: str
    project_key: str | None
    period: str | None
    job_reference: str | None
    generated_display: str | None
    status: str
    headline: dict[str, Any] = field(default_factory=dict)

    def public(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ForecastRowDTO:
    cost_code: str | None = None
    budget_code_key: str | None = None
    recommended_final_cost: str | None = None
    cost_to_complete: str | None = None
    change_amount: str | None = None
    requires_human_acceptance: bool | None = None
    acceptance_status: str | None = None

    def public(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReviewItemDTO:
    cost_code: str | None = None
    budget_code_key: str | None = None
    review_priority: str | None = None
    review_reason: str | None = None
    acceptance_status: str | None = None

    def public(self) -> dict[str, Any]:
        return asdict(self)


# --- redaction self-check -----------------------------------------------------

# Patterns that indicate a dev-internal leaked into a user-facing payload.
_LEAK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("absolute_path", re.compile(r"/(?:Users|Library|home|var|private|tmp)/")),
    ("run_stamp", re.compile(r"\d{8}_\d{6}")),
    ("module_path", re.compile(r"construction_financial_review\.")),
    ("cli_command", re.compile(r"python3?\s+-m|--project\s")),
)


def find_redaction_leaks(payload: Any, _path: str = "$") -> list[str]:
    """Recursively scan a JSON-serializable payload for forbidden dev-internals.

    Returns a list of human-readable leak descriptions (empty == clean). Tests assert
    this is empty for every user-facing response.
    """
    leaks: list[str] = []
    if isinstance(payload, dict):
        for k, v in payload.items():
            leaks.extend(find_redaction_leaks(v, f"{_path}.{k}"))
    elif isinstance(payload, (list, tuple)):
        for i, v in enumerate(payload):
            leaks.extend(find_redaction_leaks(v, f"{_path}[{i}]"))
    elif isinstance(payload, str):
        for name, pat in _LEAK_PATTERNS:
            if pat.search(payload):
                leaks.append(f"{_path}: {name} -> {payload!r}")
    return leaks
