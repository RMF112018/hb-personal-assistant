"""Project-scoped schedule import pipeline orchestration (Phase A1)."""

from __future__ import annotations

from typing import Any

from hb_assistant.construction.analytics.project_schedule_analytics_trust_service import (
    ledger_from_import_preview,
    ledger_from_pipeline_status,
    normalize_quality_status,
)
from hb_assistant.construction.analytics.schedule_cpm_read_service import ScheduleCpmReadService
from hb_assistant.construction.analytics.schedule_cpm_trust import public_cpm_trust_fields
from hb_assistant.construction.analytics.schedule_cpm_recompute_service import (
    ScheduleCpmRecomputeService,
)
from hb_assistant.construction.analytics.schedule_file_parser import ScheduleImportError
from hb_assistant.construction.analytics.schedule_import_service import (
    ScheduleImportService,
    _PREVIEW_CACHE,
)
from hb_assistant.construction.analytics.schedule_trust_service import ScheduleTrustService
from hb_assistant.store.connection import open_connection
from hb_assistant.store.project_schedule_hub_repository import (
    MEMBERSHIP_ACCEPTED,
    ProjectScheduleHubRepository,
)
from hb_assistant.store.schedule_cpm_import_observability_repository import (
    ScheduleCpmImportObservabilityRepository,
)
from hb_assistant.store.schedule_import_repository import ScheduleImportRepository
from hb_assistant.store.schedule_quality_repository import ScheduleQualityRepository

_PIPELINE_STAGES: tuple[tuple[str, str], ...] = (
    ("parse_package", "Parse / package assembly"),
    ("persist_version", "Persist schedule version"),
    ("identity_trust", "Identity / trust resolution"),
    ("quality_evaluation", "Schedule quality evaluation"),
    ("default_diff", "Default prior-version diff"),
    ("cpm_recompute", "Computed CPM recompute"),
    ("baseline_readiness", "Baseline comparison readiness"),
    ("driver_analysis", "Driver analysis readiness"),
    ("review_workbench", "Review workbench preview readiness"),
    ("memo_export", "Memo/export readiness"),
    ("hub_readiness", "Project Schedule Hub readiness"),
)


