"""Portfolio-level schedule review dashboard read model (Phase 18)."""

from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime, timezone
from typing import Any, Literal

from hb_assistant.construction.analytics.project_schedule_analytics_trust_service import (
    pm_analytics_trust_payload,
)
from hb_assistant.construction.analytics.project_schedule_review_disposition import (
    DISPOSITION_NEEDS_REVIEW,
    enrich_item_disposition_pm_fields,
    normalize_disposition,
)
from hb_assistant.construction.analytics.project_schedule_review_rollup_service import (
    build_review_status_rollup,
)
from hb_assistant.construction.analytics.project_schedule_review_service import (
    ProjectScheduleReviewService,
)
from hb_assistant.construction.analytics.project_schedule_summary_service import (
    ProjectScheduleSummaryService,
)
from hb_assistant.construction.analytics.schedule_project_catalog import ScheduleProjectCatalog

# Schedule data dates older than this threshold are treated as stale for portfolio triage.
SCHEDULE_STALENESS_THRESHOLD_DAYS = 30

PortfolioStatus = Literal[
    "blocked",
    "operator_action_required",
    "needs_review",
    "stale",
    "degraded",
    "ready",
    "missing",
    "unknown",
]

_STATUS_FILTERS: list[str] = [
    "ready",
    "degraded",
    "blocked",
    "missing",
    "stale",
    "needs_review",
    "operator_action_required",
]

_PM_FORBIDDEN_KEYS = frozenset(
    {
        "schedule_version_key",
        "schedule_identity_key",
        "import_id",
        "package_id",
        "cpm_run_id",
        "source_export_proxy",
        "source_record_id",
        "raw_project_id",
        "procore_project_id",
        "db_id",
        "file_sha256",
        "file_path",
        "failure_message",
        "internal_hash",
        "evaluation_run_id",
        "review_item_id",
    }
)

_IDENTITY_OPERATOR_STATUSES = frozenset({"review_required", "ambiguous", "mismatch", "blocked"})

_NEXT_ACTIONS: list[dict[str, Any]] = [
    {
        "action_key": "identity_review_required",
        "label": "Identity review required",
        "pm_description": "Confirm schedule identity before relying on comparison or review metrics.",
        "priority": 10,
    },
    {
        "action_key": "analytics_trust_blocked",
        "label": "Analytics trust blocked",
        "pm_description": "Schedule analytics are blocked until operator trust review is complete.",
        "priority": 20,
    },
    {
        "action_key": "schedule_import_needed",
        "label": "Schedule import needed",
        "pm_description": "Import a committed schedule update before schedule review metrics are available.",
        "priority": 30,
    },
    {
        "action_key": "schedule_update_stale",
        "label": "Schedule update stale",
        "pm_description": "The latest imported schedule data date is older than the freshness threshold.",
        "priority": 40,
    },
    {
        "action_key": "review_items_need_disposition",
        "label": "Review items need disposition",
        "pm_description": "Open the review workbench and record operator dispositions for persisted items.",
        "priority": 50,
    },
    {
        "action_key": "preview_cues_available",
        "label": "Preview cues available",
        "pm_description": "Preview cues are available to promote into the review workbench.",
        "priority": 60,
    },
    {
        "action_key": "quality_review_required",
        "label": "Quality review recommended",
        "pm_description": "Schedule quality controls indicate limitations that warrant PM review.",
        "priority": 70,
    },
    {
        "action_key": "ready_for_pm_review",
        "label": "Ready for PM review",
        "pm_description": "Schedule trust, quality, and review queues are ready for PM review at the hub.",
        "priority": 80,
    },
]

