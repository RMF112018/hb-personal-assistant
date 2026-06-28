"""Read-only aggregation of Application-computed CPM evidence for the Schedule Health surface.

PHASE 9A.1 SCOPE — READ-ONLY. Composes the already-persisted Phase 8 computed-CPM reads
(``ScheduleCpmReadService`` summary/longest-path/diagnostics + the run-row aggregates already
stored on ``schedule_cpm_runs`` + a single float-bucket aggregate query) into a compact
``computed_cpm_health`` envelope that the Schedule Health ``/health-data`` response carries as an
additive key. It performs NO CPM computation and NO writes.

Provenance: every value here is Application-computed CPM (``evidence_class``
``application_computed_cpm``). Source-export / imported critical/driving-path/float fields are NOT
surfaced — source-export evidence stays on its own Schedule Health keys, separate and unchanged.
The longest path is the computed longest path, never a "true"/forensic critical path; the
``computed_critical_outside_longest_path`` caveat from the DCMA evaluator is carried through, never
hidden.
"""

from __future__ import annotations

from collections import Counter
from typing import Any
from urllib.parse import quote

from hb_assistant.store.schedule_cpm_repository import ScheduleCpmDiagnosticsRepository

# DCMA high-total-float convention (total float > 44 working days). Product constant, NOT a
# derived value — surfaced alongside the bucket so consumers can see the threshold used.
HIGH_TOTAL_FLOAT_DAYS: float = 44.0

# Run kinds in dependency order (mirrors ScheduleCpmReadService).
_RUN_KINDS: tuple[str, ...] = (
    "graph_diagnostics",
    "forward_pass",
    "backward_pass",
    "float",
    "longest_path",
    "criticality",
)


