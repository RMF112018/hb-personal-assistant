"""Schedule file import preview and commit into local SQLite."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator
from hb_assistant.store.schedule_activity_repository import ScheduleActivityRepository
from hb_assistant.store.schedule_import_repository import ScheduleImportRepository
from hb_assistant.store.schedule_mapping_repository import ScheduleMappingRepository

from .schedule_cost_loading import assess_cost_loaded_status
from .schedule_csv_parser import PARSER_NAME as CSV_PARSER
from .schedule_csv_parser import PARSER_VERSION as CSV_VER
from .schedule_csv_parser import parse_csv_bytes
from .schedule_dto import ScheduleImportPreviewDTO, ScheduleVersionSummaryDTO
from .schedule_evidence import write_import_evidence
from .schedule_file_parser import (
    ParsedScheduleBundle,
    ScheduleImportError,
    detect_source,
    safe_basename,
)
from .schedule_xml_parser import PARSER_NAME as XML_PARSER
from .schedule_xml_parser import PARSER_VERSION as XML_VER
from .schedule_xml_parser import parse_pmxml_bytes

MAX_UPLOAD_BYTES = 50 * 1024 * 1024

# In-memory preview cache keyed by import_id (process-local; tests use single client).
_PREVIEW_CACHE: dict[str, dict[str, Any]] = {}


def ensure_schedule_schema(db_path: str) -> None:
    from hb_assistant.store.connection import get_connection
    from hb_assistant.store.schedule_schema_verify import verify_v65_schedule_float_schema

    migrator = SQLiteMigrator(db_path=db_path)
    conn = get_connection(db_path)
    try:
        missing = verify_v65_schedule_float_schema(conn)
        version = migrator.current_version()
        needs_apply = version < LATEST_SCHEMA_VERSION or bool(missing)
    finally:
        conn.close()

    if needs_apply:
        migrator.apply()

    conn2 = get_connection(db_path)
    try:
        missing_after = verify_v65_schedule_float_schema(conn2)
        version_after = migrator.current_version()
    finally:
        conn2.close()

    if version_after < LATEST_SCHEMA_VERSION or missing_after:
        raise ScheduleImportError(
            "schedule_schema_not_ready",
            message="schedule schema is not ready",
            payload={
                "schema_version": version_after,
                "schema_expected": LATEST_SCHEMA_VERSION,
                "schedule_v65_missing_columns": missing_after,
            },
        )


def version_key_for_bundle(*, project_key: str, bundle: ParsedScheduleBundle, import_id: str) -> str:
    schedule_id = bundle.schedule_id or f"import-{import_id}"
    return f"{project_key}|{schedule_id}|{bundle.data_date or import_id}"


def duplicate_view_path(schedule_version_key: str) -> str:
    from urllib.parse import quote

    return f"/schedules/activities?version={quote(schedule_version_key, safe='')}"


def validate_import_project_key(*, db_path: str, project_key: str) -> str:
    from .schedule_project_catalog import ScheduleProjectCatalog

    key = str(project_key or "").strip()
    if not key:
        raise ScheduleImportError(
            "schedule_project_required",
            message="project_key is required",
        )
    catalog = ScheduleProjectCatalog(db_path=db_path)
    if not catalog.is_selectable_project(key):
        raise ScheduleImportError(
            "schedule_project_unknown",
            message=f"project_key is not a selectable Procore project: {key}",
            payload={"project_key": key},
        )
    return key


def assert_version_matches_project(
    schedule_version_key: str, project_key: str | None
) -> None:
    if not project_key:
        return
    parts = str(schedule_version_key).split("|")
    if not parts or parts[0] != project_key:
        raise ScheduleImportError(
            "schedule_not_found",
            message="schedule version does not belong to the requested project",
        )


def _sort_key_value(row: dict[str, Any], field: str) -> Any:
    raw = row.get(field)
    if field in {"quality_score"} and raw is not None:
        try:
            return float(raw)
        except (TypeError, ValueError):
            return raw
    return raw if raw is not None else ""


def sort_version_summaries(
    rows: list[dict[str, Any]],
    *,
    sort: str = "imported_at",
    order: str = "desc",
) -> list[dict[str, Any]]:
    allowed = {
        "project_key",
        "data_date",
        "imported_at",
        "source_format",
        "quality_score",
        "quality_grade",
        "completion_posture",
        "quality_status",
        "evaluated_at",
    }
    field = sort if sort in allowed else "imported_at"
    reverse = str(order or "desc").lower() != "asc"
    return sorted(rows, key=lambda r: _sort_key_value(r, field), reverse=reverse)


class ScheduleImportService:
    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path
        self._import_repo = ScheduleImportRepository(db_path=db_path)
        self._activity_repo = ScheduleActivityRepository(db_path=db_path)
        self._mapping_repo = ScheduleMappingRepository(db_path=db_path)

    def _ensure_schema(self) -> None:
        ensure_schedule_schema(self._db_path)

    @staticmethod
    def _sha256(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def preview_bytes(
        self,
        *,
        filename: str,
        data: bytes,
        project_key: str,
        column_roles: dict[str, str] | None = None,
        confirm_supersede: bool = False,
    ) -> dict[str, Any]:
        self._ensure_schema()
        project_key = validate_import_project_key(db_path=self._db_path, project_key=project_key)
        if len(data) > MAX_UPLOAD_BYTES:
            raise ScheduleImportError(
                "schedule_file_too_large",
                message="uploaded file exceeds the size limit",
            )
        if not data:
            raise ScheduleImportError("schedule_import_invalid", message="empty upload payload")

        basename = safe_basename(filename)
        source_type, source_format = detect_source(basename, data=data)
        bundle, parser_name, parser_version = self._parse_bundle(
            data,
            source_type=source_type,
            source_format=source_format,
            column_roles=column_roles,
        )
        bundle.source_capabilities = dict(
            (bundle.schedule_options or {}).get("source_capabilities") or {}
        )
        cost_status = assess_cost_loaded_status(bundle.activities, bundle.cost_loaded_hints)
        import_id = uuid.uuid4().hex[:12]
        file_sha = self._sha256(data)
        version_key = version_key_for_bundle(
            project_key=project_key, bundle=bundle, import_id=import_id
        )
        existing = self._activity_repo.get_version_summary(version_key)
        if (
            existing
            and str(existing.get("import_status") or "") == "committed"
            and not confirm_supersede
        ):
            raise ScheduleImportError(
                "duplicate_schedule_version",
                message="schedule version already committed",
                payload={
                    "schedule_version_key": version_key,
                    "activity_count": int(existing.get("activity_count") or 0),
                    "relationship_count": int(existing.get("relationship_count") or 0),
                    "view_path": duplicate_view_path(version_key),
                },
            )

        _PREVIEW_CACHE[import_id] = {
            "project_key": project_key,
            "bundle": bundle,
            "source_type": source_type,
            "source_format": source_format,
            "parser_name": parser_name,
            "parser_version": parser_version,
            "filename": basename,
            "file_sha256": file_sha,
            "payload_sha256": self._sha256(json.dumps(
                {"activities": len(bundle.activities)}, sort_keys=True
            ).encode()),
            "column_roles": column_roles,
        }

        from .schedule_project_catalog import ScheduleProjectCatalog

        catalog = ScheduleProjectCatalog(db_path=self._db_path)
        dto = ScheduleImportPreviewDTO(
            import_id=import_id,
            display_label=bundle.schedule_name or basename,
            source_type=source_type,
            source_format=source_format,
            source_filename=basename,
            file_sha256=file_sha,
            byte_count=len(data),
            activity_count=len(bundle.activities),
            relationship_count=len(bundle.relationships),
            wbs_count=len(bundle.wbs_nodes),
            calendar_count=len(bundle.calendars),
            code_count=len(bundle.code_assignments),
            udf_count=len(bundle.udf_values),
            cost_loaded_status=cost_status,
            validation_findings=bundle.validation_findings,
            schedule_name=bundle.schedule_name,
            data_date=bundle.data_date,
            planned_start=bundle.planned_start,
            scheduled_finish=bundle.scheduled_finish,
            requires_column_mapping=source_type == "csv" and not column_roles,
            project_key=project_key,
            project_display_name=catalog.resolve_display_name(project_key),
        )
        return dto.public()

    def commit(
        self,
        *,
        import_id: str,
        project_key: str,
        confirm: bool = False,
        confirm_supersede: bool = False,
        column_roles: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        self._ensure_schema()
        project_key = validate_import_project_key(db_path=self._db_path, project_key=project_key)
        if not confirm:
            raise ScheduleImportError(
                "schedule_import_invalid",
                message="import commit requires explicit operator confirmation",
            )

        cached = _PREVIEW_CACHE.get(import_id)
        if cached is None:
            raise ScheduleImportError(
                "schedule_not_found",
                message=f"unknown import_id {import_id}",
            )

        if cached["project_key"] != project_key:
            raise ScheduleImportError(
                "schedule_import_invalid",
                message="project_key does not match preview",
            )

        bundle: ParsedScheduleBundle = cached["bundle"]
        if cached["source_type"] == "csv":
            if not column_roles and not cached.get("column_roles"):
                raise ScheduleImportError(
                    "schedule_import_invalid",
                    message="CSV import requires operator column mapping",
                )
            if column_roles:
                cached["column_roles"] = column_roles

        if not bundle.activities:
            raise ScheduleImportError(
                "schedule_import_invalid",
                message="cannot commit import with no activities",
            )

        schedule_id = bundle.schedule_id or f"import-{import_id}"
        version_key = version_key_for_bundle(
            project_key=project_key, bundle=bundle, import_id=import_id
        )
        existing = self._activity_repo.get_version_summary(version_key)
        superseded_import_id: str | None = None
        if existing and str(existing.get("import_status") or "") == "committed":
            if not confirm_supersede:
                raise ScheduleImportError(
                    "duplicate_schedule_version",
                    message="schedule version already committed",
                    payload={
                        "schedule_version_key": version_key,
                        "activity_count": int(existing.get("activity_count") or 0),
                        "relationship_count": int(existing.get("relationship_count") or 0),
                        "view_path": duplicate_view_path(version_key),
                    },
                )
            superseded_import_id = str(existing.get("import_id"))
            self._activity_repo.delete_version_subgraph(
                schedule_version_key=version_key,
                import_id=superseded_import_id,
            )
            self._import_repo.update_import(
                superseded_import_id,
                {"import_status": "superseded", "validation_status": "superseded_by_operator"},
            )
        now = datetime.now(timezone.utc).isoformat()
        cost_status = assess_cost_loaded_status(bundle.activities, bundle.cost_loaded_hints)

        record_key = f"svk-{_sha256(f'{project_key}|{schedule_id}|{import_id}')[:32]}"
        self._activity_repo.upsert_schedule_version_row(
            {
                "record_key": record_key,
                "raw_payload_id": None,
                "endpoint_key": "schedule_import",
                "endpoint_family": "schedules",
                "project_key": project_key,
                "project_id": bundle.procore_project_id,
                "record_id": schedule_id,
                "schedule_id": schedule_id,
                "schedule_name": bundle.schedule_name,
                "data_date": bundle.data_date,
                "start_date": bundle.planned_start,
                "source_quality": "file_import",
                "is_current": 0,
                "created_utc": now,
                "updated_utc": now,
                "external_writeback_performed": 0,
                "raw_payload_emitted_to_read_model": 0,
                "raw_payload_emitted_to_evidence": 0,
            }
        )

        evidence_id = write_import_evidence(
            import_id=import_id,
            project_key=project_key,
            summary={
                "activity_count": len(bundle.activities),
                "relationship_count": len(bundle.relationships),
                "source_type": cached["source_type"],
                "schedule_version_key": version_key,
            },
        )

        self._import_repo.insert_import(
            {
                "import_id": import_id,
                "project_key": project_key,
                "procore_project_id": bundle.procore_project_id,
                "source_type": cached["source_type"],
                "source_format": cached["source_format"],
                "source_filename_redacted": cached["filename"],
                "source_file_sha256": cached["file_sha256"],
                "source_payload_sha256": cached["payload_sha256"],
                "parser_name": cached["parser_name"],
                "parser_version": cached["parser_version"],
                "import_status": "committed",
                "validation_status": "ok" if not bundle.validation_findings else "warnings",
                "activity_count": len(bundle.activities),
                "relationship_count": len(bundle.relationships),
                "wbs_count": len(bundle.wbs_nodes),
                "calendar_count": len(bundle.calendars),
                "code_count": len(bundle.code_assignments),
                "udf_count": len(bundle.udf_values),
                "cost_loaded_status": cost_status,
                "schedule_version_key": version_key,
                "evidence_package_id": evidence_id,
                "created_by_operator": "operator",
                "compute_total_float_type": (bundle.schedule_options or {}).get(
                    "compute_total_float_type"
                ),
                "critical_activity_path_type": (bundle.schedule_options or {}).get(
                    "critical_activity_path_type"
                ),
                "critical_activity_float_threshold": str(
                    (bundle.schedule_options or {}).get("critical_activity_float_threshold")
                )
                if (bundle.schedule_options or {}).get("critical_activity_float_threshold")
                is not None
                else None,
                "calculate_float_based_on_finish_date": (bundle.schedule_options or {}).get(
                    "calculate_float_based_on_finish_date"
                ),
                "critical_path_type": (bundle.schedule_options or {}).get("critical_path_type"),
                "critical_float_threshold": str(
                    (bundle.schedule_options or {}).get("critical_float_threshold")
                )
                if (bundle.schedule_options or {}).get("critical_float_threshold") is not None
                else None,
                "schedule_options_json": json.dumps(
                    (bundle.schedule_options or {}).get("schedule_options_json") or {},
                    sort_keys=True,
                    default=str,
                ),
                "baseline_source": (bundle.schedule_options or {}).get("baseline_source"),
            }
        )

        self._persist_bundle(
            bundle=bundle,
            project_key=project_key,
            schedule_id=schedule_id,
            version_key=version_key,
            import_id=import_id,
            schedule_table_id=record_key,
            source_type=cached["source_type"],
            source_format=cached["source_format"],
        )

        from hb_assistant.construction.analytics.schedule_quality_service import (
            ScheduleQualityService,
        )
        from hb_assistant.construction.analytics.schedule_quality_worker import (
            poll_and_process,
        )

        quality_svc = ScheduleQualityService(db_path=self._db_path)
        queued = quality_svc.queue_after_commit(
            project_key=project_key,
            schedule_version_key=version_key,
            schedule_table_id=record_key,
            import_id=import_id,
        )
        poll_and_process(db_path=self._db_path, limit=1)

        _PREVIEW_CACHE.pop(import_id, None)
        from .schedule_project_catalog import ScheduleProjectCatalog

        catalog = ScheduleProjectCatalog(db_path=self._db_path)
        return {
            "import_id": import_id,
            "project_key": project_key,
            "project_display_name": catalog.resolve_display_name(project_key),
            "schedule_version_key": version_key,
            "activity_count": len(bundle.activities),
            "cost_loaded_status": cost_status,
            "quality_evaluation_status": queued.get("status", "pending"),
            "evaluation_run_id": queued.get("evaluation_run_id"),
            "committed_at": now,
            "superseded_import_id": superseded_import_id,
        }

    def _persist_bundle(
        self,
        *,
        bundle: ParsedScheduleBundle,
        project_key: str,
        schedule_id: str,
        version_key: str,
        import_id: str,
        schedule_table_id: str,
        source_type: str,
        source_format: str,
    ) -> None:
        base = {
            "project_key": project_key,
            "schedule_table_id": schedule_table_id,
            "schedule_id": schedule_id,
            "schedule_version_key": version_key,
            "import_id": import_id,
        }

        activities = []
        for act in bundle.activities:
            activities.append(
                {
                    **base,
                    "procore_project_id": bundle.procore_project_id,
                    "source_type": source_type,
                    "source_format": source_format,
                    "activity_id": act["activity_id"],
                    "source_activity_object_id": act.get("source_activity_object_id"),
                    "parent_activity_id": act.get("parent_activity_id"),
                    "wbs_id": act.get("wbs_id"),
                    "wbs_code": act.get("wbs_code"),
                    "wbs_path": act.get("wbs_path"),
                    "activity_name": act.get("activity_name"),
                    "activity_type": act.get("activity_type"),
                    "activity_status": act.get("activity_status"),
                    "planned_start": act.get("planned_start"),
                    "planned_finish": act.get("planned_finish"),
                    "start_date": act.get("start_date"),
                    "finish_date": act.get("finish_date"),
                    "early_start": act.get("early_start"),
                    "early_finish": act.get("early_finish"),
                    "late_start": act.get("late_start"),
                    "late_finish": act.get("late_finish"),
                    "actual_start": act.get("actual_start"),
                    "actual_finish": act.get("actual_finish"),
                    "remaining_start": act.get("remaining_start"),
                    "remaining_finish": act.get("remaining_finish"),
                    "remaining_early_start": act.get("remaining_early_start"),
                    "remaining_early_finish": act.get("remaining_early_finish"),
                    "remaining_late_start": act.get("remaining_late_start"),
                    "remaining_late_finish": act.get("remaining_late_finish"),
                    "derived_total_float_hours": act.get("derived_total_float_hours"),
                    "derived_total_float_days": act.get("derived_total_float_days"),
                    "derived_float_basis": act.get("derived_float_basis"),
                    "derived_is_critical_by_float_threshold": act.get(
                        "derived_is_critical_by_float_threshold"
                    ),
                    "explicit_total_float_hours": act.get("explicit_total_float_hours"),
                    "explicit_total_float_days": act.get("explicit_total_float_days"),
                    "explicit_free_float_hours": act.get("explicit_free_float_hours"),
                    "explicit_free_float_days": act.get("explicit_free_float_days"),
                    "float_source": act.get("float_source"),
                    "source_critical_flag": act.get("source_critical_flag"),
                    "source_driving_path_flag": act.get("source_driving_path_flag"),
                    "source_longest_path_flag": act.get("source_longest_path_flag"),
                    "float_path": act.get("float_path"),
                    "float_path_order": act.get("float_path_order"),
                    "critical_path_number": act.get("critical_path_number"),
                    "critical_path_source": act.get("critical_path_source"),
                    "target_start": act.get("target_start"),
                    "target_finish": act.get("target_finish"),
                    "target_duration": act.get("target_duration"),
                    "baseline_start": act.get("baseline_start"),
                    "baseline_finish": act.get("baseline_finish"),
                    "baseline_duration": act.get("baseline_duration"),
                    "duration_original": str(act.get("duration_original"))
                    if act.get("duration_original") is not None
                    else None,
                    "duration_unit": act.get("duration_unit"),
                    "percent_complete": str(act.get("percent_complete"))
                    if act.get("percent_complete") is not None
                    else None,
                    "physical_percent_complete": str(act.get("physical_percent_complete"))
                    if act.get("physical_percent_complete") is not None
                    else None,
                    "duration_percent_complete": str(act.get("duration_percent_complete"))
                    if act.get("duration_percent_complete") is not None
                    else None,
                    "duration_remaining": str(act.get("duration_remaining"))
                    if act.get("duration_remaining") is not None
                    else None,
                    "duration_actual": str(act.get("duration_actual"))
                    if act.get("duration_actual") is not None
                    else None,
                    "calendar_id": act.get("calendar_id"),
                    "constraint_type": act.get("constraint_type"),
                    "constraint_date": act.get("constraint_date"),
                    "total_float": str(act.get("total_float"))
                    if act.get("total_float") is not None
                    else None,
                    "free_float": str(act.get("free_float"))
                    if act.get("free_float") is not None
                    else None,
                    "is_critical": act.get("is_critical"),
                    "is_longest_path": act.get("is_longest_path"),
                    "is_milestone": act.get("is_milestone"),
                    "cost_code": act.get("cost_code"),
                    "cost_loaded_amount": str(act.get("cost_loaded_amount"))
                    if act.get("cost_loaded_amount") is not None
                    else None,
                    "cost_loaded_source_type": act.get("cost_loaded_source_type"),
                    "raw_json_redacted": json.dumps(
                        {k: act[k] for k in act if k != "source_row_hash"},
                        sort_keys=True,
                        default=str,
                    ),
                    "raw_source_fields_json": json.dumps(act, sort_keys=True, default=str),
                    "source_row_hash": act.get("source_row_hash"),
                }
            )
        self._activity_repo.bulk_upsert_activities(activities)

        rels = [{**base, **r, "raw_json_redacted": json.dumps(r, default=str)} for r in bundle.relationships]
        self._activity_repo.bulk_insert_table("procore_ep_schedule_relationships", rels)

        wbs = [{**base, **w} for w in bundle.wbs_nodes]
        self._activity_repo.bulk_insert_table("procore_ep_schedule_wbs_nodes", wbs)

        cals = [{**base, **c, "raw_json_redacted": json.dumps(c, default=str)} for c in bundle.calendars]
        self._activity_repo.bulk_insert_table("procore_ep_schedule_calendars", cals)

        codes = [{**base, **c} for c in bundle.code_assignments]
        self._activity_repo.bulk_insert_table("procore_ep_schedule_activity_code_assignments", codes)

        udfs = [{**base, **u} for u in bundle.udf_values]
        self._activity_repo.bulk_insert_table("procore_ep_schedule_udf_values", udfs)

    def _parse_bundle(
        self,
        data: bytes,
        *,
        source_type: str,
        source_format: str,
        column_roles: dict[str, str] | None,
    ) -> tuple[ParsedScheduleBundle, str, str]:
        if source_type == "xml":
            if source_format == "ms_project_xml":
                from .schedule_msp_xml_parser import PARSER_NAME as MSP_PARSER
                from .schedule_msp_xml_parser import PARSER_VERSION as MSP_VER
                from .schedule_msp_xml_parser import parse_msp_xml_bytes

                return parse_msp_xml_bytes(data), MSP_PARSER, MSP_VER
            return parse_pmxml_bytes(data), XML_PARSER, XML_VER
        if source_type == "csv":
            return parse_csv_bytes(data, column_roles=column_roles), CSV_PARSER, CSV_VER
        if source_type == "xer":
            from .schedule_xer_parser import PARSER_NAME as XER_PARSER
            from .schedule_xer_parser import PARSER_VERSION as XER_VER
            from .schedule_xer_parser import parse_xer_bytes

            return parse_xer_bytes(data), XER_PARSER, XER_VER
        raise ScheduleImportError(
            "unsupported_schedule_format",
            message="unsupported source type",
        )


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


class ScheduleReadService:
    """Read-only schedule intelligence queries."""

    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path
        self._activity_repo = ScheduleActivityRepository(db_path=db_path)
        self._mapping_repo = ScheduleMappingRepository(db_path=db_path)
        from hb_assistant.store.schedule_quality_repository import ScheduleQualityRepository

        self._quality_repo = ScheduleQualityRepository(db_path=db_path)

    def _ensure_schema(self) -> None:
        ensure_schedule_schema(self._db_path)

    def list_projects(self) -> dict[str, Any]:
        from .schedule_project_catalog import ScheduleProjectCatalog

        self._ensure_schema()
        catalog = ScheduleProjectCatalog(db_path=self._db_path)
        projects = catalog.list_browse_projects()
        for project in projects:
            project["display_label"] = project.get("display_name") or project["project_key"]
        return {
            "catalog_status": catalog.catalog_status(),
            "projects": projects,
        }

    def _version_summary_row(self, r: dict[str, Any]) -> dict[str, Any] | None:
        from .schedule_project_catalog import ScheduleProjectCatalog

        svk = r.get("schedule_version_key")
        if not svk:
            return None
        row_project = str(r.get("project_key") or str(svk).split("|")[0])
        q_count = len(self._mapping_repo.list_quality_findings(str(svk)))
        run = self._quality_repo.get_latest_run(str(svk)) or self._quality_repo.get_pending_run(
            str(svk)
        )
        scorecard = self._quality_repo.get_latest_scorecard(str(svk)) if run else None
        parts = str(svk).split("|")
        data_date = parts[2] if len(parts) >= 3 else None
        completion_posture = scorecard.get("completion_posture") if scorecard else None
        catalog = ScheduleProjectCatalog(db_path=self._db_path)
        dto = ScheduleVersionSummaryDTO(
            schedule_version_key=str(svk),
            project_key=row_project,
            source_type=str(r.get("source_type") or ""),
            source_format=str(r.get("source_format") or ""),
            display_label=str(r.get("source_filename_redacted") or svk),
            data_date=data_date,
            planned_start=None,
            scheduled_finish=None,
            activity_count=int(r.get("activity_count_live") or r.get("activity_count") or 0),
            relationship_count=int(
                r.get("relationship_count_live") or r.get("relationship_count") or 0
            ),
            cost_loaded_status=str(r.get("cost_loaded_status") or "not_cost_loaded"),
            imported_at=str(r.get("created_at") or ""),
            quality_finding_count=q_count,
            quality_status=str(run.get("status")) if run else "not_evaluated",
            quality_score=scorecard.get("quality_score") if scorecard else None,
            quality_grade=scorecard.get("quality_grade") if scorecard else None,
            quality_profile=str(run.get("assessment_profile")) if run else None,
            project_display_name=catalog.resolve_display_name(row_project),
            completion_posture=str(completion_posture) if completion_posture else None,
            evaluated_at=str(run.get("completed_at")) if run and run.get("completed_at") else None,
        )
        return dto.public()

    def list_versions(
        self,
        project_key: str | None = None,
        *,
        sort: str = "imported_at",
        order: str = "desc",
    ) -> list[dict[str, Any]]:
        self._ensure_schema()
        rows = self._activity_repo.list_versions(project_key)
        out: list[dict[str, Any]] = []
        for r in rows:
            summary = self._version_summary_row(r)
            if summary:
                out.append(summary)
        return sort_version_summaries(out, sort=sort, order=order)

    def get_summary(self, schedule_version_key: str) -> dict[str, Any] | None:
        self._ensure_schema()
        row = self._activity_repo.get_version_summary(schedule_version_key)
        if not row:
            return None
        return {
            "schedule_version_key": schedule_version_key,
            "project_key": row.get("project_key"),
            "source_type": row.get("source_type"),
            "source_format": row.get("source_format"),
            "display_label": row.get("source_filename_redacted"),
            "activity_count": self._activity_repo.count_activities(schedule_version_key),
            "relationship_count": self._activity_repo.count_relationships(schedule_version_key),
            "cost_loaded_status": row.get("cost_loaded_status"),
            "imported_at": row.get("created_at"),
            "evidence_package_id": row.get("evidence_package_id"),
        }

    def list_activities(
        self,
        schedule_version_key: str,
        *,
        limit: int | None = None,
        offset: int = 0,
        for_diff: bool = False,
    ) -> list[dict[str, Any]]:
        self._ensure_schema()
        if for_diff:
            total = self._activity_repo.count_activities(schedule_version_key)
            return self._activity_repo.list_activities(
                schedule_version_key, limit=max(total, 1), offset=0
            )
        cap = min(limit if limit is not None else 500, 10000)
        return self._activity_repo.list_activities(schedule_version_key, limit=cap, offset=offset)

    def count_activities(self, schedule_version_key: str) -> int:
        self._ensure_schema()
        return self._activity_repo.count_activities(schedule_version_key)

    def list_relationships(self, schedule_version_key: str) -> list[dict[str, Any]]:
        self._ensure_schema()
        return self._activity_repo.list_relationships(schedule_version_key)

    def list_quality(self, schedule_version_key: str) -> list[dict[str, Any]]:
        self._ensure_schema()
        return self._mapping_repo.list_quality_findings(schedule_version_key)