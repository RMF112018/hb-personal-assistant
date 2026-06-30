"""Change-driver analysis and causal-sequence storytelling for Project Schedule Hub Phase 3."""

from __future__ import annotations

from collections import Counter, deque
from typing import Any

from hb_assistant.store.connection import open_connection
from hb_assistant.store.schedule_mapping_repository import ScheduleMappingRepository

from .project_schedule_comparison import ProjectScheduleComparisonService
from .schedule_graph import build_adjacency

_DRIVER_PREVIEW = 5
_DRIVER_MAX = 25
_MOVEMENT_CANDIDATE_CAP = 200
_BFS_DEPTH = 4
_BFS_NODES_PER_DRIVER = 50
_SUCCESSOR_PREVIEW = 10
_LOGIC_PREVIEW = 10
_DURATION_PREVIEW = 10
_MILESTONE_PREVIEW = 10
_MILESTONE_REVERSE_DEPTH = 5
_MIN_DRIVER_SCORE = 5.0

_SEQUENCE_CUE = "Sequence cue only — review logic and dates; not a causation finding."
_ADVISORY_POSTURE = "sequence_cues_not_causation"

_DRIVER_DRILLDOWN_TYPES = frozenset(
    {
        "drivers",
        "impacted_successors",
        "logic_changes",
        "duration_changes",
        "milestone_impacts",
    }
)

_WEIGHT_DOWNSTREAM = 3.0
_WEIGHT_MILESTONE = 10.0
_WEIGHT_FLOAT_DAY = 1.0
_WEIGHT_CRITICAL = 15.0
_WEIGHT_NEAR_CRITICAL = 8.0
_WEIGHT_LOGIC = 5.0
_WEIGHT_SELF_FINISH = 2.0


