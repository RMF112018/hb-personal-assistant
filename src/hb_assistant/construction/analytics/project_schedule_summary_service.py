"""PM-facing project Schedule Hub read model.

This service is deliberately read-only. It summarizes already-persisted schedule import,
identity, diff, activity, and CPM facts for the Project module Schedule Hub. It never imports,
recomputes CPM, computes new diffs, or mutates schedule source rows.
"""

from __future__ import annotations

import logging
import re
import time
from collections import Counter, deque
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from hb_assistant.store.connection import open_connection
from hb_assistant.store.project_schedule_hub_repository import ProjectScheduleHubRepository
from hb_assistant.store.schedule_identity_repository import ScheduleIdentityRepository
from hb_assistant.store.schedule_mapping_repository import ScheduleMappingRepository
from hb_assistant.store.schedule_import_repository import ScheduleImportRepository

from .project_schedule_comparison import (
    ProjectScheduleComparisonService,
    comparison_activity_movement,
    comparison_finish_field,
    comparison_finish_sql,
    comparison_start_field,
    label_from_source,
)
from .project_schedule_canonical_metrics import ProjectScheduleCanonicalMetricService
from .project_schedule_drilldown_service import ProjectScheduleDrilldownService
from .project_schedule_driver_analysis_service import ProjectScheduleDriverAnalysisService
from .project_schedule_memo_service import ProjectScheduleMemoService
from .project_schedule_narrative_qa import validate_summary as validate_schedule_narrative
from .project_schedule_review_service import ProjectScheduleReviewService
from .schedule_trust_service import ScheduleTrustService
from .schedule_import_service import ensure_schedule_schema

_RAW_KEY_PATTERN = re.compile(r"^[^|]+\|[^|]+\|.+$")
_FORBIDDEN_STORY_WORDS = (
    "caused the delay",
    "responsible for the delay",
    "compensable delay",
    "excusable delay",
    "contractor-caused",
    "owner-caused",
    "claim impact",
)
_LOG = logging.getLogger(__name__)
_SLOW_STAGE_MS = 250.0

_VERSION_CAP = 12
_TOP_ACTIONS_CAP = 5
_ALL_ACTIONS_CAP = 25
_TOP_IMPACTED_CAP = 10
_DIRECT_REMAINING_CHANGE_CAP = 10
_UPSTREAM_REMAINING_IMPACT_CAP = 10
_RECENT_COMPLETIONS_CAP = 10
_RECENT_STARTS_CAP = 10
_CRITICAL_PATH_PREVIEW_CAP = 20
_MILESTONE_CAP = 20
_REMAINING_SAMPLE_CAP = 25

_ACTIVITY_COLUMNS = """
    activity_id, activity_name, wbs_code, wbs_path, start_date, finish_date,
    actual_start, actual_finish, remaining_start, remaining_finish,
    remaining_early_start, remaining_early_finish, duration_original,
    duration_remaining, constraint_type, is_critical, is_milestone,
    total_float, derived_total_float_days, explicit_total_float_days,
    target_start, target_finish, baseline_start, baseline_finish
"""


@dataclass(frozen=True)
class _VersionChoice:
    version: dict[str, Any]
    identity_match: dict[str, Any] | None


