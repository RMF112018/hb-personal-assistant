"""PM review workbench — sync persisted review queue from schedule intelligence signals."""

from __future__ import annotations

from typing import Any

from hb_assistant.store.project_schedule_hub_repository import (
    REVIEW_DISMISSED,
    REVIEW_OPEN,
    REVIEW_REVIEWED,
    REVIEW_WATCHING,
    ProjectScheduleHubRepository,
)

_PREVIEW_LIMIT = 12
_QUEUE_LIMIT = 100

_ITEM_DRIVER = "driver"
_ITEM_MILESTONE = "milestone"
_ITEM_NEGATIVE_FLOAT = "negative_float"
_ITEM_WORSENED_FLOAT = "worsened_float"
_ITEM_CRITICAL = "critical_remaining"


class ProjectScheduleReviewService:
    def __init__(self, *, db_path: str) -> None:
        self._repo = ProjectScheduleHubRepository(db_path=db_path)

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
    ) -> dict[str, Any]:
        candidates = self._collect_candidates(
            driver_analysis=driver_analysis,
            milestones=milestones,
            remaining_health=remaining_health,
            cpm_summary=cpm_summary,
            change_impact=change_impact,
            remaining_activities=remaining_activities,
        )
        synced = 0
        for item in candidates:
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
    ) -> dict[str, Any]:
        """Read-only workbench preview — merges live candidates with persisted disposition."""
        candidates = self._collect_candidates(
            driver_analysis=driver_analysis,
            milestones=milestones,
            remaining_health=remaining_health,
            cpm_summary=cpm_summary,
            change_impact=change_impact,
            remaining_activities=remaining_activities,
        )
        items = [
            self._public_item(self._merge_candidate(project_key=project_key, schedule_version_key=schedule_version_key, candidate=candidate))
            for candidate in candidates
        ]
        return self._workbench_envelope(project_key=project_key, items=items, synced=False)

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
    ) -> dict[str, Any]:
        sync = self.sync_queue(
            project_key=project_key,
            schedule_version_key=schedule_version_key,
            driver_analysis=driver_analysis,
            milestones=milestones,
            remaining_health=remaining_health,
            cpm_summary=cpm_summary,
            change_impact=change_impact,
            remaining_activities=remaining_activities,
        )
        items = [
            self._public_item(row)
            for row in self._repo.list_review_items(
                project_key=project_key,
                schedule_version_key=schedule_version_key,
                limit=_QUEUE_LIMIT,
            )
        ]
        envelope = self._workbench_envelope(project_key=project_key, items=items, synced=True)
        envelope["sync"] = sync
        return envelope

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
            self._public_item(row)
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
        return {"item": updated}

    def _collect_candidates(
        self,
        *,
        driver_analysis: dict[str, Any] | None,
        milestones: dict[str, Any] | None,
        remaining_health: dict[str, Any] | None,
        cpm_summary: dict[str, Any] | None,
        change_impact: dict[str, Any] | None,
        remaining_activities: list[dict[str, Any]] | None,
    ) -> list[dict[str, Any]]:
        seen: set[str] = set()
        out: list[dict[str, Any]] = []

        def add(
            *,
            stable_item_key: str,
            item_type: str,
            item_title: str,
            priority: int,
            source_activity_id: str | None = None,
            evidence: dict[str, Any] | None = None,
        ) -> None:
            if stable_item_key in seen:
                return
            seen.add(stable_item_key)
            out.append(
                {
                    "stable_item_key": stable_item_key,
                    "item_type": item_type,
                    "item_title": item_title,
                    "priority": priority,
                    "source_activity_id": source_activity_id,
                    "evidence": evidence or {},
                }
            )

        prior = (driver_analysis or {}).get("prior_update") or driver_analysis or {}
        if prior.get("available"):
            for driver in prior.get("top_drivers") or []:
                aid = str(driver.get("activity_id") or "")
                if not aid:
                    continue
                add(
                    stable_item_key=f"driver:{aid}",
                    item_type=_ITEM_DRIVER,
                    item_title=f"Review driver: {driver.get('activity_name') or aid}",
                    priority=int(driver.get("review_priority") or 50),
                    source_activity_id=aid,
                    evidence={
                        "driver_score": driver.get("driver_score"),
                        "downstream_moved_later_count": driver.get("downstream_moved_later_count"),
                        "wbs_code": driver.get("wbs_code"),
                    },
                )

        for ms in (milestones or {}).get("items") or []:
            movement = int(ms.get("movement_days") or 0)
            if movement <= 0:
                continue
            aid = str(ms.get("activity_id") or "")
            if not aid:
                continue
            add(
                stable_item_key=f"milestone:{aid}",
                item_type=_ITEM_MILESTONE,
                item_title=f"Milestone moved later: {ms.get('activity_name') or aid}",
                priority=min(95, 60 + movement),
                source_activity_id=aid,
                evidence={"movement_days": movement, "forecast_date": ms.get("forecast_date")},
            )

        neg_preview = (remaining_health or {}).get("float_pressure", {}).get("preview") or []
        neg_count = int((remaining_health or {}).get("float_pressure", {}).get("negative_float_count") or 0)
        if neg_count and not neg_preview and remaining_activities:
            neg_preview = [
                a
                for a in remaining_activities
                if self._float_value(a) is not None and self._float_value(a) < 0
            ][:5]
        for row in neg_preview:
            aid = str(row.get("activity_id") or "")
            if not aid:
                continue
            add(
                stable_item_key=f"negative_float:{aid}",
                item_type=_ITEM_NEGATIVE_FLOAT,
                item_title=f"Negative float: {row.get('activity_name') or aid}",
                priority=78,
                source_activity_id=aid,
                evidence={"total_float": row.get("total_float")},
            )

        worsened = (change_impact or {}).get("direct_remaining_changes", {}).get("items") or []
        for row in worsened:
            delta = row.get("float_delta_days")
            if delta is None or float(delta) >= 0:
                continue
            aid = str(row.get("activity_id") or "")
            if not aid:
                continue
            add(
                stable_item_key=f"worsened_float:{aid}",
                item_type=_ITEM_WORSENED_FLOAT,
                item_title=f"Worsened float: {row.get('activity_name') or aid}",
                priority=72,
                source_activity_id=aid,
                evidence={"float_delta_days": delta},
            )

        critical_preview = (cpm_summary or {}).get("critical_path", {}).get("items") or []
        for row in critical_preview[:5]:
            aid = str(row.get("activity_id") or "")
            if not aid:
                continue
            add(
                stable_item_key=f"critical:{aid}",
                item_type=_ITEM_CRITICAL,
                item_title=f"Critical remaining: {row.get('activity_name') or aid}",
                priority=68,
                source_activity_id=aid,
                evidence={"computed_cpm_critical": True},
            )

        out.sort(key=lambda item: (-int(item.get("priority") or 0), str(item.get("item_title") or "")))
        return out

    def _merge_candidate(
        self,
        *,
        project_key: str,
        schedule_version_key: str,
        candidate: dict[str, Any],
    ) -> dict[str, Any]:
        stable_item_key = str(candidate["stable_item_key"])
        persisted = self._repo.get_latest_review_item_by_stable_key(
            project_key=project_key,
            stable_item_key=stable_item_key,
        )
        if persisted and str(persisted.get("schedule_version_key")) == schedule_version_key:
            return persisted
        if persisted:
            return {
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
        return {
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

    @staticmethod
    def _public_item(row: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in row.items()
            if key not in {"schedule_version_key", "project_key", "evidence_json"}
        }

    @staticmethod
    def _workbench_envelope(*, project_key: str, items: list[dict[str, Any]], synced: bool) -> dict[str, Any]:
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

    @staticmethod
    def _float_value(row: dict[str, Any]) -> float | None:
        raw = row.get("total_float")
        if raw in (None, ""):
            raw = row.get("derived_total_float_days")
        try:
            return float(raw) if raw not in (None, "") else None
        except (TypeError, ValueError):
            return None