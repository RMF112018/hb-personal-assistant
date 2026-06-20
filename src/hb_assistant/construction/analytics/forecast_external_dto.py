"""Read-only, redacted DTOs for External-Forecast Evaluation (Implementation Phase 4).

The evaluation pipeline handles an untrusted uploaded file plus on-disk backend packages, so its
records carry filesystem paths, raw run stamps, and package directory names. These DTOs are the
structural boundary: they expose only business-facing fields (friendly labels, opaque
``import_id``/``eval_id``, cost codes, costs, metric values, severities) and OMIT every
dev-internal. ``forecast_dto.find_redaction_leaks`` is the backstop scan asserted by tests.

A file SHA-256 *is* surfaced (it is an integrity fingerprint, not a dev-internal) but the source
absolute path never is — only the basename of the uploaded file.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from hb_assistant.construction.analytics.forecast_dto import (
    find_redaction_leaks,
    friendly_datetime_from_stamp,
)

__all__ = [
    "ImportPreviewDTO",
    "MappingRowDTO",
    "MappingProposalDTO",
    "ComparisonRowDTO",
    "AccuracyRowDTO",
    "AnomalyFindingDTO",
    "ReviewItemDTO",
    "EvaluationSummaryDTO",
    "EvaluationListItemDTO",
    "find_redaction_leaks",
]

BASELINE_LABELS: dict[str, str] = {
    "actuals": "Actuals to date",
    "current_budget": "Current budget",
    "erp_jtd": "ERP job-to-date",
    "model_eac": "Backend model forecast",
    "model_p50": "Backend model P50",
    "model_p80": "Backend model P80",
    "prior_external": "Prior external forecast",
}


@dataclass(frozen=True)
class ImportPreviewDTO:
    import_id: str
    display_label: str
    source_system: str
    period: str | None
    source_filename: str  # basename only
    file_sha256: str
    byte_count: int
    sheet_names: list[str] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    sample_rows: list[dict[str, Any]] = field(default_factory=list)
    row_count: int = 0

    def public(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MappingRowDTO:
    raw_label: str
    canonical_budget_code_key: str | None = None
    canonical_month: str | None = None
    mapping_confidence: str | None = None
    mapping_status: str = "unmapped"  # mapped | unmapped | ambiguous

    def public(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MappingProposalDTO:
    import_id: str
    mapped_count: int
    unmapped_count: int
    rows: list[MappingRowDTO] = field(default_factory=list)

    def public(self) -> dict[str, Any]:
        return {
            "import_id": self.import_id,
            "mapped_count": self.mapped_count,
            "unmapped_count": self.unmapped_count,
            "rows": [r.public() for r in self.rows],
        }


@dataclass(frozen=True)
class ComparisonRowDTO:
    budget_code_key: str
    baseline: str
    baseline_label: str
    external_value: str | None
    baseline_value: str | None
    gap_absolute: str | None
    gap_percent: str | None

    def public(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AccuracyRowDTO:
    baseline: str
    baseline_label: str
    metric: str
    metric_value: str
    sample_n: int

    def public(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AnomalyFindingDTO:
    flag_code: str
    severity: str  # critical | high | medium | low | informational
    budget_code_key: str | None
    message: str  # humanized, path-free

    def public(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReviewItemDTO:
    reason_code: str
    severity: str
    budget_code_key: str | None
    detail: str
    status: str = "open"

    def public(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvaluationListItemDTO:
    eval_id: str
    display_label: str
    status: str  # succeeded | failed
    generated_display: str | None = None

    def public(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvaluationSummaryDTO:
    eval_id: str
    display_label: str
    status: str
    source_system: str | None = None
    period: str | None = None
    generated_display: str | None = None
    mapped_count: int = 0
    unmapped_count: int = 0
    baselines_compared: list[str] = field(default_factory=list)
    accuracy: list[AccuracyRowDTO] = field(default_factory=list)
    comparison: list[ComparisonRowDTO] = field(default_factory=list)
    anomalies: list[AnomalyFindingDTO] = field(default_factory=list)
    review_items: list[ReviewItemDTO] = field(default_factory=list)
    message: str | None = None  # generic, redacted failure reason

    def public(self) -> dict[str, Any]:
        return {
            "eval_id": self.eval_id,
            "display_label": self.display_label,
            "status": self.status,
            "source_system": self.source_system,
            "period": self.period,
            "generated_display": self.generated_display,
            "mapped_count": self.mapped_count,
            "unmapped_count": self.unmapped_count,
            "baselines_compared": list(self.baselines_compared),
            "accuracy": [a.public() for a in self.accuracy],
            "comparison": [c.public() for c in self.comparison],
            "anomalies": [a.public() for a in self.anomalies],
            "review_items": [r.public() for r in self.review_items],
            "message": self.message,
        }


def eval_label(source_system: str | None, period: str | None, stamp: str | None) -> str:
    """Friendly evaluation label, e.g. 'External forecast (Excel) — Jun 2026 — Jun 20, 2026 …'."""
    parts = ["External forecast"]
    if source_system:
        parts[0] = f"External forecast ({source_system.capitalize()})"
    if period:
        parts.append(period)
    friendly = friendly_datetime_from_stamp(stamp)
    if friendly:
        parts.append(friendly)
    return " — ".join(parts)