class ProjectScheduleSummaryService:
    """Build the Project module Schedule Hub envelope."""

    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path
        self._identity = ScheduleIdentityRepository(db_path=db_path)
        self._mapping = ScheduleMappingRepository(db_path=db_path)
        self._hub_repo = ProjectScheduleHubRepository(db_path=db_path)
        self._trust = ScheduleTrustService(db_path=db_path)
        self._comparison = ProjectScheduleComparisonService(db_path=db_path)
        self._drilldowns = ProjectScheduleDrilldownService(db_path=db_path)
        self._drivers = ProjectScheduleDriverAnalysisService(db_path=db_path)
        self._review = ProjectScheduleReviewService(db_path=db_path)
        self._memo = ProjectScheduleMemoService()
        self._imports = ScheduleImportRepository(db_path=db_path)
        self._canonical_metrics = ProjectScheduleCanonicalMetricService(db_path=db_path)
        self._stage_timings: list[dict[str, Any]] = []
        self._named_review: Any = None

    @property
    def _named_baseline_review(self) -> Any:
        if self._named_review is None:
            from .project_schedule_named_baseline_review_service import (
                ProjectScheduleNamedBaselineReviewService,
            )

            self._named_review = ProjectScheduleNamedBaselineReviewService(db_path=self._db_path)
        return self._named_review

    def build_summary(self, project_key: str, *, as_of: date | None = None) -> dict[str, Any]:
        self._stage_timings = []
        ensure_schedule_schema(self._db_path)
        as_of_date = as_of or datetime.now(timezone.utc).date()
        project_name = self._timed(
            "project_display_lookup",
            project_key=project_key,
            fn=lambda: self._project_display_name(project_key),
        )
        versions = self._timed(
            "version_resolution",
            project_key=project_key,
            query_key="hub_project_versions",
            cap=_VERSION_CAP,
            fn=lambda: self._hub_project_versions(project_key),
        )
        if not versions:
            return self._empty_summary(project_key, project_name, as_of_date)

        current_choice = self._resolve_current(project_key, versions, as_of_date=as_of_date)
        if current_choice is None:
            return self._review_required_summary(project_key, project_name, as_of_date, versions)

        current = current_choice.version
        current_key = str(current["schedule_version_key"])
        current_label = self._friendly_label(current)
        current_data_date = self._data_date(current)
        previous_choice = self._resolve_previous(project_key, current_choice, versions)
        previous = previous_choice.version if previous_choice else None
        previous_key = str(previous["schedule_version_key"]) if previous else None
        previous_data_date = self._data_date(previous) if previous else None
        comparison_context = self._prior_update_comparison_context(
            current_choice=current_choice,
            previous_choice=previous_choice,
            as_of_date=as_of_date,
        )

        activity_summary = self._timed(
            "current_activity_summary",
            project_key=project_key,
            schedule_version_key=current_key,
            query_key="hub_activity_summary",
            fn=lambda: self._activity_summary(current_key),
        )
        remaining = self._timed(
            "remaining_activity_sample",
            project_key=project_key,
            schedule_version_key=current_key,
            query_key="hub_remaining_activities",
            cap=_REMAINING_SAMPLE_CAP,
            fn=lambda: self._remaining_activity_rows(current_key, limit=_REMAINING_SAMPLE_CAP),
        )

        recent = self._timed(
            "recent_progress",
            project_key=project_key,
            schedule_version_key=current_key,
            query_key="hub_recent_progress",
            cap=_RECENT_COMPLETIONS_CAP + _RECENT_STARTS_CAP,
            fn=lambda: self._recent_progress(
                current_key=current_key,
                previous_key=previous_key,
                previous_data_date=previous_data_date,
                current_data_date=current_data_date,
                as_of_date=as_of_date,
            ),
        )
        cpm_summary = self._timed(
            "cpm_summary_path_reads",
            project_key=project_key,
            schedule_version_key=current_key,
            query_key="hub_cpm_preview",
            cap=_CRITICAL_PATH_PREVIEW_CAP,
            fn=lambda: self._computed_cpm(current_key),
        )
        change_impact = self._timed(
            "diff_and_change_impact",
            project_key=project_key,
            schedule_version_key=current_key,
            query_key="hub_change_impact",
            cap=_DIRECT_REMAINING_CHANGE_CAP + _UPSTREAM_REMAINING_IMPACT_CAP,
            fn=lambda: self._change_impact(
                project_key=project_key,
                current=current,
                previous=previous,
                current_key=current_key,
                previous_key=previous_key,
                comparison_context=comparison_context,
            ),
        )
        milestones = self._timed(
            "milestones",
            project_key=project_key,
            schedule_version_key=current_key,
            query_key="hub_milestones",
            cap=_MILESTONE_CAP,
            fn=lambda: self._milestones(current_key, previous_key, recent),
        )
        comparison_ready = bool(comparison_context.get("available"))
        baseline_summary = self._baseline_summary(
            project_key=project_key,
            current=current,
            current_key=current_key,
            previous=previous,
        )
        identity_blocked = _requires_identity_review(current_choice.identity_match)
        change_driver_analysis = self._timed(
            "driver_analysis",
            project_key=project_key,
            schedule_version_key=current_key,
            query_key="hub_driver_analysis",
            fn=lambda: self._drivers.build_hub_analysis(
                project_key=project_key,
                current_key=current_key,
                previous_key=previous_key,
                baseline_key=baseline_summary.get("_selected_baseline_schedule_version_key"),
                diff_id=current.get("default_diff_id"),
                milestones=milestones,
                comparison_ready=comparison_ready and not identity_blocked,
            ),
        )
        remaining_health = self._remaining_health(
            remaining=remaining,
            activity_summary=activity_summary,
            change_impact=change_impact,
            cpm_summary=cpm_summary,
            current_choice=current_choice,
            previous=previous,
        )
        forecast = self._timed(
            "forecast_finish",
            project_key=project_key,
            schedule_version_key=current_key,
            query_key="hub_forecast_finish",
            fn=lambda: self._forecast_finish(current_key, previous_key),
        )
        actions = self._actions(
            readiness_inputs={
                "previous": previous,
                "current_choice": current_choice,
                "cpm_summary": cpm_summary,
                "change_impact": change_impact,
                "remaining": remaining,
            },
            remaining_health=remaining_health,
            forecast=forecast,
            milestones=milestones,
        )
        trends = self._trends(versions, current_choice)
        trend_series = self._trend_series(versions, current_choice, previous_key=previous_key)
        accepted_identity_key = _identity_key(current_choice.identity_match)
        schedule_trust = self._trust.build_trust_envelope(
            project_key=project_key,
            current_choice=current_choice,
            versions=versions,
            accepted_identity_key=accepted_identity_key,
        )
        review_workbench = self._timed(
            "review_queue",
            project_key=project_key,
            schedule_version_key=current_key,
            query_key="hub_review_workbench",
            fn=lambda: self._review.build_preview(
                project_key=project_key,
                schedule_version_key=current_key,
                driver_analysis=change_driver_analysis,
                milestones=milestones,
                remaining_health=remaining_health,
                cpm_summary=cpm_summary,
                change_impact=change_impact,
                remaining_activities=remaining,
                as_of_date=as_of_date,
                baseline_summary=baseline_summary,
                include_activity_metric_cues=False,
            ),
        )
        source_float_summary = {
            "basis": "source_export_float",
            "evidence_class": "source_exported",
            "field_precedence": ["total_float", "derived_total_float_days", "explicit_total_float_days"],
            "app_computed_cpm_evidence": "separate",
            "negative_float_remaining_count": remaining_health["float_pressure"]["negative_float_count"],
            "zero_float_remaining_count": remaining_health["float_pressure"]["zero_float_count"],
            "near_critical_source_count": remaining_health["float_pressure"]["near_critical_count"],
        }
        computed_cpm_summary = {
            "basis": "application_computed_cpm",
            "available": cpm_summary["summary"]["available"],
            "critical_remaining_count": cpm_summary["summary"].get("critical_remaining_count", 0),
            "near_critical_remaining_count": cpm_summary["summary"].get("near_critical_remaining_count", 0),
            "drilldown_url": cpm_summary["summary"].get("drilldown_url"),
            "source_cpm_run_id": cpm_summary["summary"].get("source_cpm_run_id"),
            "selected_cpm_run": _pm_cpm_run_payload(cpm_summary["summary"].get("selected_cpm_run")),
            "all_cpm_runs": _pm_cpm_run_list(cpm_summary["summary"].get("all_cpm_runs")),
            "excluded_cpm_runs": _pm_cpm_run_list(cpm_summary["summary"].get("excluded_cpm_runs")),
            "run_availability": {
                key: _pm_cpm_run_payload(value)
                for key, value in (cpm_summary["summary"].get("run_availability") or {}).items()
            },
            "selected_run_policy": cpm_summary["summary"].get("selected_run_policy"),
            "data_date": cpm_summary["summary"].get("data_date"),
            "computed_at": cpm_summary["summary"].get("computed_at"),
            "run_status": cpm_summary["summary"].get("run_status"),
            "calculation_type": cpm_summary["summary"].get("calculation_type"),
            "criticality_basis": cpm_summary["summary"].get("criticality_basis"),
            "critical_float_threshold_days": cpm_summary["summary"].get("critical_float_threshold_days"),
            "near_critical_float_threshold_days": cpm_summary["summary"].get("near_critical_float_threshold_days"),
            "near_critical_threshold_source": cpm_summary["summary"].get("near_critical_threshold_source"),
            "source_export_evidence": cpm_summary["summary"].get("source_export_evidence"),
            "source_export_float_basis": cpm_summary["summary"].get("source_export_float_basis"),
            "app_computed_float_basis": cpm_summary["summary"].get("app_computed_float_basis"),
        }
        review_drilldowns = self._drilldowns.build_preview_map(
            project_key=project_key,
            current_key=current_key,
            previous_key=previous_key,
            baseline_key=baseline_summary.get("_selected_baseline_schedule_version_key"),
            prior_summary=change_impact.get("direct_remaining_changes", {}).get("summary", {}),
            baseline_summary=baseline_summary.get("comparison"),
            upstream_items=change_impact.get("upstream_remaining_impact", {}).get("items", []),
            negative_float_count=source_float_summary["negative_float_remaining_count"],
            critical_count=computed_cpm_summary["critical_remaining_count"],
            near_critical_count=computed_cpm_summary["near_critical_remaining_count"],
        )
        identity_review = {
            "status": schedule_trust.get("status"),
            "review_reasons": schedule_trust.get("review_reasons", []),
            "review_queue_count": len(
                [c for c in schedule_trust.get("candidate_series", []) if c.get("requires_review")]
            ),
            "identity_review_url": f"/schedules/identity-review?project={project_key}",
        }
        readiness = self._readiness(
            versions=versions,
            current_choice=current_choice,
            previous=previous,
            cpm_summary=cpm_summary,
            change_impact=change_impact,
            milestones=milestones,
            remaining_count=activity_summary["remaining_count"],
            trends=trends,
            baseline_summary=baseline_summary,
            schedule_trust=schedule_trust,
        )
        command = self._command_summary(
            forecast=forecast,
            remaining=remaining,
            remaining_health=remaining_health,
            cpm_summary=cpm_summary,
            change_impact=change_impact,
            milestones=milestones,
        )
        story = self._schedule_story(
            current_label=current_label,
            current_data_date=current_data_date,
            previous=previous,
            previous_data_date=previous_data_date,
            forecast=forecast,
            recent=recent,
            remaining=remaining,
            remaining_health=remaining_health,
            cpm_summary=cpm_summary,
            change_impact=change_impact,
            change_driver_analysis=change_driver_analysis,
            actions=actions,
            readiness=readiness,
        )

        hub_payload = {
            "surface": "project_schedule_hub",
            "project_key": project_key,
            "project_display_name": project_name,
            "as_of_date": as_of_date.isoformat(),
            "status": "ready" if readiness["ready_for_pm_review"] else "partial",
            "current_schedule": {
                "available": True,
                "friendly_label": current_label,
                "source_filename": current.get("display_label"),
                "data_date": _date_str(current_data_date),
                "imported_at": current.get("imported_at"),
                "source_format": current.get("source_format"),
                "activity_count": current.get("activity_count"),
                "relationship_count": current.get("relationship_count"),
            },
            "previous_update": {
                "available": previous is not None,
                "friendly_label": self._friendly_label(previous) if previous else None,
                "data_date": _date_str(previous_data_date),
                "comparison_ready": previous is not None and not readiness["identity_review_required"]["required"],
                "comparison_basis": "same_schedule_identity" if previous else None,
                "unavailable_reason": comparison_context.get("unavailable_reason"),
            },
            "readiness": readiness,
            "schedule_story": story,
            "command_summary": command,
            "recent_progress": recent,
            "change_impact": change_impact,
            "change_driver_analysis": {
                k: v for k, v in change_driver_analysis.items() if not str(k).startswith("_")
            },
            "review_workbench": {
                k: v for k, v in review_workbench.items() if k != "items"
            },
            "remaining_health": remaining_health,
            "critical_path": cpm_summary["critical_path"],
            "milestones": milestones,
            "computed_cpm": _pm_cpm_summary_payload(cpm_summary["summary"]),
            "trend_summary": trends,
            "trend_series": trend_series,
            "schedule_trust": schedule_trust,
            "identity_review": identity_review,
            "baseline_summary": {k: v for k, v in baseline_summary.items() if not str(k).startswith("_")},
            "review_drilldowns": review_drilldowns,
            "source_float_summary": source_float_summary,
            "computed_cpm_summary": computed_cpm_summary,
            "actions": {
                "preview_limit": _TOP_ACTIONS_CAP,
                "preview": actions[:_TOP_ACTIONS_CAP],
                "all_items": actions,
                "total_count": len(actions),
            },
            "technical_links": self._technical_links(project_key, current_key, previous_key, change_impact),
            "technical_evidence": {
                "collapsed_by_default": True,
                "raw_keys_available": True,
                "performance_stage_timings": self._stage_timings,
                "schedule_version_key": current_key,
                "previous_schedule_version_key": previous_key,
                "selected_baseline_schedule_version_key": baseline_summary.get(
                    "_selected_baseline_schedule_version_key"
                ),
                "prior_update_comparison_context": comparison_context,
                "schedule_identity_key": (
                    current_choice.identity_match.get("schedule_identity_key")
                    if current_choice.identity_match
                    else None
                ),
                "source_export_evidence": "separate",
            },
        }
        hub_payload["narrative_qa"] = validate_schedule_narrative(hub_payload)
        return hub_payload

    # ------------------------------------------------------------------ resolvers

    def _resolve_current(
        self, project_key: str, versions: list[dict[str, Any]], *, as_of_date: date
    ) -> _VersionChoice | None:
        choices = [
            _VersionChoice(v, self._identity.get_match_for_version(str(v["schedule_version_key"])))
            for v in versions
        ]
        resolved = [
            c
            for c in choices
            if self._trust.is_hub_eligible(
                project_key=project_key,
                version=c.version,
                identity_match=c.identity_match,
            )
        ]
        non_future = [
            c for c in resolved
            if (data_date := self._data_date(c.version)) is None or data_date <= as_of_date
        ]
        if not non_future:
            return None
        resolved = non_future
        if not resolved:
            return None
        resolved.sort(key=lambda c: (_date_sort_key(self._data_date(c.version)), str(c.version.get("imported_at") or "")), reverse=True)
        if len(resolved) > 1:
            first = resolved[0]
            second = resolved[1]
            if (
                self._data_date(first.version) == self._data_date(second.version)
                and str(first.version.get("imported_at") or "") == str(second.version.get("imported_at") or "")
                and _identity_key(first.identity_match) != _identity_key(second.identity_match)
            ):
                return None
        return resolved[0] if resolved else None

    def _resolve_previous(
        self, project_key: str, current: _VersionChoice, versions: list[dict[str, Any]]
    ) -> _VersionChoice | None:
        current_key = str(current.version["schedule_version_key"])
        current_identity = _identity_key(current.identity_match)
        current_date = self._data_date(current.version)
        candidates: list[_VersionChoice] = []
        for version in versions:
            version_key = str(version["schedule_version_key"])
            if version_key == current_key:
                continue
            match = self._identity.get_match_for_version(version_key)
            if not self._trust.is_hub_eligible(
                project_key=project_key,
                version=version,
                identity_match=match,
            ):
                continue
            if current_identity and _identity_key(match) and current_identity != _identity_key(match):
                continue
            vdate = self._data_date(version)
            if current_date and vdate and vdate >= current_date:
                continue
            candidates.append(_VersionChoice(version, match))
        candidates.sort(
            key=lambda c: (_date_sort_key(self._data_date(c.version)), str(c.version.get("imported_at") or "")),
            reverse=True,
        )
        return candidates[0] if candidates else None

    def _prior_update_comparison_context(
        self,
        *,
        current_choice: _VersionChoice,
        previous_choice: _VersionChoice | None,
        as_of_date: date,
    ) -> dict[str, Any]:
        current_key = str(current_choice.version["schedule_version_key"])
        previous_key = str(previous_choice.version["schedule_version_key"]) if previous_choice else None
        identity_key = _identity_key(current_choice.identity_match)
        unavailable_reason = None
        if not previous_key:
            unavailable_reason = "no_prior_update"
        elif _requires_identity_review(current_choice.identity_match):
            unavailable_reason = "identity_review_required"
        return {
            "available": previous_key is not None and unavailable_reason is None,
            "current_version_key": current_key,
            "previous_version_key": previous_key,
            "diff_id": current_choice.version.get("default_diff_id"),
            "comparison_basis": "prior_update",
            "finish_movement_basis": "resolved_finish_date",
            "schedule_identity_key": identity_key,
            "as_of_date": as_of_date.isoformat(),
            "unavailable_reason": unavailable_reason,
            "as_of_eligibility_basis": "hub_eligible_schedule_data_date_on_or_before_as_of",
            "tie_breakers": ["schedule_data_date_desc", "imported_at_desc"],
        }

    def _named_slot_comparison_context(
        self,
        *,
        project_key: str,
        current_choice: _VersionChoice,
        baseline_version_key: str,
        comparison_basis: str,
        as_of_date: date,
    ) -> dict[str, Any]:
        current_key = str(current_choice.version["schedule_version_key"])
        identity_key = _identity_key(current_choice.identity_match)
        baseline_version = self._version_row(project_key, baseline_version_key)
        unavailable_reason = None
        if not baseline_version:
            unavailable_reason = "baseline_invalid"
        elif _requires_identity_review(current_choice.identity_match):
            unavailable_reason = "identity_review_required"
        return {
            "available": baseline_version is not None and unavailable_reason is None,
            "current_version_key": current_key,
            "comparison_schedule_version_key": baseline_version_key,
            "previous_version_key": None,
            "diff_id": current_choice.version.get("default_diff_id"),
            "comparison_basis": comparison_basis,
            "source_model": "named_slot",
            "finish_movement_basis": "resolved_finish_date",
            "schedule_identity_key": identity_key,
            "as_of_date": as_of_date.isoformat(),
            "unavailable_reason": unavailable_reason,
            "as_of_eligibility_basis": "hub_eligible_schedule_data_date_on_or_before_as_of",
            "tie_breakers": ["named_slot_selection"],
        }

    # ------------------------------------------------------------------ bounded hub reads

    def _timed(
        self,
        stage: str,
        *,
        project_key: str,
        fn: Callable[[], Any],
        schedule_version_key: str | None = None,
        query_key: str | None = None,
        cap: int | None = None,
    ) -> Any:
        started = time.perf_counter()
        result = fn()
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        row_count = _result_row_count(result)
        entry = {
            "stage": stage,
            "elapsed_ms": elapsed_ms,
            "project_key": project_key,
            "schedule_version_key": schedule_version_key,
            "query_key": query_key,
            "row_count": row_count,
            "cap": cap,
        }
        self._stage_timings.append(entry)
        if elapsed_ms >= _SLOW_STAGE_MS:
            _LOG.warning(
                "project_schedule_hub_slow_stage stage=%s elapsed_ms=%.3f project_key=%s "
                "schedule_version_key=%s query_key=%s row_count=%s cap=%s",
                stage,
                elapsed_ms,
                project_key,
                schedule_version_key,
                query_key,
                row_count,
                cap,
            )
        return result

    def explain_query_plan(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with open_connection(self._db_path) as conn:
            rows = conn.execute(f"EXPLAIN QUERY PLAN {sql}", params).fetchall()
        return [dict(row) for row in rows]

    def explain_version_resolution_queries(self, project_key: str) -> dict[str, list[dict[str, Any]]]:
        before_sql = """
            SELECT i.import_id, i.project_key, i.schedule_version_key, i.source_type,
                   i.source_format, i.import_status, i.activity_count, i.relationship_count,
                   i.cost_loaded_status, i.created_at, i.source_filename_redacted,
                   COUNT(DISTINCT a.activity_id) AS activity_count_live,
                   COUNT(DISTINCT r.id) AS relationship_count_live
            FROM schedule_file_imports i
            LEFT JOIN procore_ep_schedule_activities a
              ON a.import_id = i.import_id
            LEFT JOIN procore_ep_schedule_relationships r
              ON r.import_id = i.import_id
            WHERE i.import_status='committed' AND i.project_key=?
            GROUP BY i.import_id ORDER BY i.created_at DESC
        """
        after_sql = """
            SELECT import_id, project_key, schedule_version_key, source_type,
                   source_format, import_status, activity_count, relationship_count,
                   cost_loaded_status, created_at, source_filename_redacted
            FROM schedule_file_imports
            WHERE import_status='committed'
              AND project_key=?
              AND schedule_version_key IS NOT NULL
            ORDER BY created_at DESC
            LIMIT ?
        """
        return {
            "before": self.explain_query_plan(before_sql, (project_key,)),
            "after": self.explain_query_plan(after_sql, (project_key, _VERSION_CAP)),
        }

    def _hub_project_versions(self, project_key: str) -> list[dict[str, Any]]:
        with open_connection(self._db_path) as conn:
            rows = conn.execute(
                """
                SELECT import_id, project_key, schedule_version_key, source_type,
                       source_format, import_status, activity_count, relationship_count,
                       cost_loaded_status, created_at, source_filename_redacted
                FROM schedule_file_imports
                WHERE import_status='committed'
                  AND project_key=?
                  AND schedule_version_key IS NOT NULL
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (project_key, _VERSION_CAP),
            ).fetchall()
            versions = [dict(row) for row in rows]
            for version in versions:
                version["activity_count_live"] = version.get("activity_count")
                version["relationship_count_live"] = version.get("relationship_count")
                version["display_label"] = version.get("source_filename_redacted")
                version["source_filename"] = version.get("source_filename_redacted")
                version["imported_at"] = version.get("created_at")
                version["data_date"] = _date_str(self._data_date(version))
                diff = conn.execute(
                    """
                    SELECT id AS diff_id FROM schedule_version_diffs
                    WHERE project_key=? AND to_schedule_version_key=?
                    ORDER BY created_at DESC, diff_id DESC
                    LIMIT 1
                    """,
                    (project_key, version["schedule_version_key"]),
                ).fetchone()
                version["default_diff_id"] = int(diff["diff_id"]) if diff else None
        return versions

    def _activity_summary(self, schedule_version_key: str) -> dict[str, Any]:
        return self._canonical_metrics.activity_summary(schedule_version_key)
        with open_connection(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT
                  COUNT(*) AS total_count,
                  SUM(CASE WHEN actual_finish IS NULL OR TRIM(actual_finish)='' THEN 1 ELSE 0 END) AS remaining_count,
                  SUM(CASE WHEN (actual_finish IS NULL OR TRIM(actual_finish)='')
                            AND CAST(COALESCE(NULLIF(total_float, ''), NULLIF(derived_total_float_days, ''), NULLIF(explicit_total_float_days, ''), '0') AS REAL) < 0
                           THEN 1 ELSE 0 END) AS negative_float_count,
                  SUM(CASE WHEN (actual_finish IS NULL OR TRIM(actual_finish)='')
                            AND CAST(COALESCE(NULLIF(total_float, ''), NULLIF(derived_total_float_days, ''), NULLIF(explicit_total_float_days, ''), '999999') AS REAL) = 0
                           THEN 1 ELSE 0 END) AS zero_float_count,
                  SUM(CASE WHEN (actual_finish IS NULL OR TRIM(actual_finish)='')
                            AND CAST(COALESCE(NULLIF(total_float, ''), NULLIF(derived_total_float_days, ''), NULLIF(explicit_total_float_days, ''), '999999') AS REAL) > 0
                            AND CAST(COALESCE(NULLIF(total_float, ''), NULLIF(derived_total_float_days, ''), NULLIF(explicit_total_float_days, ''), '999999') AS REAL) <= 10
                           THEN 1 ELSE 0 END) AS near_critical_count,
                  SUM(CASE WHEN (actual_finish IS NULL OR TRIM(actual_finish)='')
                            AND constraint_type IS NOT NULL AND TRIM(constraint_type) <> ''
                           THEN 1 ELSE 0 END) AS constrained_remaining_count
                FROM procore_ep_schedule_activities
                WHERE schedule_version_key=?
                """,
                (schedule_version_key,),
            ).fetchone()
        data = dict(row) if row else {}
        return {key: int(data.get(key) or 0) for key in (
            "total_count",
            "remaining_count",
            "negative_float_count",
            "zero_float_count",
            "near_critical_count",
            "constrained_remaining_count",
        )}

    def _remaining_activity_rows(self, schedule_version_key: str, *, limit: int) -> list[dict[str, Any]]:
        with open_connection(self._db_path) as conn:
            rows = conn.execute(
                f"""
                SELECT {_ACTIVITY_COLUMNS}
                FROM procore_ep_schedule_activities
                WHERE schedule_version_key=?
                  AND (actual_finish IS NULL OR TRIM(actual_finish)='')
                ORDER BY
                  CASE WHEN CAST(COALESCE(NULLIF(total_float, ''), NULLIF(derived_total_float_days, ''), NULLIF(explicit_total_float_days, ''), '999999') AS REAL) < 0 THEN 0 ELSE 1 END,
                  CAST(COALESCE(NULLIF(total_float, ''), NULLIF(derived_total_float_days, ''), NULLIF(explicit_total_float_days, ''), '999999') AS REAL),
                  COALESCE(remaining_finish, remaining_early_finish, finish_date, activity_id)
                LIMIT ?
                """,
                (schedule_version_key, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def _activity_rows_by_ids(self, schedule_version_key: str | None, activity_ids: set[str]) -> dict[str, dict[str, Any]]:
        if not schedule_version_key or not activity_ids:
            return {}
        ids = sorted(activity_ids)
        placeholders = ",".join("?" for _ in ids)
        with open_connection(self._db_path) as conn:
            rows = conn.execute(
                f"""
                SELECT {_ACTIVITY_COLUMNS}
                FROM procore_ep_schedule_activities
                WHERE schedule_version_key=?
                  AND activity_id IN ({placeholders})
                """,
                (schedule_version_key, *ids),
            ).fetchall()
        return {str(row["activity_id"]): dict(row) for row in rows}

    # ------------------------------------------------------------------ model pieces

    def _recent_progress(
        self,
        *,
        current_key: str,
        previous_key: str | None,
        previous_data_date: date | None,
        current_data_date: date | None,
        as_of_date: date,
    ) -> dict[str, Any]:
        start = previous_data_date or (as_of_date - timedelta(days=14))
        end = current_data_date or as_of_date
        with open_connection(self._db_path) as conn:
            completed_count = int(conn.execute(
                """
                SELECT COUNT(*) FROM procore_ep_schedule_activities
                WHERE schedule_version_key=?
                  AND actual_finish >= ? AND actual_finish <= ?
                """,
                (current_key, start.isoformat(), end.isoformat()),
            ).fetchone()[0] or 0)
            started_count = int(conn.execute(
                """
                SELECT COUNT(*) FROM procore_ep_schedule_activities c
                WHERE c.schedule_version_key=?
                  AND c.actual_start IS NOT NULL AND TRIM(c.actual_start) <> ''
                  AND (
                    (c.actual_start >= ? AND c.actual_start <= ?)
                    OR (
                      ? IS NOT NULL
                      AND NOT EXISTS (
                        SELECT 1 FROM procore_ep_schedule_activities previous
                        WHERE previous.schedule_version_key=?
                          AND previous.activity_id=c.activity_id
                          AND previous.actual_start IS NOT NULL
                          AND TRIM(previous.actual_start) <> ''
                      )
                    )
                  )
                """,
                (current_key, start.isoformat(), end.isoformat(), previous_key, previous_key),
            ).fetchone()[0] or 0)
            completed_milestone_count = int(conn.execute(
                """
                SELECT COUNT(*) FROM procore_ep_schedule_activities
                WHERE schedule_version_key=?
                  AND actual_finish >= ? AND actual_finish <= ?
                  AND (is_milestone=1 OR LOWER(COALESCE(activity_name, '')) LIKE '%milestone%')
                """,
                (current_key, start.isoformat(), end.isoformat()),
            ).fetchone()[0] or 0)
            completed_critical_count = int(conn.execute(
                """
                SELECT COUNT(*) FROM procore_ep_schedule_activities
                WHERE schedule_version_key=?
                  AND actual_finish >= ? AND actual_finish <= ?
                  AND (
                    is_critical=1
                    OR CAST(COALESCE(NULLIF(total_float, ''), NULLIF(derived_total_float_days, ''), NULLIF(explicit_total_float_days, ''), '999999') AS REAL) <= 10
                  )
                """,
                (current_key, start.isoformat(), end.isoformat()),
            ).fetchone()[0] or 0)
            open_should_have_finished = int(conn.execute(
                """
                SELECT COUNT(*) FROM procore_ep_schedule_activities
                WHERE schedule_version_key=?
                  AND (actual_finish IS NULL OR TRIM(actual_finish)='')
                  AND COALESCE(remaining_finish, remaining_early_finish, finish_date) < ?
                """,
                (current_key, (current_data_date or as_of_date).isoformat()),
            ).fetchone()[0] or 0)
            completed_rows = conn.execute(
                f"""
                SELECT {_ACTIVITY_COLUMNS}
                FROM procore_ep_schedule_activities
                WHERE schedule_version_key=?
                  AND actual_finish >= ? AND actual_finish <= ?
                ORDER BY actual_finish DESC, activity_id
                LIMIT ?
                """,
                (current_key, start.isoformat(), end.isoformat(), _RECENT_COMPLETIONS_CAP),
            ).fetchall()
            started_rows = conn.execute(
                f"""
                SELECT {_ACTIVITY_COLUMNS}
                FROM procore_ep_schedule_activities c
                WHERE c.schedule_version_key=?
                  AND c.actual_start IS NOT NULL AND TRIM(c.actual_start) <> ''
                  AND (
                    (c.actual_start >= ? AND c.actual_start <= ?)
                    OR (
                      ? IS NOT NULL
                      AND NOT EXISTS (
                        SELECT 1 FROM procore_ep_schedule_activities previous
                        WHERE previous.schedule_version_key=?
                          AND previous.activity_id=c.activity_id
                          AND previous.actual_start IS NOT NULL
                          AND TRIM(previous.actual_start) <> ''
                      )
                    )
                  )
                ORDER BY c.actual_start DESC, c.activity_id
                LIMIT ?
                """,
                (current_key, start.isoformat(), end.isoformat(), previous_key, previous_key, _RECENT_STARTS_CAP),
            ).fetchall()
        return {
            "window_start": start.isoformat(),
            "window_end": end.isoformat(),
            "window_basis": "previous_schedule_data_date" if previous_data_date else "last_14_calendar_days",
            "completed_count": completed_count,
            "started_count": started_count,
            "completed_milestone_count": completed_milestone_count,
            "completed_critical_or_near_critical_count": completed_critical_count,
            "open_forecast_complete_count": open_should_have_finished,
            "completed_items": [_activity_item(dict(a)) for a in completed_rows],
            "started_items": [_activity_item(dict(a)) for a in started_rows],
        }

    def _direct_remaining_comparison(
        self,
        current_key: str,
        previous_key: str,
    ) -> dict[str, Any]:
        result = self._comparison.compare_versions(left_key=current_key, right_key=previous_key)
        finish_changed_items = [
            {
                "activity": _activity_item_from_drilldown(row),
                "start_delta_days": row.get("start_delta_days"),
                "finish_delta_days": row.get("finish_delta_days"),
                "float_delta_days": row.get("float_delta_days"),
            }
            for row in self._comparison.filter_rows(result["rows"], "finish_changed")
        ]
        finish_changed_items.sort(
            key=lambda item: abs(item.get("finish_delta_days") or 0),
            reverse=True,
        )
        return {
            "summary": result["summary"],
            "top_impacted_wbs": self._comparison.top_wbs(
                [row for row in result["rows"] if row.get("finish_delta_days") not in (None, 0)]
            ),
            "top_impacted_activities": finish_changed_items[:_TOP_IMPACTED_CAP],
            "items": finish_changed_items[:_DIRECT_REMAINING_CHANGE_CAP],
        }

    def _baseline_summary(
        self,
        *,
        project_key: str,
        current: dict[str, Any],
        current_key: str,
        previous: dict[str, Any] | None,
    ) -> dict[str, Any]:
        selection = self._hub_repo.get_active_baseline_selection(
            project_key=project_key,
            current_schedule_version_key=current_key,
        )
        baseline_projects = self._imports.list_baseline_projects(current_key)
        original = baseline_projects[0] if baseline_projects else None
        original_label = None
        if original:
            original_label = original.get("baseline_project_name") or original.get("source_project_name")

        if not selection:
            status = "original_only" if original else "no_selection"
            return {
                "selected_baseline_available": False,
                "selected_baseline_label": None,
                "selected_baseline_data_date": None,
                "original_baseline_detected": bool(original),
                "original_baseline_label": original_label,
                "status": status,
                "comparison": {},
                "current_update_label": self._friendly_label(current),
                "previous_update_label": self._friendly_label(previous) if previous else None,
            }

        from .project_schedule_selected_baseline_service import (
            ProjectScheduleSelectedBaselineService,
            public_selected_baseline_state,
        )

        selected_baseline_state = ProjectScheduleSelectedBaselineService(db_path=self._db_path).get_state(
            project_key=project_key,
            current_schedule_version_key=current_key,
        )
        baseline_key = str(selection["selected_baseline_schedule_version_key"])
        baseline_version = self._version_row(project_key, baseline_key)
        comparison: dict[str, Any] = {}
        if selected_baseline_state.get("status") == "ready":
            comparison_result = self._comparison.compare_versions(left_key=current_key, right_key=baseline_key)
            current_finish = _parse_date(
                self._forecast_finish(current_key, baseline_key).get("current_forecast_finish")
            )
            baseline_finish = _parse_date(
                self._forecast_finish(current_key, baseline_key).get("previous_forecast_finish")
            )
            comparison = {
                **comparison_result["summary"],
                "forecast_finish_delta_days": _date_delta_days(baseline_finish, current_finish),
                "comparison_basis": "selected_baseline",
            }
        return {
            "selected_baseline_available": True,
            "selected_baseline_label": self._friendly_label(baseline_version) if baseline_version else label_from_source(baseline_key),
            "selected_baseline_data_date": _date_str(self._data_date(baseline_version)) if baseline_version else None,
            "original_baseline_detected": bool(original),
            "original_baseline_label": original_label,
            "status": selected_baseline_state.get("status") or "recompute_required",
            "readiness": selected_baseline_state.get("readiness"),
            "recompute_required": bool(selected_baseline_state.get("recompute_required")),
            "selected_baseline_state": public_selected_baseline_state(selected_baseline_state),
            "current_update_label": self._friendly_label(current),
            "previous_update_label": self._friendly_label(previous) if previous else None,
            "comparison": comparison,
            "_selected_baseline_schedule_version_key": baseline_key,
        }

    def _version_row(self, project_key: str, schedule_version_key: str) -> dict[str, Any] | None:
        with open_connection(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT import_id, project_key, schedule_version_key, source_format,
                       activity_count, relationship_count, created_at, source_filename_redacted
                FROM schedule_file_imports
                WHERE project_key=? AND schedule_version_key=? AND import_status='committed'
                ORDER BY created_at DESC LIMIT 1
                """,
                (project_key, schedule_version_key),
            ).fetchone()
        if not row:
            return None
        version = dict(row)
        version["imported_at"] = version.get("created_at")
        version["display_label"] = version.get("source_filename_redacted")
        return version

    def build_drilldown(
        self,
        project_key: str,
        *,
        drilldown_type: str,
        limit: int = 100,
        offset: int = 0,
        as_of: date | None = None,
        comparison_basis: str = "prior_update",
    ) -> dict[str, Any]:
        from .project_schedule_comparison_basis_resolver import resolve_workbench_comparison_basis

        resolved = resolve_workbench_comparison_basis(comparison_basis)
        as_of_date = as_of or datetime.now(timezone.utc).date()
        hub_context: dict[str, Any] | None = None
        comparison_context: dict[str, Any]
        current_key: str
        comparison_key: str | None
        baseline_key: str | None = None

        if resolved.source_model == "named_slot":
            try:
                hub_context, _ = self.build_resolved_hub_context(
                    project_key,
                    resolved=resolved,
                    as_of=as_of,
                )
            except ValueError as exc:
                reason = str(exc)
                if reason in {"baseline_not_selected", "baseline_invalid"}:
                    return {
                        "available": False,
                        "reason": reason,
                        "comparison_basis": resolved.comparison_basis,
                    }
                raise
            if not hub_context:
                return {"available": False, "reason": "no_schedule", "comparison_basis": resolved.comparison_basis}
            provenance = hub_context.get("comparison_provenance") or {}
            comparison_context = hub_context.get("comparison_context") or {}
            current_key = str(hub_context.get("schedule_version_key") or "")
            comparison_key = str(provenance.get("comparison_schedule_version_key") or "") or None
            baseline_key = comparison_key
        else:
            versions = self._hub_project_versions(project_key)
            if not versions:
                return {"available": False, "reason": "no_schedule"}
            current_choice = self._resolve_current(project_key, versions, as_of_date=as_of_date)
            if not current_choice:
                return {"available": False, "reason": "review_required"}
            current_key = str(current_choice.version["schedule_version_key"])
            previous_choice = self._resolve_previous(project_key, current_choice, versions)
            previous_key = str(previous_choice.version["schedule_version_key"]) if previous_choice else None
            comparison_context = self._prior_update_comparison_context(
                current_choice=current_choice,
                previous_choice=previous_choice,
                as_of_date=as_of_date,
            )
            baseline = self._hub_repo.get_active_baseline_selection(
                project_key=project_key,
                current_schedule_version_key=current_key,
            )
            baseline_key = str(baseline["selected_baseline_schedule_version_key"]) if baseline else None
            comparison_key = self._drilldowns.resolve_comparison_key(
                project_key=project_key,
                drilldown_type=drilldown_type,
                current_key=current_key,
                previous_key=previous_key,
                baseline_key=baseline_key,
            )

        if drilldown_type == "upstream_cues":
            if hub_context:
                items = (
                    hub_context.get("change_impact", {})
                    .get("upstream_remaining_impact", {})
                    .get("items", [])
                )
            else:
                summary = self.build_summary(project_key, as_of=as_of)
                items = summary.get("change_impact", {}).get("upstream_remaining_impact", {}).get("items", [])
            return {
                "available": True,
                "drilldown_type": drilldown_type,
                "count": len(items),
                "limit": limit,
                "offset": offset,
                "items": items[offset : offset + limit],
                "comparison_basis": resolved.comparison_basis,
                "comparison_context": comparison_context,
                "finish_movement_basis": comparison_context.get("finish_movement_basis"),
            }
        if not comparison_key:
            return {
                "available": False,
                "reason": comparison_context.get("unavailable_reason") or "comparison_unavailable",
                "comparison_basis": resolved.comparison_basis,
                "comparison_context": comparison_context,
            }
        out = self._drilldowns.list_drilldown(
            project_key=project_key,
            drilldown_type=drilldown_type,
            current_key=current_key,
            comparison_key=comparison_key,
            limit=limit,
            offset=offset,
        )
        if drilldown_type.startswith("baseline_") or resolved.source_model == "named_slot":
            out["comparison_basis"] = resolved.comparison_basis
        else:
            out["comparison_basis"] = comparison_context["comparison_basis"]
            out["comparison_context"] = comparison_context
        out["finish_movement_basis"] = comparison_context.get("finish_movement_basis")
        if resolved.source_model == "named_slot":
            out["comparison_context"] = comparison_context
            provenance = (hub_context or {}).get("comparison_provenance") or {}
            out["comparison_schedule_version_key"] = provenance.get("comparison_schedule_version_key")
        return out

    def build_review_items(
        self,
        project_key: str,
        *,
        review_status: str | None = None,
        limit: int = 100,
        offset: int = 0,
        as_of: date | None = None,
        comparison_basis: str = "prior_update",
        source_metric: str | None = None,
        severity: str | None = None,
        item_type: str | None = None,
        confidence: str | None = None,
        phase: str | None = None,
        floor: str | None = None,
        sector_area: str | None = None,
        subcontractor: str | None = None,
        cost_code: str | None = None,
    ) -> dict[str, Any]:
        from .project_schedule_comparison_basis_resolver import resolve_workbench_comparison_basis

        resolved = resolve_workbench_comparison_basis(comparison_basis)
        baseline_context: dict[str, Any] | None = None
        try:
            context, baseline_context = self.build_resolved_hub_context(
                project_key,
                resolved=resolved,
                as_of=as_of,
            )
        except ValueError as exc:
            reason = str(exc)
            if reason in {"baseline_not_selected", "baseline_invalid"}:
                return {
                    "available": False,
                    "reason": reason,
                    "comparison_basis": resolved.comparison_basis,
                    "baseline_context": baseline_context,
                }
            raise
        if not context:
            return {"available": False, "reason": "no_schedule", "comparison_basis": resolved.comparison_basis}
        if resolved.source_model == "legacy_v90" and not self._legacy_baseline_available(
            context.get("baseline_summary") or {}
        ):
            return {
                "available": False,
                "reason": str((context.get("baseline_summary") or {}).get("reason") or "baseline_unavailable"),
                "comparison_basis": resolved.comparison_basis,
            }
        if resolved.source_model == "named_slot":
            scope = self._named_baseline_review.scope_from_context(
                project_key=context["project_key"],
                current_schedule_version_key=context["schedule_version_key"],
                comparison_basis=resolved.comparison_basis,
                baseline_context=baseline_context or {},
                as_of_date=context.get("as_of_date"),
                schedule_data_date=context.get("schedule_data_date"),
            )
            workbench = self._named_baseline_review.build_preview(
                scope=scope,
                driver_analysis=context.get("driver_analysis"),
                milestones=context.get("milestones"),
                remaining_health=context.get("remaining_health"),
                cpm_summary=context.get("cpm_summary"),
                change_impact=context.get("change_impact"),
                remaining_activities=context.get("remaining_activities"),
                as_of_date=context.get("as_of_date"),
                baseline_summary=context.get("baseline_summary"),
                comparison_basis=resolved.comparison_basis,
            )
        else:
            workbench = self._review.build_preview(
                project_key=context["project_key"],
                schedule_version_key=context["schedule_version_key"],
                driver_analysis=context.get("driver_analysis"),
                milestones=context.get("milestones"),
                remaining_health=context.get("remaining_health"),
                cpm_summary=context.get("cpm_summary"),
                change_impact=context.get("change_impact"),
                remaining_activities=context.get("remaining_activities"),
                comparison_basis=resolved.preview_basis,
                as_of_date=context.get("as_of_date"),
                baseline_summary=context.get("baseline_summary"),
                include_activity_metric_cues=True,
                response_comparison_basis=resolved.comparison_basis,
                carry_forward_disposition=True,
            )
        items = workbench.get("items") or []
        items = self._review.filter_items(
            items,
            review_status=review_status,
            severity=severity,
            source_metric=source_metric,
            item_type=item_type,
            confidence=confidence,
            phase=phase,
            floor=floor,
            sector_area=sector_area,
            subcontractor=subcontractor,
            cost_code=cost_code,
        )
        sliced = items[offset : offset + max(1, min(limit, 200))]
        workbench_meta = {k: v for k, v in workbench.items() if k != "items"}
        if resolved.source_model == "named_slot":
            workbench_meta["baseline_context"] = baseline_context
        return {
            "available": True,
            "count": len(items),
            "limit": limit,
            "offset": offset,
            "items": sliced,
            "comparison_basis": resolved.comparison_basis,
            "workbench": workbench_meta,
        }

    def sync_review_workbench(
        self,
        project_key: str,
        *,
        as_of: date | None = None,
        comparison_basis: str = "prior_update",
    ) -> dict[str, Any]:
        from .project_schedule_comparison_basis_resolver import resolve_workbench_comparison_basis

        resolved = resolve_workbench_comparison_basis(comparison_basis)
        if resolved.source_model == "named_slot":
            try:
                context, baseline_context = self.build_resolved_hub_context(
                    project_key,
                    resolved=resolved,
                    as_of=as_of,
                )
            except ValueError as exc:
                reason = str(exc)
                if reason in {"baseline_not_selected", "baseline_invalid"}:
                    raise
                raise
            if not context:
                return {"available": False, "reason": "no_schedule", "comparison_basis": resolved.comparison_basis}
            scope = self._named_baseline_review.scope_from_context(
                project_key=context["project_key"],
                current_schedule_version_key=context["schedule_version_key"],
                comparison_basis=resolved.comparison_basis,
                baseline_context=baseline_context or {},
                as_of_date=context.get("as_of_date"),
                schedule_data_date=context.get("schedule_data_date"),
            )
            workbench = self._named_baseline_review.sync_and_list(
                scope=scope,
                driver_analysis=context.get("driver_analysis"),
                milestones=context.get("milestones"),
                remaining_health=context.get("remaining_health"),
                cpm_summary=context.get("cpm_summary"),
                change_impact=context.get("change_impact"),
                remaining_activities=context.get("remaining_activities"),
                as_of_date=context.get("as_of_date"),
                baseline_summary=context.get("baseline_summary"),
                comparison_basis=resolved.comparison_basis,
            )
            workbench["baseline_context"] = baseline_context
            return workbench
        context = self._review_workbench_context(project_key, as_of=as_of)
        if not context:
            return {"available": False, "reason": "no_schedule"}
        if resolved.source_model == "legacy_v90" and not self._legacy_baseline_available(
            context.get("baseline_summary") or {}
        ):
            return {
                "available": False,
                "reason": str((context.get("baseline_summary") or {}).get("reason") or "baseline_unavailable"),
                "comparison_basis": resolved.comparison_basis,
            }
        return self._review.sync_and_list(
            project_key=context["project_key"],
            schedule_version_key=context["schedule_version_key"],
            driver_analysis=context.get("driver_analysis"),
            milestones=context.get("milestones"),
            remaining_health=context.get("remaining_health"),
            cpm_summary=context.get("cpm_summary"),
            change_impact=context.get("change_impact"),
            remaining_activities=context.get("remaining_activities"),
            as_of_date=context.get("as_of_date"),
            baseline_summary=context.get("baseline_summary"),
            comparison_basis=resolved.preview_basis,
        )

    def build_driver_detail(
        self,
        project_key: str,
        activity_id: str,
        *,
        comparison_basis: str = "prior_update",
        as_of: date | None = None,
    ) -> dict[str, Any]:
        from .project_schedule_comparison_basis_resolver import resolve_workbench_comparison_basis
        from .project_schedule_named_baseline_service import ProjectScheduleNamedBaselineService

        resolved = resolve_workbench_comparison_basis(comparison_basis)
        as_of_date = as_of or datetime.now(timezone.utc).date()
        versions = self._hub_project_versions(project_key)
        if not versions:
            return {"available": False, "reason": "no_schedule", "comparison_basis": resolved.comparison_basis}
        current_choice = self._resolve_current(project_key, versions, as_of_date=as_of_date)
        if not current_choice:
            return {"available": False, "reason": "review_required", "comparison_basis": resolved.comparison_basis}
        current_key = str(current_choice.version["schedule_version_key"])
        comparison_key: str | None = None
        diff_id: int | None = current_choice.version.get("default_diff_id")
        baseline_context: dict[str, Any] | None = None

        if resolved.source_model == "prior_update":
            previous_choice = self._resolve_previous(project_key, current_choice, versions)
            comparison_key = (
                str(previous_choice.version["schedule_version_key"]) if previous_choice else None
            )
        elif resolved.source_model == "legacy_v90":
            baseline = self._hub_repo.get_active_baseline_selection(
                project_key=project_key,
                current_schedule_version_key=current_key,
            )
            comparison_key = (
                str(baseline["selected_baseline_schedule_version_key"]) if baseline else None
            )
            diff_id = None
            if not comparison_key:
                return {
                    "available": False,
                    "reason": "baseline_unavailable",
                    "comparison_basis": resolved.comparison_basis,
                }
        else:
            slot_key = str(resolved.slot_key or resolved.comparison_basis)
            resolution = ProjectScheduleNamedBaselineService(db_path=self._db_path).resolve_slot_for_controls(
                project_key,
                slot_key=slot_key,
                as_of=as_of_date,
            )
            baseline_context = self._baseline_context_from_named_resolution(resolution)
            status = str(resolution.get("selection_status") or "missing")
            if status == "missing":
                return {
                    "available": False,
                    "reason": "baseline_not_selected",
                    "comparison_basis": resolved.comparison_basis,
                    "baseline_context": baseline_context,
                }
            if status == "invalid":
                return {
                    "available": False,
                    "reason": "baseline_invalid",
                    "comparison_basis": resolved.comparison_basis,
                    "baseline_context": baseline_context,
                }
            comparison_key = str(resolution.get("schedule_version_key") or "")
            diff_id = None

        milestones = self._milestones(current_key, comparison_key, {"completed_milestone_count": 0})
        detail = self._drivers.build_driver_detail(
            project_key=project_key,
            activity_id=activity_id,
            current_key=current_key,
            previous_key=comparison_key,
            diff_id=diff_id,
            milestones=milestones,
            comparison_ready=bool(comparison_key)
            and not _requires_identity_review(current_choice.identity_match),
            comparison_basis=resolved.comparison_basis,
            baseline_context=baseline_context,
        )
        if not detail.get("available"):
            return detail
        detail.update(
            self._driver_detail_disposition_fields(
                project_key=project_key,
                activity_id=activity_id,
                current_schedule_version_key=current_key,
                comparison_basis=resolved.comparison_basis,
                source_model=resolved.source_model,
                baseline_context=baseline_context,
                comparison_schedule_version_key=comparison_key,
            )
        )
        return detail

    def _driver_detail_disposition_fields(
        self,
        *,
        project_key: str,
        activity_id: str,
        current_schedule_version_key: str,
        comparison_basis: str,
        source_model: str,
        baseline_context: dict[str, Any] | None,
        comparison_schedule_version_key: str | None,
    ) -> dict[str, Any]:
        from hb_assistant.store.project_schedule_named_baseline_review_repository import (
            NamedBaselineReviewIdentity,
        )

        stable_key = f"driver:{activity_id}"
        source_metric_key = "change_driver_analysis"
        source_signal_type = "driver"
        default = {
            "review_status": "open",
            "review_item_id": None,
            "disposition_schedule_version_key": comparison_schedule_version_key,
            "disposition_basis": comparison_basis,
            "disposition_source": "preview",
            "review_scope": None,
        }
        if source_model == "legacy_v90":
            return {
                **default,
                "disposition_source": "unavailable_or_preview",
            }
        if source_model == "prior_update":
            row = self._hub_repo.get_review_item_for_version_scope(
                project_key=project_key,
                schedule_version_key=current_schedule_version_key,
                stable_item_key=stable_key,
                source_activity_id=activity_id,
            )
            if not row:
                return {**default, "disposition_source": "preview", "review_scope": "prior_update"}
            return {
                "review_status": str(row.get("review_status") or "open"),
                "review_item_id": row.get("review_item_id"),
                "disposition_schedule_version_key": current_schedule_version_key,
                "disposition_basis": "prior_update",
                "disposition_source": "prior_update_review",
                "review_scope": "prior_update",
            }
        baseline_key = str((baseline_context or {}).get("schedule_version_key") or comparison_schedule_version_key or "")
        if not baseline_key:
            return default
        identity = NamedBaselineReviewIdentity(
            project_key=project_key,
            current_schedule_version_key=current_schedule_version_key,
            comparison_basis=comparison_basis,
            baseline_schedule_version_key=baseline_key,
            source_stable_key=stable_key,
            source_metric_key=source_metric_key,
            source_signal_type=source_signal_type,
            source_activity_id=activity_id,
        )
        row = self._named_baseline_review._repo.get_by_identity(identity=identity)
        if not row:
            return {
                **default,
                "disposition_source": "preview",
                "review_scope": "named_baseline",
                "disposition_schedule_version_key": baseline_key,
            }
        return {
            "review_status": str(row.get("review_status") or "open"),
            "review_item_id": row.get("review_item_id"),
            "disposition_schedule_version_key": str(row.get("baseline_schedule_version_key") or baseline_key),
            "disposition_basis": str(row.get("comparison_basis") or comparison_basis),
            "disposition_source": "named_baseline_review",
            "review_scope": "named_baseline",
        }

    def _review_workbench_context(self, project_key: str, *, as_of: date | None = None) -> dict[str, Any] | None:
        as_of_date = as_of or datetime.now(timezone.utc).date()
        versions = self._hub_project_versions(project_key)
        if not versions:
            return None
        current_choice = self._resolve_current(project_key, versions, as_of_date=as_of_date)
        if not current_choice:
            return None
        current = current_choice.version
        current_key = str(current["schedule_version_key"])
        previous_choice = self._resolve_previous(project_key, current_choice, versions)
        previous_key = str(previous_choice.version["schedule_version_key"]) if previous_choice else None
        comparison_context = self._prior_update_comparison_context(
            current_choice=current_choice,
            previous_choice=previous_choice,
            as_of_date=as_of_date,
        )
        milestones = self._milestones(current_key, previous_key, {"completed_milestone_count": 0})
        baseline_summary = self._baseline_summary(
            project_key=project_key,
            current=current,
            current_key=current_key,
            previous=previous_choice.version if previous_choice else None,
        )
        comparison_ready = bool(comparison_context.get("available"))
        change_driver_analysis = self._drivers.build_hub_analysis(
            project_key=project_key,
            current_key=current_key,
            previous_key=previous_key,
            baseline_key=baseline_summary.get("_selected_baseline_schedule_version_key"),
            diff_id=current.get("default_diff_id"),
            milestones=milestones,
            comparison_ready=comparison_ready,
        )
        remaining = self._remaining_activity_rows(current_key, limit=_REMAINING_SAMPLE_CAP)
        activity_summary = self._activity_summary(current_key)
        change_impact = self._change_impact(
            project_key=project_key,
            current=current,
            previous=previous_choice.version if previous_choice else None,
            current_key=current_key,
            previous_key=previous_key,
            comparison_context=comparison_context,
        )
        cpm_summary = self._computed_cpm(current_key)
        remaining_health = self._remaining_health(
            remaining=remaining,
            activity_summary=activity_summary,
            change_impact=change_impact,
            cpm_summary=cpm_summary,
            current_choice=current_choice,
            previous=previous_choice.version if previous_choice else None,
        )
        return {
            "project_key": project_key,
            "schedule_version_key": current_key,
            "driver_analysis": change_driver_analysis,
            "milestones": milestones,
            "remaining_health": remaining_health,
            "cpm_summary": cpm_summary,
            "change_impact": change_impact,
            "remaining_activities": remaining,
            "as_of_date": as_of_date,
            "baseline_summary": baseline_summary,
        }

    def build_schedule_hub_context(self, project_key: str, *, as_of: date | None = None) -> dict[str, Any] | None:
        """Public schedule intelligence context for controls, workbench, and related surfaces.

        Delegates to ``_review_workbench_context`` because that helper is the established
        composition point for version resolution and schedule intelligence assembly.
        Duplicating that logic here would risk drift across hub, workbench, and controls.
        """
        context = self._review_workbench_context(project_key, as_of=as_of)
        if not context:
            return None
        versions = self._hub_project_versions(project_key)
        as_of_date = context.get("as_of_date") or datetime.now(timezone.utc).date()
        current_choice = self._resolve_current(project_key, versions, as_of_date=as_of_date)
        enriched = dict(context)
        if current_choice:
            enriched["schedule_data_date"] = _date_str(self._data_date(current_choice.version))
        return enriched

    def build_baseline_summary_for_version(
        self,
        *,
        project_key: str,
        current: dict[str, Any],
        current_key: str,
        previous: dict[str, Any] | None,
        baseline_version_key: str,
    ) -> dict[str, Any]:
        """Build baseline comparison summary for an explicit prior schedule version."""

        baseline_projects = self._imports.list_baseline_projects(current_key)
        original = baseline_projects[0] if baseline_projects else None
        original_label = None
        if original:
            original_label = original.get("baseline_project_name") or original.get("source_project_name")

        baseline_version = self._version_row(project_key, baseline_version_key)
        if not baseline_version:
            return {
                "available": False,
                "selected_baseline_available": False,
                "status": "invalid_selection",
                "reason": "invalid_schedule_version_key",
                "original_baseline_detected": bool(original),
                "original_baseline_label": original_label,
                "comparison": {},
                "current_update_label": self._friendly_label(current),
                "previous_update_label": self._friendly_label(previous) if previous else None,
            }

        comparison: dict[str, Any] = {}
        try:
            comparison_result = self._comparison.compare_versions(
                left_key=current_key, right_key=baseline_version_key
            )
            current_finish = _parse_date(
                self._forecast_finish(current_key, baseline_version_key).get("current_forecast_finish")
            )
            baseline_finish = _parse_date(
                self._forecast_finish(current_key, baseline_version_key).get("previous_forecast_finish")
            )
            comparison = {
                **comparison_result["summary"],
                "forecast_finish_delta_days": _date_delta_days(baseline_finish, current_finish),
                "comparison_basis": "named_baseline",
            }
        except Exception:
            comparison = {}

        return {
            "available": True,
            "selected_baseline_available": True,
            "selected_baseline_label": self._friendly_label(baseline_version),
            "selected_baseline_data_date": _date_str(self._data_date(baseline_version)),
            "original_baseline_detected": bool(original),
            "original_baseline_label": original_label,
            "status": "ready",
            "readiness": {"ready": True, "blockers": [], "backend_derived": True},
            "recompute_required": False,
            "current_update_label": self._friendly_label(current),
            "previous_update_label": self._friendly_label(previous) if previous else None,
            "comparison": comparison,
            "_selected_baseline_schedule_version_key": baseline_version_key,
        }

    def build_schedule_hub_context_with_named_baseline(
        self,
        project_key: str,
        *,
        as_of: date | None = None,
        baseline_version_key: str,
        comparison_basis: str,
    ) -> dict[str, Any] | None:
        """Schedule hub context with comparisons anchored to a named baseline version."""

        as_of_date = as_of or datetime.now(timezone.utc).date()
        versions = self._hub_project_versions(project_key)
        if not versions:
            return None
        current_choice = self._resolve_current(project_key, versions, as_of_date=as_of_date)
        if not current_choice:
            return None
        current = current_choice.version
        current_key = str(current["schedule_version_key"])
        previous_choice = self._resolve_previous(project_key, current_choice, versions)
        previous = previous_choice.version if previous_choice else None
        baseline_version = self._version_row(project_key, baseline_version_key)
        comparison_context = self._named_slot_comparison_context(
            project_key=project_key,
            current_choice=current_choice,
            baseline_version_key=baseline_version_key,
            comparison_basis=comparison_basis,
            as_of_date=as_of_date,
        )
        milestones = self._milestones(current_key, baseline_version_key, {"completed_milestone_count": 0})
        baseline_summary = self.build_baseline_summary_for_version(
            project_key=project_key,
            current=current,
            current_key=current_key,
            previous=previous,
            baseline_version_key=baseline_version_key,
        )
        comparison_ready = bool(comparison_context.get("available"))
        change_impact = self._change_impact(
            project_key=project_key,
            current=current,
            previous=baseline_version,
            current_key=current_key,
            previous_key=baseline_version_key,
            comparison_context=comparison_context,
            comparison_key=baseline_version_key,
        )
        remaining = self._remaining_activity_rows(current_key, limit=_REMAINING_SAMPLE_CAP)
        activity_summary = self._activity_summary(current_key)
        cpm_summary = self._computed_cpm(current_key)
        remaining_health = self._remaining_health(
            remaining=remaining,
            activity_summary=activity_summary,
            change_impact=change_impact,
            cpm_summary=cpm_summary,
            current_choice=current_choice,
            previous=baseline_version,
        )
        change_driver_analysis = self._drivers.build_hub_analysis(
            project_key=project_key,
            current_key=current_key,
            previous_key=None,
            baseline_key=baseline_version_key,
            diff_id=current.get("default_diff_id"),
            milestones=milestones,
            comparison_ready=comparison_ready,
        )
        return {
            "project_key": project_key,
            "schedule_version_key": current_key,
            "driver_analysis": change_driver_analysis,
            "milestones": milestones,
            "remaining_health": remaining_health,
            "cpm_summary": cpm_summary,
            "change_impact": change_impact,
            "remaining_activities": remaining,
            "as_of_date": as_of_date,
            "baseline_summary": baseline_summary,
            "schedule_data_date": _date_str(self._data_date(current)),
            "comparison_provenance": {
                "comparison_basis": comparison_basis,
                "source_model": "named_slot",
                "comparison_schedule_version_key": baseline_version_key,
                "current_schedule_version_key": current_key,
            },
            "comparison_context": comparison_context,
        }

    def build_resolved_hub_context(
        self,
        project_key: str,
        *,
        resolved: Any,
        as_of: date | None = None,
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        from .project_schedule_comparison_basis_resolver import ResolvedComparisonBasis
        from .project_schedule_named_baseline_service import ProjectScheduleNamedBaselineService

        if not isinstance(resolved, ResolvedComparisonBasis):
            raise TypeError("resolved_must_be_ResolvedComparisonBasis")

        if resolved.source_model == "named_slot":
            slot_key = str(resolved.slot_key or resolved.comparison_basis)
            named = ProjectScheduleNamedBaselineService(db_path=self._db_path)
            resolution = named.resolve_slot_for_controls(project_key, slot_key=slot_key, as_of=as_of)
            baseline_context = self._baseline_context_from_named_resolution(resolution)
            status = str(resolution.get("selection_status") or "missing")
            if status == "missing":
                raise ValueError("baseline_not_selected")
            if status == "invalid":
                raise ValueError("baseline_invalid")
            context = self.build_schedule_hub_context_with_named_baseline(
                project_key,
                as_of=as_of,
                baseline_version_key=str(resolution.get("schedule_version_key") or ""),
                comparison_basis=resolved.comparison_basis,
            )
            return context, baseline_context

        if resolved.source_model == "legacy_v90":
            context = self._review_workbench_context(project_key, as_of=as_of)
            return context, {"basis": "baseline", "selection_status": "legacy_v90"}

        context = self._review_workbench_context(project_key, as_of=as_of)
        return context, {"basis": "prior_update", "selection_status": "not_applicable"}

    @staticmethod
    def _legacy_baseline_available(baseline_summary: dict[str, Any]) -> bool:
        return bool(
            baseline_summary.get("available")
            or baseline_summary.get("selected_baseline_available")
            or baseline_summary.get("_selected_baseline_schedule_version_key")
        )

    @staticmethod
    def _baseline_context_from_named_resolution(resolution: dict[str, Any]) -> dict[str, Any]:
        from .project_schedule_baseline_vocabulary import label_for_slot

        slot_key = str(resolution.get("slot_key") or "")
        return {
            "basis": slot_key,
            "slot_key": slot_key,
            "slot_label": str(resolution.get("slot_label") or label_for_slot(slot_key)),
            "selection_status": str(resolution.get("selection_status") or "missing"),
            "selection_id": resolution.get("selection_id"),
            "schedule_version_key": resolution.get("schedule_version_key"),
            "schedule_data_date": resolution.get("schedule_data_date"),
            "display_name": resolution.get("display_name"),
        }

    def _export_comparison_context_from_named(
        self,
        *,
        project_key: str,
        project_name: str,
        as_of: date,
        comparison_basis: str,
        hub_context: dict[str, Any],
        baseline_context: dict[str, Any],
    ) -> dict[str, Any]:
        from .project_schedule_baseline_vocabulary import comparison_label_for_basis, label_for_slot

        provenance = hub_context.get("comparison_provenance") or {}
        current_key = str(
            provenance.get("current_schedule_version_key")
            or hub_context.get("schedule_version_key")
            or ""
        )
        comparison_key = str(
            provenance.get("comparison_schedule_version_key")
            or baseline_context.get("schedule_version_key")
            or ""
        )
        slot_key = str(baseline_context.get("slot_key") or comparison_basis)
        return {
            "project_key": project_key,
            "project_name": project_name,
            "as_of": as_of.isoformat(),
            "comparison_basis": comparison_basis,
            "comparison_label": comparison_label_for_basis(comparison_basis) or comparison_basis,
            "source_model": "named_slot",
            "slot_key": slot_key,
            "slot_label": str(baseline_context.get("slot_label") or label_for_slot(slot_key)),
            "current_schedule_version_key": current_key,
            "comparison_schedule_version_key": comparison_key,
            "baseline_schedule_version_key": comparison_key,
            "current_data_date": hub_context.get("schedule_data_date"),
            "comparison_data_date": baseline_context.get("schedule_data_date"),
        }

    def _schedule_story_for_named_export(
        self,
        *,
        comparison_label: str,
        comparison_version_key: str,
        current_label: str,
        change_impact: dict[str, Any],
        driver_analysis: dict[str, Any],
        remaining_health: dict[str, Any],
    ) -> dict[str, Any]:
        summary = (
            change_impact.get("direct_remaining_changes", {}).get("summary", {})
            if change_impact.get("available")
            else {}
        )
        later = int(summary.get("finish_moved_later_count") or 0)
        earlier = int(summary.get("finish_moved_earlier_count") or 0)
        worsened = int(summary.get("worsened_float_count") or 0)
        negative_float = remaining_health.get("float_pressure", {}).get("negative_float_count", 0)
        baseline_drivers = (driver_analysis or {}).get("baseline") or driver_analysis or {}
        driver_narrative = self._drivers.build_narrative(baseline_drivers)
        headline = f"Remaining schedule movement compared against {comparison_label.lower()}."
        synopsis = (
            f"Current update {current_label} is compared against named anchor version "
            f"{comparison_version_key}. "
            f"{later} remaining activities moved later, {earlier} moved earlier, and {worsened} lost float."
        )
        what_changed = synopsis
        why_it_matters = driver_narrative.get("primary_driver_narrative") or (
            f"Review movement relative to {comparison_label.lower()} before disposition updates."
        )
        return {
            "headline": headline,
            "synopsis": synopsis,
            "what_changed": what_changed,
            "why_it_matters": why_it_matters,
            "primary_driver_narrative": driver_narrative.get("primary_driver_narrative"),
            "primary_change_driver": why_it_matters,
            "caveats": [
                "Named-baseline export uses the selected slot schedule version as the comparison anchor.",
            ],
        }

    def _build_named_export_summary(
        self,
        project_key: str,
        *,
        hub_context: dict[str, Any],
        baseline_context: dict[str, Any],
        comparison_basis: str,
        as_of: date,
    ) -> dict[str, Any]:
        project_name = self._project_display_name(project_key)
        export_comparison_context = self._export_comparison_context_from_named(
            project_key=project_key,
            project_name=project_name,
            as_of=as_of,
            comparison_basis=comparison_basis,
            hub_context=hub_context,
            baseline_context=baseline_context,
        )
        if not export_comparison_context.get("comparison_schedule_version_key"):
            return {
                "available": False,
                "reason": "comparison_context_incomplete",
                "comparison_basis": comparison_basis,
            }
        current_key = str(hub_context.get("schedule_version_key") or "")
        change_impact = hub_context.get("change_impact") or {}
        milestones = hub_context.get("milestones") or {}
        remaining_health = hub_context.get("remaining_health") or {}
        cpm_summary = hub_context.get("cpm_summary") or {"summary": {}}
        remaining = hub_context.get("remaining_activities") or []
        driver_analysis = hub_context.get("driver_analysis") or {}
        current_version = self._version_row(project_key, current_key) or {}
        current_label = self._friendly_label(current_version) if current_version else current_key
        forecast = self._forecast_finish(
            current_key,
            str(export_comparison_context.get("comparison_schedule_version_key")),
        )
        command = self._command_summary(
            forecast=forecast,
            remaining=remaining,
            remaining_health=remaining_health,
            cpm_summary=cpm_summary,
            change_impact=change_impact,
            milestones=milestones,
        )
        schedule_story = self._schedule_story_for_named_export(
            comparison_label=str(export_comparison_context.get("comparison_label") or comparison_basis),
            comparison_version_key=str(export_comparison_context.get("comparison_schedule_version_key")),
            current_label=current_label,
            change_impact=change_impact,
            driver_analysis=driver_analysis,
            remaining_health=remaining_health,
        )
        return {
            "available": True,
            "project_key": project_key,
            "project_display_name": project_name,
            "as_of_date": as_of.isoformat(),
            "comparison_basis": comparison_basis,
            "comparison_provenance": hub_context.get("comparison_provenance"),
            "export_comparison_context": export_comparison_context,
            "schedule_story": schedule_story,
            "command_summary": command,
            "change_impact": change_impact,
            "milestones": milestones,
            "remaining_health": remaining_health,
            "computed_cpm": cpm_summary.get("summary") or {},
            "change_driver_analysis": driver_analysis,
            "review_workbench": {},
        }

    def build_export(
        self,
        project_key: str,
        *,
        export_format: str = "markdown",
        as_of: date | None = None,
        variant: str = "standard",
        scope: str = "full",
        include_persisted_review: bool = False,
        comparison_basis: str = "prior_update",
    ) -> dict[str, Any]:
        from .project_schedule_comparison_basis_resolver import resolve_workbench_comparison_basis

        resolved = resolve_workbench_comparison_basis(comparison_basis)
        as_of_date = as_of or datetime.now(timezone.utc).date()
        if resolved.source_model == "named_slot":
            try:
                hub_context, baseline_context = self.build_resolved_hub_context(
                    project_key,
                    resolved=resolved,
                    as_of=as_of_date,
                )
            except ValueError as exc:
                reason = str(exc)
                if reason in {"baseline_not_selected", "baseline_invalid"}:
                    return {
                        "available": False,
                        "reason": reason,
                        "comparison_basis": resolved.comparison_basis,
                    }
                raise
            if not hub_context:
                return {
                    "available": False,
                    "reason": "no_schedule",
                    "comparison_basis": resolved.comparison_basis,
                }
            summary = self._build_named_export_summary(
                project_key,
                hub_context=hub_context,
                baseline_context=baseline_context,
                comparison_basis=resolved.comparison_basis,
                as_of=as_of_date,
            )
            if not summary.get("available", True):
                return summary
            if include_persisted_review or variant == "executive" or scope == "review_items":
                scope_obj = self._named_baseline_review.scope_from_context(
                    project_key=project_key,
                    current_schedule_version_key=str(hub_context.get("schedule_version_key") or ""),
                    comparison_basis=resolved.comparison_basis,
                    baseline_context=baseline_context,
                    as_of_date=as_of_date,
                    schedule_data_date=hub_context.get("schedule_data_date"),
                )
                summary["persisted_review_items"] = self._named_baseline_review._repo.list_in_scope(
                    scope=scope_obj,
                    limit=100,
                )
        else:
            summary = self.build_summary(project_key, as_of=as_of_date)
            summary["comparison_basis"] = resolved.comparison_basis
            if include_persisted_review or variant == "executive" or scope == "review_items":
                context = self._review_workbench_context(project_key, as_of=as_of_date)
                if context:
                    listed = self._review.list_items(
                        project_key=project_key,
                        schedule_version_key=context["schedule_version_key"],
                        limit=100,
                    )
                    summary["persisted_review_items"] = listed.get("items") or []
        return self._memo.build_export(
            summary,
            export_format=export_format,
            variant=variant,
            scope=scope,
        )

    def build_driver_drilldown(
        self,
        project_key: str,
        *,
        drilldown_type: str,
        limit: int = 100,
        offset: int = 0,
        driver_activity_id: str | None = None,
        as_of: date | None = None,
        comparison_basis: str = "prior_update",
    ) -> dict[str, Any]:
        from .project_schedule_comparison_basis_resolver import resolve_workbench_comparison_basis

        resolved = resolve_workbench_comparison_basis(comparison_basis)
        as_of_date = as_of or datetime.now(timezone.utc).date()
        if resolved.source_model == "named_slot":
            try:
                hub_context, _ = self.build_resolved_hub_context(
                    project_key,
                    resolved=resolved,
                    as_of=as_of,
                )
            except ValueError as exc:
                reason = str(exc)
                if reason in {"baseline_not_selected", "baseline_invalid"}:
                    return {
                        "available": False,
                        "reason": reason,
                        "comparison_basis": resolved.comparison_basis,
                    }
                raise
            if not hub_context:
                return {"available": False, "reason": "no_schedule", "comparison_basis": resolved.comparison_basis}
            provenance = hub_context.get("comparison_provenance") or {}
            comparison_context = hub_context.get("comparison_context") or {}
            current_key = str(hub_context.get("schedule_version_key") or "")
            comparison_key = str(provenance.get("comparison_schedule_version_key") or "")
            milestones = hub_context.get("milestones") or {}
            comparison_ready = bool(comparison_context.get("available"))
            out = self._drivers.list_drilldown(
                project_key=project_key,
                drilldown_type=drilldown_type,
                current_key=current_key,
                previous_key=comparison_key,
                diff_id=comparison_context.get("diff_id"),
                milestones=milestones,
                driver_activity_id=driver_activity_id,
                limit=limit,
                offset=offset,
                comparison_ready=comparison_ready,
            )
            out["comparison_basis"] = resolved.comparison_basis
            out["comparison_context"] = comparison_context
            out["comparison_schedule_version_key"] = comparison_key
            return out

        versions = self._hub_project_versions(project_key)
        if not versions:
            return {"available": False, "reason": "no_schedule"}
        current_choice = self._resolve_current(project_key, versions, as_of_date=as_of_date)
        if not current_choice:
            return {"available": False, "reason": "review_required"}
        current_key = str(current_choice.version["schedule_version_key"])
        previous_choice = self._resolve_previous(project_key, current_choice, versions)
        previous_key = str(previous_choice.version["schedule_version_key"]) if previous_choice else None
        comparison_context = self._prior_update_comparison_context(
            current_choice=current_choice,
            previous_choice=previous_choice,
            as_of_date=as_of_date,
        )
        comparison_ready = bool(comparison_context["available"])
        milestones = self._milestones(current_key, previous_key, {"completed_milestone_count": 0})
        out = self._drivers.list_drilldown(
            project_key=project_key,
            drilldown_type=drilldown_type,
            current_key=current_key,
            previous_key=previous_key,
            diff_id=comparison_context.get("diff_id"),
            milestones=milestones,
            driver_activity_id=driver_activity_id,
            limit=limit,
            offset=offset,
            comparison_ready=comparison_ready,
        )
        out["comparison_context"] = comparison_context
        out["comparison_basis"] = resolved.comparison_basis
        return out

    def _change_impact(
        self,
        *,
        project_key: str,
        current: dict[str, Any],
        previous: dict[str, Any] | None,
        current_key: str,
        previous_key: str | None,
        comparison_context: dict[str, Any],
        comparison_key: str | None = None,
    ) -> dict[str, Any]:
        effective_key = comparison_key or previous_key
        effective_previous = previous
        if not effective_previous or not effective_key:
            reason = (
                "baseline_invalid"
                if comparison_context.get("source_model") == "named_slot"
                else "no_prior_update"
            )
            return {
                "available": False,
                "reason": comparison_context.get("unavailable_reason") or reason,
                "comparison_basis": comparison_context["comparison_basis"],
                "finish_movement_basis": comparison_context["finish_movement_basis"],
                "as_of_date": comparison_context["as_of_date"],
                "comparison_schedule_version_key": comparison_context.get("comparison_schedule_version_key"),
                "direct_remaining_changes": {"items": [], "summary": {}},
                "upstream_remaining_impact": {"items": [], "summary": {}},
            }
        direct_comparison = self._direct_remaining_comparison(current_key, effective_key)
        diff_id = current.get("default_diff_id")
        detail_rows = (
            self._mapping.list_diff_detail_facts(
                int(diff_id),
                project_key=project_key,
                limit=_DIRECT_REMAINING_CHANGE_CAP + _UPSTREAM_REMAINING_IMPACT_CAP + 50,
                offset=0,
            )
            if diff_id
            else []
        )
        changed_ids = {str(r.get("activity_id")) for r in detail_rows if r.get("activity_id")}
        current_by_id = self._activity_rows_by_ids(current_key, changed_ids)
        previous_by_id = self._activity_rows_by_ids(effective_key, changed_ids)
        upstream_candidates: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
        for aid in sorted(changed_ids):
            current_activity = current_by_id.get(aid)
            previous_activity = previous_by_id.get(aid, {})
            if not current_activity:
                continue
            movement = _comparison_activity_movement(current_activity, previous_activity)
            if _nonempty(current_activity.get("actual_start")) or _nonempty(current_activity.get("actual_finish")):
                upstream_candidates.append((aid, current_activity, movement))
        upstream = self._upstream_remaining_impact(
            current_key=current_key,
            candidates=upstream_candidates[: _UPSTREAM_REMAINING_IMPACT_CAP * 2],
        )
        return {
            "available": True,
            "diff_id": diff_id,
            "comparison_basis": comparison_context["comparison_basis"],
            "finish_movement_basis": comparison_context["finish_movement_basis"],
            "as_of_date": comparison_context["as_of_date"],
            "comparison_schedule_version_key": comparison_context.get("comparison_schedule_version_key")
            or effective_key,
            "direct_remaining_changes": {
                **direct_comparison,
                "default_limit": _DIRECT_REMAINING_CHANGE_CAP,
            },
            "upstream_remaining_impact": {
                "summary": {
                    "changed_upstream_count": len(upstream),
                    "affected_remaining_successor_count": sum(int(u.get("affected_remaining_successor_count") or 0) for u in upstream),
                },
                "items": upstream[:_UPSTREAM_REMAINING_IMPACT_CAP],
                "default_limit": _UPSTREAM_REMAINING_IMPACT_CAP,
                "caveat": "Associations are based on persisted relationships and changed activities; they are review cues, not causation findings.",
            },
        }

    def _upstream_remaining_impact(
        self,
        *,
        current_key: str,
        candidates: list[tuple[str, dict[str, Any], dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        if not candidates:
            return []
        out: list[dict[str, Any]] = []
        with open_connection(self._db_path) as conn:
            for aid, activity, movement in candidates:
                rows = conn.execute(
                    """
                    SELECT r.successor_activity_id,
                           a.total_float, a.derived_total_float_days, a.explicit_total_float_days,
                           a.is_critical
                    FROM procore_ep_schedule_relationships r
                    JOIN procore_ep_schedule_activities a
                      ON a.schedule_version_key=r.schedule_version_key
                     AND a.activity_id=r.successor_activity_id
                    WHERE r.schedule_version_key=?
                      AND r.predecessor_activity_id=?
                      AND (a.actual_finish IS NULL OR TRIM(a.actual_finish)='')
                    LIMIT ?
                    """,
                    (current_key, aid, _UPSTREAM_REMAINING_IMPACT_CAP),
                ).fetchall()
                if not rows:
                    continue
                critical_affected = sum(1 for row in rows if _is_critical_or_near(dict(row)))
                out.append(
                    {
                        "activity": _activity_item(activity),
                        "language": "appears associated with remaining successor movement; review sequence and logic",
                        "affected_remaining_successor_count": len(rows),
                        "affected_critical_or_near_count": critical_affected,
                        **movement,
                    }
                )
                if len(out) >= _UPSTREAM_REMAINING_IMPACT_CAP:
                    break
        return out

    def _computed_cpm(self, current_key: str) -> dict[str, Any]:
        canonical_summary = self._canonical_metrics.computed_cpm_summary(current_key)
        with open_connection(self._db_path) as conn:
            runs: dict[str, dict[str, Any]] = {}
            for row in conn.execute(
                    """
                    SELECT cpm_run_id, calculation_type, cpm_recalculation_status,
                           analysis_scope, source_run_id, created_at, node_count,
                           edge_count, diagnostic_count, computed_activity_count,
                           blocked_activity_count, is_acyclic
                    FROM schedule_cpm_runs
                    WHERE schedule_version_key=?
                    ORDER BY created_at DESC, cpm_run_id DESC
                    """,
                    (current_key,),
            ).fetchall():
                calc_type = str(row["calculation_type"])
                if calc_type not in runs:
                    runs[calc_type] = dict(row)
            source_run = next(
                (
                    runs[k]
                    for k in ("criticality", "float", "backward_pass", "forward_pass")
                    if runs.get(k)
                ),
                None,
            )
            critical_count = 0
            near_count = 0
            if source_run:
                row = conn.execute(
                    """
                    SELECT
                      SUM(CASE WHEN car.computed_critical_flag=1 THEN 1 ELSE 0 END) AS critical_count,
                      SUM(CASE WHEN car.computed_near_critical_flag=1 THEN 1 ELSE 0 END) AS near_count
                    FROM schedule_cpm_activity_results car
                    JOIN procore_ep_schedule_activities a
                      ON a.schedule_version_key=car.schedule_version_key
                     AND a.activity_id=car.activity_id
                    WHERE car.schedule_version_key=?
                      AND car.cpm_run_id=?
                      AND (a.actual_finish IS NULL OR TRIM(a.actual_finish)='')
                    """,
                    (current_key, source_run["cpm_run_id"]),
                ).fetchone()
                critical_count = int((row["critical_count"] if row else 0) or 0)
                near_count = int((row["near_count"] if row else 0) or 0)
            lp_run = runs.get("longest_path")
            primary_path = None
            path_items: list[dict[str, Any]] = []
            if lp_run:
                primary_path = conn.execute(
                    """
                    SELECT path_id, path_type, path_rank, path_status, path_basis,
                           start_activity_id, end_activity_id, activity_count,
                           relationship_count, path_duration, path_start_offset_days,
                           path_finish_offset_days, path_total_float
                    FROM schedule_cpm_paths
                    WHERE cpm_run_id=? AND schedule_version_key=?
                    ORDER BY path_rank, path_id
                    LIMIT 1
                    """,
                    (lp_run["cpm_run_id"], current_key),
                ).fetchone()
                if primary_path:
                    path_items = [
                        dict(row)
                        for row in conn.execute(
                            """
                            SELECT activity_id, activity_name,
                                   computed_early_start AS forecast_start,
                                   computed_early_finish AS forecast_finish,
                                   computed_total_float AS total_float,
                                   path_sequence
                            FROM schedule_cpm_path_activities
                            WHERE path_id=?
                            ORDER BY path_sequence
                            LIMIT ?
                            """,
                            (primary_path["path_id"], _CRITICAL_PATH_PREVIEW_CAP),
                        ).fetchall()
                    ]
        available = bool(runs)
        missing = [
            kind
            for kind in ("graph_diagnostics", "forward_pass", "backward_pass", "float", "longest_path", "criticality")
            if kind not in runs
        ]
        return {
            "summary": canonical_summary,
            "critical_path": {
                "available": bool(primary_path),
                "basis": "computed_cpm" if primary_path else "unavailable",
                "activity_count": dict(primary_path).get("activity_count") if primary_path else None,
                "items": [_activity_item(a) for a in path_items],
                "default_limit": _CRITICAL_PATH_PREVIEW_CAP,
                "caveats": [] if primary_path else ["No persisted longest-path CPM run is available."],
            },
        }

    def _remaining_health(
        self,
        *,
        remaining: list[dict[str, Any]],
        activity_summary: dict[str, Any],
        change_impact: dict[str, Any],
        cpm_summary: dict[str, Any],
        current_choice: _VersionChoice,
        previous: dict[str, Any] | None,
    ) -> dict[str, Any]:
        remaining_count = int(activity_summary.get("remaining_count") or 0)
        negative_float_count = int(activity_summary.get("negative_float_count") or 0)
        zero_float_count = int(activity_summary.get("zero_float_count") or 0)
        near_count = int(activity_summary.get("near_critical_count") or 0)
        constrained_count = int(activity_summary.get("constrained_remaining_count") or 0)
        drivers: list[str] = []
        if negative_float_count:
            drivers.append(f"{negative_float_count} remaining activities have negative float.")
        if change_impact.get("available") and change_impact["direct_remaining_changes"]["summary"].get("finish_moved_later_count"):
            drivers.append("Remaining activities moved later since the prior update.")
        if _requires_identity_review(current_choice.identity_match):
            drivers.append("Schedule identity review is required before comparison is reliable.")
        if not previous:
            drivers.append("No prior comparable update is available.")
        if not cpm_summary["summary"]["available"]:
            drivers.append("Computed CPM is unavailable.")
        if not drivers:
            drivers.append("Remaining-work schedule indicators are available for review.")
        status = "unknown"
        if remaining_count:
            status = "good"
            if near_count or constrained_count or not previous:
                status = "watch"
            if negative_float_count or near_count >= 10:
                status = "at_risk"
            if _requires_identity_review(current_choice.identity_match):
                status = "blocked"
        return {
            "status": status,
            "remaining_activity_count": remaining_count,
            "drivers": drivers[:5],
            "float_pressure": {
                "negative_float_count": negative_float_count,
                "zero_float_count": zero_float_count,
                "near_critical_count": near_count,
                "preview": [
                    {
                        "activity_id": row.get("activity_id"),
                        "activity_name": row.get("activity_name"),
                        "total_float": row.get("total_float") or row.get("derived_total_float_days"),
                    }
                    for row in remaining
                    if (_float_days(row) or 0) < 0
                ][:5],
            },
            "logic_risk": {
                "constrained_remaining_count": constrained_count,
                "missing_logic_count": None,
                "status": "relationship_detail_available" if remaining_count else "not_applicable",
            },
            "comparison_readiness": {
                "prior_update_available": previous is not None,
                "identity_review_required": _requires_identity_review(current_choice.identity_match),
            },
        }

    def _milestones(
        self,
        current_key: str,
        previous_key: str | None,
        recent: dict[str, Any],
    ) -> dict[str, Any]:
        with open_connection(self._db_path) as conn:
            remaining_milestone_count = int(conn.execute(
                """
                SELECT COUNT(*) FROM procore_ep_schedule_activities
                WHERE schedule_version_key=?
                  AND (actual_finish IS NULL OR TRIM(actual_finish)='')
                  AND (
                    is_milestone=1
                    OR LOWER(COALESCE(activity_name, '')) LIKE '%milestone%'
                    OR LOWER(COALESCE(activity_name, '')) LIKE '%substantial completion%'
                    OR LOWER(COALESCE(activity_name, '')) LIKE '%final completion%'
                  )
                """,
                (current_key,),
            ).fetchone()[0] or 0)
            at_risk_count = int(conn.execute(
                """
                SELECT COUNT(*) FROM procore_ep_schedule_activities
                WHERE schedule_version_key=?
                  AND (actual_finish IS NULL OR TRIM(actual_finish)='')
                  AND (
                    is_milestone=1
                    OR LOWER(COALESCE(activity_name, '')) LIKE '%milestone%'
                    OR LOWER(COALESCE(activity_name, '')) LIKE '%substantial completion%'
                    OR LOWER(COALESCE(activity_name, '')) LIKE '%final completion%'
                  )
                  AND (
                    is_critical=1
                    OR CAST(COALESCE(NULLIF(total_float, ''), NULLIF(derived_total_float_days, ''), NULLIF(explicit_total_float_days, ''), '999999') AS REAL) <= 10
                  )
                """,
                (current_key,),
            ).fetchone()[0] or 0)
            rows = [
                dict(row)
                for row in conn.execute(
                    f"""
                    SELECT {_ACTIVITY_COLUMNS}
                    FROM procore_ep_schedule_activities
                    WHERE schedule_version_key=?
                      AND (actual_finish IS NULL OR TRIM(actual_finish)='')
                      AND (
                        is_milestone=1
                        OR LOWER(COALESCE(activity_name, '')) LIKE '%milestone%'
                        OR LOWER(COALESCE(activity_name, '')) LIKE '%substantial completion%'
                        OR LOWER(COALESCE(activity_name, '')) LIKE '%final completion%'
                      )
                    ORDER BY COALESCE(remaining_finish, remaining_early_finish, finish_date, activity_id)
                    LIMIT ?
                    """,
                    (current_key, _MILESTONE_CAP),
                ).fetchall()
            ]
        previous_by_id = self._activity_rows_by_ids(previous_key, {str(a.get("activity_id")) for a in rows})
        moved_later = 0
        items = []
        for a in rows:
            prev = previous_by_id.get(str(a.get("activity_id")), {})
            movement = _date_delta_days(_parse_date(_comparison_finish_field(prev)), _parse_date(_comparison_finish_field(a)))
            if movement and movement > 0:
                moved_later += 1
            item = _activity_item(a)
            item["forecast_date"] = _comparison_finish_field(a)
            item["movement_days"] = movement
            item["inferred"] = not _truthy(a.get("is_milestone"))
            items.append(item)
        return {
            "items": items,
            "remaining_milestone_count": remaining_milestone_count,
            "at_risk_count": at_risk_count,
            "moved_later_count": moved_later,
            "completed_recently_count": recent.get("completed_milestone_count", 0),
        }

    def _forecast_finish(
        self, current_key: str, previous_key: str | None
    ) -> dict[str, Any]:
        with open_connection(self._db_path) as conn:
            current_finish = _parse_date(conn.execute(
                f"""
                SELECT MAX({comparison_finish_sql("a")})
                FROM procore_ep_schedule_activities a
                WHERE a.schedule_version_key=?
                  AND (a.actual_finish IS NULL OR TRIM(a.actual_finish)='')
                """,
                (current_key,),
            ).fetchone()[0])
            previous_finish = None
            if previous_key:
                previous_finish = _parse_date(conn.execute(
                    f"""
                    SELECT MAX({comparison_finish_sql("p")})
                    FROM procore_ep_schedule_activities c
                    JOIN procore_ep_schedule_activities p
                      ON p.activity_id=c.activity_id
                     AND p.schedule_version_key=?
                    WHERE c.schedule_version_key=?
                      AND (c.actual_finish IS NULL OR TRIM(c.actual_finish)='')
                    """,
                    (previous_key, current_key),
                ).fetchone()[0])
        return {
            "current_forecast_finish": _date_str(current_finish),
            "previous_forecast_finish": _date_str(previous_finish),
            "movement_days": _date_delta_days(previous_finish, current_finish),
        }

    def _actions(
        self,
        *,
        readiness_inputs: dict[str, Any],
        remaining_health: dict[str, Any],
        forecast: dict[str, Any],
        milestones: dict[str, Any],
    ) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []

        def add(priority: int, code: str, title: str, explanation: str, evidence: str, review: str) -> None:
            actions.append(
                {
                    "priority": priority,
                    "code": code,
                    "title": title,
                    "explanation": _safe_story_text(explanation),
                    "evidence_basis": evidence,
                    "recommended_review": _safe_story_text(review),
                    "drilldown_anchor": code,
                }
            )

        current_choice = readiness_inputs["current_choice"]
        if _requires_identity_review(current_choice.identity_match):
            add(100, "identity_review", "Resolve schedule series match", "Comparison is blocked until the current update is matched to the correct schedule series.", "schedule identity match requires review", "Open identity review before relying on update comparison.")
        if not readiness_inputs["previous"]:
            add(90, "no_prior_update", "Import or confirm a prior update", "No comparable prior update is available, so movement and trend context are limited.", "no prior comparable schedule", "Confirm whether an earlier update should be imported or matched.")
        neg = remaining_health["float_pressure"]["negative_float_count"]
        if neg:
            add(80, "negative_float", "Review remaining negative-float work", f"{neg} remaining activities are below zero float.", "remaining-work float pressure", "Review the activities and confirm the current completion sequence.")
        movement = forecast.get("movement_days")
        if movement and movement > 0:
            add(75, "forecast_finish_moved_later", "Review forecast finish movement", f"Forecast finish moved {movement} days later versus comparable remaining work.", "current-vs-previous forecast finish comparison", "Confirm which activities are driving the finish movement.")
        direct = readiness_inputs["change_impact"].get("direct_remaining_changes", {}).get("summary", {})
        if direct.get("finish_moved_later_count"):
            add(70, "remaining_work_moved_later", "Review remaining activities that moved later", f"{direct['finish_moved_later_count']} remaining activities moved later.", "direct persisted activity comparison", "Review the top changed remaining activities and affected WBS areas.")
        upstream = readiness_inputs["change_impact"].get("upstream_remaining_impact", {}).get("summary", {})
        if upstream.get("changed_upstream_count"):
            add(60, "upstream_sequence_review", "Review upstream changes tied to remaining successors", "Completed or in-progress changed activities appear associated with remaining successor work.", "persisted relationships and changed activity facts", "Review sequence and logic before the next update.")
        if milestones.get("moved_later_count"):
            add(55, "milestones_moved", "Review moved remaining milestones", f"{milestones['moved_later_count']} remaining milestones moved later.", "milestone forecast comparison", "Confirm milestone dates and downstream implications.")
        if not readiness_inputs["cpm_summary"]["summary"]["available"]:
            add(40, "cpm_unavailable", "Confirm critical path evidence", "Computed CPM is unavailable, so critical-path confidence is limited.", "computed CPM run availability", "Use technical CPM drilldown or run the approved CPM workflow outside this page.")
        actions.sort(key=lambda a: (-int(a["priority"]), str(a["code"])))
        return actions[:_ALL_ACTIONS_CAP]

    def _readiness(
        self,
        *,
        versions: list[dict[str, Any]],
        current_choice: _VersionChoice,
        previous: dict[str, Any] | None,
        cpm_summary: dict[str, Any],
        change_impact: dict[str, Any],
        milestones: dict[str, Any],
        remaining_count: int,
        trends: dict[str, Any],
        baseline_summary: dict[str, Any] | None = None,
        schedule_trust: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        del versions, milestones
        identity_required = (
            _requires_identity_review(current_choice.identity_match)
            or (schedule_trust or {}).get("status") == "review_required"
        )
        baseline = baseline_summary or {}
        baseline_unavailable = baseline.get("status") == "no_selection" and not baseline.get("original_baseline_detected")
        baseline_reason = (
            "No selected comparison baseline."
            if baseline_unavailable
            else None
        )
        checks = {
            "no_schedule": {"required": False, "reason": None},
            "no_prior_update": {"required": previous is None, "reason": "no comparable prior update" if previous is None else None},
            "identity_review_required": {"required": identity_required, "reason": "schedule identity match requires review" if identity_required else None},
            "cpm_unavailable": {"required": not cpm_summary["summary"]["available"], "reason": "no persisted computed CPM run" if not cpm_summary["summary"]["available"] else None},
            "diff_unavailable": {"required": not change_impact.get("available"), "reason": change_impact.get("reason") if not change_impact.get("available") else None},
            "baseline_unavailable": {"required": baseline_unavailable, "reason": baseline_reason},
            "no_remaining_activities": {"required": remaining_count == 0, "reason": "all activities have actual finish values" if remaining_count == 0 else None},
            "insufficient_trend_history": {"required": not trends.get("available"), "reason": trends.get("reason") if not trends.get("available") else None},
        }
        blocking = identity_required or remaining_count == 0
        return {
            **checks,
            "ready_for_pm_review": not blocking,
            "partial_reasons": [
                key for key, value in checks.items() if value.get("required")
            ],
        }

    def _trends(self, versions: list[dict[str, Any]], current_choice: _VersionChoice) -> dict[str, Any]:
        current_identity = _identity_key(current_choice.identity_match)
        comparable: list[dict[str, Any]] = []
        for version in versions:
            match = self._identity.get_match_for_version(str(version["schedule_version_key"]))
            if current_identity and _identity_key(match) != current_identity:
                continue
            comparable.append(version)
        comparable.sort(key=lambda v: _date_sort_key(self._data_date(v)))
        if len(comparable) < 2:
            return {
                "available": False,
                "reason": "at_least_two_comparable_updates_required",
                "minimum_required": 2,
                "comparable_update_count": len(comparable),
                "series": [],
            }
        return {
            "available": True,
            "reason": None,
            "minimum_required": 2,
            "comparable_update_count": len(comparable),
            "series": [
                {
                    "friendly_label": self._friendly_label(v),
                    "data_date": _date_str(self._data_date(v)),
                    "activity_count": v.get("activity_count"),
                }
                for v in comparable[-_VERSION_CAP:]
            ],
        }

    def _trend_series(
        self,
        versions: list[dict[str, Any]],
        current_choice: _VersionChoice,
        *,
        previous_key: str | None,
    ) -> dict[str, Any]:
        base = self._trends(versions, current_choice)
        if not base.get("available"):
            return {**base, "metrics": []}
        current_identity = _identity_key(current_choice.identity_match)
        comparable = [
            v
            for v in versions
            if not current_identity
            or _identity_key(self._identity.get_match_for_version(str(v["schedule_version_key"]))) == current_identity
        ]
        comparable.sort(key=lambda v: _date_sort_key(self._data_date(v)))
        points: list[dict[str, Any]] = []
        prior_key: str | None = None
        for version in comparable[-_VERSION_CAP:]:
            version_key = str(version["schedule_version_key"])
            with open_connection(self._db_path) as conn:
                remaining_count = int(
                    conn.execute(
                        """
                        SELECT COUNT(*) FROM procore_ep_schedule_activities
                        WHERE schedule_version_key=?
                          AND (actual_finish IS NULL OR TRIM(actual_finish)='')
                        """,
                        (version_key,),
                    ).fetchone()[0]
                    or 0
                )
                negative_float = int(
                    conn.execute(
                        """
                        SELECT COUNT(*) FROM procore_ep_schedule_activities
                        WHERE schedule_version_key=?
                          AND (actual_finish IS NULL OR TRIM(actual_finish)='')
                          AND CAST(COALESCE(NULLIF(total_float, ''), NULLIF(derived_total_float_days, ''), NULLIF(explicit_total_float_days, ''), '999999') AS REAL) < 0
                        """,
                        (version_key,),
                    ).fetchone()[0]
                    or 0
                )
                forecast_finish = _parse_date(
                    conn.execute(
                        f"""
                        SELECT MAX({comparison_finish_sql('a')})
                        FROM procore_ep_schedule_activities a
                        WHERE a.schedule_version_key=?
                          AND (a.actual_finish IS NULL OR TRIM(a.actual_finish)='')
                        """,
                        (version_key,),
                    ).fetchone()[0]
                )
                critical_remaining = int(
                    conn.execute(
                        """
                        SELECT COUNT(*) FROM procore_ep_schedule_activities
                        WHERE schedule_version_key=?
                          AND (actual_finish IS NULL OR TRIM(actual_finish)='')
                          AND CAST(COALESCE(NULLIF(is_critical, ''), '0') AS INTEGER) = 1
                        """,
                        (version_key,),
                    ).fetchone()[0]
                    or 0
                )
            moved_later = 0
            if prior_key:
                moved_later = int(
                    self._comparison.compare_versions(left_key=version_key, right_key=prior_key)["summary"].get(
                        "finish_moved_later_count"
                    )
                    or 0
                )
            prior_version = next(
                (v for v in comparable if str(v.get("schedule_version_key")) == prior_key),
                None,
            )
            prior_date = self._data_date(prior_version) if prior_version else None
            current_date = self._data_date(version)
            gap_days = (
                (current_date - prior_date).days
                if prior_date and current_date
                else None
            )
            milestone_moved_later = 0
            if prior_key:
                try:
                    comparison = self._comparison.compare_versions(left_key=version_key, right_key=prior_key)
                    milestone_moved_later = int(
                        comparison.get("milestones", {}).get("summary", {}).get("moved_later_count")
                        or comparison.get("summary", {}).get("moved_remaining_milestones_count")
                        or 0
                    )
                except Exception:
                    milestone_moved_later = 0
            points.append(
                {
                    "friendly_label": self._friendly_label(version),
                    "data_date": _date_str(current_date),
                    "forecast_finish": _date_str(forecast_finish),
                    "remaining_activity_count": remaining_count,
                    "negative_float_remaining_count": negative_float,
                    "critical_remaining_count": critical_remaining,
                    "milestone_moved_later_count": milestone_moved_later,
                    "finish_moved_later_count": moved_later,
                    "data_date_gap_days": gap_days,
                }
            )
            prior_key = version_key
        return {
            **base,
            "metrics": points,
        }

    def _command_summary(
        self,
        *,
            forecast: dict[str, Any],
            remaining: list[dict[str, Any]],
        remaining_health: dict[str, Any],
        cpm_summary: dict[str, Any],
        change_impact: dict[str, Any],
        milestones: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "forecast_finish": forecast.get("current_forecast_finish"),
            "forecast_finish_delta_days": forecast.get("movement_days"),
            "remaining_activity_count": remaining_health["remaining_activity_count"],
            "remaining_milestone_count": milestones.get("remaining_milestone_count", 0),
            "critical_remaining_count": cpm_summary["summary"].get("critical_remaining_count") or sum(1 for a in remaining if _truthy(a.get("is_critical"))),
            "near_critical_remaining_count": cpm_summary["summary"].get("near_critical_remaining_count") or remaining_health["float_pressure"]["near_critical_count"],
            "negative_float_remaining_count": remaining_health["float_pressure"]["negative_float_count"],
            "zero_float_remaining_count": remaining_health["float_pressure"]["zero_float_count"],
            "remaining_finish_moved_later_count": change_impact.get("direct_remaining_changes", {}).get("summary", {}).get("finish_moved_later_count", 0),
            "remaining_finish_moved_earlier_count": change_impact.get("direct_remaining_changes", {}).get("summary", {}).get("finish_moved_earlier_count", 0),
            "remaining_finish_changed_count": change_impact.get("direct_remaining_changes", {}).get("summary", {}).get("finish_changed_count", 0),
            "new_remaining_activities": change_impact.get("direct_remaining_changes", {}).get("summary", {}).get("new_remaining_activities", 0),
            "health_status": remaining_health["status"],
            "health_summary": remaining_health["drivers"][0] if remaining_health["drivers"] else None,
        }

    def _schedule_story(
        self,
        *,
        current_label: str,
        current_data_date: date | None,
        previous: dict[str, Any] | None,
        previous_data_date: date | None,
        forecast: dict[str, Any],
        recent: dict[str, Any],
        remaining: list[dict[str, Any]],
        remaining_health: dict[str, Any],
        cpm_summary: dict[str, Any],
        change_impact: dict[str, Any],
        change_driver_analysis: dict[str, Any] | None = None,
        actions: list[dict[str, Any]],
        readiness: dict[str, Any],
    ) -> dict[str, Any]:
        prior_driver_analysis = (change_driver_analysis or {}).get("prior_update") or change_driver_analysis or {}
        driver_narrative = self._drivers.build_narrative(prior_driver_analysis)
        movement = forecast.get("movement_days")
        summary = change_impact.get("direct_remaining_changes", {}).get("summary", {}) if change_impact.get("available") else {}
        later = int(summary.get("finish_moved_later_count") or 0)
        earlier = int(summary.get("finish_moved_earlier_count") or 0)
        finish_changed = int(summary.get("finish_changed_count") or 0)
        worsened = int(summary.get("worsened_float_count") or 0)
        milestones_later = int(summary.get("moved_remaining_milestones_count") or 0)
        negative_float = remaining_health["float_pressure"]["negative_float_count"]
        if movement is None:
            headline = f"{current_label} is ready for remaining-work review."
        elif movement > 0:
            headline = f"Forecast finish moved {movement} days later since the previous update."
        elif movement < 0:
            headline = f"Forecast finish moved {abs(movement)} days earlier since the previous update."
        elif later > 0 or finish_changed > 0:
            headline = "Forecast finish is unchanged, but remaining work moved materially."
        elif negative_float > 0:
            headline = "Final completion is holding, but the remaining sequence is under pressure."
        else:
            headline = "Forecast finish is unchanged from the previous update."
        primary_driver = "No comparable prior update is available."
        if change_impact.get("available"):
            if later and earlier:
                primary_driver = (
                    f"{later} remaining activities moved later and {earlier} moved earlier "
                    "in the persisted update comparison."
                )
            elif later:
                primary_driver = f"{later} remaining activities moved later in the persisted update comparison."
            elif earlier:
                primary_driver = f"{earlier} remaining activities moved earlier in the persisted update comparison."
            else:
                primary_driver = "No remaining finish movement detected in the persisted update comparison."
        primary_driver_narrative = driver_narrative.get("primary_driver_narrative")
        if primary_driver_narrative:
            primary_driver = primary_driver_narrative
        what_changed = primary_driver
        if change_impact.get("available") and (later or finish_changed or worsened):
            what_changed = (
                f"{later} remaining activities moved later, {finish_changed} changed finish, "
                f"and {worsened} lost float."
            )
        if driver_narrative.get("top_review_sequence"):
            seq = driver_narrative["top_review_sequence"]
            why_it_matters = (
                f"Candidate driver {seq.get('driver_activity_name') or seq.get('driver_activity_id')} "
                f"in {seq.get('wbs_code') or 'the schedule'} appears connected to "
                f"{seq.get('downstream_count', 0)} downstream activities — review this sequence first."
            )
        else:
            why_it_matters = (
                f"The schedule is holding the final finish date while {negative_float} remaining activities "
                f"carry negative float."
                if movement in (0, None) and negative_float > 0
                else "Review whether remaining-work movement affects completion sequence and milestone readiness."
            )
        recent_summary = f"{recent['completed_count']} activities completed and {recent['started_count']} activities started in the review window."
        remaining_summary = f"{remaining_health['remaining_activity_count']} activities remain open; health is {remaining_health['status'].replace('_', ' ')}."
        cp_summary = (
            f"Computed CPM shows {cpm_summary['summary']['critical_remaining_count']} critical and {cpm_summary['summary']['near_critical_remaining_count']} near-critical remaining activities."
            if cpm_summary["summary"]["available"]
            else "Computed CPM is unavailable, so critical-path confidence is limited."
        )
        review_bits = []
        if negative_float > 0:
            review_bits.append("the negative-float sequence")
        if milestones_later > 0:
            review_bits.append(f"the {milestones_later} slipped milestones")
        if later > 0:
            review_bits.append("the activities driving the remaining-work movement")
        review_next = actions[0]["title"] if actions else (
            f"Review {', '.join(review_bits)}." if review_bits else "Review remaining work and milestone movement."
        )
        synopsis = (
            f"The current update is {current_label} with data date {_date_str(current_data_date) or 'unknown'}. "
            f"Previous data date is {_date_str(previous_data_date) if previous else 'not available'}. "
            f"{what_changed} {why_it_matters} {review_next}"
        )
        caveats = []
        if readiness["identity_review_required"]["required"]:
            caveats.append("Schedule identity review is required before relying on update comparison.")
        if readiness["diff_unavailable"]["required"]:
            caveats.append("Version-diff detail is unavailable for this project update.")
        if readiness["cpm_unavailable"]["required"]:
            caveats.append("Computed CPM is unavailable for this update.")
        caveats.append("This summary identifies schedule movement and review priorities. It does not determine delay causation, responsibility, entitlement, or compensability.")
        if prior_driver_analysis.get("available"):
            caveats.append("Driver rankings and downstream chains are sequence cues for review, not causation findings.")
        story = {
            "headline": _safe_story_text(headline),
            "synopsis": _safe_story_text(synopsis),
            "what_changed": _safe_story_text(what_changed),
            "why_it_matters": _safe_story_text(why_it_matters),
            "primary_change_driver": _safe_story_text(primary_driver),
            "recent_progress_summary": _safe_story_text(recent_summary),
            "remaining_work_summary": _safe_story_text(remaining_summary),
            "critical_path_summary": _safe_story_text(cp_summary),
            "review_next_summary": _safe_story_text(review_next),
            "caveats": [_safe_story_text(c) for c in caveats],
        }
        if primary_driver_narrative:
            story["primary_driver_narrative"] = _safe_story_text(primary_driver_narrative)
        if driver_narrative.get("top_review_sequence"):
            story["top_review_sequence"] = driver_narrative["top_review_sequence"]
        return story

    # ------------------------------------------------------------------ states and helpers

    def _empty_summary(self, project_key: str, project_name: str, as_of_date: date) -> dict[str, Any]:
        readiness = {
            "no_schedule": {"required": True, "reason": "no committed schedule imports for project"},
            "no_prior_update": {"required": True, "reason": "no schedule update available"},
            "identity_review_required": {"required": False, "reason": None},
            "cpm_unavailable": {"required": True, "reason": "no schedule update available"},
            "diff_unavailable": {"required": True, "reason": "no schedule update available"},
            "baseline_unavailable": {"required": True, "reason": "no schedule update available"},
            "no_remaining_activities": {"required": False, "reason": None},
            "insufficient_trend_history": {"required": True, "reason": "at_least_two_comparable_updates_required"},
            "ready_for_pm_review": False,
            "partial_reasons": ["no_schedule", "no_prior_update", "cpm_unavailable", "diff_unavailable", "baseline_unavailable", "insufficient_trend_history"],
        }
        return {
            "surface": "project_schedule_hub",
            "project_key": project_key,
            "project_display_name": project_name,
            "as_of_date": as_of_date.isoformat(),
            "status": "no_schedule",
            "current_schedule": {"available": False},
            "previous_update": {"available": False},
            "readiness": readiness,
            "schedule_story": {
                "headline": "No schedule update is imported for this project.",
                "synopsis": "Import a schedule update to review remaining work, movement, critical path, and PM review actions.",
                "primary_change_driver": "No schedule data is available.",
                "recent_progress_summary": "Recent progress is unavailable until a schedule is imported.",
                "remaining_work_summary": "Remaining work is unavailable until a schedule is imported.",
                "critical_path_summary": "Critical path is unavailable until schedule and CPM evidence are available.",
                "review_next_summary": "Import a schedule update for this project.",
                "caveats": ["No schedule conclusions are available without imported schedule data."],
            },
            "command_summary": {},
            "recent_progress": {},
            "change_impact": {"available": False, "reason": "no_schedule"},
            "remaining_health": {"status": "unknown", "drivers": ["No schedule data is available."]},
            "critical_path": {"available": False},
            "milestones": {"items": []},
            "computed_cpm": {"available": False, "summary": "Computed CPM is unavailable because no schedule is imported."},
            "trend_summary": {"available": False, "reason": "at_least_two_comparable_updates_required", "comparable_update_count": 0},
            "actions": {
                "preview_limit": 5,
                "preview": [{
                    "priority": 100,
                    "code": "import_schedule",
                    "title": "Import a schedule update",
                    "explanation": "No schedule is imported for this project.",
                    "evidence_basis": "schedule import list",
                    "recommended_review": "Open schedule import and upload the current project schedule.",
                    "drilldown_anchor": "import_schedule",
                }],
                "all_items": [],
                "total_count": 1,
            },
            "technical_links": {
                "schedule_import_url": f"/projects/{project_key}/schedule/import",
            },
            "technical_evidence": {"collapsed_by_default": True, "raw_keys_available": False},
        }

    def _review_required_summary(
        self, project_key: str, project_name: str, as_of_date: date, versions: list[dict[str, Any]]
    ) -> dict[str, Any]:
        out = self._empty_summary(project_key, project_name, as_of_date)
        out["status"] = "review_required"
        out["current_schedule"] = {"available": False, "candidate_count": len(versions)}
        out["readiness"]["no_schedule"] = {"required": False, "reason": None}
        out["readiness"]["identity_review_required"] = {"required": True, "reason": "multiple possible current schedules require review"}
        out["schedule_story"]["headline"] = "Schedule identity review is required."
        out["schedule_story"]["synopsis"] = "Multiple possible current schedule updates exist. Resolve schedule identity before relying on comparison or remaining-work health."
        return out

    def _project_display_name(self, project_key: str) -> str:
        with open_connection(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT display_name FROM procore_ep_projects
                WHERE project_key=?
                ORDER BY is_current DESC, updated_utc DESC
                LIMIT 1
                """,
                (project_key,),
            ).fetchone()
        return str(row[0]) if row and row[0] else project_key

    @staticmethod
    def _data_date(version: dict[str, Any] | None) -> date | None:
        if not version:
            return None
        return _parse_date(version.get("data_date")) or _parse_date(str(version.get("schedule_version_key") or "").split("|")[-1])

    @staticmethod
    def _friendly_label(version: dict[str, Any] | None) -> str:
        if not version:
            return ""
        for value in (version.get("display_label"), version.get("source_filename"), version.get("source_filename_redacted")):
            label = _label_from_source(value)
            if label:
                return label
        data_date = ProjectScheduleSummaryService._data_date(version)
        if data_date:
            return f"Update {data_date.strftime('%b %d, %Y')}"
        raw = str(version.get("schedule_version_key") or "")
        return "Schedule Update" if _RAW_KEY_PATTERN.match(raw) else raw or "Schedule Update"

    @staticmethod
    def _technical_links(
        project_key: str, current_key: str, previous_key: str | None, change_impact: dict[str, Any]
    ) -> dict[str, Any]:
        encoded_current = current_key.replace("|", "%7C")
        links = {
            "schedule_versions_url": f"/schedules/versions?project={project_key}",
            "schedule_health_url": f"/schedules/quality?project={project_key}&version={encoded_current}",
            "computed_cpm_url": f"/schedules/cpm?project={project_key}&version={encoded_current}",
            "activities_url": f"/schedules/activities?project={project_key}&version={encoded_current}",
            "identity_review_url": f"/schedules/identity-review?project={project_key}",
            "schedule_import_url": f"/projects/{project_key}/schedule/import",
            "schedule_workbench_url": f"/projects/{project_key}/schedule/workbench",
            "schedule_export_url": f"/api/projects/{project_key}/schedule/export?format=markdown",
        }
        if change_impact.get("diff_id"):
            links["version_comparison_url"] = f"/schedules/version-diff?project={project_key}&diff_id={change_impact['diff_id']}"
        elif previous_key:
            links["version_comparison_url"] = f"/schedules/version-diff?project={project_key}"
        return links


def _result_row_count(result: Any) -> int | None:
    if isinstance(result, list):
        return len(result)
    if isinstance(result, dict):
        for key in ("total_count", "remaining_count", "completed_count", "activity_count"):
            value = result.get(key)
            if isinstance(value, int):
                return value
        for key in ("items", "series", "preview", "all_items"):
            value = result.get(key)
            if isinstance(value, list):
                return len(value)
    return None


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text[: len(fmt)], fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _date_str(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _date_sort_key(value: date | None) -> str:
    return value.isoformat() if value else ""


def _date_delta_days(old: date | None, new: date | None) -> int | None:
    if not old or not new:
        return None
    return (new - old).days


def _date_in_window(value: date | None, start: date, end: date) -> bool:
    return bool(value and start <= value <= end)


def _nonempty(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _float_days(activity: dict[str, Any]) -> float | None:
    for key in ("total_float", "derived_total_float_days", "explicit_total_float_days", "computed_total_float"):
        value = activity.get(key)
        if value is None or str(value).strip() == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _comparison_finish_sql(alias: str) -> str:
    return (
        f"COALESCE(NULLIF(TRIM({alias}.remaining_finish), ''), "
        f"NULLIF(TRIM({alias}.finish_date), ''), "
        f"NULLIF(TRIM({alias}.remaining_early_finish), ''))"
    )


def _comparison_start_sql(alias: str) -> str:
    return (
        f"COALESCE(NULLIF(TRIM({alias}.remaining_start), ''), "
        f"NULLIF(TRIM({alias}.start_date), ''), "
        f"NULLIF(TRIM({alias}.remaining_early_start), ''))"
    )


def _comparison_finish_field(activity: dict[str, Any]) -> Any:
    for key in ("remaining_finish", "finish_date", "remaining_early_finish"):
        if _nonempty(activity.get(key)):
            return activity.get(key)
    return None


def _comparison_start_field(activity: dict[str, Any]) -> Any:
    for key in ("remaining_start", "start_date", "remaining_early_start"):
        if _nonempty(activity.get(key)):
            return activity.get(key)
    return None


def _forecast_finish_field(activity: dict[str, Any]) -> Any:
    for key in ("remaining_finish", "remaining_early_finish", "finish_date", "planned_finish", "target_finish", "baseline_finish"):
        if _nonempty(activity.get(key)):
            return activity.get(key)
    return None


def _forecast_start_field(activity: dict[str, Any]) -> Any:
    for key in ("remaining_start", "remaining_early_start", "start_date", "planned_start", "target_start", "baseline_start"):
        if _nonempty(activity.get(key)):
            return activity.get(key)
    return None


def _comparison_activity_movement(current: dict[str, Any], previous: dict[str, Any]) -> dict[str, Any]:
    return {
        "start_delta_days": _date_delta_days(
            _parse_date(_comparison_start_field(previous)),
            _parse_date(_comparison_start_field(current)),
        ),
        "finish_delta_days": _date_delta_days(
            _parse_date(_comparison_finish_field(previous)),
            _parse_date(_comparison_finish_field(current)),
        ),
        "float_delta_days": (
            None
            if _float_days(previous) is None or _float_days(current) is None
            else _float_days(current) - _float_days(previous)
        ),
    }


def _activity_movement(current: dict[str, Any], previous: dict[str, Any]) -> dict[str, Any]:
    return _comparison_activity_movement(current, previous)


def _activity_item_from_drilldown(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "activity_id": row.get("activity_id"),
        "activity_name": row.get("activity_name"),
        "wbs_code": row.get("wbs_code"),
        "wbs_path": row.get("wbs_path"),
        "forecast_start": row.get("current_start"),
        "forecast_finish": row.get("current_finish"),
        "actual_start": None,
        "actual_finish": None,
        "total_float": row.get("current_float"),
    }


def _activity_item(activity: dict[str, Any]) -> dict[str, Any]:
    return {
        "activity_id": activity.get("activity_id"),
        "activity_name": activity.get("activity_name"),
        "wbs_code": activity.get("wbs_code"),
        "wbs_path": activity.get("wbs_path"),
        "forecast_start": _forecast_start_field(activity),
        "forecast_finish": _forecast_finish_field(activity),
        "actual_start": activity.get("actual_start"),
        "actual_finish": activity.get("actual_finish"),
        "total_float": activity.get("total_float") or activity.get("computed_total_float"),
    }


def _is_milestone(activity: dict[str, Any]) -> bool:
    if _truthy(activity.get("is_milestone")):
        return True
    name = str(activity.get("activity_name") or "").lower()
    duration = str(activity.get("duration_remaining") or activity.get("duration_original") or "").strip()
    return ("milestone" in name or "substantial completion" in name or "final completion" in name) and duration in {"", "0", "0.0"}


def _is_critical_or_near(activity: dict[str, Any]) -> bool:
    if _truthy(activity.get("is_critical")) or _truthy(activity.get("computed_critical_flag")) or _truthy(activity.get("computed_near_critical_flag")):
        return True
    f = _float_days(activity)
    return f is not None and f <= 10


def _successor_map(relationships: list[dict[str, Any]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for rel in relationships:
        pred = str(rel.get("predecessor_activity_id") or "")
        succ = str(rel.get("successor_activity_id") or "")
        if pred and succ:
            out.setdefault(pred, []).append(succ)
    return out


def _remaining_successors(
    activity_id: str, successor_map: dict[str, list[str]], remaining_ids: set[str]
) -> list[str]:
    found: list[str] = []
    seen = {activity_id}
    queue: deque[str] = deque(successor_map.get(activity_id, []))
    while queue and len(found) < 25:
        node = queue.popleft()
        if node in seen:
            continue
        seen.add(node)
        if node in remaining_ids:
            found.append(node)
        queue.extend(successor_map.get(node, []))
    return found


def _identity_key(match: dict[str, Any] | None) -> str | None:
    return str(match.get("schedule_identity_key")) if match and match.get("schedule_identity_key") else None


def _requires_identity_review(match: dict[str, Any] | None) -> bool:
    return bool(match and int(match.get("requires_review") or 0))


def _label_from_source(value: Any) -> str | None:
    if not value:
        return None
    text = str(value).strip().split("/")[-1]
    text = re.sub(r"\.(zip|xer|xml|pmxml|csv)$", "", text, flags=re.I)
    if not text or _RAW_KEY_PATTERN.match(text):
        return None
    match = re.search(r"\b([A-Z]{2,}[A-Z0-9]*\d{1,3})\b", text.upper())
    return match.group(1) if match else text


def _safe_story_text(text: str) -> str:
    safe = text
    for word in _FORBIDDEN_STORY_WORDS:
        safe = re.sub(re.escape(word), "schedule movement", safe, flags=re.I)
    return safe


def _pm_cpm_run_payload(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return {
        key: item
        for key, item in value.items()
        if key != "schedule_version_key"
    }


def _pm_cpm_run_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [payload for item in value if (payload := _pm_cpm_run_payload(item))]


def _pm_cpm_summary_payload(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    out = {
        key: item
        for key, item in value.items()
        if key != "schedule_version_key"
    }
    out["selected_cpm_run"] = _pm_cpm_run_payload(value.get("selected_cpm_run"))
    out["all_cpm_runs"] = _pm_cpm_run_list(value.get("all_cpm_runs"))
    out["excluded_cpm_runs"] = _pm_cpm_run_list(value.get("excluded_cpm_runs"))
    out["run_availability"] = {
        key: _pm_cpm_run_payload(item)
        for key, item in (value.get("run_availability") or {}).items()
    }
    return out
