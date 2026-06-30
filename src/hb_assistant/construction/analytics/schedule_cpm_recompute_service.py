"""Synchronous application-computed CPM recompute for committed schedule versions."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from hb_assistant.construction.analytics.schedule_cpm_read_service import ScheduleCpmReadService
from hb_assistant.construction.analytics.schedule_cpm_service import ScheduleCpmGraphService
from hb_assistant.store.connection import open_connection
from hb_assistant.store.schedule_cpm_import_observability_repository import (
    ScheduleCpmImportObservabilityRepository,
    count_canonical_inputs,
)

_logger = logging.getLogger(__name__)

_CHAIN_STEPS: tuple[tuple[str, str], ...] = (
    ("graph_diagnostics", "run_graph_diagnostics"),
    ("forward_pass", "run_forward_pass"),
    ("backward_pass", "run_backward_pass"),
    ("float", "run_float_calculation"),
    ("longest_path", "run_longest_path"),
    ("criticality", "run_criticality_classification"),
)


class ScheduleCpmRecomputeService:
    """Thin orchestration wrapper around the canonical six-step CPM chain."""

    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path
        self._cpm = ScheduleCpmGraphService(db_path=db_path)
        self._read = ScheduleCpmReadService(db_path=db_path)
        self._observability = ScheduleCpmImportObservabilityRepository(db_path=db_path)

    def recompute(
        self,
        schedule_version_key: str,
        *,
        import_id: str | None = None,
        package_id: str | None = None,
        trigger_source: str = "import_commit",
    ) -> dict[str, Any]:
        started = datetime.now(timezone.utc)
        with open_connection(self._db_path) as conn:
            canonical_activity_count, canonical_relationship_count = count_canonical_inputs(
                conn, schedule_version_key=schedule_version_key
            )

        failed_step: str | None = None
        failure_reason: str | None = None
        graph_node_count: int | None = None
        graph_edge_count: int | None = None
        diagnostics_count: int | None = None
        try:
            for step_name, method_name in _CHAIN_STEPS:
                failed_step = step_name
                getattr(self._cpm, method_name)(schedule_version_key)
        except Exception as exc:
            failure_reason = str(exc)[:500]
            _logger.exception(
                "CPM recompute failed at %s for %s",
                failed_step,
                schedule_version_key,
            )
            summary = self._read.cpm_summary(schedule_version_key)
            diag_run = (summary.get("runs") or {}).get("graph_diagnostics") or {}
            if diag_run.get("available"):
                graph_node_count = _optional_int(diag_run.get("node_count"))
                graph_edge_count = _optional_int(diag_run.get("edge_count"))
                diagnostics_count = _optional_int(diag_run.get("diagnostic_count"))
            envelope = self._envelope(
                schedule_version_key,
                status="failed",
                triggered=True,
                failure_reason=failure_reason,
                failed_step=failed_step,
                canonical_input_activity_count=canonical_activity_count,
                canonical_input_relationship_count=canonical_relationship_count,
                graph_node_count=graph_node_count,
                graph_edge_count=graph_edge_count,
                diagnostics_count=diagnostics_count,
            )
            return self._persist_observability(
                envelope,
                import_id=import_id,
                package_id=package_id,
                trigger_source=trigger_source,
                started=started,
                canonical_activity_count=canonical_activity_count,
                canonical_relationship_count=canonical_relationship_count,
                graph_node_count=graph_node_count,
                graph_edge_count=graph_edge_count,
                failed_step=failed_step,
                failure_reason=failure_reason,
            )

        summary = self._read.cpm_summary(schedule_version_key)
        runs = summary.get("runs") or {}
        critical_run = runs.get("criticality") or {}
        diag_run = runs.get("graph_diagnostics") or {}
        lp_run = runs.get("longest_path") or {}
        dcma = summary.get("dcma_critical_path") or {}

        graph_node_count = _optional_int(diag_run.get("node_count")) if diag_run.get("available") else None
        graph_edge_count = _optional_int(diag_run.get("edge_count")) if diag_run.get("available") else None
        diagnostics_count = (
            _optional_int(diag_run.get("diagnostic_count")) if diag_run.get("available") else None
        )

        activities = self._read.cpm_activities(schedule_version_key, limit=10000)
        activity_rows = activities.get("activities") or []
        near_critical = sum(1 for row in activity_rows if row.get("computed_near_critical_flag"))
        critical_count = sum(1 for row in activity_rows if row.get("computed_critical_flag"))
        if not critical_count:
            critical_count = int(dcma.get("computed_critical_activity_count") or 0)

        complete = all((runs.get(kind) or {}).get("available") for kind, _ in _CHAIN_STEPS)
        envelope = self._envelope(
            schedule_version_key,
            status="complete" if complete else "partial",
            triggered=True,
            cpm_run_id=critical_run.get("cpm_run_id") if critical_run.get("available") else None,
            computed_activity_count=int(
                critical_run.get("computed_activity_count") or activities.get("total_count") or 0
            ),
            computed_critical_activity_count=critical_count,
            computed_near_critical_activity_count=near_critical,
            longest_path_available=bool(lp_run.get("available")),
            diagnostics_count=diagnostics_count,
            canonical_input_activity_count=canonical_activity_count,
            canonical_input_relationship_count=canonical_relationship_count,
            graph_node_count=graph_node_count,
            graph_edge_count=graph_edge_count,
        )
        return self._persist_observability(
            envelope,
            import_id=import_id,
            package_id=package_id,
            trigger_source=trigger_source,
            started=started,
            canonical_activity_count=canonical_activity_count,
            canonical_relationship_count=canonical_relationship_count,
            graph_node_count=graph_node_count,
            graph_edge_count=graph_edge_count,
            failed_step=None,
            failure_reason=None,
        )

    def _persist_observability(
        self,
        envelope: dict[str, Any],
        *,
        import_id: str | None,
        package_id: str | None,
        trigger_source: str,
        started: datetime,
        canonical_activity_count: int,
        canonical_relationship_count: int,
        graph_node_count: int | None,
        graph_edge_count: int | None,
        failed_step: str | None,
        failure_reason: str | None,
    ) -> dict[str, Any]:
        if not import_id:
            return envelope

        finished = datetime.now(timezone.utc)
        duration_ms = max(0, int((finished - started).total_seconds() * 1000))
        status = str(envelope.get("cpm_recompute_status") or "unavailable")
        failure_code = "cpm_chain_failed" if status == "failed" else None
        diagnostics = {
            key: envelope[key]
            for key in (
                "computed_activity_count",
                "computed_critical_activity_count",
                "computed_near_critical_activity_count",
                "longest_path_available",
                "diagnostics_count",
            )
            if envelope.get(key) is not None
        }
        row = self._observability.upsert(
            import_id=import_id,
            schedule_version_key=str(envelope.get("schedule_version_key") or ""),
            package_id=package_id,
            trigger_source=trigger_source,
            canonical_input_activity_count=canonical_activity_count,
            canonical_input_relationship_count=canonical_relationship_count,
            graph_node_count=graph_node_count,
            graph_edge_count=graph_edge_count,
            status=status,
            started_at=started.isoformat(),
            finished_at=finished.isoformat(),
            duration_ms=duration_ms,
            error_count=1 if status == "failed" else 0,
            failure_code=failure_code,
            failure_message=failure_reason,
            failed_step=failed_step,
            cpm_run_id=envelope.get("cpm_run_id"),
            diagnostics=diagnostics,
        )
        out = dict(envelope)
        out["cpm_observability"] = _public_observability_fields(row)
        out["duration_ms"] = duration_ms
        return out

    @staticmethod
    def _envelope(schedule_version_key: str, *, status: str, triggered: bool, **extra: Any) -> dict[str, Any]:
        out: dict[str, Any] = {
            "schedule_version_key": schedule_version_key,
            "cpm_recompute_triggered": triggered,
            "cpm_recompute_status": status,
        }
        for key, value in extra.items():
            if value is not None:
                out[key] = value
        return out


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _public_observability_fields(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "import_id": row.get("import_id"),
        "package_id": row.get("package_id"),
        "schedule_version_key": row.get("schedule_version_key"),
        "trigger_source": row.get("trigger_source"),
        "canonical_input_activity_count": row.get("canonical_input_activity_count"),
        "canonical_input_relationship_count": row.get("canonical_input_relationship_count"),
        "graph_node_count": row.get("graph_node_count"),
        "graph_edge_count": row.get("graph_edge_count"),
        "status": row.get("status"),
        "started_at": row.get("started_at"),
        "finished_at": row.get("finished_at"),
        "duration_ms": row.get("duration_ms"),
        "failure_code": row.get("failure_code"),
        "failure_message": row.get("failure_message"),
        "failed_step": row.get("failed_step"),
        "cpm_run_id": row.get("cpm_run_id"),
        "diagnostics": row.get("diagnostics") or {},
    }
