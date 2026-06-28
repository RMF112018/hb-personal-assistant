"""Read-only surfacing of the application-computed CPM chain (Phases 1-7).

PHASE 8 SCOPE — READ-ONLY. Assembles surfacing DTOs (run-chain summary, computed activity
results, longest path, diagnostics, and the DCMA critical-path integration evidence) from the
already-persisted ``schedule_cpm_*`` tables. It performs NO CPM computation and NO writes —
it only reads the latest runs via the repository and the Phase 7 read-only evaluator.

Computed views expose application-owned CPM fields only (explicit whitelist). Source-export /
imported critical/driving-path/float/early-late fields are NOT surfaced here; source-export
evidence remains on the existing Schedule Health surface, separate and unchanged.
"""

from __future__ import annotations

from typing import Any

from hb_assistant.store.schedule_cpm_repository import ScheduleCpmDiagnosticsRepository

# Run kinds in dependency order (graph diagnostics first).
_RUN_KINDS: tuple[str, ...] = (
    "graph_diagnostics",
    "forward_pass",
    "backward_pass",
    "float",
    "longest_path",
    "criticality",
)

# Latest-run precedence for the computed activity table (most complete first).
_ACTIVITY_RUN_PRECEDENCE: tuple[str, ...] = (
    "criticality",
    "float",
    "backward_pass",
    "forward_pass",
)

# Explicit app-owned-field whitelist for the computed activity view. Source-export fields
# (source_critical_flag, source_driving_path_flag, source/imported float, is_critical,
# imported early/late) are NOT in these tables and are never surfaced.
_ACTIVITY_WHITELIST: tuple[str, ...] = (
    "activity_id",
    "activity_name",
    "topological_index",
    "computed_early_start",
    "computed_early_finish",
    "computed_late_start",
    "computed_late_finish",
    "early_start_offset_days",
    "early_finish_offset_days",
    "late_start_offset_days",
    "late_finish_offset_days",
    "duration_value",
    "duration_unit",
    "duration_source",
    "predecessor_count",
    "successor_count",
    "forward_pass_status",
    "backward_pass_status",
    "computed_total_float",
    "computed_free_float",
    "computed_criticality_class",
    "computed_criticality_status",
    "computed_critical_flag",
    "computed_near_critical_flag",
    "longest_path_member_flag",
    "longest_path_sequence",
    "computed_criticality_notes_json",
)

_RUN_SUMMARY_FIELDS: tuple[str, ...] = (
    "cpm_run_id",
    "calculation_type",
    "cpm_recalculation_status",
    "analysis_scope",
    "source_run_id",
    "created_at",
    "node_count",
    "edge_count",
    "diagnostic_count",
    "computed_activity_count",
    "blocked_activity_count",
    "is_acyclic",
)


