"""Review cue collection and materialization for Project Schedule Review Workbench."""

from __future__ import annotations

from datetime import date
from typing import Any

from hb_assistant.store.connection import open_connection
from hb_assistant.store.schedule_identity_repository import parse_schedule_version_data_date
from hb_assistant.store.schedule_quality_repository import ScheduleQualityRepository

from .project_schedule_baseline_vocabulary import comparison_label_for_basis
from .project_schedule_comparison_basis_resolver import resolve_workbench_comparison_basis
from .project_schedule_review_cue_taxonomy import apply_taxonomy_fields
from .project_schedule_review_evidence_service import ProjectScheduleReviewEvidenceService
from .project_schedule_udf_normalization_service import ProjectScheduleUdfNormalizationService
from .project_schedule_visualization_metric_contract import NON_CAUSATION_CAVEAT

NON_CAUSATION_CUE = (
    "This is a schedule-control review cue for PM follow-up. "
    "It is not a causation, responsibility, entitlement, compensability, or delay-damages determination."
)

CONFIDENCE_PRODUCTION = "production_backed"
CONFIDENCE_PARTIAL = "partial_dimension_support"
CONFIDENCE_SPARSE = "sparse_support"
CONFIDENCE_READINESS = "readiness_only"
CONFIDENCE_BLOCKED = "blocked"

_ITEM_METRIC_SHOULD_HAVE_FINISHED = "metric_should_have_finished"
_ITEM_METRIC_WINDOW_START = "metric_window_start"
_ITEM_METRIC_WINDOW_FINISH = "metric_window_finish"
_ITEM_METRIC_CRITICAL_ISSUES = "metric_critical_issues"
_ITEM_METRIC_DELAY = "metric_delay_analysis"
_ITEM_METRIC_QUALITY = "metric_quality_finding"
_ITEM_METRIC_COMPRESSION = "metric_compression_readiness"

_SEVERITY_PRIORITY = {"critical": 92, "high": 82, "medium": 62, "low": 42}
_ACTIVITY_CUE_LIMIT = 25


