"""PM-facing Schedule Controls analytics — composes existing schedule intelligence."""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import urlencode

from hb_assistant.store.schedule_cpm_import_observability_repository import (
    ScheduleCpmImportObservabilityRepository,
)

from .project_schedule_baseline_vocabulary import (
    comparison_label_for_basis,
    is_named_baseline_basis,
    label_for_slot,
    normalize_controls_comparison_basis,
    slot_key_for_basis,
)
from .project_schedule_named_baseline_service import ProjectScheduleNamedBaselineService
from .project_schedule_narrative_qa import validate_controls_text
from .project_schedule_review_cue_taxonomy import taxonomy_for_item_type
from .project_schedule_review_service import ProjectScheduleReviewService
from .project_schedule_summary_service import ProjectScheduleSummaryService
from .project_schedule_visualization_metric_contract import NON_CAUSATION_CAVEAT

_ADVISORY_POSTURE = "sequence_cues_not_causation"
_TOP_CONTROLS_LIMIT = 8
_SEVERITY_RANK = {"critical": 4, "review": 3, "watch": 2, "info": 1}
_CONFIDENCE_RANK = {"high": 3, "medium": 2, "low": 1}

_CATEGORY_FROM_CUE: dict[str, str] = {
    "change_driver": "critical_path",
    "milestone_movement": "movement",
    "float_pressure": "float",
    "float_erosion": "float",
    "critical_path": "critical_path",
    "execution_reliability": "execution",
    "start_reliability": "execution",
    "finish_reliability": "execution",
    "issue_category": "quality",
    "period_movement": "movement",
    "schedule_quality": "quality",
    "compression_readiness": "quality",
    "metric_readiness": "quality",
    "schedule_review": "review",
}


