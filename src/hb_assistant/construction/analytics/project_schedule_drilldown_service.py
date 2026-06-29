"""Bounded drilldown queries for Project Schedule Hub Phase 2."""

from __future__ import annotations

from typing import Any

from hb_assistant.store.project_schedule_hub_repository import ProjectScheduleHubRepository

from .project_schedule_comparison import DRILLDOWN_TYPES, ProjectScheduleComparisonService

_DEFAULT_LIMIT = 100
_MAX_LIMIT = 200
_PREVIEW_LIMIT = 10


class ProjectScheduleDrilldownService:
    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path
        self._comparison = ProjectScheduleComparisonService(db_path=db_path)
        self._hub_repo = ProjectScheduleHubRepository(db_path=db_path)

    def list_drilldown(
        self,
        *,
        project_key: str,
        drilldown_type: str,
        current_key: str,
        comparison_key: str | None,
        limit: int = _DEFAULT_LIMIT,
        offset: int = 0,
    ) -> dict[str, Any]:
        if drilldown_type not in DRILLDOWN_TYPES:
            raise ValueError("unsupported_drilldown_type")
        limit = max(1, min(limit, _MAX_LIMIT))
        offset = max(0, offset)

        comparison = self._comparison.compare_versions(left_key=current_key, right_key=comparison_key)
        rows = self._comparison.filter_rows(comparison["rows"], drilldown_type)
        if drilldown_type == "negative_float":
            rows = self._comparison.filter_rows(comparison["rows"], "negative_float")
        rows.sort(key=lambda row: abs(row.get("finish_delta_days") or 0), reverse=True)
        total = len(rows)
        page = rows[offset : offset + limit]
        return {
            "available": True,
            "drilldown_type": drilldown_type,
            "count": total,
            "limit": limit,
            "offset": offset,
            "items": page,
            "comparison_basis": "resolved_finish_date",
        }

    def build_preview_map(
        self,
        *,
        project_key: str,
        current_key: str,
        previous_key: str | None,
        baseline_key: str | None,
        prior_summary: dict[str, Any],
        baseline_summary: dict[str, Any] | None,
        upstream_items: list[dict[str, Any]],
        negative_float_count: int,
        critical_count: int,
        near_critical_count: int,
    ) -> dict[str, Any]:
        prior_comparison = self._comparison.compare_versions(left_key=current_key, right_key=previous_key)
        baseline_comparison = (
            self._comparison.compare_versions(left_key=current_key, right_key=baseline_key)
            if baseline_key
            else {"rows": [], "summary": {}}
        )

        def preview(drilldown_type: str, count: int, rows: list[dict[str, Any]]) -> dict[str, Any]:
            filtered = self._comparison.filter_rows(rows, drilldown_type)
            filtered.sort(key=lambda row: abs(row.get("finish_delta_days") or 0), reverse=True)
            return {
                "count": count,
                "default_limit": _PREVIEW_LIMIT,
                "items": filtered[:_PREVIEW_LIMIT],
                "drilldown_url": (
                    f"/api/projects/{project_key}/schedule/drilldowns"
                    f"?type={drilldown_type}&limit={_DEFAULT_LIMIT}&offset=0"
                ),
            }

        s = prior_summary or prior_comparison.get("summary") or {}
        bs = (baseline_summary or {}) if baseline_summary else (baseline_comparison.get("summary") or {})
        out = {
            "remaining_later": preview("remaining_later", int(s.get("finish_moved_later_count") or 0), prior_comparison["rows"]),
            "remaining_earlier": preview("remaining_earlier", int(s.get("finish_moved_earlier_count") or 0), prior_comparison["rows"]),
            "finish_changed": preview("finish_changed", int(s.get("finish_changed_count") or 0), prior_comparison["rows"]),
            "new_remaining": preview("new_remaining", int(s.get("new_remaining_activities") or 0), prior_comparison["rows"]),
            "worsened_float": preview("worsened_float", int(s.get("worsened_float_count") or 0), prior_comparison["rows"]),
            "improved_float": preview("improved_float", int(s.get("improved_float_count") or 0), prior_comparison["rows"]),
            "milestones_later": preview(
                "milestones_later",
                int(s.get("moved_remaining_milestones_count") or 0),
                prior_comparison["rows"],
            ),
            "negative_float": {
                "count": negative_float_count,
                "default_limit": _PREVIEW_LIMIT,
                "items": self._comparison.filter_rows(prior_comparison["rows"], "negative_float")[:_PREVIEW_LIMIT],
                "drilldown_url": f"/api/projects/{project_key}/schedule/drilldowns?type=negative_float",
            },
            "critical_remaining": {
                "count": critical_count,
                "default_limit": _PREVIEW_LIMIT,
                "items": self._comparison.filter_rows(prior_comparison["rows"], "critical_remaining")[:_PREVIEW_LIMIT],
                "drilldown_url": f"/api/projects/{project_key}/schedule/drilldowns?type=critical_remaining",
            },
            "near_critical_remaining": {
                "count": near_critical_count,
                "default_limit": _PREVIEW_LIMIT,
                "items": self._comparison.filter_rows(prior_comparison["rows"], "near_critical_remaining")[:_PREVIEW_LIMIT],
                "drilldown_url": f"/api/projects/{project_key}/schedule/drilldowns?type=near_critical_remaining",
            },
            "upstream_cues": {
                "count": len(upstream_items),
                "default_limit": _PREVIEW_LIMIT,
                "items": upstream_items[:_PREVIEW_LIMIT],
                "drilldown_url": f"/api/projects/{project_key}/schedule/drilldowns?type=upstream_cues",
            },
        }
        if baseline_key:
            out["baseline_remaining_later"] = preview(
                "baseline_remaining_later",
                int(bs.get("finish_moved_later_count") or 0),
                baseline_comparison["rows"],
            )
            out["baseline_finish_changed"] = preview(
                "baseline_finish_changed",
                int(bs.get("finish_changed_count") or 0),
                baseline_comparison["rows"],
            )
            out["baseline_milestones_later"] = preview(
                "baseline_milestones_later",
                int(bs.get("moved_remaining_milestones_count") or 0),
                baseline_comparison["rows"],
            )
        return out

    def resolve_comparison_key(
        self,
        *,
        project_key: str,
        drilldown_type: str,
        current_key: str,
        previous_key: str | None,
        baseline_key: str | None,
    ) -> str | None:
        if drilldown_type.startswith("baseline_"):
            return baseline_key
        if drilldown_type == "upstream_cues":
            return previous_key
        return previous_key