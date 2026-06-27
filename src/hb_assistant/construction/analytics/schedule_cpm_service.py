"""Service that runs CPM graph diagnostics for one committed schedule version.

PHASE 1 — GRAPH DIAGNOSTICS ONLY. Loads committed activities and relationships for a
``schedule_version_key``, builds the directed activity graph, and persists the structural
diagnostics + deterministic topological order. It does NOT compute CPM dates, float, or the
critical path, and it never reads source-export critical/float flags for logic. The
persisted run records ``cpm_recalculation_status='not_implemented'`` so the system clearly
reports CPM recalculation is not implemented beyond these diagnostics.
"""

from __future__ import annotations

import json
from typing import Any

from hb_assistant.store.connection import open_connection
from hb_assistant.store.schedule_activity_repository import ScheduleActivityRepository
from hb_assistant.store.schedule_cpm_repository import (
    ScheduleCpmDiagnosticsRepository,
    deterministic_cpm_run_id,
)

from .schedule_cpm_graph import GraphBuildResult, build_graph

_PAGE = 1000


class ScheduleCpmGraphService:
    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path
        self._activities = ScheduleActivityRepository(db_path=db_path)
        self._cpm = ScheduleCpmDiagnosticsRepository(db_path=db_path)

    def _load_all_activities(self, schedule_version_key: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0
        while True:
            page = self._activities.list_activities(
                schedule_version_key, limit=_PAGE, offset=offset
            )
            rows.extend(page)
            if len(page) < _PAGE:
                break
            offset += _PAGE
        return rows

    def _run_metadata(self, schedule_version_key: str) -> tuple[str, str]:
        """Return (project_key, import_id) for the version from committed rows.

        Reads directly so it does not depend on the paginated read-model projection.
        Falls back to parsing project_key from the version key when no rows exist.
        """
        with open_connection(self._db_path) as conn:
            for table in (
                "procore_ep_schedule_activities",
                "procore_ep_schedule_relationships",
            ):
                cur = conn.execute(
                    f"SELECT project_key, import_id FROM {table} "
                    "WHERE schedule_version_key=? LIMIT 1",
                    (schedule_version_key,),
                )
                row = cur.fetchone()
                if row is not None:
                    return str(row["project_key"]), str(row["import_id"])
        project_key = schedule_version_key.split("|", 1)[0]
        return project_key, ""

    def run_graph_diagnostics(self, schedule_version_key: str) -> dict[str, Any]:
        """Build + persist graph diagnostics for the version; return a public summary."""
        activities = self._load_all_activities(schedule_version_key)
        relationships = self._activities.list_relationships(schedule_version_key)
        result = build_graph(activities, relationships)

        project_key, import_id = self._run_metadata(schedule_version_key)

        signature = [
            "|".join(
                [
                    d.diagnostic_type,
                    d.severity,
                    d.activity_id or "",
                    d.relationship_ref or "",
                ]
            )
            for d in result.diagnostics
        ]
        run_id = deterministic_cpm_run_id(
            schedule_version_key=schedule_version_key,
            import_id=import_id,
            diagnostic_signature=signature,
        )

        topo_json = (
            json.dumps(result.topological_order)
            if result.topological_order is not None
            else None
        )
        run_row = {
            "cpm_run_id": run_id,
            "project_key": project_key,
            "schedule_version_key": schedule_version_key,
            "import_id": import_id,
            "node_count": result.node_count,
            "edge_count": result.edge_count,
            "is_acyclic": 1 if result.is_acyclic else 0,
            "diagnostic_count": len(result.diagnostics),
            "topological_order_json": topo_json,
            "analysis_scope": result.analysis_scope,
            "cpm_recalculation_status": result.cpm_recalculation_status,
        }

        diagnostic_rows: list[dict[str, Any]] = []
        for idx, d in enumerate(result.diagnostics):
            diagnostic_rows.append(
                {
                    "diagnostic_id": f"{run_id}_{idx:05d}",
                    "cpm_run_id": run_id,
                    "project_key": project_key,
                    "schedule_version_key": schedule_version_key,
                    "import_id": import_id,
                    "activity_id": d.activity_id,
                    "relationship_ref": d.relationship_ref,
                    "diagnostic_type": d.diagnostic_type,
                    "severity": d.severity,
                    "summary": d.summary,
                    "evidence_json": json.dumps(d.evidence) if d.evidence else None,
                }
            )

        self._cpm.replace_run_with_diagnostics(run_row, diagnostic_rows)

        return self._public_summary(run_id, result)

    @staticmethod
    def _public_summary(run_id: str, result: GraphBuildResult) -> dict[str, Any]:
        return {
            "cpm_run_id": run_id,
            "node_count": result.node_count,
            "edge_count": result.edge_count,
            "is_acyclic": result.is_acyclic,
            "diagnostic_count": len(result.diagnostics),
            "topological_order": result.topological_order,
            "analysis_scope": result.analysis_scope,
            "cpm_recalculation_status": result.cpm_recalculation_status,
            "diagnostics": result.diagnostics_as_dicts(),
        }
