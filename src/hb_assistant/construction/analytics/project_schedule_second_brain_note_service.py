"""PM-safe schedule second-brain note source payloads (Phase 19).

Assembles deterministic note inputs from existing schedule read models only.
No source-card pipeline, no raw DB rows, no LLM calls.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks
from hb_assistant.construction.analytics.project_schedule_baseline_vocabulary import (
    comparison_label_for_basis,
)
from hb_assistant.construction.analytics.project_schedule_controls_service import (
    ProjectScheduleControlsService,
)
from hb_assistant.construction.analytics.project_schedule_portfolio_review_service import (
    ProjectSchedulePortfolioReviewService,
)
from hb_assistant.construction.analytics.project_schedule_summary_service import (
    ProjectScheduleSummaryService,
)

NOTE_TYPES = frozenset(
    {
        "schedule_update",
        "baseline_comparison",
        "controls_snapshot",
        "review_summary",
        "portfolio_snapshot",
    }
)

_DEFAULT_COMPARISON_BASIS: dict[str, str] = {
    "schedule_update": "prior_update",
    "baseline_comparison": "current_contract_baseline",
    "controls_snapshot": "prior_update",
    "review_summary": "prior_update",
}

_CAPABILITY_LIMITATIONS = [
    "Sequence cues are advisory and highlight sequence movement for PM review only.",
    "HTML-in-ZIP schedule imports remain unsupported.",
    "Portfolio rollup uses thin per-project trust slices; large catalogs may need batching.",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_label(value: Any, *, fallback: str = "—") -> str:
    text = str(value or "").strip()
    return text or fallback


def _trust_status(row: dict[str, Any], key: str) -> str:
    return _safe_label(row.get(key), fallback="unavailable")


class ProjectScheduleSecondBrainNoteService:
    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path
        self._summary = ProjectScheduleSummaryService(db_path=db_path)
        self._controls = ProjectScheduleControlsService(db_path=db_path)
        self._portfolio = ProjectSchedulePortfolioReviewService(db_path=db_path)

    def build_note_source(
        self,
        note_type: str,
        *,
        project_key: str | None = None,
        as_of: date | None = None,
        comparison_basis: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        normalized = str(note_type or "").strip().lower()
        if normalized not in NOTE_TYPES:
            raise ValueError("unsupported_note_type")
        as_of_date = as_of or datetime.now(timezone.utc).date()
        basis = comparison_basis or _DEFAULT_COMPARISON_BASIS.get(normalized)
        if normalized == "portfolio_snapshot":
            payload = self._build_portfolio_payload(as_of_date=as_of_date, status=status, project_key=project_key)
        else:
            if not project_key:
                raise ValueError("project_key_required")
            if normalized == "controls_snapshot":
                payload = self._build_controls_payload(
                    project_key=project_key,
                    as_of_date=as_of_date,
                    comparison_basis=str(basis or "prior_update"),
                )
            else:
                scope = "review_items" if normalized == "review_summary" else "full"
                payload = self._build_export_payload(
                    project_key=project_key,
                    note_type=normalized,
                    as_of_date=as_of_date,
                    comparison_basis=str(basis or "prior_update"),
                    scope=scope,
                )
        leaks = find_redaction_leaks(payload)
        if leaks:
            raise ValueError(f"note_source_redaction_leak:{leaks}")
        return payload

    def _build_export_payload(
        self,
        *,
        project_key: str,
        note_type: str,
        as_of_date: date,
        comparison_basis: str,
        scope: str,
    ) -> dict[str, Any]:
        export = self._summary.build_export(
            project_key,
            export_format="markdown",
            as_of=as_of_date,
            scope=scope,
            comparison_basis=comparison_basis,
        )
        if not export.get("available", True):
            return {
                "note_type": note_type,
                "project_key": project_key,
                "project_label": project_key,
                "available": False,
                "reason": export.get("reason"),
                "comparison_basis": comparison_basis,
                "as_of": as_of_date.isoformat(),
                "generated_at": _utc_now(),
                "generation_mode": "deterministic",
                "body_markdown": "",
                "capability_limitations": list(_CAPABILITY_LIMITATIONS),
                "safe_links": {},
                "recommended_actions": [],
                "review_status": {},
                "quality_controls": {},
            }
        analytics_trust = export.get("analytics_trust") or {}
        identity_trust = analytics_trust.get("identity_trust") or {}
        slice_row = self._summary.build_portfolio_trust_slice(project_key, as_of=as_of_date)
        review_status: dict[str, Any] = {}
        context = self._summary.build_schedule_hub_context(project_key, as_of=as_of_date)
        if context:
            from hb_assistant.construction.analytics.project_schedule_review_rollup_service import (
                build_review_status_rollup,
            )
            from hb_assistant.construction.analytics.project_schedule_review_service import (
                ProjectScheduleReviewService,
            )

            listed = ProjectScheduleReviewService(db_path=self._db_path).list_items(
                project_key=project_key,
                schedule_version_key=str(context.get("schedule_version_key") or ""),
                limit=50,
            )
            review_status = build_review_status_rollup(
                items=listed.get("items") or [],
                analytics_trust_status=str(analytics_trust.get("status") or ""),
                identity_gate=str((identity_trust or {}).get("gate") or ""),
            )
        quality_controls: dict[str, Any] = {}
        if context and context.get("schedule_version_key"):
            from hb_assistant.construction.analytics.project_schedule_quality_controls_service import (
                ProjectScheduleQualityControlsService,
            )

            quality_controls = ProjectScheduleQualityControlsService(db_path=self._db_path).build_quality_controls(
                str(context.get("schedule_version_key") or ""),
                analytics_trust=analytics_trust,
                identity_trust=identity_trust,
            )
        comparison_label = comparison_label_for_basis(comparison_basis)
        recommended = []
        if review_status.get("recommended_next_action"):
            recommended.append(str(review_status["recommended_next_action"]))
        return {
            "note_type": note_type,
            "project_key": project_key,
            "project_label": _safe_label(slice_row.get("project_label") or project_key),
            "schedule_label": _safe_label(slice_row.get("schedule_label")),
            "schedule_data_date": _safe_label(slice_row.get("schedule_data_date") or as_of_date.isoformat()),
            "comparison_basis": comparison_basis,
            "comparison_label": comparison_label,
            "analytics_trust_status": _trust_status(analytics_trust, "status"),
            "identity_trust_status": _trust_status(identity_trust, "status"),
            "cpm_trust_status": _trust_status(analytics_trust.get("cpm_trust") or {}, "status"),
            "quality_trust_status": _trust_status(quality_controls, "status"),
            "review_status": review_status,
            "quality_controls": quality_controls,
            "recommended_actions": recommended,
            "safe_links": {
                "schedule_hub": f"/projects/{project_key}/schedule",
                "workbench": f"/projects/{project_key}/schedule/workbench?comparison_basis={comparison_basis}",
                "controls": f"/projects/{project_key}/schedule/controls?comparison_basis={comparison_basis}",
            },
            "capability_limitations": list(_CAPABILITY_LIMITATIONS),
            "body_markdown": str(export.get("body") or ""),
            "available": True,
            "as_of": as_of_date.isoformat(),
            "generated_at": _utc_now(),
            "generation_mode": "deterministic",
        }

    def _build_controls_payload(
        self,
        *,
        project_key: str,
        as_of_date: date,
        comparison_basis: str,
    ) -> dict[str, Any]:
        controls = self._controls.build_controls(
            project_key,
            as_of=as_of_date,
            comparison_basis=comparison_basis,
        )
        analytics_trust = controls.get("analytics_trust") or {}
        identity_trust = analytics_trust.get("identity_trust") or {}
        quality_controls = controls.get("quality_controls") or {}
        review_status = (controls.get("sections") or {}).get("review_workbench", {}).get("review_status") or {}
        return {
            "note_type": "controls_snapshot",
            "project_key": project_key,
            "project_label": _safe_label(controls.get("project_display_name") or project_key),
            "schedule_label": _safe_label(controls.get("schedule_label")),
            "schedule_data_date": _safe_label(controls.get("schedule_data_date")),
            "comparison_basis": comparison_basis,
            "comparison_label": comparison_label_for_basis(comparison_basis),
            "analytics_trust_status": _trust_status(analytics_trust, "status"),
            "identity_trust_status": _trust_status(identity_trust, "status"),
            "cpm_trust_status": _trust_status(analytics_trust.get("cpm_trust") or {}, "status"),
            "quality_trust_status": _trust_status(quality_controls, "status"),
            "review_status": review_status,
            "quality_controls": quality_controls,
            "recommended_actions": [
                str((controls.get("sections") or {}).get("review_workbench", {}).get("recommended_next_action") or "")
            ],
            "safe_links": controls.get("links") or {},
            "capability_limitations": list(_CAPABILITY_LIMITATIONS),
            "top_controls": controls.get("top_controls") or [],
            "available": bool(controls.get("available", True)),
            "as_of": as_of_date.isoformat(),
            "generated_at": _utc_now(),
            "generation_mode": "deterministic",
        }

    def _build_portfolio_payload(
        self,
        *,
        as_of_date: date,
        status: str | None,
        project_key: str | None,
    ) -> dict[str, Any]:
        dashboard = self._portfolio.build_dashboard(
            status=status,
            project_key=project_key,
            include_technical=False,
            as_of=as_of_date,
        )
        summary = dashboard.get("portfolio_summary") or {}
        recommended = []
        for row in dashboard.get("projects") or []:
            action = (row.get("recommended_next_action") or {}).get("label")
            if action:
                recommended.append(f"{row.get('project_label')}: {action}")
        return {
            "note_type": "portfolio_snapshot",
            "project_key": project_key,
            "project_label": "Portfolio",
            "schedule_label": None,
            "schedule_data_date": as_of_date.isoformat(),
            "comparison_basis": "portfolio",
            "comparison_label": "Portfolio schedule review",
            "analytics_trust_status": "mixed",
            "identity_trust_status": "mixed",
            "cpm_trust_status": "mixed",
            "quality_trust_status": "mixed",
            "review_status": summary,
            "quality_controls": {},
            "recommended_actions": recommended[:12],
            "safe_links": {
                "portfolio_dashboard": "/projects/all/schedule/review",
            },
            "capability_limitations": list(_CAPABILITY_LIMITATIONS),
            "portfolio_summary": summary,
            "projects": dashboard.get("projects") or [],
            "body_markdown": self._portfolio.build_export_markdown(status=status, project_key=project_key),
            "available": True,
            "as_of": as_of_date.isoformat(),
            "generated_at": _utc_now(),
            "generation_mode": "deterministic",
        }

    def idempotency_key(self, payload: dict[str, Any]) -> str:
        return "|".join(
            [
                str(payload.get("note_type") or ""),
                str(payload.get("project_key") or "portfolio"),
                str(payload.get("schedule_data_date") or payload.get("as_of") or ""),
                str(payload.get("comparison_basis") or ""),
                str(payload.get("comparison_label") or ""),
            ]
        )
