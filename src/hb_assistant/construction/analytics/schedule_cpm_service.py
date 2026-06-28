"""Service for CPM analysis over one committed schedule version.

``run_graph_diagnostics`` (Phase 1) builds the directed activity graph and persists the
structural diagnostics + deterministic topological order (``cpm_recalculation_status=
'not_implemented'``).

``run_forward_pass`` (Phase 2) reuses that graph to compute application-owned early start /
early finish dates over an acyclic graph, persisting them to the V84 result tables with
``cpm_recalculation_status='forward_pass_only'``.

``run_backward_pass`` (Phase 3) reuses that graph plus the persisted forward-pass results to
compute application-owned late start / late finish dates over the reverse topological order,
persisting them to its own run with ``cpm_recalculation_status='backward_pass_only'``. None
of these paths computes float or critical/longest path, reads source-export critical/float
flags for logic, or overwrites any source schedule field.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from hb_assistant.store.connection import open_connection
from hb_assistant.store.schedule_activity_repository import ScheduleActivityRepository
from hb_assistant.store.schedule_cpm_repository import (
    ScheduleCpmDiagnosticsRepository,
    deterministic_cpm_run_id,
)
from hb_assistant.store.schedule_identity_repository import parse_schedule_version_data_date

from .schedule_cpm_backward_pass import (
    BLOCK_MISSING_FORWARD_PASS,
    BackwardPassResult,
    compute_backward_pass,
    resolve_finish_anchor,
)
from .schedule_cpm_forward_pass import (
    RUN_BLOCKED,
    ForwardPassResult,
    compute_forward_pass,
)
from .schedule_cpm_graph import GraphBuildResult, build_graph

_PAGE = 1000


def _parse_iso_date(value: Any) -> datetime | None:
    """Best-effort parse of an ISO date / datetime string (e.g. "2026-02-01 08:00")."""
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    for candidate in (raw, raw[:19], raw[:10]):
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            continue
    return None


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

        diagnostic_rows = self._build_diagnostic_rows(
            run_id,
            result,
            project_key=project_key,
            schedule_version_key=schedule_version_key,
            import_id=import_id,
        )

        self._cpm.replace_run_with_diagnostics(run_row, diagnostic_rows)

        return self._public_summary(run_id, result)

    @staticmethod
    def _build_diagnostic_rows(
        run_id: str,
        result: GraphBuildResult,
        *,
        project_key: str,
        schedule_version_key: str,
        import_id: str,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for idx, d in enumerate(result.diagnostics):
            rows.append(
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
        return rows

    @staticmethod
    def _diagnostic_signature(result: GraphBuildResult) -> list[str]:
        return [
            "|".join(
                [d.diagnostic_type, d.severity, d.activity_id or "", d.relationship_ref or ""]
            )
            for d in result.diagnostics
        ]

    def _resolve_anchor(
        self, schedule_version_key: str, activities: list[dict[str, Any]]
    ) -> tuple[datetime | None, str | None]:
        """Deterministic schedule-start-anchor precedence.

        Project-level planned start is not persisted as a distinct field, so the schedule
        data date (from the version key) leads, then the minimum activity planned_start,
        then the minimum activity start_date. Returns (anchor, source) or (None, None).
        """
        data_date = parse_schedule_version_data_date(schedule_version_key)
        if data_date is not None:
            return data_date, "data_date"
        for field_name, source in (
            ("planned_start", "min_activity_planned_start"),
            ("start_date", "min_activity_start_date"),
        ):
            parsed = [
                p
                for a in activities
                if (p := _parse_iso_date(a.get(field_name))) is not None
            ]
            if parsed:
                return min(parsed), source
        return None, None

    def run_forward_pass(self, schedule_version_key: str) -> dict[str, Any]:
        """Compute + persist a deterministic forward pass for the version.

        Forward pass only — no backward pass, float, or critical path. Source-export fields
        are never read for logic or overwritten. Returns a public summary; a blocked run
        (fatal graph diagnostic or missing anchor) persists a run row with no result rows.
        """
        activities = self._load_all_activities(schedule_version_key)
        relationships = self._activities.list_relationships(schedule_version_key)
        calendars = self._activities.list_calendars(schedule_version_key)
        graph = build_graph(activities, relationships)
        project_key, import_id = self._run_metadata(schedule_version_key)
        anchor, anchor_source = self._resolve_anchor(schedule_version_key, activities)

        result = compute_forward_pass(
            activities,
            relationships,
            graph,
            anchor=anchor,
            anchor_source=anchor_source,
            calendars=calendars,
        )

        run_id = deterministic_cpm_run_id(
            schedule_version_key=schedule_version_key,
            import_id=import_id,
            diagnostic_signature=self._diagnostic_signature(graph),
            kind="forward_pass",
        )

        run_row = {
            "cpm_run_id": run_id,
            "project_key": project_key,
            "schedule_version_key": schedule_version_key,
            "import_id": import_id,
            "node_count": result.node_count,
            "edge_count": result.edge_count,
            "is_acyclic": 1 if graph.is_acyclic else 0,
            "diagnostic_count": result.diagnostic_count,
            "topological_order_json": (
                json.dumps(graph.topological_order)
                if graph.topological_order is not None
                else None
            ),
            "analysis_scope": "forward_pass",
            "cpm_recalculation_status": result.cpm_recalculation_status,
            "calculation_type": result.calculation_type,
            "schedule_start_anchor": result.anchor_iso,
            "schedule_start_anchor_source": result.anchor_source,
            "computed_activity_count": result.computed_activity_count,
            "blocked_activity_count": result.blocked_activity_count,
        }

        diagnostic_rows = self._build_diagnostic_rows(
            run_id,
            graph,
            project_key=project_key,
            schedule_version_key=schedule_version_key,
            import_id=import_id,
        )

        activity_rows = [
            {
                "cpm_run_id": run_id,
                "schedule_version_key": schedule_version_key,
                "project_key": project_key,
                "activity_id": a.activity_id,
                "activity_name": a.activity_name,
                "topological_index": a.topological_index,
                "computed_early_start": a.computed_early_start,
                "computed_early_finish": a.computed_early_finish,
                "early_start_offset_days": a.early_start_offset_days,
                "early_finish_offset_days": a.early_finish_offset_days,
                "duration_value": a.duration_value,
                "duration_unit": a.duration_unit,
                "duration_source": a.duration_source,
                "predecessor_count": a.predecessor_count,
                "successor_count": a.successor_count,
                "forward_pass_status": a.forward_pass_status,
                "forward_pass_notes_json": json.dumps(a.notes) if a.notes else None,
            }
            for a in result.activities
        ]

        relationship_rows = [
            {
                "cpm_run_id": run_id,
                "schedule_version_key": schedule_version_key,
                "project_key": project_key,
                "relationship_row_id": r.relationship_row_id,
                "relationship_ref": r.relationship_ref,
                "predecessor_activity_id": r.predecessor_activity_id,
                "successor_activity_id": r.successor_activity_id,
                "relationship_type": r.relationship_type,
                "lag_value": None if r.lag_value is None else str(r.lag_value),
                "lag_unit": r.lag_unit,
                "normalized_lag_days": r.normalized_lag_days,
                "predecessor_early_start_offset": r.predecessor_early_start_offset,
                "predecessor_early_finish_offset": r.predecessor_early_finish_offset,
                "candidate_successor_early_start_offset": r.candidate_successor_early_start_offset,
                "relationship_calc_status": r.relationship_calc_status,
                "relationship_calc_notes_json": json.dumps(r.notes) if r.notes else None,
            }
            for r in result.relationships
        ]

        self._cpm.replace_forward_pass_run(
            run_row, diagnostic_rows, activity_rows, relationship_rows
        )

        return self._forward_pass_summary(run_id, result)

    @staticmethod
    def _forward_pass_summary(run_id: str, result: ForwardPassResult) -> dict[str, Any]:
        return {
            "cpm_run_id": run_id,
            "run_status": result.run_status,
            "blocked": result.run_status == RUN_BLOCKED,
            "block_reason": result.block_reason,
            "calculation_type": result.calculation_type,
            "cpm_recalculation_status": result.cpm_recalculation_status,
            "schedule_start_anchor": result.anchor_iso,
            "schedule_start_anchor_source": result.anchor_source,
            "node_count": result.node_count,
            "edge_count": result.edge_count,
            "diagnostic_count": result.diagnostic_count,
            "computed_activity_count": result.computed_activity_count,
            "blocked_activity_count": result.blocked_activity_count,
            "activities": [
                {
                    "activity_id": a.activity_id,
                    "topological_index": a.topological_index,
                    "early_start_offset_days": a.early_start_offset_days,
                    "early_finish_offset_days": a.early_finish_offset_days,
                    "computed_early_start": a.computed_early_start,
                    "computed_early_finish": a.computed_early_finish,
                    "duration_value": a.duration_value,
                    "duration_source": a.duration_source,
                    "forward_pass_status": a.forward_pass_status,
                }
                for a in result.activities
            ],
            "relationships": [
                {
                    "relationship_ref": r.relationship_ref,
                    "relationship_type": r.relationship_type,
                    "normalized_lag_days": r.normalized_lag_days,
                    "candidate_successor_early_start_offset": (
                        r.candidate_successor_early_start_offset
                    ),
                    "relationship_calc_status": r.relationship_calc_status,
                }
                for r in result.relationships
            ],
        }

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

    # --------------------------------------------------------------- Phase 3 backward pass

    def run_backward_pass(self, schedule_version_key: str) -> dict[str, Any]:
        """Compute + persist a deterministic backward pass for the version.

        Backward pass only — no float, longest path, or critical path. Reads the persisted
        forward-pass results (blocks if absent); never reads source-export fields for logic
        or overwrites any source field; never mutates the forward-pass run's rows. Returns a
        public summary; a blocked run persists a run row with no result rows.
        """
        activities = self._load_all_activities(schedule_version_key)
        relationships = self._activities.list_relationships(schedule_version_key)
        graph = build_graph(activities, relationships)
        project_key, import_id = self._run_metadata(schedule_version_key)

        forward_run = self._cpm.get_forward_pass_run(schedule_version_key)
        start_anchor = (
            _parse_iso_date(forward_run["schedule_start_anchor"]) if forward_run else None
        )
        if (
            forward_run is None
            or forward_run.get("cpm_recalculation_status") != "forward_pass_only"
            or start_anchor is None
        ):
            blocked = compute_backward_pass(
                graph,
                [],
                [],
                finish_anchor_offset=None,
                finish_anchor_source=None,
                finish_anchor_caveat=None,
                start_anchor=None,
            )
            # Graph-fatal blocks take precedence; otherwise it's missing forward-pass.
            if blocked.block_reason != BLOCK_MISSING_FORWARD_PASS and graph.is_acyclic:
                blocked.block_reason = BLOCK_MISSING_FORWARD_PASS
            return self._persist_backward_run(
                schedule_version_key,
                project_key,
                import_id,
                graph,
                blocked,
                start_anchor=start_anchor,
                start_anchor_source=(
                    forward_run.get("schedule_start_anchor_source") if forward_run else None
                ),
                forward_activities=[],
                forward_relationships=[],
            )

        fwd_activities = self._cpm.list_activity_results(forward_run["cpm_run_id"])
        fwd_relationships = self._cpm.list_relationship_results(forward_run["cpm_run_id"])

        max_ef = max(
            (
                v
                for a in fwd_activities
                if (v := a.get("early_finish_offset_days")) is not None
            ),
            default=None,
        )
        source_scheduled_finish = self._max_source_date(activities, "finish_date")
        source_planned_finish = self._max_source_date(activities, "planned_finish")
        finish_offset, finish_source, finish_caveat = resolve_finish_anchor(
            source_scheduled_finish=source_scheduled_finish,
            source_planned_finish=source_planned_finish,
            max_early_finish_offset=max_ef,
            start_anchor=start_anchor,
        )

        result = compute_backward_pass(
            graph,
            fwd_activities,
            fwd_relationships,
            finish_anchor_offset=finish_offset,
            finish_anchor_source=finish_source,
            finish_anchor_caveat=finish_caveat,
            start_anchor=start_anchor,
        )

        return self._persist_backward_run(
            schedule_version_key,
            project_key,
            import_id,
            graph,
            result,
            start_anchor=start_anchor,
            start_anchor_source=forward_run.get("schedule_start_anchor_source"),
            forward_activities=fwd_activities,
            forward_relationships=fwd_relationships,
        )

    @staticmethod
    def _max_source_date(activities: list[dict[str, Any]], field_name: str) -> datetime | None:
        parsed = [
            d for a in activities if (d := _parse_iso_date(a.get(field_name))) is not None
        ]
        return max(parsed) if parsed else None

    def _persist_backward_run(
        self,
        schedule_version_key: str,
        project_key: str,
        import_id: str,
        graph: GraphBuildResult,
        result: BackwardPassResult,
        *,
        start_anchor: datetime | None,
        start_anchor_source: str | None,
        forward_activities: list[dict[str, Any]],
        forward_relationships: list[dict[str, Any]],
    ) -> dict[str, Any]:
        run_id = deterministic_cpm_run_id(
            schedule_version_key=schedule_version_key,
            import_id=import_id,
            diagnostic_signature=self._diagnostic_signature(graph),
            kind="backward_pass",
        )

        run_row = {
            "cpm_run_id": run_id,
            "project_key": project_key,
            "schedule_version_key": schedule_version_key,
            "import_id": import_id,
            "node_count": result.node_count,
            "edge_count": result.edge_count,
            "is_acyclic": 1 if graph.is_acyclic else 0,
            "diagnostic_count": result.diagnostic_count,
            "topological_order_json": (
                json.dumps(graph.topological_order)
                if graph.topological_order is not None
                else None
            ),
            "analysis_scope": "backward_pass",
            "cpm_recalculation_status": result.cpm_recalculation_status,
            "calculation_type": result.calculation_type,
            "schedule_start_anchor": start_anchor.isoformat() if start_anchor else None,
            "schedule_start_anchor_source": start_anchor_source,
            "schedule_finish_anchor": result.finish_anchor_iso,
            "schedule_finish_anchor_source": result.finish_anchor_source,
            "computed_activity_count": result.late_date_activity_count,
            "blocked_activity_count": result.late_date_blocked_activity_count,
        }

        diagnostic_rows = self._build_diagnostic_rows(
            run_id,
            graph,
            project_key=project_key,
            schedule_version_key=schedule_version_key,
            import_id=import_id,
        )

        fwd_by_id = {str(a.get("activity_id")): a for a in forward_activities}
        activity_rows = [
            {
                "cpm_run_id": run_id,
                "schedule_version_key": schedule_version_key,
                "project_key": project_key,
                "activity_id": b.activity_id,
                "activity_name": b.activity_name,
                "topological_index": b.topological_index,
                # Early values copied from the forward run (forward run rows untouched).
                "computed_early_start": fwd_by_id.get(b.activity_id, {}).get(
                    "computed_early_start"
                ),
                "computed_early_finish": fwd_by_id.get(b.activity_id, {}).get(
                    "computed_early_finish"
                ),
                "early_start_offset_days": b.early_start_offset_days,
                "early_finish_offset_days": b.early_finish_offset_days,
                "duration_value": b.duration_value,
                "duration_unit": fwd_by_id.get(b.activity_id, {}).get("duration_unit"),
                "duration_source": fwd_by_id.get(b.activity_id, {}).get("duration_source"),
                "predecessor_count": fwd_by_id.get(b.activity_id, {}).get(
                    "predecessor_count", 0
                ),
                "successor_count": fwd_by_id.get(b.activity_id, {}).get("successor_count", 0),
                "forward_pass_status": fwd_by_id.get(b.activity_id, {}).get(
                    "forward_pass_status", "computed"
                ),
                "forward_pass_notes_json": fwd_by_id.get(b.activity_id, {}).get(
                    "forward_pass_notes_json"
                ),
                # Late values computed by the backward pass.
                "computed_late_start": b.computed_late_start,
                "computed_late_finish": b.computed_late_finish,
                "late_start_offset_days": b.late_start_offset_days,
                "late_finish_offset_days": b.late_finish_offset_days,
                "backward_pass_status": b.backward_pass_status,
                "backward_pass_notes_json": json.dumps(b.notes) if b.notes else None,
                "terminal_activity_flag": 1 if b.terminal_activity_flag else 0,
                "controlling_successor_activity_id": b.controlling_successor_activity_id,
                "controlling_successor_relationship_id": b.controlling_successor_relationship_id,
            }
            for b in result.activities
        ]

        fwd_rel_by_key = {
            (
                str(r.get("predecessor_activity_id")),
                str(r.get("successor_activity_id")),
                str(r.get("relationship_type") or ""),
                str(r.get("relationship_row_id") or ""),
            ): r
            for r in forward_relationships
        }
        relationship_rows = []
        for b in result.relationships:
            fwd = fwd_rel_by_key.get(
                (
                    b.predecessor_activity_id,
                    b.successor_activity_id,
                    str(b.relationship_type or ""),
                    str(b.relationship_row_id or ""),
                ),
                {},
            )
            relationship_rows.append(
                {
                    "cpm_run_id": run_id,
                    "schedule_version_key": schedule_version_key,
                    "project_key": project_key,
                    "relationship_row_id": b.relationship_row_id,
                    "relationship_ref": b.relationship_ref,
                    "predecessor_activity_id": b.predecessor_activity_id,
                    "successor_activity_id": b.successor_activity_id,
                    "relationship_type": b.relationship_type,
                    "lag_value": fwd.get("lag_value"),
                    "lag_unit": fwd.get("lag_unit"),
                    "normalized_lag_days": b.normalized_lag_days,
                    "predecessor_early_start_offset": fwd.get("predecessor_early_start_offset"),
                    "predecessor_early_finish_offset": fwd.get(
                        "predecessor_early_finish_offset"
                    ),
                    "candidate_successor_early_start_offset": fwd.get(
                        "candidate_successor_early_start_offset"
                    ),
                    "relationship_calc_status": fwd.get("relationship_calc_status", "computed"),
                    "relationship_calc_notes_json": fwd.get("relationship_calc_notes_json"),
                    "candidate_predecessor_late_start": b.candidate_predecessor_late_start,
                    "candidate_predecessor_late_finish": b.candidate_predecessor_late_finish,
                    "backward_relationship_calc_status": b.backward_relationship_calc_status,
                    "backward_relationship_calc_notes_json": (
                        json.dumps(b.notes) if b.notes else None
                    ),
                }
            )

        self._cpm.replace_backward_pass_run(
            run_row, diagnostic_rows, activity_rows, relationship_rows
        )
        return self._backward_pass_summary(run_id, result)

    @staticmethod
    def _backward_pass_summary(run_id: str, result: BackwardPassResult) -> dict[str, Any]:
        return {
            "cpm_run_id": run_id,
            "run_status": result.run_status,
            "blocked": result.run_status == RUN_BLOCKED,
            "block_reason": result.block_reason,
            "calculation_type": result.calculation_type,
            "cpm_recalculation_status": result.cpm_recalculation_status,
            "schedule_finish_anchor": result.finish_anchor_iso,
            "schedule_finish_anchor_source": result.finish_anchor_source,
            "finish_anchor_offset": result.finish_anchor_offset,
            "finish_anchor_caveat": result.finish_anchor_caveat,
            "node_count": result.node_count,
            "edge_count": result.edge_count,
            "diagnostic_count": result.diagnostic_count,
            "late_date_activity_count": result.late_date_activity_count,
            "late_date_blocked_activity_count": result.late_date_blocked_activity_count,
            "activities": [
                {
                    "activity_id": a.activity_id,
                    "topological_index": a.topological_index,
                    "early_start_offset_days": a.early_start_offset_days,
                    "early_finish_offset_days": a.early_finish_offset_days,
                    "late_start_offset_days": a.late_start_offset_days,
                    "late_finish_offset_days": a.late_finish_offset_days,
                    "computed_late_start": a.computed_late_start,
                    "computed_late_finish": a.computed_late_finish,
                    "terminal_activity_flag": a.terminal_activity_flag,
                    "controlling_successor_activity_id": a.controlling_successor_activity_id,
                    "backward_pass_status": a.backward_pass_status,
                }
                for a in result.activities
            ],
            "relationships": [
                {
                    "relationship_ref": r.relationship_ref,
                    "relationship_type": r.relationship_type,
                    "normalized_lag_days": r.normalized_lag_days,
                    "candidate_predecessor_late_start": r.candidate_predecessor_late_start,
                    "candidate_predecessor_late_finish": r.candidate_predecessor_late_finish,
                    "backward_relationship_calc_status": r.backward_relationship_calc_status,
                }
                for r in result.relationships
            ],
        }