_PRIORITY_RANK: dict[str, int] = {
    "blocked": 0,
    "operator_action_required": 1,
    "needs_review": 2,
    "stale": 3,
    "degraded": 4,
    "ready": 5,
    "missing": 1,
    "unknown": 6,
}


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def staleness_from_data_date(
    data_date: str | None,
    *,
    has_schedule: bool,
    as_of: date | None = None,
) -> tuple[str, int | None]:
    """Return ``(staleness_status, age_days)`` for portfolio triage."""
    if not has_schedule:
        return "missing", None
    parsed = _parse_iso_date(data_date)
    if not parsed:
        return "unknown", None
    today = as_of or datetime.now(timezone.utc).date()
    age_days = (today - parsed).days
    if age_days > SCHEDULE_STALENESS_THRESHOLD_DAYS:
        return "stale", age_days
    return "current", age_days


def _project_links(project_key: str) -> dict[str, str]:
    base = f"/projects/{project_key}/schedule"
    return {
        "hub": base,
        "controls": f"{base}?panel=controls",
        "workbench": f"{base}/workbench",
        "import": f"/projects/{project_key}/schedule/import",
        "identity_review": f"/schedules/identity-review?project={project_key}",
    }


def _primary_link(project_key: str, action_key: str) -> str:
    links = _project_links(project_key)
    if action_key == "identity_review_required":
        return links["identity_review"]
    if action_key in {"schedule_import_needed"}:
        return links["import"]
    if action_key in {"review_items_need_disposition", "preview_cues_available"}:
        return links["workbench"]
    if action_key == "quality_review_required":
        return links["controls"]
    return links["hub"]


def resolve_recommended_next_action(
    *,
    project_key: str,
    has_schedule: bool,
    schedule_resolved: bool,
    staleness_status: str,
    analytics_trust_status: str | None,
    identity_trust_status: str | None,
    identity_gate: str | None,
    cpm_trust_status: str | None,
    quality_trust_status: str | None,
    review_status: dict[str, Any],
) -> dict[str, Any]:
    """Deterministic PM-safe next-action classification."""
    needs_review = int(review_status.get("needs_review") or 0)
    preview_count = int(review_status.get("preview_cue_count") or 0)

    selected_key = "ready_for_pm_review"
    if identity_trust_status in _IDENTITY_OPERATOR_STATUSES or identity_gate == "blocked":
        selected_key = "identity_review_required"
    elif analytics_trust_status == "blocked":
        selected_key = "analytics_trust_blocked"
    elif not has_schedule or not schedule_resolved:
        selected_key = "schedule_import_needed"
    elif needs_review > 0:
        selected_key = "review_items_need_disposition"
    elif preview_count > 0:
        selected_key = "preview_cues_available"
    elif staleness_status == "stale":
        selected_key = "schedule_update_stale"
    elif quality_trust_status in {"degraded", "blocked"}:
        selected_key = "quality_review_required"
    elif cpm_trust_status in {"degraded", "blocked"}:
        selected_key = "quality_review_required"

    action = next(row for row in _NEXT_ACTIONS if row["action_key"] == selected_key)
    return {
        "action_key": action["action_key"],
        "label": action["label"],
        "pm_description": action["pm_description"],
        "primary_link": _primary_link(project_key, action["action_key"]),
        "priority": action["priority"],
    }


def _is_blocked(
    *,
    analytics_trust_status: str | None,
    identity_gate: str | None,
    cpm_trust_status: str | None,
    quality_trust_status: str | None,
) -> bool:
    return any(
        status == "blocked"
        for status in (
            analytics_trust_status,
            identity_gate,
            cpm_trust_status,
            quality_trust_status,
        )
    )


def _is_degraded(
    *,
    analytics_trust_status: str | None,
    identity_gate: str | None,
    cpm_trust_status: str | None,
    quality_trust_status: str | None,
) -> bool:
    return any(
        status == "degraded"
        for status in (
            analytics_trust_status,
            identity_gate,
            cpm_trust_status,
            quality_trust_status,
        )
    )


def _operator_action_required(
    *,
    has_schedule: bool,
    schedule_resolved: bool,
    identity_trust_status: str | None,
    identity_gate: str | None,
    analytics_trust_status: str | None,
) -> bool:
    if not has_schedule or not schedule_resolved:
        return True
    if identity_trust_status in _IDENTITY_OPERATOR_STATUSES:
        return True
    if identity_gate in {"blocked", "degraded"}:
        return True
    if analytics_trust_status == "blocked":
        return True
    return False


