"""PM review workbench — sync persisted review queue from schedule intelligence signals."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from hb_assistant.store.project_schedule_hub_repository import (
    EVENT_CARRIED_FORWARD,
    EVENT_CREATED,
    REVIEW_DISMISSED,
    REVIEW_OPEN,
    REVIEW_REVIEWED,
    REVIEW_WATCHING,
    ProjectScheduleHubRepository,
)

_PREVIEW_LIMIT = 12
_QUEUE_LIMIT = 100


class ProjectScheduleReviewService:
    def __init__(self, *, db_path: str) -> None:
        self._repo = ProjectScheduleHubRepository(db_path=db_path)
        from .project_schedule_review_cue_service import ProjectScheduleReviewCueService

        self._cues = ProjectScheduleReviewCueService(db_path=db_path)

    def sync_queue(
        self,
        *,
        project_key: str,
        schedule_version_key: str,
        driver_analysis: dict[str, Any] | None = None,
        milestones: dict[str, Any] | None = None,
        remaining_health: dict[str, Any] | None = None,
        cpm_summary: dict[str, Any] | None = None,
        change_impact: dict[str, Any] | None = None,
        remaining_activities: list[dict[str, Any]] | None = None,
        as_of_date: date | None = None,
        baseline_summary: dict[str, Any] | None = None,
        comparison_basis: str = "prior_update",
    ) -> dict[str, Any]:
        as_of = as_of_date or datetime.now(timezone.utc).date()
        candidates = self._collect_candidates(
            project_key=project_key,
            schedule_version_key=schedule_version_key,
            driver_analysis=driver_analysis,
            milestones=milestones,
            remaining_health=remaining_health,
            cpm_summary=cpm_summary,
            change_impact=change_impact,
            remaining_activities=remaining_activities,
            as_of_date=as_of,
            baseline_summary=baseline_summary,
            comparison_basis=comparison_basis,
            materializable_only=True,
        )
        synced = 0
        for item in candidates:
            if not (item.get("evidence") or {}).get("materializable", item.get("materializable", True)):
                continue
            self._repo.upsert_review_item(
                project_key=project_key,
                schedule_version_key=schedule_version_key,
                stable_item_key=item["stable_item_key"],
                item_type=item["item_type"],
                item_title=item["item_title"],
                priority=item["priority"],
                evidence=item.get("evidence"),
                source_activity_id=item.get("source_activity_id"),
            )
            synced += 1
        return {"synced_count": synced, "candidate_count": len(candidates)}

    def build_preview(
        self,
        *,
        project_key: str,
        schedule_version_key: str,
        driver_analysis: dict[str, Any] | None = None,
        milestones: dict[str, Any] | None = None,
        remaining_health: dict[str, Any] | None = None,
        cpm_summary: dict[str, Any] | None = None,
        change_impact: dict[str, Any] | None = None,
        remaining_activities: list[dict[str, Any]] | None = None,
        comparison_basis: str = "prior_update",
        as_of_date: date | None = None,
        baseline_summary: dict[str, Any] | None = None,
        include_activity_metric_cues: bool = True,
        response_comparison_basis: str | None = None,
        carry_forward_disposition: bool = True,
    ) -> dict[str, Any]:
        """Read-only workbench preview — merges live candidates with persisted disposition."""
        return self._build_workbench(
            project_key=project_key,
            schedule_version_key=schedule_version_key,
            driver_analysis=driver_analysis,
            milestones=milestones,
            remaining_health=remaining_health,
            cpm_summary=cpm_summary,
            change_impact=change_impact,
            remaining_activities=remaining_activities,
            comparison_basis=comparison_basis,
            as_of_date=as_of_date,
            baseline_summary=baseline_summary,
            include_activity_metric_cues=include_activity_metric_cues,
            synced=False,
            carry_forward_disposition=carry_forward_disposition,
            response_comparison_basis=response_comparison_basis,
        )

    def sync_and_list(
        self,
        *,
        project_key: str,
        schedule_version_key: str,
        driver_analysis: dict[str, Any] | None = None,
        milestones: dict[str, Any] | None = None,
        remaining_health: dict[str, Any] | None = None,
        cpm_summary: dict[str, Any] | None = None,
        change_impact: dict[str, Any] | None = None,
        remaining_activities: list[dict[str, Any]] | None = None,
        as_of_date: date | None = None,
        baseline_summary: dict[str, Any] | None = None,
        comparison_basis: str = "prior_update",
    ) -> dict[str, Any]:
        basis = comparison_basis if comparison_basis in {"prior_update", "baseline"} else "prior_update"
        sync = {"synced_count": 0, "candidate_count": 0}
        if basis == "prior_update":
            sync = self.sync_queue(
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
                comparison_basis="prior_update",
            )
        envelope = self._build_workbench(
            project_key=project_key,
            schedule_version_key=schedule_version_key,
            driver_analysis=driver_analysis,
            milestones=milestones,
            remaining_health=remaining_health,
            cpm_summary=cpm_summary,
            change_impact=change_impact,
            remaining_activities=remaining_activities,
            comparison_basis=basis,
            as_of_date=as_of_date,
            baseline_summary=baseline_summary,
            synced=basis == "prior_update",
            use_persisted=basis == "prior_update",
        )
        envelope["sync"] = sync
        return envelope

    def _build_workbench(
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
        comparison_basis: str,
        as_of_date: date | None,
        baseline_summary: dict[str, Any] | None,
        include_activity_metric_cues: bool = True,
        synced: bool,
        use_persisted: bool = False,
        carry_forward_disposition: bool = True,
        response_comparison_basis: str | None = None,
    ) -> dict[str, Any]:
        as_of = as_of_date or datetime.now(timezone.utc).date()
        bases: dict[str, Any] = {}
        candidate_cache: dict[tuple[str, bool], list[dict[str, Any]]] = {}

        def cached_candidates(basis_key: str, materializable_only: bool) -> list[dict[str, Any]]:
            cache_key = (basis_key, materializable_only)
            if cache_key not in candidate_cache:
                candidate_cache[cache_key] = self._collect_candidates(
                    project_key=project_key,
                    schedule_version_key=schedule_version_key,
                    driver_analysis=driver_analysis,
                    milestones=milestones,
                    remaining_health=remaining_health,
                    cpm_summary=cpm_summary,
                    change_impact=change_impact,
                    remaining_activities=remaining_activities,
                    as_of_date=as_of,
                    baseline_summary=baseline_summary,
                    comparison_basis=basis_key,
                    materializable_only=materializable_only,
                    include_activity_metric_cues=include_activity_metric_cues,
                )
            return candidate_cache[cache_key]

        for basis_key, basis_driver in (
            ("prior_update", (driver_analysis or {}).get("prior_update") or driver_analysis),
            ("baseline", (driver_analysis or {}).get("baseline") or {}),
        ):
            if basis_key == "baseline" and not basis_driver.get("available"):
                bases[basis_key] = {"available": False, "reason": basis_driver.get("reason", "baseline_unavailable")}
                continue
            live_keys = {
                str(c["stable_item_key"]) for c in cached_candidates(basis_key, True)
            }
            candidates = cached_candidates(basis_key, False)
            if use_persisted and basis_key == "prior_update":
                items = [
                    self._public_item(self._enrich_persisted_item(row, live_keys=live_keys))
                    for row in self._repo.list_review_items(
                        project_key=project_key,
                        schedule_version_key=schedule_version_key,
                        limit=_QUEUE_LIMIT,
                    )
                ]
            else:
                if carry_forward_disposition:
                    items = [
                        self._public_item(
                            self._merge_candidate(
                                project_key=project_key,
                                schedule_version_key=schedule_version_key,
                                candidate=candidate,
                                live_keys=live_keys,
                            )
                        )
                        for candidate in candidates
                    ]
                else:
                    items = [
                        self._public_item(
                            self._preview_candidate(
                                project_key=project_key,
                                schedule_version_key=schedule_version_key,
                                candidate=candidate,
                            )
                        )
                        for candidate in candidates
                    ]
            bases[basis_key] = self._workbench_envelope(
                project_key=project_key,
                items=items,
                synced=synced and basis_key == "prior_update",
                comparison_basis=basis_key,
            )
        active = bases.get(comparison_basis) or bases.get("prior_update") or {"available": False}
        envelope = dict(active)
        envelope["bases"] = bases
        outward_basis = response_comparison_basis or comparison_basis
        envelope["comparison_basis"] = outward_basis
        if response_comparison_basis and response_comparison_basis != comparison_basis:
            envelope["read_only_baseline_preview"] = True
        return envelope

    def _preview_candidate(
        self,
        *,
        project_key: str,
        schedule_version_key: str,
        candidate: dict[str, Any],
    ) -> dict[str, Any]:
        merged = {
            "review_item_id": None,
            "project_key": project_key,
            "schedule_version_key": schedule_version_key,
            "stable_item_key": candidate["stable_item_key"],
            "item_type": candidate["item_type"],
            "item_title": candidate["item_title"],
            "priority": candidate["priority"],
            "review_status": REVIEW_OPEN,
            "pm_notes": None,
            "evidence": candidate.get("evidence") or {},
            "source_activity_id": candidate.get("source_activity_id"),
            "reviewed_by_operator": None,
            "reviewed_at": None,
        }
        merged.update(self._lineage_flags(prior=None, schedule_version_key=schedule_version_key, existing=False))
        return merged

    def list_items(
        self,
        *,
        project_key: str,
        schedule_version_key: str | None = None,
        review_status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        items = [
            self._public_item(self._enrich_persisted_item(row))
            for row in self._repo.list_review_items(
                project_key=project_key,
                schedule_version_key=schedule_version_key,
                review_status=review_status,
                limit=max(1, min(limit, 200)),
                offset=max(0, offset),
            )
        ]
        return {
            "available": True,
            "count": len(items),
            "limit": limit,
            "offset": offset,
            "items": items,
        }

    def get_item_detail(self, *, review_item_id: str) -> dict[str, Any]:
        row = self._repo.get_review_item(review_item_id=review_item_id)
        if not row:
            raise ValueError("review_item_not_found")
        enriched = self._enrich_persisted_item(row)
        events = self._repo.list_review_item_events(review_item_id=review_item_id, limit=100)
        item = self._public_item(enriched)
        return {
            "available": True,
            "item": item,
            "events": events,
            "lineage": {
                "lineage": item.get("lineage"),
                "new_since_last_review": item.get("new_since_last_review"),
                "still_open_from_prior": item.get("still_open_from_prior"),
            },
        }

    def list_item_events(self, *, review_item_id: str, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        row = self._repo.get_review_item(review_item_id=review_item_id)
        if not row:
            raise ValueError("review_item_not_found")
        events = self._repo.list_review_item_events(
            review_item_id=review_item_id,
            limit=max(1, min(limit, 200)),
        )
        return {
            "available": True,
            "review_item_id": review_item_id,
            "count": len(events),
            "limit": limit,
            "offset": max(0, offset),
            "events": events,
        }

    def update_item(
        self,
        *,
        review_item_id: str,
        review_status: str | None = None,
        pm_notes: str | None = None,
        reviewed_by_operator: str | None = None,
    ) -> dict[str, Any]:
        updated = self._repo.update_review_item(
            review_item_id=review_item_id,
            review_status=review_status,
            pm_notes=pm_notes,
            reviewed_by_operator=reviewed_by_operator,
        )
        if not updated:
            raise ValueError("review_item_not_found")
        return {"item": self._public_item(self._enrich_persisted_item(updated))}

    def filter_items(
        self,
        items: list[dict[str, Any]],
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
        return self._cues.filter_cues(
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
        baseline_summary: dict[str, Any] | None = None,
        comparison_basis: str = "prior_update",
        materializable_only: bool = False,
        include_activity_metric_cues: bool = True,
    ) -> list[dict[str, Any]]:
        if materializable_only:
            return self._cues.collect_materializable_cues(
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
        return self._cues.collect_review_cues(
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

    def _merge_candidate(
        self,
        *,
        project_key: str,
        schedule_version_key: str,
        candidate: dict[str, Any],
        live_keys: set[str] | None = None,
    ) -> dict[str, Any]:
        stable_item_key = str(candidate["stable_item_key"])
        persisted = self._repo.get_latest_review_item_by_stable_key(
            project_key=project_key,
            stable_item_key=stable_item_key,
        )
        if persisted and str(persisted.get("schedule_version_key")) == schedule_version_key:
            merged = dict(persisted)
            merged.update(self._lineage_flags(prior=persisted, schedule_version_key=schedule_version_key, existing=True))
            merged = self._apply_stale_signal(merged, stable_item_key=stable_item_key, live_keys=live_keys)
            return merged
        if persisted:
            merged = {
                "review_item_id": None,
                "project_key": project_key,
                "schedule_version_key": schedule_version_key,
                "stable_item_key": stable_item_key,
                "item_type": candidate["item_type"],
                "item_title": candidate["item_title"],
                "priority": candidate["priority"],
                "review_status": persisted.get("review_status", REVIEW_OPEN),
                "pm_notes": persisted.get("pm_notes"),
                "evidence": candidate.get("evidence") or {},
                "source_activity_id": candidate.get("source_activity_id"),
                "reviewed_by_operator": persisted.get("reviewed_by_operator"),
                "reviewed_at": persisted.get("reviewed_at"),
            }
            merged.update(self._lineage_flags(prior=persisted, schedule_version_key=schedule_version_key, existing=False))
            return merged
        merged = {
            "review_item_id": None,
            "project_key": project_key,
            "schedule_version_key": schedule_version_key,
            "stable_item_key": stable_item_key,
            "item_type": candidate["item_type"],
            "item_title": candidate["item_title"],
            "priority": candidate["priority"],
            "review_status": REVIEW_OPEN,
            "pm_notes": None,
            "evidence": candidate.get("evidence") or {},
            "source_activity_id": candidate.get("source_activity_id"),
            "reviewed_by_operator": None,
            "reviewed_at": None,
        }
        merged.update(self._lineage_flags(prior=None, schedule_version_key=schedule_version_key, existing=False))
        return merged

    def _enrich_persisted_item(
        self,
        row: dict[str, Any],
        *,
        live_keys: set[str] | None = None,
    ) -> dict[str, Any]:
        enriched = dict(row)
        events = self._repo.list_review_item_events(
            review_item_id=str(row["review_item_id"]),
            limit=10,
        )
        event_types = {str(event.get("event_type")) for event in events}
        carried = EVENT_CARRIED_FORWARD in event_types
        enriched["lineage"] = "carried_forward" if carried else "existing"
        enriched["new_since_last_review"] = EVENT_CREATED in event_types and not carried
        enriched["still_open_from_prior"] = carried and str(row.get("review_status")) in {
            REVIEW_OPEN,
            REVIEW_WATCHING,
        }
        return self._apply_stale_signal(
            enriched,
            stable_item_key=str(row.get("stable_item_key") or ""),
            live_keys=live_keys,
        )

    @staticmethod
    def _apply_stale_signal(
        row: dict[str, Any],
        *,
        stable_item_key: str,
        live_keys: set[str] | None,
    ) -> dict[str, Any]:
        if not live_keys or not stable_item_key or stable_item_key in live_keys:
            return row
        if str(row.get("review_status")) in {REVIEW_REVIEWED, REVIEW_DISMISSED}:
            return row
        evidence = dict(row.get("evidence") or row.get("evidence_json") or {})
        evidence["stale_signal"] = True
        notes = list(evidence.get("data_quality_notes") or [])
        if "Live signal no longer present in current schedule intelligence." not in notes:
            notes.append("Live signal no longer present in current schedule intelligence.")
        evidence["data_quality_notes"] = notes
        row = dict(row)
        row["evidence"] = evidence
        row["stale_signal"] = True
        row["data_quality_notes"] = notes
        return row

    @staticmethod
    def _lineage_flags(
        *,
        prior: dict[str, Any] | None,
        schedule_version_key: str,
        existing: bool,
    ) -> dict[str, Any]:
        if existing:
            return {
                "lineage": "existing",
                "new_since_last_review": False,
                "still_open_from_prior": False,
            }
        if not prior:
            return {
                "lineage": "new",
                "new_since_last_review": True,
                "still_open_from_prior": False,
            }
        carried = str(prior.get("schedule_version_key")) != schedule_version_key
        status = str(prior.get("review_status") or REVIEW_OPEN)
        still_open = status in {REVIEW_OPEN, REVIEW_WATCHING}
        return {
            "lineage": "carried_forward" if carried else "existing",
            "new_since_last_review": False,
            "still_open_from_prior": carried and still_open,
        }

    @staticmethod
    def _public_item(row: dict[str, Any]) -> dict[str, Any]:
        evidence = row.get("evidence")
        if evidence is None:
            evidence = row.get("evidence_json") or {}
        if not isinstance(evidence, dict):
            evidence = {}
        item = {
            key: value
            for key, value in row.items()
            if key not in {"schedule_version_key", "project_key", "evidence_json"}
        }
        item["evidence"] = evidence
        for key in (
            "source_metric_key",
            "source_signal_type",
            "confidence",
            "severity",
            "phase",
            "floor",
            "sector_area",
            "subcontractor",
            "cost_code",
            "cue_summary",
            "caveats",
            "partial_dimension_support",
            "data_quality_notes",
            "stale_signal",
            "comparison_basis",
            "as_of",
            "schedule_data_date",
            "data_date",
            "activity_name",
            "wbs_code",
            "cue_category",
            "cue_label",
            "recommended_review_action",
            "evidence_summary",
            "source_file_names",
            "source_formats",
            "field_lineage_available",
            "technical_evidence_available",
        ):
            if item.get(key) in (None, "", []):
                value = evidence.get(key)
                if value not in (None, "", []):
                    item[key] = value
        return item

    @staticmethod
    def _workbench_envelope(
        *,
        project_key: str,
        items: list[dict[str, Any]],
        synced: bool,
        comparison_basis: str = "prior_update",
    ) -> dict[str, Any]:
        open_items = [i for i in items if i.get("review_status") == REVIEW_OPEN]
        watching_items = [i for i in items if i.get("review_status") == REVIEW_WATCHING]
        reviewed_items = [i for i in items if i.get("review_status") == REVIEW_REVIEWED]
        dismissed_items = [i for i in items if i.get("review_status") == REVIEW_DISMISSED]
        prioritized = sorted(
            [i for i in items if i.get("review_status") in {REVIEW_OPEN, REVIEW_WATCHING}],
            key=lambda row: (-int(row.get("priority") or 0), str(row.get("item_title") or "")),
        )
        return {
            "available": True,
            "comparison_basis": comparison_basis,
            "persisted": synced,
            "summary": {
                "total_count": len(items),
                "open_count": len(open_items),
                "watching_count": len(watching_items),
                "reviewed_count": len(reviewed_items),
                "dismissed_count": len(dismissed_items),
            },
            "preview_limit": _PREVIEW_LIMIT,
            "preview": prioritized[:_PREVIEW_LIMIT],
            "items": items,
            "workbench_url": f"/projects/{project_key}/schedule/workbench",
            "export_url": f"/api/projects/{project_key}/schedule/export?format=markdown",
        }