class ScheduleHealthCpmService:
    """Composes existing read-only CPM services into the Schedule Health CPM envelope."""

    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path
        self._cpm = ScheduleCpmDiagnosticsRepository(db_path=db_path)

    # ------------------------------------------------------------------ public entrypoint

    def build_computed_cpm_health(self, schedule_version_key: str) -> dict[str, Any]:
        """Return the additive ``computed_cpm_health`` envelope for one schedule version.

        Fail-soft: when no computed CPM runs exist the envelope reports ``available: False`` with a
        reason so Schedule Health still loads on source-export evidence alone.
        """
        # Lazy import: the Phase 8 read service is READ-ONLY (reads runs, never computes/writes).
        from hb_assistant.construction.analytics.schedule_cpm_read_service import (
            ScheduleCpmReadService,
        )

        reader = ScheduleCpmReadService(db_path=self._db_path)
        summary = reader.cpm_summary(schedule_version_key)

        run_entries = summary.get("runs", {})
        run_chain = {
            kind: {
                "available": bool(entry.get("available")),
                "status": entry.get("cpm_recalculation_status"),
                "analysis_scope": entry.get("analysis_scope"),
            }
            for kind, entry in ((k, run_entries.get(k, {})) for k in _RUN_KINDS)
        }
        missing = summary.get("missing_dependency_reasons", [])

        if not summary.get("available"):
            return {
                "available": False,
                "reason": "no_computed_cpm",
                "evidence_class": "application_computed_cpm",
                "source_export_evidence": "separate",
                "run_chain": run_chain,
                "missing_dependency_reasons": missing,
                "links": {
                    "computed_cpm": f"/schedules/cpm?version={quote(schedule_version_key)}"
                },
            }

        return {
            "available": True,
            "evidence_class": "application_computed_cpm",
            "source_export_evidence": "separate",
            "run_chain": run_chain,
            "counts": self._counts(schedule_version_key),
            "longest_path_summary": self._longest_path_summary(reader, schedule_version_key),
            "dcma_critical_path_metric": self._dcma_metric(summary.get("dcma_critical_path", {})),
            "diagnostics_summary": self._diagnostics_summary(reader, schedule_version_key),
            "missing_dependency_reasons": missing,
            "links": {
                "computed_cpm": f"/schedules/cpm?version={quote(schedule_version_key)}"
            },
        }

    # ------------------------------------------------------------------------- counts

    def _counts(self, schedule_version_key: str) -> dict[str, Any]:
        """Activity-level aggregates, all pre-aggregated on the run row except float buckets.

        The criticality run carries the criticality classification aggregates and is also the
        source of the per-activity computed_total_float used for the float buckets; the float run
        is the fallback when criticality has not run.
        """
        criticality = self._cpm.get_criticality_run(schedule_version_key)
        activity_source = criticality or self._cpm.get_float_run(schedule_version_key)

        counts: dict[str, Any] = {
            "computed_activity_count": _opt_int(
                (activity_source or {}).get("computed_activity_count")
            ),
            "computed_critical_activity_count": _opt_int(
                (criticality or {}).get("computed_critical_activity_count")
            ),
            "computed_near_critical_activity_count": _opt_int(
                (criticality or {}).get("computed_near_critical_activity_count")
            ),
            "computed_noncritical_activity_count": _opt_int(
                (criticality or {}).get("computed_noncritical_activity_count")
            ),
            "longest_path_member_count": _opt_int(
                (criticality or {}).get("longest_path_member_count")
            ),
            "critical_float_threshold_days": _opt_float(
                (criticality or {}).get("critical_float_threshold_days")
            ),
            "near_critical_float_threshold_days": _opt_float(
                (criticality or {}).get("near_critical_float_threshold_days")
            ),
            "negative_total_float_count": None,
            "zero_total_float_count": None,
            "high_total_float_count": None,
            "classified_total_float_count": None,
            "high_total_float_threshold_days": HIGH_TOTAL_FLOAT_DAYS,
        }

        if activity_source and activity_source.get("cpm_run_id"):
            buckets = self._cpm.float_risk_counts(
                str(activity_source["cpm_run_id"]),
                high_total_float_days=HIGH_TOTAL_FLOAT_DAYS,
            )
            counts.update(buckets)
        return counts

    # ------------------------------------------------------------------ longest path

    @staticmethod
    def _longest_path_summary(reader: Any, schedule_version_key: str) -> dict[str, Any]:
        lp = reader.cpm_longest_path(schedule_version_key)
        if not lp.get("available") or not lp.get("path"):
            return {"available": False, "reason": lp.get("reason")}
        path = lp["path"]
        return {
            "available": True,
            "path_id": path.get("path_id"),
            "path_type": path.get("path_type"),
            "activity_count": _opt_int(path.get("activity_count")),
            "relationship_count": _opt_int(path.get("relationship_count")),
            "path_duration": _opt_float(path.get("path_duration")),
            "path_total_float": _opt_float(path.get("path_total_float")),
            "start_activity_id": path.get("start_activity_id"),
            "end_activity_id": path.get("end_activity_id"),
        }

    # ------------------------------------------------------------------ DCMA metric

    @staticmethod
    def _dcma_metric(dcma: dict[str, Any]) -> dict[str, Any]:
        """Curated mirror of cpm_summary().dcma_critical_path (application-computed basis)."""
        if not dcma.get("available"):
            return {"available": False, "measurable": False}
        return {
            "available": True,
            "measurable": bool(dcma.get("measurable")),
            "basis": dcma.get("basis"),
            "source_critical_flags_used": bool(dcma.get("source_critical_flags_used", False)),
            "reason_codes": dcma.get("reason_codes", []),
            "caveats": dcma.get("caveats", []),
            "path_id": dcma.get("path_id"),
            "path_activity_count": _opt_int(dcma.get("path_activity_count")),
            "computed_critical_activity_count": _opt_int(
                dcma.get("computed_critical_activity_count")
            ),
            "longest_path_critical_activity_count": _opt_int(
                dcma.get("longest_path_critical_activity_count")
            ),
            "dependency_run_ids": dcma.get("dependency_run_ids"),
        }

    # ------------------------------------------------------------------ diagnostics

    @staticmethod
    def _diagnostics_summary(reader: Any, schedule_version_key: str) -> dict[str, Any]:
        diag = reader.cpm_diagnostics(schedule_version_key)
        rows = diag.get("diagnostics", []) if diag.get("available") else []
        by_severity = Counter(str(r.get("severity")) for r in rows if r.get("severity"))
        by_calc = Counter(
            str(r.get("calculation_type")) for r in rows if r.get("calculation_type")
        )
        return {
            "available": bool(diag.get("available")),
            "total_count": _opt_int(diag.get("total_count")) or len(rows),
            "by_severity": dict(by_severity),
            "by_calculation_type": dict(by_calc),
        }


def _opt_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _opt_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