class ScheduleCpmReadService:
    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path
        self._cpm = ScheduleCpmDiagnosticsRepository(db_path=db_path)

    # ------------------------------------------------------------------ latest-run lookup

    def _latest_run(self, schedule_version_key: str, calculation_type: str) -> dict[str, Any] | None:
        for run in self._cpm.list_runs(schedule_version_key):
            if str(run.get("calculation_type")) == calculation_type:
                return run
        return None

    def _run_entry(self, run: dict[str, Any] | None) -> dict[str, Any]:
        if run is None:
            return {"available": False}
        entry: dict[str, Any] = {"available": True}
        for key in _RUN_SUMMARY_FIELDS:
            if key in run:
                entry[key] = run[key]
        return entry

    def _dcma_evidence(self, schedule_version_key: str) -> dict[str, Any]:
        # Lazy import: the Phase 7 evaluator is READ-ONLY (reads runs, never computes/writes).
        from hb_assistant.construction.analytics.schedule_cpm_service import (
            ScheduleCpmGraphService,
        )

        evaluation = ScheduleCpmGraphService(db_path=self._db_path).evaluate_dcma_critical_path(
            schedule_version_key
        )
        if evaluation is None:
            return {"available": False, "measurable": False}
        return {
            "available": True,
            "measurable": evaluation.measurable,
            "basis": evaluation.basis,
            "dependency_run_ids": evaluation.dependency_run_ids,
            "path_id": evaluation.path_id,
            "path_activity_count": evaluation.path_activity_count,
            "computed_critical_activity_count": evaluation.computed_critical_activity_count,
            "longest_path_critical_activity_count": (
                evaluation.longest_path_critical_activity_count
            ),
            "reason_codes": evaluation.reason_codes,
            "caveats": evaluation.caveats,
            "source_critical_flags_used": False,
        }

    # ------------------------------------------------------------------------- summary

    def cpm_summary(self, schedule_version_key: str) -> dict[str, Any]:
        runs = {kind: self._latest_run(schedule_version_key, kind) for kind in _RUN_KINDS}
        run_entries = {kind: self._run_entry(run) for kind, run in runs.items()}
        dcma = self._dcma_evidence(schedule_version_key)

        missing = [kind for kind, run in runs.items() if run is None]
        return {
            "schedule_version_key": schedule_version_key,
            "available": any(run is not None for run in runs.values()),
            "runs": run_entries,
            "dcma_critical_path": dcma,
            "missing_dependency_reasons": missing,
            "evidence_class": "application_computed_cpm",
            "source_export_evidence": "separate",
        }

    # ---------------------------------------------------------------------- activities

    def cpm_activities(
        self, schedule_version_key: str, *, limit: int | None = None, offset: int = 0
    ) -> dict[str, Any]:
        source_run = None
        for kind in _ACTIVITY_RUN_PRECEDENCE:
            source_run = self._latest_run(schedule_version_key, kind)
            if source_run is not None:
                break
        if source_run is None:
            return {
                "schedule_version_key": schedule_version_key,
                "available": False,
                "source_run": None,
                "activities": [],
                "total_count": 0,
                "limit": limit if limit is not None else 500,
                "offset": offset,
                "truncated": False,
                "reason": "no_computed_cpm_run",
            }

        rows = self._cpm.list_activity_results(source_run["cpm_run_id"])
        projected = [
            {k: row.get(k) for k in _ACTIVITY_WHITELIST if k in row} for row in rows
        ]
        total = len(projected)
        page_limit = limit if limit is not None else 500
        window = projected[offset : offset + page_limit]
        return {
            "schedule_version_key": schedule_version_key,
            "available": True,
            "source_run": {
                "cpm_run_id": source_run.get("cpm_run_id"),
                "calculation_type": source_run.get("calculation_type"),
                "cpm_recalculation_status": source_run.get("cpm_recalculation_status"),
            },
            "activities": window,
            "total_count": total,
            "limit": page_limit,
            "offset": offset,
            "truncated": offset + len(window) < total,
        }

    # --------------------------------------------------------------------- longest path

    def cpm_longest_path(self, schedule_version_key: str) -> dict[str, Any]:
        lp_run = self._latest_run(schedule_version_key, "longest_path")
        if lp_run is None:
            return {
                "schedule_version_key": schedule_version_key,
                "available": False,
                "reason": "no_longest_path_run",
                "path": None,
                "activities": [],
            }
        paths = self._cpm.list_paths(lp_run["cpm_run_id"])
        primary = next((p for p in paths if p.get("path_rank") == 1), paths[0] if paths else None)
        if primary is None:
            return {
                "schedule_version_key": schedule_version_key,
                "available": False,
                "reason": "no_longest_path_row",
                "path": None,
                "activities": [],
            }
        members = self._cpm.list_path_activities(primary["path_id"])
        return {
            "schedule_version_key": schedule_version_key,
            "available": True,
            "path": {
                k: primary.get(k)
                for k in (
                    "path_id", "path_type", "path_rank", "path_status", "path_basis",
                    "start_activity_id", "end_activity_id", "activity_count",
                    "relationship_count", "path_duration", "path_start_offset_days",
                    "path_finish_offset_days", "path_total_float", "path_notes_json",
                )
                if k in primary
            },
            "activities": members,
        }

    # ----------------------------------------------------------------------- diagnostics

    def cpm_diagnostics(self, schedule_version_key: str) -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        for kind in _RUN_KINDS:
            run = self._latest_run(schedule_version_key, kind)
            if run is None:
                continue
            for d in self._cpm.list_diagnostics(run["cpm_run_id"]):
                items.append(
                    {
                        "cpm_run_id": run.get("cpm_run_id"),
                        "calculation_type": run.get("calculation_type"),
                        "severity": d.get("severity"),
                        "diagnostic_type": d.get("diagnostic_type"),
                        "summary": d.get("summary"),
                        "activity_id": d.get("activity_id"),
                        "relationship_ref": d.get("relationship_ref"),
                    }
                )
        return {
            "schedule_version_key": schedule_version_key,
            "available": bool(items),
            "diagnostics": items,
            "total_count": len(items),
        }