def _is_ready(
    *,
    has_schedule: bool,
    schedule_resolved: bool,
    staleness_status: str,
    analytics_trust_status: str | None,
    identity_trust_status: str | None,
    identity_gate: str | None,
    cpm_trust_status: str | None,
    quality_trust_status: str | None,
    review_status: dict[str, Any],
) -> bool:
    if not has_schedule or not schedule_resolved:
        return False
    if staleness_status != "current":
        return False
    if analytics_trust_status != "ready":
        return False
    if identity_trust_status != "trusted" or identity_gate != "ready":
        return False
    if cpm_trust_status not in {None, "ready"}:
        return False
    if quality_trust_status not in {None, "ready"}:
        return False
    if int(review_status.get("needs_review") or 0) > 0:
        return False
    if int(review_status.get("preview_cue_count") or 0) > 0:
        return False
    return True


def classify_portfolio_status(
    *,
    has_schedule: bool,
    schedule_resolved: bool,
    staleness_status: str,
    analytics_trust_status: str | None,
    identity_trust_status: str | None,
    identity_gate: str | None,
    cpm_trust_status: str | None,
    quality_trust_status: str | None,
    review_status: dict[str, Any],
    operator_action: bool,
) -> PortfolioStatus:
    if not has_schedule:
        return "missing"
    if _is_blocked(
        analytics_trust_status=analytics_trust_status,
        identity_gate=identity_gate,
        cpm_trust_status=cpm_trust_status,
        quality_trust_status=quality_trust_status,
    ):
        return "blocked"
    if operator_action:
        return "operator_action_required"
    if int(review_status.get("needs_review") or 0) > 0 or int(review_status.get("preview_cue_count") or 0) > 0:
        return "needs_review"
    if staleness_status == "stale":
        return "stale"
    if _is_degraded(
        analytics_trust_status=analytics_trust_status,
        identity_gate=identity_gate,
        cpm_trust_status=cpm_trust_status,
        quality_trust_status=quality_trust_status,
    ):
        return "degraded"
    if _is_ready(
        has_schedule=has_schedule,
        schedule_resolved=schedule_resolved,
        staleness_status=staleness_status,
        analytics_trust_status=analytics_trust_status,
        identity_trust_status=identity_trust_status,
        identity_gate=identity_gate,
        cpm_trust_status=cpm_trust_status,
        quality_trust_status=quality_trust_status,
        review_status=review_status,
    ):
        return "ready"
    if staleness_status == "unknown":
        return "unknown"
    return "degraded"


def _strip_pm_forbidden(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _strip_pm_forbidden(inner)
            for key, inner in value.items()
            if key not in _PM_FORBIDDEN_KEYS
        }
    if isinstance(value, list):
        return [_strip_pm_forbidden(item) for item in value]
    return value


def _public_review_status(rollup: dict[str, Any]) -> dict[str, Any]:
    return {
        "persisted_item_count": int(rollup.get("persisted_item_count") or 0),
        "preview_cue_count": int(rollup.get("preview_cue_count") or 0),
        "needs_review": int(rollup.get("needs_review") or 0),
        "accepted_for_follow_up": int(rollup.get("accepted_for_follow_up") or 0),
        "dismissed_not_material": int(rollup.get("dismissed_not_material") or 0),
        "resolved": int(rollup.get("resolved") or 0),
        "blocked": int(rollup.get("blocked") or 0),
    }