class ProjectScheduleDriverAnalysisService:
    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path
        self._comparison = ProjectScheduleComparisonService(db_path=db_path)
        self._mapping = ScheduleMappingRepository(db_path=db_path)

    def build_hub_analysis(
        self,
        *,
        project_key: str,
        current_key: str,
        previous_key: str | None,
        baseline_key: str | None,
        diff_id: int | None,
        milestones: dict[str, Any] | None = None,
        comparison_ready: bool = True,
    ) -> dict[str, Any]:
        prior = self.build_analysis(
            project_key=project_key,
            current_key=current_key,
            previous_key=previous_key,
            diff_id=diff_id,
            milestones=milestones,
            comparison_ready=comparison_ready,
            comparison_basis="prior_update",
        )
        if baseline_key and comparison_ready:
            if baseline_key == previous_key and prior.get("available"):
                baseline = {**prior, "comparison_basis": "baseline"}
                baseline = {k: v for k, v in baseline.items() if not str(k).startswith("_")}
            else:
                baseline = self.build_analysis(
                    project_key=project_key,
                    current_key=current_key,
                    previous_key=baseline_key,
                    diff_id=None,
                    milestones=milestones,
                    comparison_ready=True,
                    comparison_basis="baseline",
                )
        else:
            baseline = self._unavailable("baseline_unavailable")
        return {
            "available": bool(prior.get("available") or baseline.get("available")),
            "advisory_posture": _ADVISORY_POSTURE,
            "prior_update": {k: v for k, v in prior.items() if not str(k).startswith("_")},
            "baseline": {k: v for k, v in baseline.items() if not str(k).startswith("_")},
            "_prior_update": prior,
            "_baseline": baseline,
        }

    def build_analysis(
        self,
        *,
        project_key: str,
        current_key: str,
        previous_key: str | None,
        diff_id: int | None,
        milestones: dict[str, Any] | None = None,
        comparison_ready: bool = True,
        comparison_basis: str = "prior_update",
    ) -> dict[str, Any]:
        if not previous_key or not comparison_ready:
            return self._unavailable("comparison_unavailable", comparison_basis=comparison_basis)

        comparison = self._comparison.compare_versions(left_key=current_key, right_key=previous_key)
        rows = comparison.get("rows") or []
        row_by_id = {str(r.get("activity_id")): r for r in rows if r.get("activity_id")}

        forward_adj, reverse_adj = self._load_adjacency(current_key)
        prior_rels, current_rels = self._load_relationship_sets(current_key, previous_key)
        logic_changes = self._logic_changes(project_key=project_key, diff_id=diff_id, row_by_id=row_by_id)
        duration_changes = self._duration_changes(
            current_key=current_key,
            previous_key=previous_key,
            row_by_id=row_by_id,
            forward_adj=forward_adj,
        )
        moved_milestone_ids = self._moved_milestone_ids(rows, milestones)
        drivers = self._rank_drivers(
            rows=rows,
            row_by_id=row_by_id,
            forward_adj=forward_adj,
            logic_changes=logic_changes,
            moved_milestone_ids=moved_milestone_ids,
            prior_rels=prior_rels,
            current_rels=current_rels,
        )
        milestone_impacts = self._milestone_impacts(
            milestones=milestones or {},
            drivers=drivers,
            reverse_adj=reverse_adj,
            row_by_id=row_by_id,
        )
        pm_drivers = [d for d in drivers if d.get("context_quality") != "low"]
        top = pm_drivers[0] if pm_drivers else (drivers[0] if drivers else None)
        top_wbs = (top or {}).get("display_wbs") or "—"
        top_wbs_reason = (top or {}).get("wbs_context_reason")
        summary = {
            "candidate_driver_count": len(drivers),
            "top_wbs_area": top_wbs,
            "top_wbs_context_reason": top_wbs_reason,
            "top_driver_activity_id": (top or {}).get("activity_id"),
            "top_driver_activity_name": (top or {}).get("activity_name"),
            "top_driver_downstream_count": int((top or {}).get("downstream_moved_later_count") or 0),
            "top_driver_milestone_touch_count": int((top or {}).get("milestone_touch_count") or 0),
            "logic_change_count": logic_changes.get("summary", {}).get("total_count", 0),
            "duration_change_count": duration_changes.get("summary", {}).get("total_count", 0),
            "milestone_impact_count": milestone_impacts.get("summary", {}).get("total_count", 0),
        }
        return {
            "available": True,
            "comparison_basis": comparison_basis,
            "comparison_finish_basis": "resolved_finish_date",
            "advisory_posture": _ADVISORY_POSTURE,
            "summary": summary,
            "top_drivers": (pm_drivers or drivers)[:_DRIVER_PREVIEW],
            "logic_changes": logic_changes,
            "duration_changes": duration_changes,
            "milestone_impacts": milestone_impacts,
            "review_drilldowns": self._preview_drilldowns(
                project_key=project_key,
                drivers=drivers,
                logic_changes=logic_changes,
                duration_changes=duration_changes,
                milestone_impacts=milestone_impacts,
            ),
            "_all_drivers": drivers,
        }

    def build_driver_detail(
        self,
        *,
        project_key: str,
        activity_id: str,
        current_key: str,
        previous_key: str | None,
        diff_id: int | None,
        milestones: dict[str, Any] | None = None,
        comparison_ready: bool = True,
        comparison_basis: str = "prior_update",
        baseline_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not previous_key or not comparison_ready:
            return {
                "available": False,
                "reason": "comparison_unavailable",
                "comparison_basis": comparison_basis,
            }
        analysis = self.build_analysis(
            project_key=project_key,
            current_key=current_key,
            previous_key=previous_key,
            diff_id=diff_id,
            milestones=milestones,
            comparison_ready=comparison_ready,
            comparison_basis=comparison_basis,
        )
        if not analysis.get("available"):
            return {"available": False, "reason": analysis.get("reason", "unavailable")}

        comparison = self._comparison.compare_versions(left_key=current_key, right_key=previous_key)
        rows = comparison.get("rows") or []
        row_by_id = {str(r.get("activity_id")): r for r in rows if r.get("activity_id")}
        row = row_by_id.get(activity_id)
        if not row:
            return {"available": False, "reason": "activity_not_found"}

        forward_adj, reverse_adj = self._load_adjacency(current_key)
        moved_milestone_ids = self._moved_milestone_ids(rows, milestones)
        logic_changes = analysis["logic_changes"]
        logic_for_activity = (logic_changes.get("_by_activity") or {}).get(activity_id, [])
        driver_match = next(
            (d for d in analysis.get("_all_drivers") or [] if str(d.get("activity_id")) == activity_id),
            None,
        )
        upstream = self._compact_pred_chain(activity_id, reverse_adj, row_by_id, limit=8)
        downstream = self._successors_for_driver(
            driver_activity_id=activity_id,
            forward_adj=forward_adj,
            row_by_id=row_by_id,
            moved_milestone_ids=moved_milestone_ids,
        )
        payload = {
            "available": True,
            "activity_id": activity_id,
            "comparison_basis": comparison_basis,
            "advisory_posture": _ADVISORY_POSTURE,
            "activity": {
                "activity_id": activity_id,
                "activity_name": row.get("activity_name"),
                "wbs_code": row.get("wbs_code"),
                "prior_start": row.get("prior_start"),
                "current_start": row.get("current_start"),
                "start_delta_days": row.get("start_delta_days"),
                "prior_finish": row.get("prior_finish"),
                "current_finish": row.get("current_finish"),
                "finish_delta_days": row.get("finish_delta_days"),
                "prior_float": row.get("prior_float"),
                "current_float": row.get("current_float"),
                "float_delta_days": row.get("float_delta_days"),
                "computed_cpm_critical": row.get("computed_cpm_critical"),
                "computed_cpm_near_critical": row.get("computed_cpm_near_critical"),
            },
            "driver_rank": driver_match,
            "upstream_path": upstream,
            "downstream_impacts": downstream[:15],
            "logic_changes": logic_for_activity[:10],
            "sequence_cue": _SEQUENCE_CUE,
            "detail_url": f"/api/projects/{project_key}/schedule/drivers/{activity_id}/detail",
        }
        if baseline_context:
            payload["baseline_context"] = baseline_context
        return payload

    def build_narrative(self, analysis: dict[str, Any]) -> dict[str, Any]:
        if not analysis.get("available"):
            return {}
        top = (analysis.get("top_drivers") or [None])[0]
        if not top:
            return {}
        basis = str(top.get("movement_basis") or "downstream_cluster")
        wbs_label = top.get("display_wbs") or "the schedule"
        activity_label = top.get("activity_name") or top.get("activity_id") or "This activity"
        downstream = int(top.get("downstream_moved_later_count") or 0)
        milestone_name = top.get("top_milestone_name")
        milestone_clause = f", including {milestone_name}" if milestone_name else ""
        finish_delta = int(top.get("finish_delta_days") or 0)
        start_delta = int(top.get("start_delta_days") or 0)
        duration_delta = int(top.get("duration_delta_days") or 0)

        if basis == "self_finish_moved":
            movement_days = max(abs(finish_delta), abs(start_delta))
            movement_clause = (
                f"{activity_label} moved by {movement_days} days"
                if movement_days
                else f"{activity_label} shows date movement in this comparison"
            )
        elif basis == "duration_extended":
            movement_clause = (
                f"{activity_label} extended by {duration_delta} days"
                if duration_delta
                else f"{activity_label} shows a duration increase in this comparison"
            )
        elif basis == "logic_changed":
            movement_clause = f"{activity_label} has logic changes in this comparison"
        elif basis == "float_degraded":
            movement_clause = f"{activity_label} shows float degradation nearby in this comparison"
        elif basis == "milestone_path_touched":
            movement_clause = f"{activity_label} appears connected to moved milestone paths"
        else:
            movement_clause = (
                f"{activity_label} did not move materially itself, but it sits upstream of "
                f"{downstream} activities that moved later"
            )

        narrative = (
            f"The largest movement appears concentrated around {wbs_label}. "
            f"{movement_clause} and appears connected to {downstream} downstream activities"
            f"{milestone_clause}. Review this sequence first."
        )
        return {
            "primary_driver_narrative": narrative,
            "movement_basis": basis,
            "top_review_sequence": {
                "wbs_code": top.get("display_wbs"),
                "wbs_context_reason": top.get("wbs_context_reason"),
                "driver_activity_id": top.get("activity_id"),
                "driver_activity_name": top.get("activity_name"),
                "downstream_count": downstream,
                "milestone_touch_count": top.get("milestone_touch_count"),
                "review_priority": top.get("review_priority"),
                "movement_basis": basis,
                "context_quality": top.get("context_quality"),
            },
        }

    def list_drilldown(
        self,
        *,
        project_key: str,
        drilldown_type: str,
        current_key: str,
        previous_key: str | None,
        diff_id: int | None,
        milestones: dict[str, Any] | None = None,
        driver_activity_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
        comparison_ready: bool = True,
    ) -> dict[str, Any]:
        if drilldown_type not in _DRIVER_DRILLDOWN_TYPES:
            raise ValueError("unsupported_driver_drilldown_type")
        analysis = self.build_analysis(
            project_key=project_key,
            current_key=current_key,
            previous_key=previous_key,
            diff_id=diff_id,
            milestones=milestones,
            comparison_ready=comparison_ready,
        )
        if not analysis.get("available"):
            return {"available": False, "reason": analysis.get("reason", "unavailable")}

        limit = max(1, min(limit, 200))
        offset = max(0, offset)

        if drilldown_type == "drivers":
            items = analysis["_all_drivers"][offset : offset + limit]
            return self._page(drilldown_type, items, len(analysis["_all_drivers"]), limit, offset)

        if drilldown_type == "impacted_successors":
            if not driver_activity_id:
                raise ValueError("driver_activity_id_required")
            comparison = self._comparison.compare_versions(left_key=current_key, right_key=previous_key)
            row_by_id = {str(r.get("activity_id")): r for r in comparison.get("rows") or [] if r.get("activity_id")}
            forward_adj, _ = self._load_adjacency(current_key)
            moved_milestone_ids = self._moved_milestone_ids(comparison.get("rows") or [], milestones)
            items = self._successors_for_driver(
                driver_activity_id=driver_activity_id,
                forward_adj=forward_adj,
                row_by_id=row_by_id,
                moved_milestone_ids=moved_milestone_ids,
            )
            return self._page(drilldown_type, items[offset : offset + limit], len(items), limit, offset)

        if drilldown_type == "logic_changes":
            items = analysis["logic_changes"].get("items") or []
            return self._page(drilldown_type, items[offset : offset + limit], len(items), limit, offset)

        if drilldown_type == "duration_changes":
            items = analysis["duration_changes"].get("items") or []
            return self._page(drilldown_type, items[offset : offset + limit], len(items), limit, offset)

        items = analysis["milestone_impacts"].get("items") or []
        return self._page(drilldown_type, items[offset : offset + limit], len(items), limit, offset)

    def _rank_drivers(
        self,
        *,
        rows: list[dict[str, Any]],
        row_by_id: dict[str, dict[str, Any]],
        forward_adj: dict[str, list[str]],
        logic_changes: dict[str, Any],
        moved_milestone_ids: set[str],
        prior_rels: dict[str, dict[str, Any]],
        current_rels: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        logic_by_activity = logic_changes.get("_by_activity") or {}
        movement_rows = sorted(
            [r for r in rows if self._has_movement_signal(r)],
            key=lambda r: abs(r.get("finish_delta_days") or 0),
            reverse=True,
        )[:_MOVEMENT_CANDIDATE_CAP]

        candidates: set[str] = {str(r["activity_id"]) for r in movement_rows if r.get("activity_id")}
        for aid in logic_by_activity:
            candidates.add(str(aid))

        for pred, succs in forward_adj.items():
            moved_succs = sum(
                1 for s in succs if ((row_by_id.get(s) or {}).get("finish_delta_days") or 0) > 0
            )
            if moved_succs >= 2:
                candidates.add(str(pred))

        drivers: list[dict[str, Any]] = []
        for aid in candidates:
            row = row_by_id.get(aid, {})
            successors = self._successors_for_driver(
                driver_activity_id=aid,
                forward_adj=forward_adj,
                row_by_id=row_by_id,
                moved_milestone_ids=moved_milestone_ids,
            )
            downstream_moved = len(successors)
            milestone_touch = sum(
                1 for s in successors if any(m in s.get("affected_milestone_path") or [] for m in moved_milestone_ids)
            ) or sum(1 for s in successors if s.get("affected_milestone_path"))
            float_deg = sum(min(0, s.get("float_delta_days") or 0) for s in successors)
            logic_score = len(logic_by_activity.get(aid, []))
            finish_delta = row.get("finish_delta_days") or 0
            start_delta = row.get("start_delta_days") or 0
            self_score = abs(finish_delta) * _WEIGHT_SELF_FINISH + abs(start_delta)
            critical_prox = 0.0
            if row.get("computed_cpm_critical"):
                critical_prox = _WEIGHT_CRITICAL
            elif row.get("computed_cpm_near_critical"):
                critical_prox = _WEIGHT_NEAR_CRITICAL
            elif any(s.get("computed_cpm_critical") for s in successors[:5]):
                critical_prox = _WEIGHT_NEAR_CRITICAL

            score = (
                downstream_moved * _WEIGHT_DOWNSTREAM
                + milestone_touch * _WEIGHT_MILESTONE
                + abs(float_deg) * _WEIGHT_FLOAT_DAY
                + logic_score * _WEIGHT_LOGIC
                + self_score
                + critical_prox
            )
            if score < _MIN_DRIVER_SCORE:
                continue

            wbs_counts = Counter(
                self._display_wbs(s.get("wbs_code"))[0] for s in successors if self._display_wbs(s.get("wbs_code"))[0] != "—"
            )
            top_milestone = None
            for s in successors:
                paths = s.get("affected_milestone_path") or []
                if paths:
                    top_milestone = paths[0].get("activity_name") or paths[0].get("activity_id")
                    break

            pred_delta = (current_rels.get(aid) or {}).get("predecessor_count", 0) - (
                prior_rels.get(aid) or {}
            ).get("predecessor_count", 0)
            succ_delta = (current_rels.get(aid) or {}).get("successor_count", 0) - (
                prior_rels.get(aid) or {}
            ).get("successor_count", 0)
            display_wbs, missing_reasons, wbs_context_reason = self._display_wbs(row.get("wbs_code"))
            movement_basis = self._movement_basis(
                row,
                logic_score=logic_score,
                downstream_moved=downstream_moved,
                float_deg=float_deg,
                milestone_touch=milestone_touch,
            )
            context_quality, context_missing = self._driver_context_quality(
                row,
                display_wbs=display_wbs,
                movement_basis=movement_basis,
            )

            drivers.append(
                {
                    "activity_id": aid,
                    "activity_name": row.get("activity_name"),
                    "wbs_code": row.get("wbs_code"),
                    "display_wbs": display_wbs,
                    "wbs_context_reason": wbs_context_reason,
                    "finish_delta_days": finish_delta,
                    "start_delta_days": start_delta,
                    "duration_delta_days": row.get("duration_delta_days"),
                    "float_delta_days": row.get("float_delta_days"),
                    "downstream_moved_later_count": downstream_moved,
                    "milestone_touch_count": milestone_touch,
                    "float_degradation_score": abs(float_deg),
                    "logic_change_count": logic_score,
                    "predecessor_count_delta": pred_delta,
                    "successor_count_delta": succ_delta,
                    "computed_cpm_critical": row.get("computed_cpm_critical"),
                    "computed_cpm_near_critical": row.get("computed_cpm_near_critical"),
                    "dominant_impacted_wbs": wbs_counts.most_common(1)[0][0] if wbs_counts else display_wbs,
                    "top_milestone_name": top_milestone,
                    "review_priority": min(100, int(score)),
                    "driver_score": round(score, 2),
                    "movement_basis": movement_basis,
                    "context_quality": context_quality,
                    "missing_context_reasons": missing_reasons + context_missing,
                    "sequence_cue": _SEQUENCE_CUE,
                    "impacted_successors_preview": successors[:_SUCCESSOR_PREVIEW],
                }
            )

        drivers.sort(key=lambda d: (-d["review_priority"], str(d.get("activity_id") or "")))
        return drivers[:_DRIVER_MAX]

    def _successors_for_driver(
        self,
        *,
        driver_activity_id: str,
        forward_adj: dict[str, list[str]],
        row_by_id: dict[str, dict[str, Any]],
        moved_milestone_ids: set[str],
    ) -> list[dict[str, Any]]:
        visited: set[str] = set()
        queue: deque[tuple[str, int]] = deque([(driver_activity_id, 0)])
        items: list[dict[str, Any]] = []

        while queue and len(items) < _BFS_NODES_PER_DRIVER:
            aid, depth = queue.popleft()
            if depth >= _BFS_DEPTH:
                continue
            for succ in forward_adj.get(aid, []):
                if succ in visited or succ == driver_activity_id:
                    continue
                visited.add(succ)
                row = row_by_id.get(succ)
                if not row:
                    continue
                finish_delta = row.get("finish_delta_days")
                if finish_delta is None or finish_delta == 0:
                    queue.append((succ, depth + 1))
                    continue
                milestone_path = self._milestone_path_from(
                    succ, forward_adj, row_by_id, moved_milestone_ids, max_depth=_BFS_DEPTH - depth
                )
                items.append(
                    {
                        "activity_id": succ,
                        "activity_name": row.get("activity_name"),
                        "wbs_code": row.get("wbs_code"),
                        "prior_start": row.get("prior_start"),
                        "current_start": row.get("current_start"),
                        "start_delta_days": row.get("start_delta_days"),
                        "prior_finish": row.get("prior_finish"),
                        "current_finish": row.get("current_finish"),
                        "finish_delta_days": finish_delta,
                        "prior_float": row.get("prior_float"),
                        "current_float": row.get("current_float"),
                        "float_delta_days": row.get("float_delta_days"),
                        "computed_cpm_critical": row.get("computed_cpm_critical"),
                        "computed_cpm_near_critical": row.get("computed_cpm_near_critical"),
                        "affected_milestone_path": milestone_path,
                        "sequence_cue": _SEQUENCE_CUE,
                        "depth_from_driver": depth + 1,
                    }
                )
                queue.append((succ, depth + 1))
        items.sort(key=lambda r: abs(r.get("finish_delta_days") or 0), reverse=True)
        return items

    def _milestone_path_from(
        self,
        start_id: str,
        forward_adj: dict[str, list[str]],
        row_by_id: dict[str, dict[str, Any]],
        moved_milestone_ids: set[str],
        *,
        max_depth: int,
    ) -> list[dict[str, Any]]:
        if start_id in moved_milestone_ids:
            row = row_by_id.get(start_id) or {}
            return [{"activity_id": start_id, "activity_name": row.get("activity_name")}]
        found: list[dict[str, Any]] = []
        queue: deque[tuple[str, int]] = deque([(start_id, 0)])
        seen: set[str] = {start_id}
        while queue and len(found) < 3:
            aid, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for succ in forward_adj.get(aid, []):
                if succ in seen:
                    continue
                seen.add(succ)
                if succ in moved_milestone_ids:
                    row = row_by_id.get(succ) or {}
                    found.append({"activity_id": succ, "activity_name": row.get("activity_name")})
                else:
                    queue.append((succ, depth + 1))
        return found

    def _logic_changes(
        self,
        *,
        project_key: str,
        diff_id: int | None,
        row_by_id: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        if not diff_id:
            return {"available": False, "reason": "diff_unavailable", "summary": {}, "items": [], "_by_activity": {}}

        facts = self._mapping.list_diff_detail_facts(
            int(diff_id),
            project_key=project_key,
            change_domain="relationship",
            limit=500,
            offset=0,
        )
        by_activity: dict[str, list[dict[str, Any]]] = {}
        items: list[dict[str, Any]] = []
        added = removed = type_changed = lag_changed = 0

        for fact in facts:
            change_type = str(fact.get("change_type") or "")
            if change_type == "logic_added":
                added += 1
            elif change_type == "logic_removed":
                removed += 1
            elif change_type == "logic_changed":
                field = str(fact.get("field_name") or "")
                if field == "relationship_type":
                    type_changed += 1
                elif field in {"lag_value", "lag_unit"}:
                    lag_changed += 1

            pred = str(fact.get("predecessor_activity_id") or "")
            succ = str(fact.get("successor_activity_id") or "")
            touched = {a for a in (pred, succ) if a}
            finish_touched = any((row_by_id.get(a) or {}).get("finish_delta_days") not in (None, 0) for a in touched)
            item = {
                "change_type": change_type,
                "predecessor_activity_id": pred,
                "successor_activity_id": succ,
                "field_name": fact.get("field_name"),
                "from_value": fact.get("from_value"),
                "to_value": fact.get("to_value"),
                "severity": fact.get("severity"),
                "finish_movement_linked": finish_touched,
                "sequence_cue": _SEQUENCE_CUE,
            }
            items.append(item)
            for aid in touched:
                by_activity.setdefault(aid, []).append(item)

        items.sort(key=lambda i: (0 if i.get("finish_movement_linked") else 1, str(i.get("change_type"))))
        return {
            "available": True,
            "summary": {
                "total_count": len(items),
                "logic_added_count": added,
                "logic_removed_count": removed,
                "relationship_type_changed_count": type_changed,
                "lag_changed_count": lag_changed,
            },
            "items": items[:_LOGIC_PREVIEW],
            "_all_items": items,
            "_by_activity": by_activity,
        }

    def _duration_changes(
        self,
        *,
        current_key: str,
        previous_key: str,
        row_by_id: dict[str, dict[str, Any]],
        forward_adj: dict[str, list[str]],
    ) -> dict[str, Any]:
        durations = self._load_duration_pairs(current_key, previous_key)
        items: list[dict[str, Any]] = []
        for aid, pair in durations.items():
            prior_d, current_d = pair
            if prior_d is None or current_d is None:
                continue
            delta = current_d - prior_d
            if delta <= 0:
                continue
            row = row_by_id.get(aid) or {}
            finish_delta = row.get("finish_delta_days") or 0
            downstream_moved = sum(
                1
                for s in forward_adj.get(aid, [])
                if ((row_by_id.get(s) or {}).get("finish_delta_days") or 0) > 0
            )
            extended_without_progress = finish_delta > 0 and delta > 0
            started_on_time_extended = bool(row.get("prior_start")) and delta > 0 and downstream_moved > 0
            items.append(
                {
                    "activity_id": aid,
                    "activity_name": row.get("activity_name"),
                    "wbs_code": row.get("wbs_code"),
                    "prior_duration_remaining": prior_d,
                    "current_duration_remaining": current_d,
                    "duration_delta_days": delta,
                    "finish_delta_days": finish_delta,
                    "downstream_moved_later_count": downstream_moved,
                    "duration_increased": True,
                    "extended_without_progress": extended_without_progress,
                    "started_on_time_extended": started_on_time_extended,
                    "sequence_cue": _SEQUENCE_CUE,
                }
            )
        items.sort(key=lambda i: (i.get("duration_delta_days", 0) * max(1, i.get("downstream_moved_later_count", 0))), reverse=True)
        return {
            "available": True,
            "summary": {
                "total_count": len(items),
                "extended_without_progress_count": sum(1 for i in items if i.get("extended_without_progress")),
                "started_on_time_extended_count": sum(1 for i in items if i.get("started_on_time_extended")),
            },
            "items": items[:_DURATION_PREVIEW],
            "_all_items": items,
        }

    def _milestone_impacts(
        self,
        *,
        milestones: dict[str, Any],
        drivers: list[dict[str, Any]],
        reverse_adj: dict[str, list[str]],
        row_by_id: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        driver_ids = {str(d.get("activity_id")) for d in drivers}
        top_driver_map = {str(d.get("activity_id")): d for d in drivers[:10]}
        items: list[dict[str, Any]] = []
        for ms in milestones.get("items") or []:
            movement = ms.get("movement_days")
            if movement is None or int(movement) <= 0:
                continue
            ms_id = str(ms.get("activity_id") or "")
            candidates = self._reverse_driver_candidates(ms_id, reverse_adj, driver_ids, max_depth=_MILESTONE_REVERSE_DEPTH)
            candidate_drivers = [
                {
                    "activity_id": cid,
                    "activity_name": (top_driver_map.get(cid) or row_by_id.get(cid) or {}).get("activity_name"),
                    "review_priority": (top_driver_map.get(cid) or {}).get("review_priority"),
                }
                for cid in candidates[:3]
            ]
            path_evidence = self._compact_pred_chain(ms_id, reverse_adj, row_by_id, limit=5)
            items.append(
                {
                    "activity_id": ms_id,
                    "activity_name": ms.get("activity_name"),
                    "movement_days": movement,
                    "forecast_date": ms.get("forecast_date"),
                    "candidate_drivers": candidate_drivers,
                    "path_evidence": path_evidence,
                    "sequence_cue": (
                        f"Candidate upstream sequence cues exist for this moved milestone; "
                        f"review {len(candidate_drivers)} linked driver(s) first."
                    ),
                }
            )
        return {
            "available": True,
            "summary": {"total_count": len(items)},
            "items": items[:_MILESTONE_PREVIEW],
            "_all_items": items,
        }

    def _reverse_driver_candidates(
        self,
        milestone_id: str,
        reverse_adj: dict[str, list[str]],
        driver_ids: set[str],
        *,
        max_depth: int,
    ) -> list[str]:
        found: list[str] = []
        queue: deque[tuple[str, int]] = deque([(milestone_id, 0)])
        seen: set[str] = {milestone_id}
        while queue:
            aid, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for pred in reverse_adj.get(aid, []):
                if pred in seen:
                    continue
                seen.add(pred)
                if pred in driver_ids:
                    found.append(pred)
                queue.append((pred, depth + 1))
        return found

    def _compact_pred_chain(
        self,
        milestone_id: str,
        reverse_adj: dict[str, list[str]],
        row_by_id: dict[str, dict[str, Any]],
        *,
        limit: int,
    ) -> list[dict[str, Any]]:
        chain: list[dict[str, Any]] = []
        current = milestone_id
        seen: set[str] = set()
        while len(chain) < limit:
            preds = [p for p in reverse_adj.get(current, []) if p not in seen]
            if not preds:
                break
            pred = preds[0]
            seen.add(pred)
            row = row_by_id.get(pred) or {}
            chain.append({"activity_id": pred, "activity_name": row.get("activity_name")})
            current = pred
        return list(reversed(chain))

    def _load_adjacency(self, version_key: str) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
        with open_connection(self._db_path) as conn:
            rels = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT predecessor_activity_id, successor_activity_id, relationship_type,
                           lag_value, lag_unit
                    FROM procore_ep_schedule_relationships
                    WHERE schedule_version_key=?
                    """,
                    (version_key,),
                ).fetchall()
            ]
        forward = build_adjacency(rels)
        reverse: dict[str, list[str]] = {}
        for pred, succs in forward.items():
            for succ in succs:
                reverse.setdefault(succ, []).append(pred)
        return forward, reverse

    def _load_relationship_sets(
        self, current_key: str, previous_key: str
    ) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
        def counts(version_key: str) -> dict[str, dict[str, Any]]:
            with open_connection(self._db_path) as conn:
                rows = conn.execute(
                    """
                    SELECT predecessor_activity_id, successor_activity_id
                    FROM procore_ep_schedule_relationships
                    WHERE schedule_version_key=?
                    """,
                    (version_key,),
                ).fetchall()
            pred_count: Counter[str] = Counter()
            succ_count: Counter[str] = Counter()
            for row in rows:
                pred_count[str(row[0])] += 1
                succ_count[str(row[1])] += 1
            ids = set(pred_count) | set(succ_count)
            return {
                aid: {"predecessor_count": pred_count.get(aid, 0), "successor_count": succ_count.get(aid, 0)}
                for aid in ids
            }

        return counts(previous_key), counts(current_key)

    def _load_duration_pairs(self, current_key: str, previous_key: str) -> dict[str, tuple[float | None, float | None]]:
        def load(key: str) -> dict[str, float | None]:
            with open_connection(self._db_path) as conn:
                rows = conn.execute(
                    """
                    SELECT activity_id, duration_remaining
                    FROM procore_ep_schedule_activities
                    WHERE schedule_version_key=?
                      AND (actual_finish IS NULL OR TRIM(actual_finish)='')
                    """,
                    (key,),
                ).fetchall()
            out: dict[str, float | None] = {}
            for row in rows:
                try:
                    out[str(row[0])] = float(row[1]) if row[1] not in (None, "") else None
                except (TypeError, ValueError):
                    out[str(row[0])] = None
            return out

        current = load(current_key)
        previous = load(previous_key)
        ids = set(current) | set(previous)
        return {aid: (previous.get(aid), current.get(aid)) for aid in ids}

    def _moved_milestone_ids(
        self, rows: list[dict[str, Any]], milestones: dict[str, Any] | None
    ) -> set[str]:
        ids = {
            str(r.get("activity_id"))
            for r in rows
            if r.get("is_milestone") and (r.get("finish_delta_days") or 0) > 0 and r.get("activity_id")
        }
        for item in (milestones or {}).get("items") or []:
            if int(item.get("movement_days") or 0) > 0 and item.get("activity_id"):
                ids.add(str(item["activity_id"]))
        return ids

    @staticmethod
    def _display_wbs(wbs_code: Any) -> tuple[str, list[str], str | None]:
        if wbs_code not in (None, ""):
            return str(wbs_code), [], None
        return "—", ["wbs_missing_from_comparison_row"], "WBS was not present in the comparison row."

    @staticmethod
    def _movement_basis(
        row: dict[str, Any],
        *,
        logic_score: int,
        downstream_moved: int,
        float_deg: float,
        milestone_touch: int,
    ) -> str:
        finish_delta = row.get("finish_delta_days") or 0
        start_delta = row.get("start_delta_days") or 0
        duration_delta = row.get("duration_delta_days") or 0
        if finish_delta not in (None, 0) or start_delta not in (None, 0):
            return "self_finish_moved"
        if duration_delta not in (None, 0) and duration_delta > 0:
            return "duration_extended"
        if logic_score:
            return "logic_changed"
        if downstream_moved >= 2:
            return "downstream_cluster"
        if float_deg < 0:
            return "float_degraded"
        if milestone_touch:
            return "milestone_path_touched"
        return "downstream_cluster"

    @staticmethod
    def _driver_context_quality(
        row: dict[str, Any],
        *,
        display_wbs: str,
        movement_basis: str,
    ) -> tuple[str, list[str]]:
        missing: list[str] = []
        activity_name = row.get("activity_name")
        activity_id = row.get("activity_id")
        if not activity_name:
            missing.append("activity_name_missing")
        if display_wbs == "—":
            missing.append("wbs_missing")
        if not activity_id:
            missing.append("activity_id_missing")
        if missing:
            if len(missing) >= 2:
                return "low", missing
            return "medium", missing
        if movement_basis == "downstream_cluster" and display_wbs == "—":
            return "medium", missing
        return "high", missing

    def _has_movement_signal(self, row: dict[str, Any]) -> bool:
        return (
            (row.get("finish_delta_days") not in (None, 0))
            or (row.get("start_delta_days") not in (None, 0))
            or (row.get("float_delta_days") not in (None, 0) and (row.get("float_delta_days") or 0) < 0)
        )

    def _preview_drilldowns(
        self,
        *,
        project_key: str,
        drivers: list[dict[str, Any]],
        logic_changes: dict[str, Any],
        duration_changes: dict[str, Any],
        milestone_impacts: dict[str, Any],
    ) -> dict[str, Any]:
        base = f"/api/projects/{project_key}/schedule/drivers"
        return {
            "drivers": {
                "count": len(drivers),
                "default_limit": _DRIVER_PREVIEW,
                "items": drivers[:_DRIVER_PREVIEW],
                "drilldown_url": f"{base}?type=drivers",
            },
            "impacted_successors": {
                "count": sum(int(d.get("downstream_moved_later_count") or 0) for d in drivers[:1]),
                "default_limit": _SUCCESSOR_PREVIEW,
                "items": (drivers[0].get("impacted_successors_preview") or []) if drivers else [],
                "drilldown_url": f"{base}?type=impacted_successors&driver_activity_id={(drivers[0].get('activity_id') if drivers else '')}",
            },
            "logic_changes": {
                "count": logic_changes.get("summary", {}).get("total_count", 0),
                "default_limit": _LOGIC_PREVIEW,
                "items": logic_changes.get("items") or [],
                "drilldown_url": f"{base}?type=logic_changes",
            },
            "duration_changes": {
                "count": duration_changes.get("summary", {}).get("total_count", 0),
                "default_limit": _DURATION_PREVIEW,
                "items": duration_changes.get("items") or [],
                "drilldown_url": f"{base}?type=duration_changes",
            },
            "milestone_impacts": {
                "count": milestone_impacts.get("summary", {}).get("total_count", 0),
                "default_limit": _MILESTONE_PREVIEW,
                "items": milestone_impacts.get("items") or [],
                "drilldown_url": f"{base}?type=milestone_impacts",
            },
        }

    def _page(
        self, drilldown_type: str, items: list[dict[str, Any]], total: int, limit: int, offset: int
    ) -> dict[str, Any]:
        return {
            "available": True,
            "drilldown_type": drilldown_type,
            "count": total,
            "limit": limit,
            "offset": offset,
            "items": items,
            "advisory_posture": _ADVISORY_POSTURE,
        }

    def _unavailable(self, reason: str, *, comparison_basis: str = "prior_update") -> dict[str, Any]:
        return {
            "available": False,
            "reason": reason,
            "comparison_basis": comparison_basis,
            "comparison_finish_basis": "resolved_finish_date",
            "advisory_posture": _ADVISORY_POSTURE,
            "summary": {},
            "top_drivers": [],
            "logic_changes": {"available": False, "summary": {}, "items": []},
            "duration_changes": {"available": False, "summary": {}, "items": []},
            "milestone_impacts": {"available": False, "summary": {}, "items": []},
            "review_drilldowns": {},
            "_all_drivers": [],
        }