"""Read-only, redacted DTOs for DB-config-backed comprehensive generation (Run Center).

A DB-config-backed run generates the comprehensive forecast package CONSUMING the live config
snapshot (materialized + the CFR_CONFIG_ROOT bridge). The underlying workflow report is saturated
with filesystem paths (materialized root, output package, live DB path) and raw run stamps — all
dev-internals that must not reach the UI. These DTOs expose only a friendly label, an opaque run_id,
status, the snapshot's friendly NAME (never its id in visible text) + item count, the fidelity-gate
result, validation, and safety booleans. ``forecast_dto.find_redaction_leaks`` is the backstop scan.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from hb_assistant.construction.analytics.forecast_dto import friendly_datetime_from_stamp


@dataclass(frozen=True)
class DbConfigRunListItemDTO:
    run_id: str
    display_label: str
    status: str
    source: str = "live_config"  # distinguishes these runs from file-config runs in the UI
    kind: str = "comprehensive"  # which generator (comprehensive/model_controls/monthly/probability)
    generated_display: str | None = None

    def public(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DbConfigRunSummaryDTO:
    run_id: str
    display_label: str
    status: str  # generated | generated_validation_failed | failed
    source: str = "live_config"
    kind: str = "comprehensive"
    generated_display: str | None = None
    config_snapshot_consumed: bool = False
    snapshot_display: str | None = None  # friendly snapshot NAME (never the id in visible text)
    snapshot_item_count: int = 0
    fidelity_gate_passed: bool = False
    validation_passed: bool = False
    no_live_writes: bool = False
    live_db_unchanged: bool = False
    package_generated: bool = False
    message: str | None = None  # coded, redacted reason on failure

    def public(self) -> dict[str, Any]:
        return asdict(self)


_KIND_LABELS: dict[str, str] = {
    "comprehensive": "Comprehensive forecast from live config",
    "model_controls": "Model controls forecast from live config",
    "monthly": "Monthly forecast from live config",
    "probability": "Probabilistic forecast from live config",
}


def _kind(record: dict[str, Any]) -> str:
    return str(record.get("generator_kind") or "comprehensive")


def _label(record: dict[str, Any]) -> str:
    friendly = friendly_datetime_from_stamp(record.get("created_stamp"))
    base = _KIND_LABELS.get(_kind(record), _KIND_LABELS["comprehensive"])
    return f"{base} — {friendly}" if friendly else base


def db_config_run_record_to_summary(record: dict[str, Any]) -> DbConfigRunSummaryDTO:
    """Build a redacted summary from a stored run record (no paths/stamps/snapshot-id emitted)."""
    status = record.get("status") or "failed"
    return DbConfigRunSummaryDTO(
        run_id=str(record.get("run_id") or ""),
        display_label=_label(record),
        status=status,
        kind=_kind(record),
        generated_display=friendly_datetime_from_stamp(record.get("created_stamp")),
        config_snapshot_consumed=bool(record.get("config_snapshot_consumed")),
        snapshot_display=record.get("snapshot_display"),
        snapshot_item_count=int(record.get("snapshot_item_count") or 0),
        fidelity_gate_passed=bool(record.get("fidelity_gate_passed")),
        validation_passed=bool(record.get("validation_passed")),
        no_live_writes=bool(record.get("no_live_writes")),
        live_db_unchanged=bool(record.get("live_db_unchanged")),
        package_generated=bool(record.get("package_generated")),
        message=record.get("message"),
    )


def db_config_run_record_to_list_item(record: dict[str, Any]) -> DbConfigRunListItemDTO:
    return DbConfigRunListItemDTO(
        run_id=str(record.get("run_id") or ""),
        display_label=_label(record),
        status=record.get("status") or "failed",
        kind=_kind(record),
        generated_display=friendly_datetime_from_stamp(record.get("created_stamp")),
    )
