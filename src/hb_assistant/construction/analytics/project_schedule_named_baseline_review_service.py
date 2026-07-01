"""Named-baseline review workbench sync, list, and disposition."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from hb_assistant.store.project_schedule_named_baseline_review_repository import (
    NamedBaselineReviewIdentity,
    NamedBaselineReviewScope,
    ProjectScheduleNamedBaselineReviewRepository,
)
from hb_assistant.store.project_schedule_hub_repository import (
    REVIEW_DISMISSED,
    REVIEW_OPEN,
    REVIEW_REVIEWED,
    REVIEW_WATCHING,
)

from .project_schedule_review_cue_service import ProjectScheduleReviewCueService
from .project_schedule_review_service import ProjectScheduleReviewService


class ProjectScheduleNamedBaselineReviewService:
    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path
        self._repo = ProjectScheduleNamedBaselineReviewRepository(db_path=db_path)
        self._cues = ProjectScheduleReviewCueService(db_path=db_path)
        self._review = ProjectScheduleReviewService(db_path=db_path)

    @staticmethod
    def scope_from_context(
        *,
        project_key: str,
        current_schedule_version_key: str,
        comparison_basis: str,
        baseline_context: dict[str, Any],
        as_of_date: date | None,
        schedule_data_date: str | None,
    ) -> NamedBaselineReviewScope:
        slot_key = str(baseline_context.get("slot_key") or comparison_basis)
        return NamedBaselineReviewScope(
            project_key=project_key,
            current_schedule_version_key=current_schedule_version_key,
            comparison_basis=comparison_basis,
            baseline_slot_key=slot_key,
            baseline_slot_label=baseline_context.get("slot_label"),
            baseline_selection_id=baseline_context.get("selection_id"),
            baseline_schedule_version_key=str(
                baseline_context.get("schedule_version_key")
                or baseline_context.get("baseline_schedule_version_key")
                or ""
            ),
            baseline_schedule_data_date=baseline_context.get("schedule_data_date")
            or baseline_context.get("baseline_schedule_data_date"),
            baseline_display_name=baseline_context.get("display_name")
            or baseline_context.get("baseline_display_name"),
            schedule_data_date=schedule_data_date,
            as_of_date=as_of_date.isoformat() if as_of_date else None,
        )

    def sync_and_list(
        self,
        *,
        scope: NamedBaselineReviewScope,
        driver_analysis: dict[str, Any] | None,
        milestones: dict[str, Any] | None,
        remaining_health: dict[str, Any] | None,
        cpm_summary: dict[str, Any] | None,
        change_impact: dict[str, Any] | None,
        remaining_activities: list[dict[str, Any]] | None,
        as_of_date: date,
        baseline_summary: dict[str, Any] | None,
        comparison_basis: str,
    ) -> dict[str, Any]:
        candidates = self._collect_candidates(
            project_key=scope.project_key,
            schedule_version_key=scope.current_schedule_version_key,
            driver_analysis=driver_analysis,
            milestones=milestones,
            remaining_health=remaining_health,
            cpm_summary=cpm_summary,
            change_impact=change_impact,
            remaining_activities=remaining_activities,
            as_of_date=as_of_date,
            baseline_summary=baseline_summary,
            comparison_basis=comparison_basis,
            materializable_only=True,
        )
        synced = 0
        for candidate in candidates:
            if not (candidate.get("evidence") or {}).get("materializable", candidate.get("materializable", True)):
                continue
            self._repo.upsert_from_candidate(scope=scope, candidate=candidate)
            synced += 1
        envelope = self._build_workbench(
            scope=scope,
            driver_analysis=driver_analysis,
            milestones=milestones,
            remaining_health=remaining_health,
            cpm_summary=cpm_summary,
            change_impact=change_impact,
            remaining_activities=remaining_activities,
            as_of_date=as_of_date,
            baseline_summary=baseline_summary,
            synced=True,
            comparison_basis=comparison_basis,
        )
        envelope["sync"] = {"synced_count": synced, "candidate_count": len(candidates)}
        return envelope

    def build_preview(
        self,
        *,
        scope: NamedBaselineReviewScope,
        driver_analysis: dict[str, Any] | None,
        milestones: dict[str, Any] | None,
        remaining_health: dict[str, Any] | None,
        cpm_summary: dict[str, Any] | None,
        change_impact: dict[str, Any] | None,
        remaining_activities: list[dict[str, Any]] | None,
        as_of_date: date,
        baseline_summary: dict[str, Any] | None,
        comparison_basis: str,
        synced: bool = False,
    ) -> dict[str, Any]:
        return self._build_workbench(
            scope=scope,
            driver_analysis=driver_analysis,
            milestones=milestones,
            remaining_health=remaining_health,
            cpm_summary=cpm_summary,
            change_impact=change_impact,
            remaining_activities=remaining_activities,
            as_of_date=as_of_date,
            baseline_summary=baseline_summary,
            synced=synced,
            comparison_basis=comparison_basis,
        )

    def update_item(
        self,
        *,
        review_item_id: str,
        project_key: str | None = None,
        review_status: str | None = None,
        disposition: str | None = None,
        pm_notes: str | None = None,
        disposition_reason: str | None = None,
        reviewed_by_operator: str | None = None,
        identity_gate: str | None = None,
        analytics_trust_status: str | None = None,
    ) -> dict[str, Any]:
        from hb_assistant.construction.analytics.project_schedule_review_disposition import (
            validate_disposition_change,
        )

        row = self._repo.get_review_item(review_item_id=review_item_id)
        if not row:
            raise ValueError("review_item_not_found")
        if project_key and str(row.get("project_key")) != project_key:
            raise ValueError("review_item_project_mismatch")
        requested_status = disposition or review_status
        if requested_status is not None:
            validate_disposition_change(
                prior_disposition=str(row.get("review_status")),
                new_disposition=requested_status,
                disposition_reason=disposition_reason,
                operator_selectable_only=True,
                trust_blocked=analytics_trust_status == "blocked" or identity_gate == "blocked",
                identity_gate_blocked=identity_gate == "blocked",
                analytics_gate_blocked=analytics_trust_status == "blocked",
            )
        updated = self._repo.update_review_item(
            review_item_id=review_item_id,
            review_status=requested_status,
            pm_notes=pm_notes,
            disposition_reason=disposition_reason,
            reviewed_by_operator=reviewed_by_operator,
        )
        if not updated:
            raise ValueError("review_item_not_found")
        return {"item": self._public_item(updated)}

    def promote_preview_cues(
        self,
        *,
        scope: NamedBaselineReviewScope,
        stable_item_keys: list[str],
        driver_analysis: dict[str, Any] | None = None,
        milestones: dict[str, Any] | None = None,
        remaining_health: dict[str, Any] | None = None,
        cpm_summary: dict[str, Any] | None = None,
        change_impact: dict[str, Any] | None = None,
        remaining_activities: list[dict[str, Any]] | None = None,
        as_of_date: date | None = None,
        baseline_summary: dict[str, Any] | None = None,
        comparison_basis: str = "prior_update",
        reviewed_by_operator: str | None = None,
        identity_gate: str | None = None,
        analytics_trust_status: str | None = None,
    ) -> dict[str, Any]:
        from hb_assistant.construction.analytics.project_schedule_review_disposition import (
            DISPOSITION_NEEDS_REVIEW,
            system_disposition_for_trust,
        )

        as_of = as_of_date or datetime.now(timezone.utc).date()
        candidates = self._collect_candidates(
            project_key=scope.project_key,
            schedule_version_key=scope.current_schedule_version_key,
            driver_analysis=driver_analysis,
            milestones=milestones,
            remaining_health=remaining_health,
            cpm_summary=cpm_summary,
            change_impact=change_impact,
            remaining_activities=remaining_activities,
            as_of_date=as_of,
            baseline_summary=baseline_summary,
            comparison_basis=comparison_basis,
            materializable_only=False,
        )
        by_key = {str(c["stable_item_key"]): c for c in candidates}
        identity_blocked = identity_gate == "blocked"
        analytics_blocked = analytics_trust_status == "blocked"
        initial_status = system_disposition_for_trust(
            identity_gate_blocked=identity_blocked,
            analytics_gate_blocked=analytics_blocked,
        ) or DISPOSITION_NEEDS_REVIEW

        promoted: list[dict[str, Any]] = []
        skipped_duplicate: list[str] = []
        missing: list[str] = []
        for raw_key in stable_item_keys:
            stable_key = str(raw_key)
            candidate = by_key.get(stable_key)
            if not candidate:
                missing.append(stable_key)
                continue
            identity = ProjectScheduleNamedBaselineReviewRepository._identity_from_candidate(scope, candidate)
            existing = self._repo.get_by_identity(identity=identity)
            if existing:
                skipped_duplicate.append(stable_key)
                promoted.append(existing)
                continue
            row = self._repo.upsert_from_candidate(
                scope=scope,
                candidate=candidate,
                emit_sync_event=False,
                initial_review_status=initial_status,
                promotion_event=True,
            )
            promoted.append(row)
        return {
            "promoted_count": len(promoted) - len(skipped_duplicate),
            "skipped_duplicate_count": len(skipped_duplicate),
            "missing_count": len(missing),
            "skipped_duplicate_keys": skipped_duplicate,
            "missing_keys": missing,
            "items": [self._public_item(row) for row in promoted],
        }

    def list_item_events(self, *, review_item_id: str, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        row = self._repo.get_review_item(review_item_id=review_item_id)
        if not row:
            raise ValueError("review_item_not_found")
        events = self._repo.list_review_item_events(review_item_id=review_item_id, limit=limit)
        return {
            "available": True,
            "review_item_id": review_item_id,
            "count": len(events),
            "limit": limit,
            "offset": max(0, offset),
            "events": events,
        }

    def _build_workbench(
        self,
        *,
        scope: NamedBaselineReviewScope,
        driver_analysis: dict[str, Any] | None,
        milestones: dict[str, Any] | None,
        remaining_health: dict[str, Any] | None,
        cpm_summary: dict[str, Any] | None,
        change_impact: dict[str, Any] | None,
        remaining_activities: list[dict[str, Any]] | None,
        as_of_date: date,
        baseline_summary: dict[str, Any] | None,
        synced: bool,
        comparison_basis: str,
    ) -> dict[str, Any]:
        materializable = self._collect_candidates(
            project_key=scope.project_key,
            schedule_version_key=scope.current_schedule_version_key,
            driver_analysis=driver_analysis,
            milestones=milestones,
            remaining_health=remaining_health,
            cpm_summary=cpm_summary,
            change_impact=change_impact,
            remaining_activities=remaining_activities,
            as_of_date=as_of_date,
            baseline_summary=baseline_summary,
            comparison_basis=comparison_basis,
            materializable_only=True,
        )
        live_keys = {str(c["stable_item_key"]) for c in materializable}
        all_candidates = self._collect_candidates(
            project_key=scope.project_key,
            schedule_version_key=scope.current_schedule_version_key,
            driver_analysis=driver_analysis,
            milestones=milestones,
            remaining_health=remaining_health,
            cpm_summary=cpm_summary,
            change_impact=change_impact,
            remaining_activities=remaining_activities,
            as_of_date=as_of_date,
            baseline_summary=baseline_summary,
            comparison_basis=comparison_basis,
            materializable_only=False,
        )
        persisted_rows = self._repo.list_in_scope(scope=scope)
        persisted_by_stable = {str(r.get("source_stable_key")): r for r in persisted_rows}
        seen_stables: set[str] = set()
        items: list[dict[str, Any]] = []
        for candidate in all_candidates:
            stable = str(candidate.get("stable_item_key") or "")
            seen_stables.add(stable)
            persisted = persisted_by_stable.get(stable)
            if persisted:
                merged = self._merge_persisted_with_candidate(
                    persisted=persisted,
                    candidate=candidate,
                    live_keys=live_keys,
                )
            else:
                merged = self._preview_candidate(candidate)
            items.append(self._public_item(merged))
        for stable, persisted in persisted_by_stable.items():
            if stable in seen_stables:
                continue
            stale = dict(persisted)
            stale["stale_signal"] = True
            items.append(self._public_item(stale))
        envelope = self._workbench_envelope(
            project_key=scope.project_key,
            items=items,
            synced=synced,
            comparison_basis=comparison_basis,
        )
        envelope["review_scope"] = "named_baseline"
        envelope["synced"] = synced
        envelope["read_only_baseline_preview"] = False
        return envelope

    def _merge_persisted_with_candidate(
        self,
        *,
        persisted: dict[str, Any],
        candidate: dict[str, Any],
        live_keys: set[str],
    ) -> dict[str, Any]:
        merged = dict(persisted)
        merged["item_type"] = candidate.get("item_type", merged.get("item_type"))
        merged["item_title"] = candidate.get("item_title", merged.get("item_title"))
        merged["priority"] = candidate.get("priority", merged.get("priority"))
        evidence = dict(candidate.get("evidence") or {})
        merged["evidence"] = evidence
        stable = str(candidate.get("stable_item_key") or "")
        if live_keys and stable and stable not in live_keys:
            if str(merged.get("review_status")) not in {REVIEW_REVIEWED, REVIEW_DISMISSED}:
                evidence = dict(merged.get("evidence") or {})
                evidence["stale_signal"] = True
                notes = list(evidence.get("data_quality_notes") or [])
                if "Live signal no longer present in current schedule intelligence." not in notes:
                    notes.append("Live signal no longer present in current schedule intelligence.")
                evidence["data_quality_notes"] = notes
                merged["evidence"] = evidence
                merged["stale_signal"] = True
        merged["lineage"] = "existing"
        merged["new_since_last_review"] = False
        merged["still_open_from_prior"] = False
        return merged

    @staticmethod
    def _preview_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
        return {
            "review_item_id": None,
            "item_type": candidate.get("item_type"),
            "item_title": candidate.get("item_title"),
            "priority": candidate.get("priority"),
            "review_status": REVIEW_OPEN,
            "pm_notes": None,
            "evidence": candidate.get("evidence") or {},
            "source_activity_id": candidate.get("source_activity_id"),
            "stable_item_key": candidate.get("stable_item_key"),
            "source_metric_key": candidate.get("source_metric_key"),
            "source_signal_type": candidate.get("source_signal_type"),
            "lineage": "new",
            "new_since_last_review": True,
            "still_open_from_prior": False,
            "review_scope": "named_baseline",
        }

    def _collect_candidates(
        self,
        *,
        project_key: str,
        schedule_version_key: str,
        driver_analysis: dict[str, Any] | None,
        milestones: dict[str, Any] | None,
        remaining_health: dict[str, Any] | None,
        cpm_summary: dict[str, Any] | None,
        change_impact: dict[str, Any] | None,
        remaining_activities: list[dict[str, Any]] | None,
        as_of_date: date,
        baseline_summary: dict[str, Any] | None,
        comparison_basis: str,
        materializable_only: bool,
    ) -> list[dict[str, Any]]:
        return self._review._collect_candidates(
            project_key=project_key,
            schedule_version_key=schedule_version_key,
            driver_analysis=driver_analysis,
            milestones=milestones,
            remaining_health=remaining_health,
            cpm_summary=cpm_summary,
            change_impact=change_impact,
            remaining_activities=remaining_activities,
            as_of_date=as_of_date,
            baseline_summary=baseline_summary,
            comparison_basis=comparison_basis,
            materializable_only=materializable_only,
            include_activity_metric_cues=True,
        )

    @staticmethod
    def _public_item(row: dict[str, Any]) -> dict[str, Any]:
        return ProjectScheduleReviewService._public_item(row)

    @staticmethod
    def _workbench_envelope(
        *,
        project_key: str,
        items: list[dict[str, Any]],
        synced: bool,
        comparison_basis: str,
        identity_gate: str | None = None,
        analytics_trust_status: str | None = None,
    ) -> dict[str, Any]:
        envelope = ProjectScheduleReviewService._workbench_envelope(
            project_key=project_key,
            items=items,
            synced=synced or any(i.get("review_item_id") for i in items),
            comparison_basis=comparison_basis,
            identity_gate=identity_gate,
            analytics_trust_status=analytics_trust_status,
        )
        envelope["prioritized"] = envelope.get("preview") or []
        envelope["review_scope"] = "named_baseline"
        return envelope

    @staticmethod
    def identity_from_row(row: dict[str, Any]) -> NamedBaselineReviewIdentity:
        return NamedBaselineReviewIdentity(
            project_key=str(row["project_key"]),
            current_schedule_version_key=str(row["current_schedule_version_key"]),
            comparison_basis=str(row["comparison_basis"]),
            baseline_schedule_version_key=str(row["baseline_schedule_version_key"]),
            source_stable_key=str(row["source_stable_key"]),
            source_metric_key=str(row["source_metric_key"]),
            source_signal_type=str(row["source_signal_type"]),
            source_activity_id=row.get("source_activity_id"),
        )
