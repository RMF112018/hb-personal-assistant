"""PM-facing Schedule Controls analytics — composes existing schedule intelligence."""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import urlencode

from hb_assistant.store.schedule_cpm_import_observability_repository import (
    ScheduleCpmImportObservabilityRepository,
)
from hb_assistant.store.schedule_quality_repository import ScheduleQualityRepository

from .project_schedule_identity_trust_service import build_identity_trust_from_hub
from .project_schedule_quality_controls_service import (
    ProjectScheduleQualityControlsService,
    pm_quality_controls_payload,
)
from .project_schedule_baseline_vocabulary import (
    comparison_label_for_basis,
    is_named_baseline_basis,
    label_for_slot,
    normalize_controls_comparison_basis,
    validate_controls_comparison_basis,
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
        self._quality_repo = ScheduleQualityRepository(db_path=db_path)
        self._quality_controls = ProjectScheduleQualityControlsService(db_path=db_path)
        self._named_baselines = ProjectScheduleNamedBaselineService(db_path=db_path)
        self._named_review: Any = None

    @property
    def _named_baseline_review(self) -> Any:
        if self._named_review is None:
            from .project_schedule_named_baseline_review_service import (
                ProjectScheduleNamedBaselineReviewService,
            )

            self._named_review = ProjectScheduleNamedBaselineReviewService(db_path=self._db_path)
        return self._named_review

    def build_controls(
        self,
        project_key: str,
        *,
        as_of: date | None = None,
        comparison_basis: str = "prior_update",
        include_technical: bool = False,
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
                comparison_basis=basis,
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

        if is_named_baseline_basis(basis):
            scope = self._named_baseline_review.scope_from_context(
                project_key=project_key,
                current_schedule_version_key=schedule_version_key,
                comparison_basis=basis,
                baseline_context=baseline_context or {},
                as_of_date=as_of_date,
                schedule_data_date=schedule_data_date or None,
            )
            workbench = self._named_baseline_review.build_preview(
                scope=scope,
                driver_analysis=context.get("driver_analysis"),
                milestones=context.get("milestones"),
                remaining_health=context.get("remaining_health"),
                cpm_summary=context.get("cpm_summary"),
                change_impact=context.get("change_impact"),
                remaining_activities=context.get("remaining_activities"),
                as_of_date=as_of_date,
                baseline_summary=baseline_summary,
                comparison_basis=basis,
            )
        else:
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
                response_comparison_basis=basis,
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
        wb_summary = workbench.get("review_status") or workbench.get("summary") or {}
        comparison_label = comparison_label_for_basis(basis)

        analytics_trust = context.get("analytics_trust") or self._controls_analytics_trust(
            project_key=project_key,
            schedule_version_key=schedule_version_key,
            context=context,
            cpm_obs_row=cpm_obs_row,
            project_display_name=str(context.get("project_display_name") or project_key),
        )
        identity_trust = analytics_trust.get("identity_trust") or {}

        quality_controls = self._quality_controls.build_quality_controls(
            schedule_version_key,
            analytics_trust=analytics_trust,
            identity_trust=identity_trust,
            cpm_observability=cpm_obs_row,
        )

        sections = self._build_sections(
            direct=direct,
            remaining_health=remaining_health,
            cpm_summary=cpm_summary,
            cpm_obs_row=cpm_obs_row,
            wb_summary=wb_summary,
            comparison_basis=basis,
            identity_trust=identity_trust,
            analytics_trust=analytics_trust,
            quality_controls=quality_controls,
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
            quality_controls=quality_controls,
        )
        overall = self._overall_summary(
            remaining_health=remaining_health,
            wb_summary=wb_summary,
            cpm_obs_row=cpm_obs_row,
            direct=direct,
            top_controls=top_controls,
            comparison_label=comparison_label,
            quality_controls=quality_controls,
            identity_trust=identity_trust,
            analytics_trust=analytics_trust,
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
            "analytics_trust": analytics_trust,
            "identity_trust": identity_trust,
            "quality_controls": pm_quality_controls_payload(quality_controls),
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
        if include_technical:
            payload["technical"] = {
                "schedule_version_key": schedule_version_key,
                "quality_controls": quality_controls,
                "cpm_observability": sections.get("cpm_observability", {}).get("technical_evidence"),
            }
        else:
            cpm_section = dict(sections.get("cpm_observability") or {})
            cpm_section.pop("technical_evidence", None)
            sections["cpm_observability"] = cpm_section
            payload["sections"] = sections
            payload["top_controls"] = [self._pm_top_control(row) for row in top_controls]
            payload.pop("schedule_version_key", None)
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

    def _controls_analytics_trust(
        self,
        *,
        project_key: str,
        schedule_version_key: str,
        context: dict[str, Any],
        cpm_obs_row: dict[str, Any] | None,
        project_display_name: str = "",
    ) -> dict[str, Any]:
        from .project_schedule_analytics_trust_service import (
            ledger_for_hub_version,
            map_committed_cpm_status,
            map_committed_identity_status,
            normalize_quality_status,
        )
        from .schedule_cpm_read_service import ScheduleCpmReadService

        quality_run = self._quality_repo.get_latest_run(schedule_version_key)
        quality_status = normalize_quality_status(
            str(quality_run.get("status")) if quality_run else None,
            committed=True,
        )
        cpm_read = ScheduleCpmReadService(db_path=self._db_path).cpm_summary(schedule_version_key)
        cpm_status = map_committed_cpm_status(cpm_read, observability=cpm_obs_row)
        membership_status = (context.get("schedule_trust") or {}).get("current_membership_status")
        identity_trust = build_identity_trust_from_hub(
            project_display_name=project_display_name or None,
            schedule_trust=context.get("schedule_trust"),
            identity_review=context.get("identity_review"),
            current_schedule=context.get("current_schedule"),
            identity_match=None,
            membership={"membership_status": membership_status} if membership_status else None,
        )
        identity_status = map_committed_identity_status(
            {"membership_status": membership_status} if membership_status else None
        )
        return ledger_for_hub_version(
            quality_status=quality_status,
            cpm_status=cpm_status,
            identity_status=identity_status,
            identity_membership_status=membership_status,
            cpm_observability=cpm_obs_row,
            identity_trust=identity_trust,
            canonical_activity_count=int((context.get("current_schedule") or {}).get("activity_count") or 0)
            or None,
            canonical_relationship_count=int(
                (context.get("current_schedule") or {}).get("relationship_count") or 0
            )
            or None,
            source_format=str((context.get("current_schedule") or {}).get("source_format") or "") or None,
        )

    def _build_sections(
        self,
        *,
        direct: dict[str, Any],
        remaining_health: dict[str, Any],
        cpm_summary: dict[str, Any],
        cpm_obs_row: dict[str, Any] | None,
        wb_summary: dict[str, Any],
        comparison_basis: str,
        identity_trust: dict[str, Any] | None = None,
        analytics_trust: dict[str, Any] | None = None,
        quality_controls: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        float_pressure = remaining_health.get("float_pressure") or {}
        cpm_sum = cpm_summary.get("summary") or {}
        identity = identity_trust or {}
        identity_status = str(identity.get("identity_trust_status") or "unavailable")
        identity_headline = str(
            identity.get("pm_message") or "Schedule identity trust gates comparison analytics."
        )
        quality = quality_controls or {}
        scorecard = quality.get("scorecard") or {}
        analytics = analytics_trust or {}
        quality_groups = {
            g.get("group_key"): g for g in quality.get("control_groups") or [] if g.get("group_key")
        }
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
                "available": bool(quality),
                "headline": "Schedule quality scorecard and control groups for PM review.",
                "quality_trust_status": quality.get("quality_trust_status"),
                "quality_run_status": quality.get("quality_run_status"),
                "overall_score": scorecard.get("overall_score"),
                "quality_grade": scorecard.get("quality_grade"),
                "groups": [
                    {
                        "group_key": g.get("group_key"),
                        "label": g.get("label"),
                        "status": g.get("status"),
                        "summary": g.get("summary"),
                    }
                    for g in quality.get("control_groups") or []
                    if g.get("group_key") != "capability_limitations"
                ],
            },
            "analytics_trust": {
                "available": True,
                "analytics_trust_status": analytics.get("analytics_trust_status"),
                "identity_gate": analytics.get("identity_gate") or identity.get("identity_gate"),
                "headline": "Analytics trust reflects import, quality, CPM, and identity readiness.",
                "trust_reasons": (analytics.get("trust_reasons") or [])[:6],
                "capability_limitations": (analytics.get("capability_limitations") or [])[:4],
                "failure_message_redacted": analytics.get("failure_message_redacted"),
            },
            "logic_integrity": self._quality_group_section(quality_groups.get("logic_integrity")),
            "constraints": self._quality_group_section(quality_groups.get("constraint_quality")),
            "float_quality": self._quality_group_section(quality_groups.get("float_quality")),
            "duration_quality": self._quality_group_section(quality_groups.get("duration_quality")),
            "date_quality": self._quality_group_section(quality_groups.get("date_quality")),
            "critical_path_readiness": self._quality_group_section(
                quality_groups.get("critical_path_readiness")
            ),
            "cost_resource_readiness": self._quality_group_section(
                quality_groups.get("cost_resource_readiness")
            ),
            "baseline_readiness": self._quality_group_section(quality_groups.get("baseline_readiness")),
            "capability_limitations": {
                "available": True,
                "headline": "Known capability limitations (not schedule defects).",
                "items": quality.get("capability_limitations") or [],
                "group": quality_groups.get("capability_limitations"),
            },
            "identity_trust": {
                "available": True,
                "identity_trust_status": identity_status,
                "identity_gate": identity.get("identity_gate"),
                "headline": identity_headline,
                "safe_schedule_label": identity.get("safe_schedule_label"),
                "operator_action_required": identity.get("operator_action_required"),
            },
            "cpm_observability": self._cpm_observability_section(cpm_obs_row),
            "review_workbench": {
                "available": True,
                "open_review_item_count": int(wb_summary.get("needs_review") or wb_summary.get("open_count") or 0),
                "watching_count": int(wb_summary.get("watching_count") or 0),
                "review_status": wb_summary,
                "headline": str(wb_summary.get("pm_summary") or "Review workbench status for the selected comparison basis."),
                "recommended_next_action": wb_summary.get("recommended_next_action"),
                "comparison_basis": comparison_basis,
                "read_only_baseline_preview": comparison_basis == "baseline" or is_named_baseline_basis(comparison_basis),
            },
        }

    @staticmethod
    def _quality_group_section(group: dict[str, Any] | None) -> dict[str, Any]:
        if not group:
            return {"available": False, "headline": "Quality group data is not available."}
        return {
            "available": True,
            "group_key": group.get("group_key"),
            "label": group.get("label"),
            "status": group.get("status"),
            "headline": group.get("summary"),
            "metrics": group.get("metrics") or [],
        }

    @staticmethod
    def _pm_top_control(row: dict[str, Any]) -> dict[str, Any]:
        cleaned = dict(row)
        for key in (
            "schedule_version_key",
            "activity_id",
            "review_item_id",
            "source_metric_key",
            "source_signal_type",
        ):
            cleaned.pop(key, None)
        return cleaned

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
        quality_controls: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        as_of_str = as_of_date.isoformat()
        for finding in (quality_controls or {}).get("top_findings") or []:
            code = str(finding.get("finding_code") or "quality_finding")
            severity = self._map_review_severity(finding.get("severity"))
            candidates.append(
                {
                    "control_id": f"quality:{code}",
                    "category": "quality",
                    "severity": severity,
                    "confidence": "high",
                    "title": f"Quality finding: {finding.get('summary') or code.replace('_', ' ')}",
                    "summary": str(finding.get("summary") or "Schedule quality finding for PM review."),
                    "why_it_matters": "Persisted quality findings may indicate schedule data issues worth review.",
                    "recommended_action": "Review the quality finding and confirm whether PM follow-up is needed.",
                    "comparison_basis": comparison_basis,
                    "source_metric_key": "schedule_quality_findings",
                    "source_signal_type": code,
                    "schedule_version_key": schedule_version_key,
                    "schedule_data_date": schedule_data_date or None,
                    "as_of": as_of_str,
                    "activity_id": None,
                    "activity_name": None,
                    "wbs_code": None,
                    "review_item_id": None,
                    "links": {
                        "review_item": f"/projects/{project_key}/schedule/workbench?{urlencode({'comparison_basis': comparison_basis, 'as_of': as_of_str})}",
                        "driver_detail": None,
                        "schedule_hub": f"/projects/{project_key}/schedule",
                    },
                    "caveats": [NON_CAUSATION_CAVEAT],
                    "data_quality_notes": [],
                    "_priority": 90 if severity in {"critical", "review"} else 70,
                }
            )
        for group in (quality_controls or {}).get("control_groups") or []:
            if group.get("group_key") == "capability_limitations":
                continue
            if group.get("status") not in {"degraded", "blocked"}:
                continue
            candidates.append(
                {
                    "control_id": f"quality-group:{group.get('group_key')}",
                    "category": "quality",
                    "severity": "review" if group.get("status") == "degraded" else "critical",
                    "confidence": "high",
                    "title": str(group.get("label") or "Schedule quality group"),
                    "summary": str(group.get("summary") or "Quality group requires PM review."),
                    "why_it_matters": "Grouped quality metrics highlight schedule readiness gaps for review.",
                    "recommended_action": "Review the quality control group metrics before relying on comparisons.",
                    "comparison_basis": comparison_basis,
                    "source_metric_key": "schedule_quality_scorecard",
                    "source_signal_type": str(group.get("group_key") or "quality_group"),
                    "schedule_version_key": schedule_version_key,
                    "schedule_data_date": schedule_data_date or None,
                    "as_of": as_of_str,
                    "activity_id": None,
                    "activity_name": None,
                    "wbs_code": None,
                    "review_item_id": None,
                    "links": {
                        "review_item": f"/projects/{project_key}/schedule/workbench?{urlencode({'comparison_basis': comparison_basis, 'as_of': as_of_str})}",
                        "driver_detail": None,
                        "schedule_hub": f"/projects/{project_key}/schedule",
                    },
                    "caveats": [NON_CAUSATION_CAVEAT],
                    "data_quality_notes": [],
                    "_priority": 75,
                }
            )
        from .project_schedule_review_disposition import DISPOSITION_NEEDS_REVIEW, is_open_disposition

        for item in items:
            if not is_open_disposition(str(item.get("review_status") or DISPOSITION_NEEDS_REVIEW)):
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
                params = {"activity_id": activity_id, "comparison_basis": comparison_basis}
                if as_of_str:
                    params["as_of"] = as_of_str
                links["driver_detail"] = (
                    f"/projects/{project_key}/schedule/driver-detail?{urlencode(params)}"
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
        quality_controls: dict[str, Any] | None = None,
        identity_trust: dict[str, Any] | None = None,
        analytics_trust: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        open_count = int(wb_summary.get("open_count") or 0)
        high_priority = sum(1 for c in top_controls if c.get("severity") in {"critical", "review"})
        health = str(remaining_health.get("status") or "unknown")
        neg_float = int((remaining_health.get("float_pressure") or {}).get("negative_float_count") or 0)
        later = int(direct.get("finish_moved_later_count") or 0)
        identity_gate = str((identity_trust or {}).get("identity_gate") or (analytics_trust or {}).get("identity_gate") or "ready")
        analytics_status = str((analytics_trust or {}).get("analytics_trust_status") or "ready")
        quality_status = str((quality_controls or {}).get("quality_trust_status") or "unavailable")

        if identity_gate == "blocked" or analytics_status == "blocked" or quality_status == "blocked":
            overall_status = "critical"
            headline = "Schedule controls are blocked by identity, analytics, or quality trust gates."
        elif health == "blocked" or (cpm_obs_row and str(cpm_obs_row.get("status")) == "failed"):
            overall_status = "critical"
            headline = "Schedule controls indicate critical review is needed before relying on comparisons."
        elif identity_gate == "degraded" or analytics_status == "degraded" or quality_status == "degraded":
            overall_status = "review"
            headline = "Schedule controls are degraded; review identity, analytics, and quality signals."
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
