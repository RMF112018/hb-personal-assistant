"""Schedule quality evaluation queue and processing service."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from hb_assistant.store.schedule_quality_repository import (
    DEFAULT_PROFILE,
    ScheduleQualityRepository,
)

from .schedule_file_parser import ScheduleImportError
from .schedule_import_service import ensure_schedule_schema
from .schedule_quality_engine import run_evaluation_for_run
from .schedule_quality_profiles import get_profile


class ScheduleQualityService:
    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path
        self._repo = ScheduleQualityRepository(db_path=db_path)

    def _ensure_schema(self) -> None:
        ensure_schedule_schema(self._db_path)

    def queue_evaluation(
        self,
        *,
        project_key: str,
        schedule_version_key: str,
        schedule_table_id: str | None,
        import_id: str | None,
        trigger_source: str,
        profile_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        self._ensure_schema()
        profile = get_profile(profile_id)
        now = datetime.now(timezone.utc).isoformat()
        run_id = f"sq-{uuid.uuid4().hex[:12]}"
        key = idempotency_key or f"{trigger_source}:{import_id or schedule_version_key}:{profile.profile_id}"
        created, run_id = self._repo.enqueue_evaluation(
            evaluation_run_id=run_id,
            project_key=project_key,
            schedule_version_key=schedule_version_key,
            schedule_table_id=schedule_table_id,
            import_id=import_id,
            assessment_profile=profile.profile_id,
            assessment_profile_version=profile.profile_version,
            method_source=profile.method_source,
            trigger_source=trigger_source,
            idempotency_key=key,
            queued_at=now,
        )
        return {
            "evaluation_run_id": run_id,
            "status": "pending",
            "created": created,
            "assessment_profile": profile.profile_id,
        }

    def queue_after_commit(
        self,
        *,
        project_key: str,
        schedule_version_key: str,
        schedule_table_id: str | None,
        import_id: str,
    ) -> dict[str, Any]:
        return self.queue_evaluation(
            project_key=project_key,
            schedule_version_key=schedule_version_key,
            schedule_table_id=schedule_table_id,
            import_id=import_id,
            trigger_source="import_commit",
            idempotency_key=f"import_commit:{import_id}:{DEFAULT_PROFILE}",
        )

    def queue_after_procore_update(
        self,
        *,
        project_key: str,
        schedule_version_key: str,
        schedule_table_id: str | None,
        import_id: str | None,
        sync_watermark: str,
    ) -> dict[str, Any]:
        return self.queue_evaluation(
            project_key=project_key,
            schedule_version_key=schedule_version_key,
            schedule_table_id=schedule_table_id,
            import_id=import_id,
            trigger_source="procore_projection",
            idempotency_key=f"procore:{sync_watermark}:{DEFAULT_PROFILE}",
        )

    def request_rerun(
        self,
        *,
        schedule_version_key: str,
        profile_id: str | None = None,
    ) -> dict[str, Any]:
        self._ensure_schema()
        from hb_assistant.store.schedule_activity_repository import ScheduleActivityRepository

        summary = ScheduleActivityRepository(db_path=self._db_path).get_version_summary(
            schedule_version_key
        )
        if not summary:
            raise ScheduleImportError("schedule_not_found", message="schedule version not found")
        profile = get_profile(profile_id)
        now = datetime.now(timezone.utc).isoformat()
        run_id = f"sq-{uuid.uuid4().hex[:12]}"
        key = f"manual_rerun:{schedule_version_key}:{profile.profile_id}:{now}"
        created, run_id = self._repo.enqueue_evaluation(
            evaluation_run_id=run_id,
            project_key=str(summary.get("project_key") or ""),
            schedule_version_key=schedule_version_key,
            schedule_table_id=None,
            import_id=summary.get("import_id"),
            assessment_profile=profile.profile_id,
            assessment_profile_version=profile.profile_version,
            method_source=profile.method_source,
            trigger_source="manual_rerun",
            idempotency_key=key,
            queued_at=now,
        )
        return {"evaluation_run_id": run_id, "status": "pending", "created": created}

    def process_next_pending(self) -> dict[str, Any] | None:
        self._ensure_schema()
        now = datetime.now(timezone.utc).isoformat()
        run = self._repo.claim_pending_run(started_at=now)
        if not run:
            return None
        return self._process_run(run)

    def process_run(self, evaluation_run_id: str) -> dict[str, Any]:
        self._ensure_schema()
        run = self._repo.get_run(evaluation_run_id)
        if not run:
            raise ScheduleImportError("schedule_not_found", message="evaluation run not found")
        return self._process_run(run)

    def _process_run(self, run: dict[str, Any]) -> dict[str, Any]:
        run_id = str(run["evaluation_run_id"])
        now = datetime.now(timezone.utc).isoformat()
        try:
            result = run_evaluation_for_run(
                db_path=self._db_path,
                evaluation_run_id=run_id,
                project_key=str(run["project_key"]),
                schedule_version_key=str(run["schedule_version_key"]),
                schedule_table_id=run.get("schedule_table_id"),
                import_id=run.get("import_id"),
                profile_id=str(run.get("assessment_profile")),
            )
            self._repo.insert_metric_results(result.metrics)
            self._repo.insert_findings(result.findings)
            self._repo.insert_scorecard(result.scorecard)
            self._repo.complete_run(
                evaluation_run_id=run_id,
                schedule_version_key=str(run["schedule_version_key"]),
                assessment_profile=str(run["assessment_profile"]),
                completed_at=now,
            )
            return {
                "evaluation_run_id": run_id,
                "status": "completed",
                "finding_count": len(result.findings),
                "metric_count": len(result.metrics),
            }
        except Exception:
            self._repo.fail_run(
                evaluation_run_id=run_id,
                error_code="quality_engine_exception",
                error_message_redacted="schedule quality evaluation failed",
                completed_at=now,
            )
            return {
                "evaluation_run_id": run_id,
                "status": "failed",
                "error_code": "quality_engine_exception",
            }

    def get_quality_summary(self, schedule_version_key: str) -> dict[str, Any]:
        self._ensure_schema()
        run = self._repo.get_latest_run(schedule_version_key)
        if not run:
            run = self._repo.get_pending_run(schedule_version_key)
        scorecard = self._repo.get_latest_scorecard(schedule_version_key) if run else None
        metrics = (
            self._repo.list_metrics(str(run["evaluation_run_id"]))
            if run and run.get("status") == "completed"
            else []
        )
        findings = self._repo.list_findings(schedule_version_key, limit=20)
        return {
            "schedule_version_key": schedule_version_key,
            "evaluation_run_id": run.get("evaluation_run_id") if run else None,
            "status": run.get("status") if run else "not_evaluated",
            "assessment_profile": run.get("assessment_profile") if run else None,
            "assessment_profile_version": run.get("assessment_profile_version") if run else None,
            "method_source": run.get("method_source") if run else None,
            "quality_score": scorecard.get("quality_score") if scorecard else None,
            "quality_grade": scorecard.get("quality_grade") if scorecard else None,
            "scorecard": self._public_scorecard(scorecard),
            "metrics": metrics,
            "finding_counts": ScheduleQualityRepository.parse_json_field(
                scorecard.get("finding_counts_json") if scorecard else None,
                {},
            ),
            "downstream_readiness": ScheduleQualityRepository.parse_json_field(
                scorecard.get("downstream_readiness_json") if scorecard else None,
                {},
            ),
            "gao_category_summary": ScheduleQualityRepository.parse_json_field(
                scorecard.get("gao_category_summary_json") if scorecard else None,
                {},
            ),
            "top_findings": [
                {
                    "severity": f.get("severity"),
                    "finding_code": f.get("finding_code"),
                    "finding_summary": f.get("finding_summary"),
                    "activity_id": f.get("activity_id"),
                    "category": f.get("category"),
                }
                for f in findings[:10]
            ],
            "disclaimer": (
                "Schedule quality metrics are deterministic CPM data checks for operator review. "
                "This is not forensic delay analysis and does not determine entitlement, "
                "responsibility, liability, or compensability."
            ),
        }

    def get_findings(
        self,
        schedule_version_key: str,
        *,
        evaluation_run_id: str | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> dict[str, Any]:
        self._ensure_schema()
        items = self._repo.list_findings(
            schedule_version_key,
            evaluation_run_id=evaluation_run_id,
            limit=limit,
            offset=offset,
        )
        return {
            "schedule_version_key": schedule_version_key,
            "evaluation_run_id": evaluation_run_id,
            "findings": [
                {
                    "severity": f.get("severity"),
                    "finding_code": f.get("finding_code"),
                    "finding_summary": f.get("finding_summary"),
                    "activity_id": f.get("activity_id"),
                    "category": f.get("category"),
                    "metric_code": f.get("metric_code"),
                }
                for f in items
            ],
        }

    def get_run_detail(self, evaluation_run_id: str) -> dict[str, Any] | None:
        self._ensure_schema()
        run = self._repo.get_run(evaluation_run_id)
        if not run:
            return None
        scorecard = self._repo.get_scorecard(evaluation_run_id)
        return {
            "evaluation_run_id": evaluation_run_id,
            "project_key": run.get("project_key"),
            "schedule_version_key": run.get("schedule_version_key"),
            "schedule_table_id": run.get("schedule_table_id"),
            "import_id": run.get("import_id"),
            "assessment_profile": run.get("assessment_profile"),
            "status": run.get("status"),
            "error_code": run.get("error_code"),
            "error_message_redacted": run.get("error_message_redacted"),
            "queued_at": run.get("queued_at"),
            "started_at": run.get("started_at"),
            "completed_at": run.get("completed_at"),
            "scorecard": self._public_scorecard(scorecard),
            "metrics": self._repo.list_metrics(evaluation_run_id),
        }

    def get_project_summary(self, project_key: str) -> dict[str, Any]:
        self._ensure_schema()
        return {
            "project_key": project_key,
            "versions": self._repo.list_project_quality_summary(project_key),
        }

    def latest_completed_scorecard(self, schedule_version_key: str) -> dict[str, Any] | None:
        self._ensure_schema()
        run = self._repo.get_latest_run(schedule_version_key)
        if not run or run.get("status") != "completed":
            return None
        return self._repo.get_scorecard(str(run["evaluation_run_id"]))

    @staticmethod
    def _public_scorecard(scorecard: dict[str, Any] | None) -> dict[str, Any] | None:
        if not scorecard:
            return None
        return {
            "quality_score": scorecard.get("quality_score"),
            "quality_grade": scorecard.get("quality_grade"),
            "dcma_measured_count": scorecard.get("dcma_measured_count"),
            "dcma_not_measurable_count": scorecard.get("dcma_not_measurable_count"),
            "dcma_pass_count": scorecard.get("dcma_pass_count"),
            "dcma_warn_count": scorecard.get("dcma_warn_count"),
            "dcma_fail_count": scorecard.get("dcma_fail_count"),
            "disclaimer_version": scorecard.get("disclaimer_version"),
        }