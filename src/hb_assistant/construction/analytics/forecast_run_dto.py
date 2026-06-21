"""Read-only, redacted DTOs for the Forecast Run Center (Implementation Phase 3).

A forecast run generates a deterministic context->analysis package chain into an isolated
work-root. The underlying workflow report carries filesystem paths (data_root, work_root,
package paths) and raw run stamps — these are dev-internals and must not reach the UI. These
DTOs expose only a friendly run label, an opaque run_id, status, validation counts, and a
derived "no live writes" safety flag. ``forecast_dto.find_redaction_leaks`` is the backstop scan.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from hb_assistant.construction.analytics.forecast_dto import friendly_datetime_from_stamp

PACKAGE_TYPE_LABELS: dict[str, str] = {
    "context": "Context",
    "analysis": "Analysis",
}


@dataclass(frozen=True)
class RunListItemDTO:
    run_id: str
    display_label: str
    status: str  # succeeded | failed
    generated_display: str | None = None

    def public(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RunSummaryDTO:
    run_id: str
    display_label: str
    status: str  # succeeded | failed
    generated_display: str | None = None
    packages: list[str] = field(default_factory=list)  # friendly type labels, e.g. ["Context", "Analysis"]
    checks_total: int = 0
    checks_passed: int = 0
    validation_passed: bool = False
    no_live_writes: bool = False  # derived: file mode + work-root outside live root
    message: str | None = None  # generic, redacted reason on failure

    def public(self) -> dict[str, Any]:
        return asdict(self)


def run_record_to_summary(record: dict[str, Any]) -> RunSummaryDTO:
    """Build a redacted RunSummaryDTO from a stored run record (no paths/stamps emitted)."""
    checks = record.get("checks") if isinstance(record.get("checks"), dict) else {}
    checks_total = len(checks)
    checks_passed = sum(1 for v in checks.values() if v is True)
    pkgs = record.get("packages") if isinstance(record.get("packages"), list) else []
    labels = [PACKAGE_TYPE_LABELS.get(p, str(p).capitalize()) for p in pkgs]
    status = record.get("status") or "failed"
    return RunSummaryDTO(
        run_id=str(record.get("run_id") or ""),
        display_label=_run_label(record),
        status=status,
        generated_display=friendly_datetime_from_stamp(record.get("created_stamp")),
        packages=labels,
        checks_total=checks_total,
        checks_passed=checks_passed,
        validation_passed=status == "succeeded" and checks_total > 0 and checks_passed == checks_total,
        no_live_writes=bool(record.get("no_live_writes")),
        message=record.get("message"),
    )


def run_record_to_list_item(record: dict[str, Any]) -> RunListItemDTO:
    return RunListItemDTO(
        run_id=str(record.get("run_id") or ""),
        display_label=_run_label(record),
        status=record.get("status") or "failed",
        generated_display=friendly_datetime_from_stamp(record.get("created_stamp")),
    )


def _run_label(record: dict[str, Any]) -> str:
    friendly = friendly_datetime_from_stamp(record.get("created_stamp"))
    base = "Context → analysis forecast"
    return f"{base} — {friendly}" if friendly else base