class ProjectScheduleReviewCueService:
    """Collect schedule-control review cues from hub signals and Phase 8B metrics."""

    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path
        self._udf = ProjectScheduleUdfNormalizationService(db_path=db_path)
        self._evidence = ProjectScheduleReviewEvidenceService(db_path=db_path)
        self._quality_repo = ScheduleQualityRepository(db_path=db_path)

    def cue_source_map(self) -> list[dict[str, Any]]:
        return [
            {"source_metric_key": "change_driver_analysis", "signal_types": ["driver"], "materializable": True},
            {"source_metric_key": "milestones", "signal_types": ["milestone_moved_later"], "materializable": True},
            {"source_metric_key": "remaining_health", "signal_types": ["negative_float"], "materializable": True},
            {"source_metric_key": "schedule_changes_over_time", "signal_types": ["worsened_float"], "materializable": True},
            {"source_metric_key": "critical_path_length_index", "signal_types": ["critical_remaining"], "materializable": True},
            {"source_metric_key": "should_have_finished_status", "signal_types": ["at_risk_activity", "delayed_activity"], "materializable": True},
            {"source_metric_key": "window_start_accuracy", "signal_types": ["late_start", "did_not_start"], "materializable": True},
            {"source_metric_key": "window_finish_accuracy", "signal_types": ["late_finish", "did_not_finish"], "materializable": True},
            {"source_metric_key": "critical_issues_category_model", "signal_types": ["issue_category"], "materializable": True},
            {"source_metric_key": "delay_analysis", "signal_types": ["period_movement"], "materializable": True},
            {"source_metric_key": "schedule_quality_findings", "signal_types": ["quality_finding"], "materializable": True},
            {"source_metric_key": "schedule_compression_ratio", "signal_types": ["compression_readiness"], "materializable": True},
        ]

    def collect_review_cues(
        self,
        *,
        project_key: str,
        schedule_version_key: str,
        as_of_date: date,
        driver_analysis: dict[str, Any] | None = None,
        milestones: dict[str, Any] | None = None,
        remaining_health: dict[str, Any] | None = None,
        cpm_summary: dict[str, Any] | None = None,
        change_impact: dict[str, Any] | None = None,
        remaining_activities: list[dict[str, Any]] | None = None,
        comparison_basis: str = "prior_update",
        baseline_summary: dict[str, Any] | None = None,
        include_activity_metric_cues: bool = True,
    ) -> list[dict[str, Any]]:
        cues = self.collect_materializable_cues(
            project_key=project_key,
            schedule_version_key=schedule_version_key,
            as_of_date=as_of_date,
            driver_analysis=driver_analysis,
            milestones=milestones,
            remaining_health=remaining_health,
            cpm_summary=cpm_summary,
            change_impact=change_impact,
            remaining_activities=remaining_activities,
            comparison_basis=comparison_basis,
            baseline_summary=baseline_summary,
            include_activity_metric_cues=include_activity_metric_cues,
        )
        preview = self._preview_only_cues(project_key, schedule_version_key, as_of_date)
        seen = {c["stable_item_key"] for c in cues}
        preview_only = [cue for cue in preview if cue["stable_item_key"] not in seen]
        if preview_only:
            cues.extend(self._evidence.enrich_cues(preview_only, schedule_version_key=schedule_version_key))
        return cues

    def collect_materializable_cues(
        self,
        *,
        project_key: str,
        schedule_version_key: str,
        as_of_date: date,
        driver_analysis: dict[str, Any] | None = None,
        milestones: dict[str, Any] | None = None,
        remaining_health: dict[str, Any] | None = None,
        cpm_summary: dict[str, Any] | None = None,
        change_impact: dict[str, Any] | None = None,
        remaining_activities: list[dict[str, Any]] | None = None,
        comparison_basis: str = "prior_update",
        baseline_summary: dict[str, Any] | None = None,
        include_activity_metric_cues: bool = True,
    ) -> list[dict[str, Any]]:
        seen: set[str] = set()
        out: list[dict[str, Any]] = []

        def add(candidate: dict[str, Any]) -> None:
            key = str(candidate["stable_item_key"])
            if key in seen:
                return
            seen.add(key)
            out.append(candidate)

        resolved = resolve_workbench_comparison_basis(comparison_basis)
        cue_basis = resolved.preview_basis
        persisted_basis = resolved.comparison_basis
        as_of = as_of_date.isoformat()
        schedule_data_date = self._schedule_data_date(schedule_version_key)
        comparison_phrase = _comparison_phrase(persisted_basis)

        driver_source = (driver_analysis or {}).get(cue_basis) or (
            (driver_analysis or {}) if cue_basis == "prior_update" else {}
        )
        if driver_source.get("available"):
            for driver in driver_source.get("top_drivers") or []:
                aid = str(driver.get("activity_id") or "")
                if not aid:
                    continue
                add(
                    self._candidate(
                        stable_item_key=f"driver:{aid}",
                        item_type="driver",
                        item_title=f"Review driver: {_activity_label(driver.get('activity_name'))}",
                        priority=int(driver.get("review_priority") or 50),
                        source_activity_id=aid,
                        source_metric_key="change_driver_analysis",
                        source_signal_type="driver",
                        confidence=CONFIDENCE_PRODUCTION,
                        severity="high",
                        comparison_basis=persisted_basis,
                        as_of=as_of,
                        schedule_data_date=schedule_data_date,
                        activity_name=str(driver.get("activity_name") or ""),
                        wbs_code=driver.get("wbs_code"),
                        cue_summary="Candidate driver sequence cue for PM review.",
                        caveats=[NON_CAUSATION_CUE],
                    )
                )

        for ms in (milestones or {}).get("items") or []:
            movement = int(ms.get("movement_days") or 0)
            if movement <= 0:
                continue
            aid = str(ms.get("activity_id") or "")
            if not aid:
                continue
            add(
                self._candidate(
                    stable_item_key=f"milestone:{aid}",
                    item_type="milestone",
                    item_title=f"Milestone moved later: {_activity_label(ms.get('activity_name'))}",
                    priority=min(95, 60 + movement),
                    source_activity_id=aid,
                    source_metric_key="milestones",
                    source_signal_type="milestone_moved_later",
                    confidence=CONFIDENCE_PRODUCTION,
                    severity="high" if movement >= 7 else "medium",
                    comparison_basis=persisted_basis,
                    as_of=as_of,
                    schedule_data_date=schedule_data_date,
                    activity_name=str(ms.get("activity_name") or ""),
                    cue_summary=f"Milestone forecast moved {movement} days later {comparison_phrase}.",
                    caveats=[NON_CAUSATION_CUE],
                )
            )

        neg_preview = (remaining_health or {}).get("float_pressure", {}).get("preview") or []
        for row in neg_preview:
            aid = str(row.get("activity_id") or "")
            if not aid:
                continue
            add(
                self._candidate(
                    stable_item_key=f"negative_float:{aid}",
                    item_type="negative_float",
                    item_title=f"Negative float: {_activity_label(row.get('activity_name'))}",
                    priority=78,
                    source_activity_id=aid,
                    source_metric_key="remaining_health",
                    source_signal_type="negative_float",
                    confidence=CONFIDENCE_PRODUCTION,
                    severity="high",
                    comparison_basis=persisted_basis,
                    as_of=as_of,
                    schedule_data_date=schedule_data_date,
                    activity_name=str(row.get("activity_name") or ""),
                    cue_summary="Activity has negative source/export float remaining.",
                    caveats=[NON_CAUSATION_CUE],
                )
            )

        for row in (change_impact or {}).get("direct_remaining_changes", {}).get("items") or []:
            delta = row.get("float_delta_days")
            if delta is None or float(delta) >= 0:
                continue
            aid = str(row.get("activity_id") or "")
            if not aid:
                continue
            add(
                self._candidate(
                    stable_item_key=f"worsened_float:{aid}",
                    item_type="worsened_float",
                    item_title=f"Worsened float: {_activity_label(row.get('activity_name'))}",
                    priority=72,
                    source_activity_id=aid,
                    source_metric_key="schedule_changes_over_time",
                    source_signal_type="worsened_float",
                    confidence=CONFIDENCE_PRODUCTION,
                    severity="medium",
                    comparison_basis=persisted_basis,
                    as_of=as_of,
                    schedule_data_date=schedule_data_date,
                    activity_name=str(row.get("activity_name") or ""),
                    cue_summary=f"Float eroded {comparison_phrase}.",
                    caveats=[NON_CAUSATION_CUE],
                )
            )

        for row in (cpm_summary or {}).get("critical_path", {}).get("items") or []:
            aid = str(row.get("activity_id") or "")
            if not aid:
                continue
            add(
                self._candidate(
                    stable_item_key=f"critical:{aid}",
                    item_type="critical_remaining",
                    item_title=f"Critical remaining: {_activity_label(row.get('activity_name'))}",
                    priority=68,
                    source_activity_id=aid,
                    source_metric_key="critical_path_length_index",
                    source_signal_type="critical_remaining",
                    confidence=CONFIDENCE_PRODUCTION,
                    severity="high",
                    comparison_basis=persisted_basis,
                    as_of=as_of,
                    schedule_data_date=schedule_data_date,
                    activity_name=str(row.get("activity_name") or ""),
                    cue_summary="Activity is on critical/near-critical remaining work.",
                    caveats=[NON_CAUSATION_CUE],
                )
            )

        if include_activity_metric_cues:
            for activity_cue in self._udf.get_should_have_finished_activity_cues(
                project_key=project_key,
                version_key=schedule_version_key,
                as_of_date=as_of_date,
                limit=_ACTIVITY_CUE_LIMIT,
            ):
                status = str(activity_cue.get("status") or "delayed")
                aid = str(activity_cue.get("activity_id") or "")
                if not aid:
                    continue
                add(
                    self._candidate(
                        stable_item_key=f"metric:should_have_finished:{status}:{aid}",
                        item_type=_ITEM_METRIC_SHOULD_HAVE_FINISHED,
                        item_title=f"Should have finished ({status}): {_activity_label(activity_cue.get('activity_name'))}",
                        priority=_SEVERITY_PRIORITY["high" if status == "delayed" else "medium"],
                        source_activity_id=aid,
                        source_metric_key="should_have_finished_status",
                        source_signal_type=f"{status}_activity",
                        confidence=activity_cue.get("confidence", CONFIDENCE_PRODUCTION),
                        severity="high" if status == "delayed" else "medium",
                        comparison_basis=persisted_basis,
                        as_of=as_of,
                        schedule_data_date=schedule_data_date,
                        activity_name=activity_cue.get("activity_name"),
                        wbs_code=activity_cue.get("wbs_code"),
                        phase=activity_cue.get("phase"),
                        floor=activity_cue.get("floor"),
                        sector_area=activity_cue.get("sector_area"),
                        subcontractor=activity_cue.get("subcontractor"),
                        cost_code=activity_cue.get("cost_code"),
                        partial_dimension_support=activity_cue.get("partial_dimension_support", False),
                        data_quality_notes=activity_cue.get("data_quality_notes", []),
                        cue_summary=activity_cue.get("cue_summary", "Overdue unfinished activity needs PM review."),
                        caveats=[NON_CAUSATION_CUE],
                    )
                )

            for activity_cue in self._udf.get_window_start_activity_cues(
                project_key=project_key,
                version_key=schedule_version_key,
                as_of_date=as_of_date,
                limit=_ACTIVITY_CUE_LIMIT,
            ):
                signal = str(activity_cue.get("signal_type") or "late_start")
                aid = str(activity_cue.get("activity_id") or "")
                if not aid:
                    continue
                add(
                    self._candidate(
                        stable_item_key=f"metric:window_start:{signal}:{aid}",
                        item_type=_ITEM_METRIC_WINDOW_START,
                        item_title=f"Window start ({signal.replace('_', ' ')}): {_activity_label(activity_cue.get('activity_name'))}",
                        priority=_SEVERITY_PRIORITY["medium"],
                        source_activity_id=aid,
                        source_metric_key="window_start_accuracy",
                        source_signal_type=signal,
                        confidence=activity_cue.get("confidence", CONFIDENCE_PRODUCTION),
                        severity="medium",
                        comparison_basis=persisted_basis,
                        as_of=as_of,
                        schedule_data_date=schedule_data_date,
                        activity_name=activity_cue.get("activity_name"),
                        wbs_code=activity_cue.get("wbs_code"),
                        phase=activity_cue.get("phase"),
                        partial_dimension_support=activity_cue.get("partial_dimension_support", False),
                        cue_summary=activity_cue.get("cue_summary", "Near-term start reliability miss."),
                        caveats=[NON_CAUSATION_CUE],
                    )
                )

            for activity_cue in self._udf.get_window_finish_activity_cues(
                project_key=project_key,
                version_key=schedule_version_key,
                as_of_date=as_of_date,
                limit=_ACTIVITY_CUE_LIMIT,
            ):
                signal = str(activity_cue.get("signal_type") or "late_finish")
                aid = str(activity_cue.get("activity_id") or "")
                if not aid:
                    continue
                add(
                    self._candidate(
                        stable_item_key=f"metric:window_finish:{signal}:{aid}",
                        item_type=_ITEM_METRIC_WINDOW_FINISH,
                        item_title=f"Window finish ({signal.replace('_', ' ')}): {_activity_label(activity_cue.get('activity_name'))}",
                        priority=_SEVERITY_PRIORITY["medium"],
                        source_activity_id=aid,
                        source_metric_key="window_finish_accuracy",
                        source_signal_type=signal,
                        confidence=activity_cue.get("confidence", CONFIDENCE_PRODUCTION),
                        severity="medium",
                        comparison_basis=persisted_basis,
                        as_of=as_of,
                        schedule_data_date=schedule_data_date,
                        activity_name=activity_cue.get("activity_name"),
                        wbs_code=activity_cue.get("wbs_code"),
                        phase=activity_cue.get("phase"),
                        partial_dimension_support=activity_cue.get("partial_dimension_support", False),
                        cue_summary=activity_cue.get("cue_summary", "Near-term finish reliability miss."),
                        caveats=[NON_CAUSATION_CUE],
                    )
                )

        if include_activity_metric_cues:
            critical_payload = self._udf.build_metric_payload(
                metric_key="critical_issues_category_model",
                project_key=project_key,
                version_key=schedule_version_key,
                as_of_date=as_of_date,
            )
            if critical_payload.get("available"):
                confidence = CONFIDENCE_PARTIAL if critical_payload.get("partial_dimension_support") else CONFIDENCE_PRODUCTION
                for point in critical_payload.get("points") or []:
                    count = int(point.get("candidate_count") or 0)
                    if count <= 0:
                        continue
                    category = str(point.get("category") or "issue_category")
                    add(
                        self._candidate(
                            stable_item_key=f"metric:critical_issues:{category}",
                            item_type=_ITEM_METRIC_CRITICAL_ISSUES,
                            item_title=f"Critical issue category: {point.get('category_label') or category}",
                            priority=_SEVERITY_PRIORITY["high"] if count >= 5 else _SEVERITY_PRIORITY["medium"],
                            source_metric_key="critical_issues_category_model",
                            source_signal_type="issue_category",
                            confidence=confidence,
                            severity="high" if count >= 5 else "medium",
                            comparison_basis=persisted_basis,
                            as_of=as_of,
                            schedule_data_date=schedule_data_date,
                            partial_dimension_support=critical_payload.get("partial_dimension_support", False),
                            cue_summary=f"{count} candidate issue(s) in this category require PM review.",
                            caveats=[NON_CAUSATION_CUE],
                            evidence_extra={"candidate_count": count, "category": category},
                        )
                    )

            delay_payload = self._udf.build_metric_payload(
                metric_key="delay_analysis",
                project_key=project_key,
                version_key=schedule_version_key,
                as_of_date=as_of_date,
            )
            if delay_payload.get("available"):
                point = (delay_payload.get("points") or [{}])[0]
                add(
                    self._candidate(
                        stable_item_key=f"metric:delay_analysis:{as_of}",
                        item_type=_ITEM_METRIC_DELAY,
                        item_title="Delay analysis review cue",
                        priority=70,
                        source_metric_key="delay_analysis",
                        source_signal_type="period_movement",
                        confidence=CONFIDENCE_PARTIAL if delay_payload.get("partial_dimension_support") else CONFIDENCE_PRODUCTION,
                        severity="medium",
                        comparison_basis=persisted_basis,
                        as_of=as_of,
                        schedule_data_date=schedule_data_date,
                        partial_dimension_support=delay_payload.get("partial_dimension_support", False),
                        cue_summary="Prior-update finish movement suggests follow-up review.",
                        caveats=[NON_CAUSATION_CUE, NON_CAUSATION_CAVEAT],
                        evidence_extra={
                            "net_movement": point.get("net_movement"),
                            "delays": point.get("delays"),
                            "gains": point.get("gains"),
                        },
                    )
                )

        for finding in self._quality_finding_cues(schedule_version_key):
            aid = str(finding.get("activity_id") or "")
            code = str(finding.get("finding_code") or "finding")
            stable = f"metric:quality_finding:{code}:{aid or 'project'}"
            add(
                self._candidate(
                    stable_item_key=stable,
                    item_type=_ITEM_METRIC_QUALITY,
                    item_title=f"Quality finding: {finding.get('finding_summary') or code}",
                    priority=_SEVERITY_PRIORITY.get(str(finding.get("severity") or "medium"), 60),
                    source_activity_id=aid or None,
                    source_metric_key="schedule_quality_findings",
                    source_signal_type="quality_finding",
                    confidence=CONFIDENCE_PRODUCTION,
                    severity=str(finding.get("severity") or "medium"),
                    comparison_basis=persisted_basis,
                    as_of=as_of,
                    schedule_data_date=schedule_data_date,
                    activity_name=finding.get("activity_name"),
                    cue_summary=str(finding.get("finding_summary") or "Schedule quality finding requires review."),
                    caveats=[NON_CAUSATION_CUE],
                )
            )

        for preview in self._quality_metric_preview_cues(schedule_version_key):
            add(preview)

        if baseline_summary:
            readiness = baseline_summary.get("readiness") or {}
            if baseline_summary.get("recompute_required") or not readiness.get("ready"):
                for blocker in readiness.get("blockers") or ["selected_baseline_recompute_required"]:
                    add(
                        self._candidate(
                            stable_item_key=f"metric:compression_readiness:{blocker}",
                            item_type=_ITEM_METRIC_COMPRESSION,
                            item_title=f"Compression readiness: {blocker.replace('_', ' ')}",
                            priority=65,
                            source_metric_key="schedule_compression_ratio",
                            source_signal_type="compression_readiness",
                            confidence=CONFIDENCE_PRODUCTION,
                            severity="medium",
                            comparison_basis="selected_baseline",
                            as_of=as_of,
                            schedule_data_date=schedule_data_date,
                            cue_summary="Selected-baseline compression metric needs operator follow-up.",
                            caveats=[NON_CAUSATION_CUE],
                        )
                    )

        out.sort(key=lambda item: (-int(item.get("priority") or 0), str(item.get("item_title") or "")))
        return self._evidence.enrich_cues(out, schedule_version_key=schedule_version_key)

    def filter_cues(
        self,
        cues: list[dict[str, Any]],
        *,
        review_status: str | None = None,
        severity: str | None = None,
        source_metric: str | None = None,
        item_type: str | None = None,
        confidence: str | None = None,
        phase: str | None = None,
        floor: str | None = None,
        sector_area: str | None = None,
        subcontractor: str | None = None,
        cost_code: str | None = None,
    ) -> list[dict[str, Any]]:
        filtered = cues
        if review_status:
            filtered = [c for c in filtered if c.get("review_status") == review_status]
        for key, value in (
            ("severity", severity),
            ("source_metric_key", source_metric),
            ("item_type", item_type),
            ("confidence", confidence),
            ("phase", phase),
            ("floor", floor),
            ("sector_area", sector_area),
            ("subcontractor", subcontractor),
            ("cost_code", cost_code),
        ):
            if not value:
                continue
            filtered = [
                c
                for c in filtered
                if str((c.get("evidence") or {}).get(key) or c.get(key) or "").lower() == str(value).lower()
            ]
        return filtered

    @staticmethod
    def build_stable_item_key(cue: dict[str, Any]) -> str:
        return str(cue.get("stable_item_key") or "")

    def _preview_only_cues(
        self,
        project_key: str,
        schedule_version_key: str,
        as_of_date: date,
    ) -> list[dict[str, Any]]:
        readiness = self._udf.get_udf_metric_readiness(project_key, schedule_version_key)
        out: list[dict[str, Any]] = []
        for metric_key, info in readiness.get("metrics", {}).items():
            if info.get("ready"):
                continue
            out.append(
                self._candidate(
                    stable_item_key=f"preview:blocked:{metric_key}",
                    item_type="readiness_preview",
                    item_title=f"Metric not ready: {metric_key.replace('_', ' ')}",
                    priority=10,
                    source_metric_key=metric_key,
                    source_signal_type="readiness_blocked",
                    confidence=CONFIDENCE_BLOCKED,
                    severity="low",
                    comparison_basis="prior_update",
                    as_of=as_of_date.isoformat(),
                    schedule_data_date=self._schedule_data_date(schedule_version_key),
                    materializable=False,
                    cue_summary="Backend metric is readiness-only; no review item was materialized.",
                    data_quality_notes=info.get("blockers", []),
                )
            )
        return out

    def _quality_finding_cues(self, schedule_version_key: str) -> list[dict[str, Any]]:
        with open_connection(self._db_path) as conn:
            rows = conn.execute(
                """
                SELECT qf.finding_code, qf.severity, qf.activity_id, qf.finding_summary,
                       a.activity_name, a.wbs_code
                FROM schedule_quality_findings qf
                JOIN schedule_quality_evaluation_runs er ON er.evaluation_run_id = qf.evaluation_run_id
                LEFT JOIN procore_ep_schedule_activities a
                  ON a.schedule_version_key = er.schedule_version_key
                 AND a.activity_id = qf.activity_id
                WHERE er.schedule_version_key=? AND er.is_latest=1
                ORDER BY qf.severity DESC, qf.finding_code
                LIMIT 25
                """,
                (schedule_version_key,),
            ).fetchall()
        return [dict(row) for row in rows]

    def _quality_metric_preview_cues(self, schedule_version_key: str) -> list[dict[str, Any]]:
        run = self._quality_repo.get_latest_run(schedule_version_key)
        if not run or run.get("status") != "completed":
            return []
        metrics = self._quality_repo.list_metrics(str(run["evaluation_run_id"]))
        scorecard = self._quality_repo.get_latest_scorecard(schedule_version_key)
        downstream = ScheduleQualityRepository.parse_json_field(
            scorecard.get("downstream_readiness_json") if scorecard else None,
            {},
        )
        by_code = {str(m.get("metric_code") or ""): m for m in metrics}
        cues: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add_preview(
            *,
            item_type: str,
            signal_type: str,
            title: str,
            summary: str,
            severity: str = "medium",
            priority: int = 68,
        ) -> None:
            stable = f"metric:quality_preview:{signal_type}"
            if stable in seen:
                return
            seen.add(stable)
            cues.append(
                self._candidate(
                    stable_item_key=stable,
                    item_type=item_type,
                    item_title=title,
                    priority=priority,
                    source_metric_key="schedule_quality_metrics",
                    source_signal_type=signal_type,
                    confidence=CONFIDENCE_PRODUCTION,
                    severity=severity,
                    comparison_basis="prior_update",
                    as_of=date.today().isoformat(),
                    schedule_data_date=self._schedule_data_date(schedule_version_key),
                    cue_summary=summary,
                    caveats=[NON_CAUSATION_CUE],
                    materializable=False,
                )
            )

        logic = by_code.get("dcma_logic")
        if logic:
            evidence = ScheduleQualityRepository.parse_json_field(logic.get("evidence_json"), {})
            status = str(logic.get("status") or "")
            if status in {"warning_threshold", "failed_threshold"}:
                add_preview(
                    item_type="metric_quality_missing_logic",
                    signal_type="missing_logic",
                    title="Logic integrity warning",
                    summary="Logic integrity metrics exceeded thresholds for this schedule update.",
                    severity="high" if status == "failed_threshold" else "medium",
                    priority=80,
                )
            open_start = int(evidence.get("open_start_count") or 0)
            if open_start > 0 and status in {"warning_threshold", "failed_threshold"}:
                add_preview(
                    item_type="metric_quality_open_start",
                    signal_type="open_start",
                    title="Open starts detected",
                    summary=f"{open_start} assessed activities have no predecessors (project-level count).",
                )
            open_finish = int(evidence.get("open_finish_count") or 0)
            if open_finish > 0 and status in {"warning_threshold", "failed_threshold"}:
                add_preview(
                    item_type="metric_quality_open_finish",
                    signal_type="open_finish",
                    title="Open finishes detected",
                    summary=f"{open_finish} assessed activities have no successors (project-level count).",
                )
            dup = int(evidence.get("duplicate_relationship_count") or 0)
            if dup > 0:
                add_preview(
                    item_type="metric_quality_duplicate_relationship",
                    signal_type="duplicate_relationship",
                    title="Duplicate relationships detected",
                    summary=f"{dup} duplicate relationship tie(s) were counted in the quality evaluation.",
                )
            self_rel = int(evidence.get("self_relationship_count") or 0)
            if self_rel > 0:
                add_preview(
                    item_type="metric_quality_self_relationship",
                    signal_type="self_relationship",
                    title="Self relationships detected",
                    summary=f"{self_rel} self-referencing relationship(s) were counted in the quality evaluation.",
                )
            orphan_refs = int(evidence.get("invalid_relationship_reference_count") or 0)
            if orphan_refs > 0:
                add_preview(
                    item_type="metric_quality_orphan_activity",
                    signal_type="orphan_activity",
                    title="Orphan relationship references",
                    summary=f"{orphan_refs} relationship reference(s) point to missing activities.",
                    severity="high",
                    priority=85,
                )

        metric_map = {
            "dcma_leads": ("metric_quality_lead", "lead", "Leads (negative lag) detected"),
            "dcma_lags": ("metric_quality_lag", "lag", "Excessive lags detected"),
            "dcma_hard_constraints": ("metric_quality_hard_constraint", "hard_constraint", "Hard constraints detected"),
            "dcma_high_float": ("metric_quality_high_float", "high_float", "High float detected"),
            "dcma_negative_float": ("metric_quality_negative_float", "negative_float", "Negative float quality signal"),
            "dcma_high_duration": ("metric_quality_high_duration", "high_duration", "High duration activities detected"),
            "dcma_invalid_dates": ("metric_quality_invalid_date", "invalid_date", "Invalid dates detected"),
        }
        for code, (item_type, signal, title) in metric_map.items():
            metric = by_code.get(code)
            if not metric:
                continue
            status = str(metric.get("status") or "")
            if status not in {"warning_threshold", "failed_threshold"}:
                continue
            num = metric.get("numerator")
            summary = f"{title} — measured ratio/count indicates review is needed (project-level aggregate)."
            if num is not None:
                summary = f"{title} — {int(num)} affected item(s) in the aggregate quality metric."
            add_preview(
                item_type=item_type,
                signal_type=signal,
                title=title,
                summary=summary,
                severity="high" if status == "failed_threshold" else "medium",
            )

        cp_state = str(downstream.get("critical_path_analytics") or "")
        if cp_state not in {"available_cpm_recalculated", "available"}:
            add_preview(
                item_type="metric_quality_critical_path_readiness",
                signal_type="critical_path_readiness",
                title="Critical path readiness gap",
                summary="Critical-path analytics are not fully ready for this schedule update.",
                severity="medium",
            )
        cost_state = str(downstream.get("true_cost_loaded_analytics") or "")
        if cost_state in {"unavailable_not_cost_loaded", "unknown", "not_ready"}:
            add_preview(
                item_type="metric_quality_cost_resource_readiness",
                signal_type="cost_resource_readiness",
                title="Cost/resource readiness gap",
                summary="Cost or resource loading analytics are limited for this schedule update.",
                severity="medium",
                priority=60,
            )
        return cues

    @staticmethod
    def _schedule_data_date(schedule_version_key: str) -> str | None:
        parsed = parse_schedule_version_data_date(schedule_version_key)
        return parsed.date().isoformat() if parsed is not None else None

    @staticmethod
    def _candidate(
        *,
        stable_item_key: str,
        item_type: str,
        item_title: str,
        priority: int,
        source_metric_key: str,
        source_signal_type: str,
        confidence: str,
        severity: str,
        comparison_basis: str,
        as_of: str,
        schedule_data_date: str | None = None,
        source_activity_id: str | None = None,
        activity_name: str | None = None,
        wbs_code: str | None = None,
        phase: str | None = None,
        floor: str | None = None,
        sector_area: str | None = None,
        subcontractor: str | None = None,
        cost_code: str | None = None,
        partial_dimension_support: bool = False,
        data_quality_notes: list[str] | None = None,
        cue_summary: str = "",
        caveats: list[str] | None = None,
        materializable: bool = True,
        evidence_extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        evidence: dict[str, Any] = {
            "source_metric_key": source_metric_key,
            "source_signal_type": source_signal_type,
            "confidence": confidence,
            "severity": severity,
            "comparison_basis": comparison_basis,
            "as_of": as_of,
            "schedule_data_date": schedule_data_date,
            "data_date": schedule_data_date,
            "activity_name": activity_name,
            "wbs_code": wbs_code,
            "phase": phase,
            "floor": floor,
            "sector_area": sector_area,
            "subcontractor": subcontractor,
            "cost_code": cost_code,
            "cue_summary": cue_summary,
            "caveats": caveats or [],
            "data_quality_notes": data_quality_notes or [],
            "partial_dimension_support": partial_dimension_support,
            "review_cue_only": True,
            "materializable": materializable,
        }
        if evidence_extra:
            evidence.update(evidence_extra)
        evidence = apply_taxonomy_fields(item_type=item_type, evidence=evidence)
        return {
            "stable_item_key": stable_item_key,
            "item_type": item_type,
            "item_title": item_title,
            "priority": priority,
            "source_activity_id": source_activity_id,
            "evidence": evidence,
            "source_metric_key": source_metric_key,
            "source_signal_type": source_signal_type,
            "confidence": confidence,
            "severity": severity,
            "phase": phase,
            "floor": floor,
            "sector_area": sector_area,
            "subcontractor": subcontractor,
            "cost_code": cost_code,
            "cue_summary": cue_summary,
            "caveats": caveats or [],
            "partial_dimension_support": partial_dimension_support,
            "materializable": materializable,
        }


def _activity_label(activity_name: Any) -> str:
    label = str(activity_name or "").strip()
    return label or "Unnamed activity"


def _comparison_phrase(comparison_basis: str) -> str:
    if comparison_basis == "prior_update":
        return "since prior update"
    label = comparison_label_for_basis(comparison_basis)
    if label:
        return label.lower()
    return "relative to comparison baseline"
