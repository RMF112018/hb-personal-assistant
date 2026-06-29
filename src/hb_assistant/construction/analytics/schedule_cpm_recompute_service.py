"""Synchronous application-computed CPM recompute for committed schedule versions."""

from __future__ import annotations

import logging
from typing import Any

from hb_assistant.construction.analytics.schedule_cpm_read_service import ScheduleCpmReadService
from hb_assistant.construction.analytics.schedule_cpm_service import ScheduleCpmGraphService

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

    def recompute(self, schedule_version_key: str) -> dict[str, Any]:
        failed_step: str | None = None
        failure_reason: str | None = None
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
            return self._envelope(
                schedule_version_key,
                status="failed",
                triggered=True,
                failure_reason=failure_reason,
                failed_step=failed_step,
            )

        summary = self._read.cpm_summary(schedule_version_key)
        runs = summary.get("runs") or {}
        critical_run = runs.get("criticality") or {}
        diag_run = runs.get("graph_diagnostics") or {}
        lp_run = runs.get("longest_path") or {}
        dcma = summary.get("dcma_critical_path") or {}

        activities = self._read.cpm_activities(schedule_version_key, limit=10000)
        activity_rows = activities.get("activities") or []
        near_critical = sum(1 for row in activity_rows if row.get("computed_near_critical_flag"))
        critical_count = sum(1 for row in activity_rows if row.get("computed_critical_flag"))
        if not critical_count:
            critical_count = int(dcma.get("computed_critical_activity_count") or 0)

        complete = all((runs.get(kind) or {}).get("available") for kind, _ in _CHAIN_STEPS)
        return self._envelope(
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
            diagnostics_count=int(diag_run.get("diagnostic_count") or 0)
            if diag_run.get("available")
            else None,
        )

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