class ProjectScheduleImportPipelineService:
    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path
        self._imports = ScheduleImportService(db_path=db_path)
        self._import_repo = ScheduleImportRepository(db_path=db_path)
        self._quality_repo = ScheduleQualityRepository(db_path=db_path)
        self._hub_repo = ProjectScheduleHubRepository(db_path=db_path)
        self._trust = ScheduleTrustService(db_path=db_path)
        self._cpm_recompute = ScheduleCpmRecomputeService(db_path=db_path)
        self._cpm_read = ScheduleCpmReadService(db_path=db_path)
        self._cpm_observability = ScheduleCpmImportObservabilityRepository(db_path=db_path)

    def preview_bytes(
        self,
        *,
        project_key: str,
        filename: str,
        data: bytes,
        column_roles: dict[str, str] | None = None,
        confirm_supersede: bool = False,
    ) -> dict[str, Any]:
        self._assert_route_project(project_key)
        preview = self._imports.preview_bytes(
            filename=filename,
            data=data,
            project_key=project_key,
            column_roles=column_roles,
            confirm_supersede=confirm_supersede,
        )
        trust_preview = self._build_trust_preview(project_key=project_key, preview=preview)
        out = dict(preview)
        out["pipeline_scope"] = "project_schedule_import"
        out["trust_preview"] = trust_preview
        out["analytics_trust"] = ledger_from_import_preview(preview, trust_preview=trust_preview)
        out["parse_stage_status"] = "complete"
        return out

    def commit(
        self,
        *,
        project_key: str,
        import_id: str,
        confirm: bool = False,
        confirm_supersede: bool = False,
        column_roles: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        self._assert_route_project(project_key)
        commit_result = self._imports.commit(
            import_id=import_id,
            project_key=project_key,
            confirm=confirm,
            confirm_supersede=confirm_supersede,
            column_roles=column_roles,
        )
        pipeline = self.build_status(project_key=project_key, import_id=import_id)
        out = dict(commit_result)
        out["pipeline_scope"] = "project_schedule_import"
        out.update(self._cpm_fields_from_pipeline(pipeline))
        out["pipeline"] = pipeline
        out["analytics_trust"] = pipeline.get("analytics_trust")
        return out

    def retry_cpm(self, *, project_key: str, import_id: str) -> dict[str, Any]:
        row = self._require_import(project_key=project_key, import_id=import_id)
        version_key = str(row.get("schedule_version_key") or "")
        if not version_key:
            raise ScheduleImportError(
                "schedule_import_invalid",
                message="import has no schedule version to recompute",
            )
        cpm = self._cpm_recompute.recompute(
            version_key,
            import_id=import_id,
            package_id=str(row.get("package_id") or "") or None,
            trigger_source="manual_retry",
        )
        pipeline = self.build_status(project_key=project_key, import_id=import_id)
        return {
            "import_id": import_id,
            "project_key": project_key,
            "schedule_version_key": version_key,
            "pipeline_scope": "project_schedule_import",
            **self._cpm_fields_from_result(cpm),
            "pipeline": pipeline,
        }

    def build_status(self, *, project_key: str, import_id: str) -> dict[str, Any]:
        row = self._require_import(project_key=project_key, import_id=import_id)
        version_key = str(row.get("schedule_version_key") or "")
        import_status = str(row.get("import_status") or "")
        committed = import_status == "committed"

        quality_run = self._quality_repo.get_latest_run(version_key) if version_key else None
        quality_status = self._map_quality_status(quality_run, committed=committed)

        cpm_summary = self._cpm_read.cpm_summary(version_key) if version_key else {"available": False}
        cpm_observability = self._cpm_observability.get_by_import_id(import_id)
        cpm_status = self._map_cpm_status(
            cpm_summary, committed=committed, observability=cpm_observability
        )

        membership = (
            self._hub_repo.get_membership(project_key=project_key, schedule_version_key=version_key)
            if version_key
            else None
        )
        identity_status = self._map_identity_status(membership, committed=committed)

        default_diff_id = (
            self._default_diff_id(project_key=project_key, schedule_version_key=version_key)
            if version_key
            else None
        )
        diff_status = (
            "complete"
            if default_diff_id
            else ("pending" if committed else "not_started")
        )

        baseline_selection = (
            self._hub_repo.get_active_baseline_selection(
                project_key=project_key,
                current_schedule_version_key=version_key,
            )
            if version_key
            else None
        )
        baseline_status = (
            "complete"
            if baseline_selection and baseline_selection.get("selected_baseline_schedule_version_key")
            else ("not_applicable" if not committed else "pending")
        )

        hub_ready = (
            committed
            and cpm_status in {"complete", "partial"}
            and identity_status == "complete"
            and quality_status in {"complete", "partial", "running", "pending"}
        )
        driver_status = "complete" if hub_ready and diff_status == "complete" else (
            "pending" if committed else "not_started"
        )
        workbench_status = driver_status
        memo_status = "complete" if hub_ready else ("pending" if committed else "not_started")

        stages = {
            "parse_package": "complete" if row else "not_started",
            "persist_version": "complete" if committed else ("running" if import_status else "not_started"),
            "identity_trust": identity_status,
            "quality_evaluation": quality_status,
            "default_diff": diff_status,
            "cpm_recompute": cpm_status,
            "baseline_readiness": baseline_status,
            "driver_analysis": driver_status,
            "review_workbench": workbench_status,
            "memo_export": memo_status,
            "hub_readiness": "complete" if hub_ready else ("partial" if committed else "not_started"),
        }

        stage_list = [
            {
                "stage": key,
                "label": label,
                "status": stages[key],
            }
            for key, label in _PIPELINE_STAGES
        ]

        overall = "complete" if hub_ready else ("partial" if committed else "pending")
        if committed and cpm_status == "failed":
            overall = "partial"

        return {
            "import_id": import_id,
            "project_key": project_key,
            "schedule_version_key": version_key or None,
            "import_status": import_status,
            "overall_status": overall,
            "stages": stage_list,
            "cpm": self._cpm_public_fields(cpm_summary, observability=cpm_observability),
            "quality_evaluation_status": quality_status,
            "identity_membership_status": (membership or {}).get("membership_status"),
            "hub_ready": hub_ready,
            "limitations": [
                "Status is derived from persisted facts; this endpoint does not recompute CPM or quality.",
            ],
            "analytics_trust": ledger_from_pipeline_status(
                {
                    "cpm": self._cpm_public_fields(cpm_summary, observability=cpm_observability),
                    "quality_evaluation_status": quality_status,
                    "identity_membership_status": (membership or {}).get("membership_status"),
                }
            ),
        }

    def _build_trust_preview(self, *, project_key: str, preview: dict[str, Any]) -> dict[str, Any]:
        import_id = str(preview.get("import_id") or "")
        cached = _PREVIEW_CACHE.get(import_id) or {}
        bundle = cached.get("bundle")
        activity_ids = {str(a.activity_id) for a in getattr(bundle, "activities", []) if getattr(a, "activity_id", None)}
        return self._trust.preview_import_trust(
            project_key=project_key,
            schedule_version_key=str(preview.get("schedule_version_key") or cached.get("schedule_version_key") or ""),
            activity_ids=activity_ids,
            source_project_id=preview.get("source_project_id"),
            data_date=preview.get("data_date"),
            duplicate_exists=bool(cached.get("duplicate_exists")),
            confirm_supersede=bool(cached.get("confirm_supersede")),
        )

    def _require_import(self, *, project_key: str, import_id: str) -> dict[str, Any]:
        row = self._import_repo.get_import(import_id)
        if not row:
            raise ScheduleImportError("schedule_not_found", message=f"unknown import_id {import_id}")
        if str(row.get("project_key") or "") != project_key:
            raise ScheduleImportError(
                "schedule_project_mismatch",
                message="import does not belong to this project",
                payload={"project_key": project_key, "import_project_key": row.get("project_key")},
            )
        return row

    @staticmethod
    def _assert_route_project(project_key: str) -> None:
        if not project_key or not str(project_key).strip():
            raise ScheduleImportError("schedule_project_required", message="project_key is required")

    @staticmethod
    def _map_quality_status(run: dict[str, Any] | None, *, committed: bool) -> str:
        return normalize_quality_status(str(run.get("status")) if run else None, committed=committed)

    @staticmethod
    def _map_cpm_status(
        summary: dict[str, Any],
        *,
        committed: bool,
        observability: dict[str, Any] | None = None,
    ) -> str:
        if not committed:
            return "not_started"
        if observability and str(observability.get("status") or "") == "failed":
            return "failed"
        runs = summary.get("runs") or {}
        kinds = (
            "graph_diagnostics",
            "forward_pass",
            "backward_pass",
            "float",
            "longest_path",
            "criticality",
        )
        if not any((runs.get(kind) or {}).get("available") for kind in kinds):
            return "pending"
        required = ("forward_pass", "backward_pass", "float", "longest_path", "criticality")
        if all((runs.get(kind) or {}).get("available") for kind in required):
            return "complete"
        if any((runs.get(kind) or {}).get("available") for kind in required):
            return "partial"
        return "unavailable"

    def _default_diff_id(self, *, project_key: str, schedule_version_key: str) -> int | None:
        with open_connection(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT id FROM schedule_version_diffs
                WHERE project_key=? AND to_schedule_version_key=?
                ORDER BY created_at DESC LIMIT 1
                """,
                (project_key, schedule_version_key),
            ).fetchone()
        return int(row[0]) if row else None

    @staticmethod
    def _map_identity_status(membership: dict[str, Any] | None, *, committed: bool) -> str:
        if not committed:
            return "not_started"
        if not membership:
            return "pending"
        status = str(membership.get("membership_status") or "")
        if status == MEMBERSHIP_ACCEPTED:
            return "complete"
        if status:
            return "partial"
        return "pending"

    def _cpm_public_fields(
        self,
        summary: dict[str, Any],
        *,
        observability: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        runs = summary.get("runs") or {}
        critical = runs.get("criticality") or {}
        dcma = summary.get("dcma_critical_path") or {}
        cpm_status = self._map_cpm_status(summary, committed=True, observability=observability)
        trust = public_cpm_trust_fields(
            observability=observability,
            cpm_recompute_status=cpm_status,
            trigger_source=str((observability or {}).get("trigger_source") or "") or None,
        )
        out: dict[str, Any] = {
            "available": bool(summary.get("available")),
            "cpm_recompute_status": cpm_status,
            "cpm_trust_status": trust.get("cpm_trust_status"),
            "cpm_run_id": critical.get("cpm_run_id") if critical.get("available") else None,
            "computed_critical_activity_count": dcma.get("computed_critical_activity_count"),
            "longest_path_available": bool((runs.get("longest_path") or {}).get("available")),
            "diagnostics_count": (runs.get("graph_diagnostics") or {}).get("diagnostic_count"),
            "failure_code": trust.get("failure_code"),
            "failed_step": trust.get("failed_step"),
            "failure_message_redacted": trust.get("failure_message_redacted"),
            "trigger_source": trust.get("trigger_source"),
            "canonical_input_activity_count": trust.get("canonical_input_activity_count"),
            "canonical_input_relationship_count": trust.get("canonical_input_relationship_count"),
            "graph_node_count": trust.get("graph_node_count"),
            "graph_edge_count": trust.get("graph_edge_count"),
            "duration_ms": trust.get("duration_ms"),
        }
        if observability and observability.get("cpm_run_id"):
            out["cpm_run_id"] = observability.get("cpm_run_id")
        return out

    @staticmethod
    def _cpm_fields_from_result(cpm: dict[str, Any]) -> dict[str, Any]:
        observability = cpm.get("cpm_observability") or {}
        return {
            "cpm_recompute_triggered": cpm.get("cpm_recompute_triggered"),
            "cpm_recompute_status": cpm.get("cpm_recompute_status"),
            "cpm_run_id": cpm.get("cpm_run_id"),
            "computed_activity_count": cpm.get("computed_activity_count"),
            "computed_critical_activity_count": cpm.get("computed_critical_activity_count"),
            "computed_near_critical_activity_count": cpm.get("computed_near_critical_activity_count"),
            "longest_path_available": cpm.get("longest_path_available"),
            "diagnostics_count": cpm.get("diagnostics_count"),
            "failure_code": observability.get("failure_code"),
            "failed_step": observability.get("failed_step"),
            "failure_message_redacted": observability.get("failure_message_redacted"),
            "cpm_observability": observability,
            "canonical_input_activity_count": cpm.get("canonical_input_activity_count"),
            "canonical_input_relationship_count": cpm.get("canonical_input_relationship_count"),
            "graph_node_count": cpm.get("graph_node_count"),
            "graph_edge_count": cpm.get("graph_edge_count"),
            "duration_ms": cpm.get("duration_ms"),
        }

    def _cpm_fields_from_pipeline(self, pipeline: dict[str, Any]) -> dict[str, Any]:
        cpm = pipeline.get("cpm") or {}
        status = cpm.get("cpm_recompute_status") or "pending"
        return {
            "cpm_recompute_triggered": status not in {"not_started", "unavailable"},
            "cpm_recompute_status": status,
            "cpm_run_id": cpm.get("cpm_run_id"),
            "computed_critical_activity_count": cpm.get("computed_critical_activity_count"),
            "longest_path_available": cpm.get("longest_path_available"),
            "diagnostics_count": cpm.get("diagnostics_count"),
        }