class ProjectSchedulePortfolioReviewService:
    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path
        self._catalog = ScheduleProjectCatalog(db_path=db_path)
        self._summary = ProjectScheduleSummaryService(db_path=db_path)
        self._review = ProjectScheduleReviewService(db_path=db_path)

    def build_dashboard(
        self,
        *,
        status: str | None = None,
        project_key: str | None = None,
        include_technical: bool = False,
        as_of: date | None = None,
    ) -> dict[str, Any]:
        """Build PM-safe portfolio schedule review dashboard.

        Uses a per-project loop over thin trust slices (not ``build_summary()``).
        Expected to remain acceptable for tens of projects; see limitations doc
        if portfolio size grows materially.
        """
        as_of_date = as_of or datetime.now(timezone.utc).date()
        projects_raw = self._catalog.list_browse_projects()
        if project_key:
            key = str(project_key).strip()
            projects_raw = [row for row in projects_raw if row.get("project_key") == key]

        project_cards: list[dict[str, Any]] = []
        for catalog_row in projects_raw:
            card = self._build_project_card(
                catalog_row,
                as_of_date=as_of_date,
                include_technical=include_technical,
            )
            if status and card.get("portfolio_status") != status:
                continue
            project_cards.append(card)

        project_cards.sort(
            key=lambda row: (
                _PRIORITY_RANK.get(str(row.get("portfolio_status") or ""), 99),
                str(row.get("project_label") or row.get("project_key") or "").lower(),
            )
        )

        summary = self._portfolio_summary(project_cards)
        return {
            "portfolio_summary": summary,
            "projects": project_cards,
            "filters": {
                "available_statuses": list(_STATUS_FILTERS),
                "available_actions": [row["action_key"] for row in _NEXT_ACTIONS],
            },
            "meta": {
                "as_of": as_of_date.isoformat(),
                "staleness_threshold_days": SCHEDULE_STALENESS_THRESHOLD_DAYS,
                "project_loop": "per_project_thin_trust_slice",
            },
        }

    def _build_project_card(
        self,
        catalog_row: dict[str, Any],
        *,
        as_of_date: date,
        include_technical: bool,
    ) -> dict[str, Any]:
        project_key = str(catalog_row.get("project_key") or "")
        project_label = (
            catalog_row.get("display_label")
            or catalog_row.get("display_name")
            or catalog_row.get("project_identity_label")
            or project_key
        )
        slice_row = self._summary.build_portfolio_trust_slice(project_key, as_of=as_of_date)
        has_schedule = bool(slice_row.get("has_schedule"))
        schedule_resolved = bool(slice_row.get("schedule_resolved"))
        schedule_data_date = slice_row.get("schedule_data_date")
        staleness_status, age_days = staleness_from_data_date(
            str(schedule_data_date) if schedule_data_date else None,
            has_schedule=has_schedule and schedule_resolved,
            as_of=as_of_date,
        )

        analytics_trust_status = slice_row.get("analytics_trust_status")
        identity_trust_status = slice_row.get("identity_trust_status") or "unavailable"
        identity_gate = slice_row.get("identity_gate")
        cpm_trust_status = slice_row.get("cpm_trust_status") or "unavailable"
        quality_trust_status = slice_row.get("quality_trust_status") or "unavailable"

        review_status = self._review_status_for_project(
            project_key=project_key,
            schedule_version_key=str(slice_row.get("schedule_version_key") or "") or None,
            analytics_trust_status=str(analytics_trust_status) if analytics_trust_status else None,
            identity_gate=str(identity_gate) if identity_gate else None,
        )
        operator_action = _operator_action_required(
            has_schedule=has_schedule,
            schedule_resolved=schedule_resolved,
            identity_trust_status=str(identity_trust_status),
            identity_gate=str(identity_gate) if identity_gate else None,
            analytics_trust_status=str(analytics_trust_status) if analytics_trust_status else None,
        )
        portfolio_status = classify_portfolio_status(
            has_schedule=has_schedule,
            schedule_resolved=schedule_resolved,
            staleness_status=staleness_status,
            analytics_trust_status=str(analytics_trust_status) if analytics_trust_status else None,
            identity_trust_status=str(identity_trust_status),
            identity_gate=str(identity_gate) if identity_gate else None,
            cpm_trust_status=str(cpm_trust_status),
            quality_trust_status=str(quality_trust_status),
            review_status=review_status,
            operator_action=operator_action,
        )
        next_action = resolve_recommended_next_action(
            project_key=project_key,
            has_schedule=has_schedule,
            schedule_resolved=schedule_resolved,
            staleness_status=staleness_status,
            analytics_trust_status=str(analytics_trust_status) if analytics_trust_status else None,
            identity_trust_status=str(identity_trust_status),
            identity_gate=str(identity_gate) if identity_gate else None,
            cpm_trust_status=str(cpm_trust_status),
            quality_trust_status=str(quality_trust_status),
            review_status=review_status,
        )

        card: dict[str, Any] = {
            "project_key": project_key,
            "project_label": project_label,
            "schedule_label": slice_row.get("schedule_label"),
            "schedule_data_date": schedule_data_date,
            "schedule_age_days": age_days,
            "schedule_staleness_status": staleness_status,
            "analytics_trust_status": analytics_trust_status or "unavailable",
            "identity_trust_status": identity_trust_status,
            "cpm_trust_status": cpm_trust_status,
            "quality_trust_status": quality_trust_status,
            "review_status": review_status,
            "portfolio_status": portfolio_status,
            "operator_action_required": operator_action,
            "ready": _is_ready(
                has_schedule=has_schedule,
                schedule_resolved=schedule_resolved,
                staleness_status=staleness_status,
                analytics_trust_status=str(analytics_trust_status) if analytics_trust_status else None,
                identity_trust_status=str(identity_trust_status),
                identity_gate=str(identity_gate) if identity_gate else None,
                cpm_trust_status=str(cpm_trust_status),
                quality_trust_status=str(quality_trust_status),
                review_status=review_status,
            ),
            "recommended_next_action": next_action,
            "links": _project_links(project_key),
        }
        if include_technical:
            analytics = slice_row.get("analytics_trust") or {}
            card["technical"] = {
                "schedule_version_key": slice_row.get("schedule_version_key"),
                "analytics_trust": pm_analytics_trust_payload(dict(analytics)),
            }
        return _strip_pm_forbidden(card)

    def _review_status_for_project(
        self,
        *,
        project_key: str,
        schedule_version_key: str | None,
        analytics_trust_status: str | None,
        identity_gate: str | None,
    ) -> dict[str, Any]:
        persisted_items = self._review.list_items(project_key=project_key, limit=200).get("items") or []
        preview_items: list[dict[str, Any]] = []
        if schedule_version_key:
            from hb_assistant.construction.analytics.project_schedule_review_cue_service import (
                ProjectScheduleReviewCueService,
            )

            preview_items = ProjectScheduleReviewCueService(db_path=self._db_path).list_quality_preview_cues(
                schedule_version_key
            )
            preview_items = [
                enrich_item_disposition_pm_fields(item)
                for item in preview_items
                if (normalize_disposition(str(item.get("review_status") or "")) or DISPOSITION_NEEDS_REVIEW)
                == DISPOSITION_NEEDS_REVIEW
            ]
        rollup = build_review_status_rollup(
            items=persisted_items,
            preview_items=preview_items,
            analytics_trust_status=analytics_trust_status,
            identity_gate=identity_gate,
        )
        return _public_review_status(rollup)

    @staticmethod
    def _portfolio_summary(projects: list[dict[str, Any]]) -> dict[str, int]:
        summary = {
            "project_count": len(projects),
            "projects_with_schedule": 0,
            "projects_without_schedule": 0,
            "ready_count": 0,
            "degraded_count": 0,
            "blocked_count": 0,
            "needs_review_count": 0,
            "stale_schedule_count": 0,
            "operator_action_required_count": 0,
        }
        for row in projects:
            if row.get("schedule_staleness_status") == "missing":
                summary["projects_without_schedule"] += 1
            else:
                summary["projects_with_schedule"] += 1
            status = str(row.get("portfolio_status") or "")
            if status == "ready":
                summary["ready_count"] += 1
            elif status == "degraded":
                summary["degraded_count"] += 1
            elif status == "blocked":
                summary["blocked_count"] += 1
            elif status == "needs_review":
                summary["needs_review_count"] += 1
            if row.get("schedule_staleness_status") == "stale":
                summary["stale_schedule_count"] += 1
            if row.get("operator_action_required"):
                summary["operator_action_required_count"] += 1
        return summary

    def build_export_markdown(self, *, status: str | None = None, project_key: str | None = None) -> str:
        dashboard = self.build_dashboard(status=status, project_key=project_key, include_technical=False)
        summary = dashboard["portfolio_summary"]
        lines = [
            "## Portfolio Schedule Review Status",
            "",
            f"- Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            f"- Staleness threshold: {SCHEDULE_STALENESS_THRESHOLD_DAYS} days",
            "- Limitation: Rollup depends on imported schedule data and completed review workflows.",
            "",
            f"- Total projects: {summary.get('project_count', 0)}",
            f"- Ready: {summary.get('ready_count', 0)}",
            f"- Degraded: {summary.get('degraded_count', 0)}",
            f"- Blocked: {summary.get('blocked_count', 0)}",
            f"- Missing schedule: {summary.get('projects_without_schedule', 0)}",
            f"- Stale schedule: {summary.get('stale_schedule_count', 0)}",
            f"- Needs review: {summary.get('needs_review_count', 0)}",
            f"- Operator action required: {summary.get('operator_action_required_count', 0)}",
            "",
            "## Priority Projects",
            "",
            "| Project | Schedule | Trust | Quality | Review | Recommended Action |",
            "|---|---|---|---|---|---|",
        ]
        for row in dashboard.get("projects") or []:
            review = row.get("review_status") or {}
            review_cell = (
                f"needs {review.get('needs_review', 0)} / preview {review.get('preview_cue_count', 0)}"
            )
            trust_cell = (
                f"A:{row.get('analytics_trust_status')} I:{row.get('identity_trust_status')} "
                f"C:{row.get('cpm_trust_status')}"
            )
            schedule_cell = f"{row.get('schedule_label') or '—'} ({row.get('schedule_staleness_status')})"
            action = (row.get("recommended_next_action") or {}).get("label") or "—"
            lines.append(
                f"| {row.get('project_label')} | {schedule_cell} | {trust_cell} | "
                f"{row.get('quality_trust_status')} | {review_cell} | {action} |"
            )
        return "\n".join(lines) + "\n"

    def build_export_csv(self, *, status: str | None = None, project_key: str | None = None) -> str:
        dashboard = self.build_dashboard(status=status, project_key=project_key, include_technical=False)
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "project_label",
                "schedule_label",
                "schedule_data_date",
                "staleness",
                "analytics_trust",
                "identity_trust",
                "cpm_trust",
                "quality_trust",
                "needs_review",
                "preview_cues",
                "recommended_action",
                "portfolio_status",
            ]
        )
        for row in dashboard.get("projects") or []:
            review = row.get("review_status") or {}
            action = (row.get("recommended_next_action") or {}).get("label") or ""
            writer.writerow(
                [
                    row.get("project_label"),
                    row.get("schedule_label"),
                    row.get("schedule_data_date"),
                    row.get("schedule_staleness_status"),
                    row.get("analytics_trust_status"),
                    row.get("identity_trust_status"),
                    row.get("cpm_trust_status"),
                    row.get("quality_trust_status"),
                    review.get("needs_review"),
                    review.get("preview_cue_count"),
                    action,
                    row.get("portfolio_status"),
                ]
            )
        return buffer.getvalue()

    def build_export_json(self, *, status: str | None = None, project_key: str | None = None) -> str:
        dashboard = self.build_dashboard(status=status, project_key=project_key, include_technical=False)
        return json.dumps(dashboard, indent=2, sort_keys=True)
