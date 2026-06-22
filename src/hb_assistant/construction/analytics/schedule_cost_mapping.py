"""Operator-controlled schedule cost mapping runs."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from hb_assistant.store.schedule_activity_repository import ScheduleActivityRepository
from hb_assistant.store.schedule_import_repository import ScheduleImportRepository
from hb_assistant.store.schedule_mapping_repository import ScheduleMappingRepository

from .schedule_cost_distribution import compute_duration_distribution
from .schedule_cost_weighting import compute_weighting_results
from .schedule_dto import DISTRIBUTION_LABELS, OPERATOR_OBJECTIVES, ScheduleMappingRunDTO
from .schedule_file_parser import ScheduleImportError
from .schedule_import_service import ensure_schedule_schema


class ScheduleCostMappingService:
    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path
        self._mapping_repo = ScheduleMappingRepository(db_path=db_path)
        self._activity_repo = ScheduleActivityRepository(db_path=db_path)
        self._import_repo = ScheduleImportRepository(db_path=db_path)

    def _ensure_schema(self) -> None:
        ensure_schedule_schema(self._db_path)

    def create_run(
        self,
        *,
        project_key: str,
        schedule_version_key: str,
        operator_objective: str = "association_only",
        created_by_operator: str = "operator",
    ) -> dict[str, Any]:
        self._ensure_schema()
        if operator_objective not in OPERATOR_OBJECTIVES:
            raise ScheduleImportError("schedule_import_invalid", message="invalid operator_objective")

        summary = self._activity_repo.get_version_summary(schedule_version_key)
        if not summary or summary.get("project_key") != project_key:
            raise ScheduleImportError(
                "schedule_not_found",
                message=f"unknown schedule_version_key {schedule_version_key}",
            )

        cost_status = str(summary.get("cost_loaded_status") or "not_cost_loaded")
        if operator_objective == "existing_cost_loaded_review" and cost_status == "not_cost_loaded":
            raise ScheduleImportError(
                "schedule_import_invalid",
                message="cost_loaded review requires detected cost-loaded schedule data",
            )

        mapping_run_id = f"map-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        self._mapping_repo.insert_mapping_run(
            {
                "mapping_run_id": mapping_run_id,
                "project_key": project_key,
                "schedule_version_key": schedule_version_key,
                "operator_objective": operator_objective,
                "financial_value_source": None,
                "distribution_method": DISTRIBUTION_LABELS.get(operator_objective),
                "cost_loaded_status_at_start": cost_status,
                "mapping_status": "in_review",
                "created_by_operator": created_by_operator,
                "created_at": now,
            }
        )

        activities = self._activity_repo.list_activities(schedule_version_key, limit=5000)
        candidates = []
        for act in activities:
            cost_code = act.get("cost_code")
            if not cost_code:
                continue
            candidates.append(
                {
                    "mapping_run_id": mapping_run_id,
                    "project_key": project_key,
                    "schedule_version_key": schedule_version_key,
                    "activity_id": act["activity_id"],
                    "candidate_cost_code": cost_code,
                    "candidate_budget_code_key": cost_code,
                    "candidate_source": "direct_activity_code",
                    "confidence_score": "0.85",
                    "evidence_json": json.dumps({"activity_name": act.get("activity_name")}),
                    "ai_assisted": 0,
                    "operator_status": "pending",
                }
            )
        self._mapping_repo.insert_candidates(candidates)

        dto = ScheduleMappingRunDTO(
            mapping_run_id=mapping_run_id,
            project_key=project_key,
            schedule_version_key=schedule_version_key,
            operator_objective=operator_objective,
            mapping_status="in_review",
            cost_loaded_status_at_start=cost_status,
            created_at=now,
            approved_at=None,
            distribution_label=DISTRIBUTION_LABELS.get(operator_objective),
        )
        return dto.public()

    def get_run(self, mapping_run_id: str) -> dict[str, Any] | None:
        self._ensure_schema()
        row = self._mapping_repo.get_mapping_run(mapping_run_id)
        if not row:
            return None
        dto = ScheduleMappingRunDTO(
            mapping_run_id=row["mapping_run_id"],
            project_key=row["project_key"],
            schedule_version_key=row["schedule_version_key"],
            operator_objective=row["operator_objective"],
            mapping_status=row["mapping_status"],
            cost_loaded_status_at_start=row.get("cost_loaded_status_at_start"),
            created_at=row["created_at"],
            approved_at=row.get("approved_at"),
            distribution_label=DISTRIBUTION_LABELS.get(row["operator_objective"]),
        )
        return dto.public()

    def list_candidates(self, mapping_run_id: str) -> list[dict[str, Any]]:
        self._ensure_schema()
        return self._mapping_repo.list_candidates(mapping_run_id)

    def review_candidate(
        self,
        candidate_id: int,
        *,
        operator_status: str,
        operator_notes: str | None = None,
        candidate_cost_code: str | None = None,
    ) -> None:
        self._ensure_schema()
        allowed = {"approved", "rejected", "edited", "not_applicable", "pending"}
        if operator_status not in allowed:
            raise ScheduleImportError("schedule_import_invalid", message="invalid operator_status")
        now = datetime.now(timezone.utc).isoformat()
        self._mapping_repo.review_candidate(
            candidate_id,
            operator_status=operator_status,
            operator_notes_redacted=operator_notes,
            reviewed_at=now,
            reviewed_by_operator="operator",
            candidate_cost_code=candidate_cost_code,
        )

    def approve_run(self, mapping_run_id: str) -> dict[str, Any]:
        self._ensure_schema()
        run = self._mapping_repo.get_mapping_run(mapping_run_id)
        if not run:
            raise ScheduleImportError(
                "schedule_not_found",
                message=f"unknown mapping_run_id {mapping_run_id}",
            )

        candidates = self._mapping_repo.list_candidates(mapping_run_id)
        approved = [c for c in candidates if c.get("operator_status") == "approved"]
        if not approved and run["operator_objective"] != "association_only":
            raise ScheduleImportError(
                "schedule_import_invalid",
                message="mapping run requires at least one approved candidate",
            )

        from hb_assistant.construction.analytics.schedule_quality_service import (
            ScheduleQualityService,
        )

        quality = ScheduleQualityService(db_path=self._db_path).latest_completed_scorecard(
            run["schedule_version_key"]
        )
        if not quality:
            raise ScheduleImportError(
                "schedule_quality_not_ready",
                message="approved cost weighting requires a completed quality scorecard",
            )

        now = datetime.now(timezone.utc).isoformat()
        self._mapping_repo.approve_mapping_run(mapping_run_id, approved_at=now)

        distributions: list[dict[str, Any]] = []
        if run["operator_objective"] == "simplified_duration_distribution":
            activities = self._activity_repo.list_activities(run["schedule_version_key"], limit=5000)
            distributions = compute_duration_distribution(
                mapping_run_id=mapping_run_id,
                project_key=run["project_key"],
                schedule_version_key=run["schedule_version_key"],
                approved_candidates=approved,
                activities=activities,
            )
            self._mapping_repo.insert_distributions(distributions)

        weighting = compute_weighting_results(
            mapping_run_id=mapping_run_id,
            project_key=run["project_key"],
            schedule_version_key=run["schedule_version_key"],
            approved_candidates=approved,
            activities=self._activity_repo.list_activities(run["schedule_version_key"], limit=5000),
            approved=True,
        )
        self._mapping_repo.insert_weighting_results(weighting)

        return {
            "mapping_run_id": mapping_run_id,
            "mapping_status": "approved",
            "approved_at": now,
            "distribution_count": len(distributions),
            "distribution_label": DISTRIBUTION_LABELS.get(run["operator_objective"]),
        }

    def list_distributions(self, mapping_run_id: str) -> list[dict[str, Any]]:
        self._ensure_schema()
        run = self._mapping_repo.get_mapping_run(mapping_run_id)
        if not run:
            raise ScheduleImportError(
                "schedule_not_found",
                message=f"unknown mapping_run_id {mapping_run_id}",
            )
        dists = self._mapping_repo.list_distributions(mapping_run_id)
        label = DISTRIBUTION_LABELS.get(run["operator_objective"])
        return [
            {
                "activity_id": d.get("activity_id"),
                "cost_code": d.get("cost_code"),
                "allocation_method": d.get("allocation_method"),
                "allocation_percent": d.get("allocation_percent"),
                "allocated_value": d.get("allocated_value"),
                "distribution_label": label,
                "operator_approved": bool(d.get("operator_approved")),
            }
            for d in dists
        ]

    def list_weighting(self, project_key: str) -> list[dict[str, Any]]:
        self._ensure_schema()
        return self._mapping_repo.list_weighting_results(project_key, approved_only=True)