class ProjectScheduleControlsService:
    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path
        self._summary = ProjectScheduleSummaryService(db_path=db_path)
        self._review = ProjectScheduleReviewService(db_path=db_path)
        self._cpm_obs = ScheduleCpmImportObservabilityRepository(db_path=db_path)
        self._named_baselines = ProjectScheduleNamedBaselineService(db_path=db_path)

    def build_controls(
        self,
        project_key: str,
        *,
        as_of: date | None = None,
        comparison_basis: str = "prior_update",
    ) -> dict[str, Any]:
        basis = normalize_controls_comparison_basis(comparison_basis)
        baseline_context = self._baseline_context_for_basis(project_key, basis=basis, as_of=as_of)
        include_workbench_links = basis in {"prior_update", "baseline"}
        preview_basis = basis
        named_resolution: dict[str, Any] | None = None

        if is_named_baseline_basis(basis):
            slot_key = str(slot_key_for_basis(basis))
            named_resolution = self._named_baselines.resolve_slot_for_controls(
                project_key, slot_key=slot_key, as_of=as_of
            )
            status = str(named_resolution.get("selection_status") or "missing")
            baseline_context = self._baseline_context_from_resolution(basis=basis, resolution=named_resolution)
            if status == "missing":
                return self._unavailable(
                    project_key,
                    reason="baseline_not_selected",
                    comparison_basis=basis,
                    as_of=as_of,
                    baseline_context=baseline_context,
                )
            if status == "invalid":
                return self._unavailable(
                    project_key,
                    reason="baseline_invalid",
                    comparison_basis=basis,
                    as_of=as_of,
                    baseline_context=baseline_context,
                )
            context = self._summary.build_schedule_hub_context_with_named_baseline(
                project_key,
                as_of=as_of,
                baseline_version_key=str(named_resolution.get("schedule_version_key") or ""),
            )
            preview_basis = "baseline"
            include_workbench_links = status == "selected"
        else:
            context = self._summary.build_schedule_hub_context(project_key, as_of=as_of)

        if not context:
            return self._unavailable(
                project_key,
                reason="no_schedule",
                comparison_basis=basis,
                as_of=as_of,
                baseline_context=baseline_context,
            )

        baseline_summary = context.get("baseline_summary") or {}
        if basis == "baseline" and not self._legacy_baseline_available(baseline_summary):
            return self._unavailable(
                project_key,
                reason=str(baseline_summary.get("reason") or "baseline_unavailable"),
                comparison_basis=basis,
                as_of=as_of,
                schedule_version_key=str(context.get("schedule_version_key") or ""),
                baseline_context=baseline_context,
            )

        as_of_date = context.get("as_of_date") or datetime.now(timezone.utc).date()
        schedule_data_date = str(context.get("schedule_data_date") or "")
        schedule_version_key = str(context.get("schedule_version_key") or "")

        workbench = self._review.build_preview(
            project_key=project_key,
            schedule_version_key=schedule_version_key,
            driver_analysis=context.get("driver_analysis"),
            milestones=context.get("milestones"),
            remaining_health=context.get("remaining_health"),
            cpm_summary=context.get("cpm_summary"),
            change_impact=context.get("change_impact"),
            remaining_activities=context.get("remaining_activities"),
            comparison_basis=preview_basis,
            as_of_date=as_of_date,
            baseline_summary=baseline_summary,
            include_activity_metric_cues=True,
        )

        cpm_obs_row = self._cpm_obs.get_latest_for_schedule_version(schedule_version_key)
        remaining_health = context.get("remaining_health") or {}
        change_impact = context.get("change_impact") or {}
        cpm_summary = context.get("cpm_summary") or {}
        direct = (
            change_impact.get("direct_remaining_changes", {}).get("summary", {})
            if change_impact.get("available")
            else {}
        )
        wb_summary = workbench.get("summary") or {}
        comparison_label = comparison_label_for_basis(basis)

        sections = self._build_sections(
            direct=direct,
            remaining_health=remaining_health,
            cpm_summary=cpm_summary,
            cpm_obs_row=cpm_obs_row,
            wb_summary=wb_summary,
            comparison_basis=basis,
        )
        top_controls = self._build_top_controls(
            project_key=project_key,
            items=workbench.get("items") or [],
            schedule_version_key=schedule_version_key,
            schedule_data_date=schedule_data_date,
            as_of_date=as_of_date,
            comparison_basis=basis,
            include_workbench_links=include_workbench_links,
            comparison_label=comparison_label,
        )
        overall = self._overall_summary(
            remaining_health=remaining_health,
            wb_summary=wb_summary,
            cpm_obs_row=cpm_obs_row,
            direct=direct,
            top_controls=top_controls,
            comparison_label=comparison_label,
        )

        if is_named_baseline_basis(basis) and named_resolution:
            baseline_context = self._baseline_context_from_resolution(basis=basis, resolution=named_resolution)

        as_of_str = as_of_date.isoformat() if isinstance(as_of_date, date) else str(as_of_date)
        payload: dict[str, Any] = {
            "available": True,
            "reason": None,
            "project_key": project_key,
            "schedule_version_key": schedule_version_key,
            "schedule_data_date": schedule_data_date or None,
            "as_of_date": as_of_str,
            "comparison_basis": basis,
            "baseline_context": baseline_context,
            "advisory_posture": _ADVISORY_POSTURE,
            "summary": overall,
            "sections": sections,
            "top_controls": top_controls,
            "provenance": self._provenance(
                context, cpm_obs_row, top_controls, comparison_label=comparison_label
            ),
            "links": self._links(
                project_key,
                as_of_str=as_of_str,
                comparison_basis=basis,
                include_workbench_link=include_workbench_links,
            ),
        }
        qa = validate_controls_text(payload)
        payload["controls_language_qa"] = qa
        return payload

    def _unavailable(
        self,
        project_key: str,
        *,
        reason: str,
        comparison_basis: str,
        as_of: date | None,
        schedule_version_key: str = "",
        baseline_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        as_of_date = as_of or datetime.now(timezone.utc).date()
        include_workbench_link = comparison_basis in {"prior_update", "baseline"} or (
            is_named_baseline_basis(comparison_basis) and str(baseline_context.get("selection_status")) == "selected"
        )
        return {
            "available": False,
            "reason": reason,
            "project_key": project_key,
            "schedule_version_key": schedule_version_key or None,
            "schedule_data_date": None,
            "as_of_date": as_of_date.isoformat(),
            "comparison_basis": comparison_basis,
            "baseline_context": baseline_context
            or self._baseline_context_for_basis(project_key, basis=comparison_basis, as_of=as_of),
            "advisory_posture": _ADVISORY_POSTURE,
            "summary": {
                "overall_status": "unknown",
                "headline": "Schedule controls are unavailable for the selected context.",
                "supporting_points": [reason.replace("_", " ")],
                "primary_review_focus": None,
                "open_review_item_count": None,
                "high_priority_review_item_count": None,
            },
            "sections": {},
            "top_controls": [],
            "provenance": {"source_services": ["project_schedule_controls_service"]},
            "links": self._links(
                project_key,
                as_of_str=as_of_date.isoformat(),
                comparison_basis=comparison_basis,
                include_workbench_link=include_workbench_link,
            ),
        }

    def _build_sections(
        self,
        *,
        direct: dict[str, Any],
        remaining_health: dict[str, Any],
        cpm_summary: dict[str, Any],
        cpm_obs_row: dict[str, Any] | None,
        wb_summary: dict[str, Any],
        comparison_basis: str,
    ) -> dict[str, Any]:
        float_pressure = remaining_health.get("float_pressure") or {}
        cpm_sum = cpm_summary.get("summary") or {}
        return {
            "movement": {
                "available": bool(direct),
                "headline": "Schedule movement since comparison context",
                "finish_moved_later_count": int(direct.get("finish_moved_later_count") or 0),
                "finish_moved_earlier_count": int(direct.get("finish_moved_earlier_count") or 0),
                "worsened_float_count": int(direct.get("worsened_float_count") or 0),
                "comparison_basis": comparison_basis,
            },
            "critical_path": {
                "available": bool(cpm_sum.get("available")),
                "critical_remaining_count": int(cpm_sum.get("critical_remaining_count") or 0),
                "near_critical_remaining_count": int(cpm_sum.get("near_critical_remaining_count") or 0),
                "headline": "Critical-path and near-critical remaining work indicators",
            },
            "float": {
                "available": True,
                "negative_float_count": int(float_pressure.get("negative_float_count") or 0),
                "zero_float_count": int(float_pressure.get("zero_float_count") or 0),
                "near_critical_count": int(float_pressure.get("near_critical_count") or 0),
                "headline": "Remaining float pressure indicators",
            },
            "execution": {
                "available": True,
                "headline": "Execution reliability cues are surfaced via review signals when metric data is ready.",
                "note": "See top controls for should-have-finished and window accuracy cues.",
            },
            "quality": {
                "available": True,
                "headline": "Schedule quality findings appear as review cues when evaluations are available.",
            },
            "cpm_observability": self._cpm_observability_section(cpm_obs_row),
            "review_workbench": {
                "available": True,
                "open_review_item_count": int(wb_summary.get("open_count") or 0),
                "watching_count": int(wb_summary.get("watching_count") or 0),
                "headline": "Review workbench preview counts for the selected comparison basis.",
                "comparison_basis": comparison_basis,
                "read_only_baseline_preview": comparison_basis == "baseline" or is_named_baseline_basis(comparison_basis),
            },
        }

    def _cpm_observability_section(self, row: dict[str, Any] | None) -> dict[str, Any]:
        if not row:
            return {
                "available": False,
                "headline": "No CPM observability record found for this schedule version.",
                "status_summary": "not_found",
            }
        status = str(row.get("status") or "unknown")
        warnings = int(row.get("warning_count") or 0)
        errors = int(row.get("error_count") or 0)
        if status == "failed":
            summary = "CPM recompute failed for the selected schedule version."
            severity = "critical"
        elif errors > 0:
            summary = "CPM recompute completed with errors."
            severity = "review"
        elif warnings > 0:
            summary = "CPM recompute completed with warnings."
            severity = "watch"
        else:
            summary = "CPM recompute succeeded for the selected schedule version."
            severity = "info"
        return {
            "available": True,
            "headline": summary,
            "status_summary": status,
            "severity": severity,
            "warning_count": warnings,
            "error_count": errors,
            "technical_evidence": {
                "cpm_run_id": row.get("cpm_run_id"),
                "import_id": row.get("import_id"),
                "package_id": row.get("package_id"),
                "trigger_source": row.get("trigger_source"),
                "canonical_input_activity_count": row.get("canonical_input_activity_count"),
                "canonical_input_relationship_count": row.get("canonical_input_relationship_count"),
                "graph_node_count": row.get("graph_node_count"),
                "graph_edge_count": row.get("graph_edge_count"),
                "failure_code": row.get("failure_code"),
            },
        }

    def _build_top_controls(
        self,
        *,
        project_key: str,
        items: list[dict[str, Any]],
        schedule_version_key: str,
        schedule_data_date: str,
        as_of_date: date,
        comparison_basis: str,
        include_workbench_links: bool = True,
        comparison_label: str | None = None,
    ) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        as_of_str = as_of_date.isoformat()
        for item in items:
            if str(item.get("review_status") or "open") not in {"open", "watching"}:
                continue
            item_type = str(item.get("item_type") or "schedule_review")
            taxonomy = taxonomy_for_item_type(item_type)
            cue_category = str(item.get("cue_category") or taxonomy.get("cue_category") or "schedule_review")
            category = _CATEGORY_FROM_CUE.get(cue_category, "review")
            activity_id = item.get("source_activity_id")
            activity_name = item.get("activity_name") or item.get("evidence", {}).get("activity_name")
            title = str(item.get("cue_label") or taxonomy.get("cue_label") or "Schedule review signal")
            if activity_name:
                title = f"{title}: {activity_name}"
            summary = str(
                item.get("cue_summary")
                or item.get("evidence", {}).get("cue_summary")
                or item.get("evidence_summary")
                or "Sequence cue for PM review."
            )
            if comparison_label:
                summary = f"{comparison_label}. {summary}"
            recommended = str(
                item.get("recommended_review_action")
                or item.get("evidence", {}).get("recommended_review_action")
                or taxonomy.get("recommended_review_action")
                or "Review the linked schedule evidence and record PM disposition when appropriate."
            )
            caveats = list(item.get("caveats") or item.get("evidence", {}).get("caveats") or [])
            if NON_CAUSATION_CAVEAT not in caveats:
                caveats = [*caveats, NON_CAUSATION_CAVEAT]
            severity = self._map_review_severity(item.get("severity"))
            confidence = self._map_confidence(item.get("confidence"))
            stable_key = str(item.get("stable_item_key") or "")
            control_id = stable_key or self._control_id(
                schedule_version_key=schedule_version_key,
                category=category,
                source_metric_key=str(item.get("source_metric_key") or item_type),
                activity_id=str(activity_id or ""),
                comparison_basis=comparison_basis,
            )
            links: dict[str, str | None] = {
                "review_item": None,
                "driver_detail": None,
                "schedule_hub": f"/projects/{project_key}/schedule",
            }
            if include_workbench_links and stable_key:
                params = {"review": stable_key, "comparison_basis": comparison_basis}
                if as_of_str:
                    params["as_of"] = as_of_str
                links["review_item"] = f"/projects/{project_key}/schedule/workbench?{urlencode(params)}"
            if include_workbench_links and activity_id:
                params = {"basis": comparison_basis}
                if as_of_str:
                    params["as_of"] = as_of_str
                links["driver_detail"] = (
                    f"/projects/{project_key}/schedule/drivers/{activity_id}?{urlencode(params)}"
                )
            candidates.append(
                {
                    "control_id": control_id,
                    "category": category,
                    "severity": severity,
                    "confidence": confidence,
                    "title": title,
                    "summary": summary,
                    "why_it_matters": "This signal highlights schedule movement or data-quality context that may need PM review.",
                    "recommended_action": recommended,
                    "comparison_basis": comparison_basis,
                    "source_metric_key": str(item.get("source_metric_key") or item_type),
                    "source_signal_type": str(item.get("source_signal_type") or item_type),
                    "schedule_version_key": schedule_version_key,
                    "schedule_data_date": schedule_data_date or None,
                    "as_of": as_of_str,
                    "activity_id": activity_id,
                    "activity_name": activity_name,
                    "wbs_code": item.get("wbs_code"),
                    "review_item_id": item.get("review_item_id"),
                    "links": links,
                    "caveats": caveats,
                    "data_quality_notes": list(item.get("data_quality_notes") or []),
                    "_priority": int(item.get("priority") or 0),
                }
            )

        candidates.sort(
            key=lambda row: (
                -_SEVERITY_RANK.get(str(row.get("severity")), 0),
                -_CONFIDENCE_RANK.get(str(row.get("confidence")), 0),
                -int(row.get("_priority") or 0),
                str(row.get("title") or ""),
            )
        )
        out = []
        for row in candidates[:_TOP_CONTROLS_LIMIT]:
            cleaned = {k: v for k, v in row.items() if k != "_priority"}
            out.append(cleaned)
        return out

    def _overall_summary(
        self,
        *,
        remaining_health: dict[str, Any],
        wb_summary: dict[str, Any],
        cpm_obs_row: dict[str, Any] | None,
        direct: dict[str, Any],
        top_controls: list[dict[str, Any]],
        comparison_label: str | None = None,
    ) -> dict[str, Any]:
        open_count = int(wb_summary.get("open_count") or 0)
        high_priority = sum(1 for c in top_controls if c.get("severity") in {"critical", "review"})
        health = str(remaining_health.get("status") or "unknown")
        neg_float = int((remaining_health.get("float_pressure") or {}).get("negative_float_count") or 0)
        later = int(direct.get("finish_moved_later_count") or 0)

        if health == "blocked" or (cpm_obs_row and str(cpm_obs_row.get("status")) == "failed"):
            overall_status = "critical"
            headline = "Schedule controls indicate critical review is needed before relying on comparisons."
        elif open_count > 0 or high_priority >= 3 or neg_float >= 5:
            overall_status = "review"
            headline = "Schedule controls recommend PM review of priority sequence and float signals."
        elif health in {"at_risk", "watch"} or later > 0 or neg_float > 0:
            overall_status = "watch"
            headline = "Schedule controls show movement or float pressure worth monitoring."
        elif health == "good":
            overall_status = "healthy"
            headline = "Schedule controls show stable remaining-work indicators for the selected context."
        else:
            overall_status = "unknown"
            headline = "Schedule controls are available with limited comparison context."

        supporting: list[str] = []
        if comparison_label:
            supporting.append(comparison_label)
        if later:
            supporting.append(f"{later} remaining activities moved later in the comparison window.")
        if neg_float:
            supporting.append(f"{neg_float} remaining activities show negative float.")
        if open_count:
            supporting.append(f"{open_count} open review workbench cues in the selected basis.")
        if not supporting:
            supporting.append("Review top controls for sequence cues and data-quality follow-up.")

        primary_focus = None
        if top_controls:
            primary_focus = str(top_controls[0].get("title") or "")

        return {
            "overall_status": overall_status,
            "headline": headline,
            "supporting_points": supporting[:4],
            "primary_review_focus": primary_focus,
            "open_review_item_count": open_count,
            "high_priority_review_item_count": high_priority,
        }

    def _provenance(
        self,
        context: dict[str, Any],
        cpm_obs_row: dict[str, Any] | None,
        top_controls: list[dict[str, Any]],
        comparison_label: str | None = None,
    ) -> dict[str, Any]:
        metric_keys = sorted({str(c.get("source_metric_key")) for c in top_controls if c.get("source_metric_key")})
        return {
            "source_services": [
                "project_schedule_summary_service",
                "project_schedule_review_service",
                "schedule_cpm_import_observability_repository",
            ],
            "source_metric_keys": metric_keys,
            "cpm_run_id": (cpm_obs_row or {}).get("cpm_run_id"),
            "import_id": (cpm_obs_row or {}).get("import_id"),
            "package_id": (cpm_obs_row or {}).get("package_id"),
            "canonical_input_activity_count": (cpm_obs_row or {}).get("canonical_input_activity_count"),
            "canonical_input_relationship_count": (cpm_obs_row or {}).get(
                "canonical_input_relationship_count"
            ),
            "schedule_version_key": context.get("schedule_version_key"),
            "comparison_label": comparison_label,
        }

    @staticmethod
    def _links(
        project_key: str,
        *,
        as_of_str: str,
        comparison_basis: str,
        include_workbench_link: bool = True,
    ) -> dict[str, str]:
        params: dict[str, str] = {"comparison_basis": comparison_basis}
        if as_of_str:
            params["as_of"] = as_of_str
        qs = urlencode(params)
        links = {
            "schedule_hub": f"/projects/{project_key}/schedule",
            "export": f"/api/projects/{project_key}/schedule/export?format=markdown&{qs}",
        }
        if include_workbench_link:
            links["review_workbench"] = f"/projects/{project_key}/schedule/workbench?{qs}"
        return links

    @staticmethod
    def _legacy_baseline_available(baseline_summary: dict[str, Any]) -> bool:
        return bool(
            baseline_summary.get("available")
            or baseline_summary.get("selected_baseline_available")
            or baseline_summary.get("_selected_baseline_schedule_version_key")
        )

    def _baseline_context_for_basis(
        self,
        project_key: str,
        *,
        basis: str,
        as_of: date | None,
    ) -> dict[str, Any]:
        if basis == "prior_update":
            return {"basis": "prior_update", "selection_status": "not_applicable"}
        if is_named_baseline_basis(basis):
            slot_key = str(slot_key_for_basis(basis))
            resolution = self._named_baselines.resolve_slot_for_controls(
                project_key, slot_key=slot_key, as_of=as_of
            )
            return self._baseline_context_from_resolution(basis=basis, resolution=resolution)
        if basis == "baseline":
            return {"basis": "baseline", "selection_status": "not_applicable"}
        return {"basis": basis, "selection_status": "not_applicable"}

    @staticmethod
    def _baseline_context_from_resolution(
        *,
        basis: str,
        resolution: dict[str, Any],
    ) -> dict[str, Any]:
        slot_key = str(resolution.get("slot_key") or basis)
        status = str(resolution.get("selection_status") or "missing")
        context: dict[str, Any] = {
            "basis": basis,
            "slot_key": slot_key,
            "slot_label": resolution.get("slot_label") or label_for_slot(slot_key),
            "selection_status": status,
        }
        if status == "selected":
            context.update(
                {
                    "baseline_schedule_version_key": resolution.get("schedule_version_key"),
                    "baseline_schedule_data_date": resolution.get("schedule_data_date"),
                    "baseline_display_name": resolution.get("display_name"),
                    "selected_at": resolution.get("selected_at"),
                    "selected_by": resolution.get("selected_by"),
                    "notes": resolution.get("notes"),
                }
            )
        return context


    @staticmethod
    def _control_id(
        *,
        schedule_version_key: str,
        category: str,
        source_metric_key: str,
        activity_id: str,
        comparison_basis: str,
    ) -> str:
        raw = "|".join([schedule_version_key, category, source_metric_key, activity_id, comparison_basis])
        digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
        return f"ctrl-{digest}"

    @staticmethod
    def _map_review_severity(value: Any) -> str:
        token = str(value or "medium").lower()
        if token == "critical":
            return "critical"
        if token == "high":
            return "review"
        if token == "medium":
            return "watch"
        return "info"

    @staticmethod
    def _map_confidence(value: Any) -> str:
        token = str(value or "").lower()
        if token == "production_backed":
            return "high"
        if token == "partial_dimension_support":
            return "medium"
        return "low"
