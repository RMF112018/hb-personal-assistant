"""Schedule file import preview and commit into local SQLite."""

from __future__ import annotations

import hashlib
import json
import logging
import posixpath
import sqlite3
import uuid
import zipfile
from datetime import datetime, timezone
from difflib import SequenceMatcher
from io import BytesIO
from typing import Any

_logger = logging.getLogger(__name__)

from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator
from hb_assistant.store.schedule_activity_repository import ScheduleActivityRepository
from hb_assistant.store.schedule_identity_repository import (
    ScheduleIdentityRepository,
    parse_schedule_version_data_date,
)
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
    ParsedScheduleEntity,
    ParsedScheduleFile,
    ParsedSchedulePackage,
    ScheduleImportError,
    detect_source,
    safe_basename,
)
from .schedule_package_assembly import assemble_schedule_package
from .schedule_xml_parser import PARSER_NAME as XML_PARSER
from .schedule_xml_parser import PARSER_VERSION as XML_VER
from .schedule_xml_parser import parse_pmxml_bytes

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_ZIP_DECOMPRESSED_BYTES = 150 * 1024 * 1024
MAX_ZIP_FILES = 100

# In-memory preview cache keyed by import_id (process-local; tests use single client).
_PREVIEW_CACHE: dict[str, dict[str, Any]] = {}


def ensure_schedule_schema(db_path: str) -> None:
    from hb_assistant.store.connection import get_connection
    from hb_assistant.store.schedule_schema_verify import (
        verify_v65_schedule_float_schema,
        verify_v80_schedule_package_equivalence_schema,
    )

    migrator = SQLiteMigrator(db_path=db_path)
    conn = get_connection(db_path)
    try:
        missing = verify_v65_schedule_float_schema(conn)
        v80_missing = verify_v80_schedule_package_equivalence_schema(conn)
        version = migrator.current_version()
        needs_apply = version < LATEST_SCHEMA_VERSION or bool(missing) or bool(v80_missing)
    finally:
        conn.close()

    if needs_apply:
        # NF-F-001 (N-A3): an ordinary schedule request must NOT ambiently migrate the managed
        # database. Self-heal only a non-managed dev/rehearsal/workspace DB; for a managed target the
        # re-verification below raises the structured schedule_schema_not_ready error, directing the
        # operator to the authorized migration route instead of silently migrating on read.
        from hb_assistant.store.schema_readiness import self_heal_if_non_managed

        self_heal_if_non_managed(db_path)

    conn2 = get_connection(db_path)
    try:
        missing_after = verify_v65_schedule_float_schema(conn2)
        v80_missing_after = verify_v80_schedule_package_equivalence_schema(conn2)
        version_after = migrator.current_version()
    finally:
        conn2.close()

    fk_issues: list[str] = []
    conn3 = get_connection(db_path)
    try:
        from hb_assistant.store.schedule_schema_verify import verify_schedule_import_fk_targets

        fk_issues = verify_schedule_import_fk_targets(conn3)
    finally:
        conn3.close()

    if version_after < LATEST_SCHEMA_VERSION or missing_after or v80_missing_after or fk_issues:
        raise ScheduleImportError(
            "schedule_schema_not_ready",
            message="schedule schema is not ready",
            payload={
                "schema_version": version_after,
                "schema_expected": LATEST_SCHEMA_VERSION,
                "schedule_v65_missing_columns": missing_after,
                "schedule_v80_missing_columns": v80_missing_after,
                "schedule_import_fk_drift": fk_issues,
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
        self._identity_repo = ScheduleIdentityRepository(db_path=db_path)
        self._mapping_repo = ScheduleMappingRepository(db_path=db_path)

    def _ensure_schema(self) -> None:
        ensure_schedule_schema(self._db_path)

    @staticmethod
    def _sha256(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def _parse_package(
        self,
        *,
        filename: str,
        data: bytes,
        column_roles: dict[str, str] | None,
    ) -> ParsedSchedulePackage:
        lower = safe_basename(filename).lower()
        package_id = f"pkg-{uuid.uuid4().hex[:12]}"
        if lower.endswith(".zip"):
            files = self._read_zip_schedule_files(filename=filename, data=data)
            package_mode = "zip_package"
        else:
            files = [(safe_basename(filename), data)]
            package_mode = "single_file"

        parsed_files: list[ParsedScheduleFile] = []
        entities: list[ParsedScheduleEntity] = []
        warnings: list[dict[str, Any]] = []
        for idx, (member_name, member_data) in enumerate(files):
            source_file_id = (
                f"pf-{package_id.removeprefix('pkg-')}-{idx + 1}-"
                f"{hashlib.sha256(member_name.encode()).hexdigest()[:8]}"
            )
            try:
                source_type, source_format = detect_source(member_name, data=member_data)
            except ScheduleImportError:
                if package_mode == "single_file":
                    raise
                warnings.append(
                    {
                        "code": "unsupported_package_file_ignored",
                        "filename": safe_basename(member_name),
                        "message": "unsupported file ignored",
                    }
                )
                continue
            try:
                if source_type == "xml" and source_format == "primavera_pmxml":
                    from .schedule_xml_parser import parse_pmxml_package_bytes

                    file_entities = parse_pmxml_package_bytes(
                        member_data, source_file_id=source_file_id
                    )
                    parser_name, parser_version = XML_PARSER, XML_VER
                else:
                    bundle, parser_name, parser_version = self._parse_bundle(
                        member_data,
                        source_type=source_type,
                        source_format=source_format,
                        column_roles=column_roles,
                    )
                    file_entities = [
                        ParsedScheduleEntity(
                            role="current",
                            source_format=source_format,
                            source_file_id=source_file_id,
                            project_object_id=bundle.procore_project_id,
                            project_id=bundle.source_project_id or bundle.schedule_id,
                            project_name=bundle.source_project_name or bundle.schedule_name,
                            data_date=bundle.data_date,
                            planned_start=bundle.planned_start,
                            scheduled_finish=bundle.scheduled_finish,
                            activities=bundle.activities,
                            relationships=bundle.relationships,
                            wbs_nodes=bundle.wbs_nodes,
                            calendars=bundle.calendars,
                            code_assignments=bundle.code_assignments,
                            udf_values=bundle.udf_values,
                            source_options=bundle.schedule_options,
                            source_capabilities=bundle.source_capabilities,
                            parser_coverage=(bundle.schedule_options or {}).get(
                                "parser_coverage", {}
                            ),
                            warnings=[
                                {"code": f.get("code"), "message": f.get("message")}
                                for f in bundle.validation_findings
                            ],
                        )
                    ]
                detected_baselines = [e for e in file_entities if e.role == "baseline"]
                parsed_files.append(
                    ParsedScheduleFile(
                        source_file_id=source_file_id,
                        filename=safe_basename(member_name),
                        source_type=source_type,
                        source_format=source_format,
                        source_vendor="primavera" if source_format.startswith("primavera") else None,
                        file_role="current_candidate"
                        if any(e.role == "current" for e in file_entities)
                        else "baseline_candidate",
                        byte_size=len(member_data),
                        sha256=self._sha256(member_data),
                        parser_name=parser_name,
                        parser_version=parser_version,
                        parser_coverage=_merge_coverage(file_entities),
                        detected_project_count=sum(1 for e in file_entities if e.role == "current"),
                        detected_activity_count=sum(len(e.activities) for e in file_entities),
                        detected_relationship_count=sum(len(e.relationships) for e in file_entities),
                        detected_baseline_project_count=len(detected_baselines),
                        warnings=[w for e in file_entities for w in e.warnings],
                    )
                )
                entities.extend(file_entities)
            except ScheduleImportError as exc:
                if package_mode == "single_file":
                    raise
                parsed_files.append(
                    ParsedScheduleFile(
                        source_file_id=source_file_id,
                        filename=safe_basename(member_name),
                        source_type=source_type,
                        source_format=source_format,
                        byte_size=len(member_data),
                        sha256=self._sha256(member_data),
                        parse_status="failed",
                        warnings=[{"code": exc.code, "message": str(exc)}],
                    )
                )
                warnings.append({"code": exc.code, "filename": member_name, "message": str(exc)})

        if not parsed_files or not any(f.parse_status == "parsed" for f in parsed_files):
            raise ScheduleImportError(
                "schedule_package_no_valid_files",
                message="package contained no valid schedule-bearing files",
                payload={"warnings": warnings},
            )

        selected = self._select_current_entity(entities)
        baselines = [e for e in entities if e.role == "baseline"]
        package = ParsedSchedulePackage(
            package_id=package_id,
            package_mode=package_mode,
            files=parsed_files,
            schedule_entities=entities,
            selected_current_entity=selected,
            baseline_entities=baselines,
            warnings=warnings,
        )
        package = assemble_schedule_package(package)
        package.package_capabilities = self._compute_capabilities(package)
        package.manifest = self._manifest(package)
        return package

    def _read_zip_schedule_files(self, *, filename: str, data: bytes) -> list[tuple[str, bytes]]:
        del filename
        try:
            zf = zipfile.ZipFile(BytesIO(data))
        except zipfile.BadZipFile as exc:
            raise ScheduleImportError("schedule_zip_invalid", message="invalid zip package") from exc
        out: list[tuple[str, bytes]] = []
        total = 0
        infos = zf.infolist()
        if len(infos) > MAX_ZIP_FILES:
            raise ScheduleImportError("schedule_zip_too_many_files", message="zip package has too many files")
        for info in infos:
            name = info.filename
            normalized = posixpath.normpath(name)
            if info.is_dir():
                continue
            # Skip macOS archive metadata and hidden/system entries: __MACOSX/ sidecars,
            # AppleDouble ._* resource forks, and dotfiles. These are not schedule files and
            # otherwise get mis-detected by extension (e.g. ._FOO.xer parsed as XER) and surface
            # as noisy parse failures.
            member_base = posixpath.basename(normalized)
            if (
                normalized.startswith("__MACOSX/")
                or "/__MACOSX/" in normalized
                or member_base.startswith("._")
                or member_base.startswith(".")
            ):
                continue
            if normalized.startswith("../") or normalized == ".." or normalized.startswith("/"):
                raise ScheduleImportError("schedule_zip_unsafe_path", message="zip contains unsafe path")
            if lower_name := safe_basename(normalized).lower():
                if lower_name.endswith(".zip"):
                    raise ScheduleImportError(
                        "schedule_zip_nested_archive",
                        message="nested archives are not supported",
                    )
            total += int(info.file_size or 0)
            if total > MAX_ZIP_DECOMPRESSED_BYTES:
                raise ScheduleImportError(
                    "schedule_zip_too_large",
                    message="zip package decompressed size exceeds limit",
                )
            try:
                out.append((safe_basename(normalized), zf.read(info)))
            except RuntimeError as exc:
                raise ScheduleImportError("schedule_zip_read_failed", message="could not read zip member") from exc
        return out

    @staticmethod
    def _select_current_entity(entities: list[ParsedScheduleEntity]) -> ParsedScheduleEntity | None:
        current = [e for e in entities if e.role == "current" and e.activities]
        if not current:
            return None
        # XER is the stronger source for current float/source-critical/source-option evidence.
        xer = [e for e in current if e.source_format == "primavera_xer"]
        if xer:
            return max(xer, key=lambda e: (len(e.activities), e.data_date or ""))
        return max(current, key=lambda e: (len(e.activities), e.data_date or ""))

    @staticmethod
    def _selected_file(package: ParsedSchedulePackage) -> ParsedScheduleFile:
        selected = package.selected_current_entity
        for file in package.files:
            if selected and file.source_file_id == selected.source_file_id:
                return file
        return package.files[0]

    @staticmethod
    def _preview_package_payload(package: ParsedSchedulePackage) -> dict[str, Any]:
        return {
            "package_id": package.package_id,
            "package_mode": package.package_mode,
            "assembly_mode": package.assembly_mode,
            "primary_current_source_file_id": package.primary_current_entity.source_file_id
            if package.primary_current_entity
            else None,
            "companion_current_source_file_ids": [
                e.source_file_id for e in package.companion_current_entities
            ],
            "field_family_lineage": package.field_family_lineage,
            "equivalence_report": package.equivalence_report,
            "merge_warnings": package.merge_warnings,
            "files": [
                {
                    "package_file_id": f.source_file_id,
                    "filename": f.filename,
                    "source_format": f.source_format,
                    "parse_status": f.parse_status,
                    "detected_projects": f.detected_project_count,
                    "detected_baseline_projects": f.detected_baseline_project_count,
                    "detected_activities": f.detected_activity_count,
                    "detected_relationships": f.detected_relationship_count,
                    "warnings": f.warnings,
                }
                for f in package.files
            ],
            "current_project_candidates": [
                {
                    "source_file_id": e.source_file_id,
                    "project_object_id": e.project_object_id,
                    "project_id": e.project_id,
                    "project_name": e.project_name,
                    "activity_count": len(e.activities),
                    "source_format": e.source_format,
                }
                for e in package.schedule_entities
                if e.role == "current"
            ],
            "baseline_project_candidates": [
                {
                    "source_file_id": e.source_file_id,
                    "project_object_id": e.project_object_id,
                    "project_id": e.project_id,
                    "project_name": e.project_name,
                    "activity_count": len(e.activities),
                    "source_format": e.source_format,
                }
                for e in package.baseline_entities
            ],
            "capabilities": package.package_capabilities,
            "warnings": package.warnings,
        }

    @staticmethod
    def _manifest(package: ParsedSchedulePackage) -> dict[str, Any]:
        selected = package.selected_current_entity
        formats = sorted({f.source_format for f in package.files if f.source_format})
        lineage_summary = {
            row["field_family"]: {
                "source_format": row.get("source_format"),
                "source_file_id": row.get("source_file_id"),
                "merge_strategy": row.get("merge_strategy"),
                "records_contributed": row.get("records_contributed"),
            }
            for row in package.field_family_lineage
            if int(row.get("precedence_rank") or 0) == 1
        }
        return {
            "package_id": package.package_id,
            "package_mode": package.package_mode,
            "assembly_mode": package.assembly_mode,
            "detected_source_formats": formats,
            "selected_current_project_object_id": selected.project_object_id if selected else None,
            "selected_current_project_id": selected.project_id if selected else None,
            "selected_current_project_name": selected.project_name if selected else None,
            "primary_current_source_file_id": package.primary_current_entity.source_file_id
            if package.primary_current_entity
            else None,
            "companion_current_source_file_ids": [
                e.source_file_id for e in package.companion_current_entities
            ],
            "equivalence_report": package.equivalence_report,
            "field_family_lineage": lineage_summary,
            "field_family_source_precedence": {
                "current_float": "primavera_xer" if "primavera_xer" in formats else "selected_current",
                "source_critical": "primavera_xer" if "primavera_xer" in formats else "selected_current",
                "source_options": "primavera_xer" if "primavera_xer" in formats else "selected_current",
                "baseline_entities": "primavera_pmxml"
                if any(e.source_format == "primavera_pmxml" for e in package.baseline_entities)
                else "unavailable",
            },
        }

    @staticmethod
    def _compute_capabilities(package: ParsedSchedulePackage) -> dict[str, Any]:
        selected = package.selected_current_entity
        merged = package.merged_current_bundle
        formats = {f.source_format for f in package.files if f.parse_status == "parsed"}
        has_current = selected is not None and bool(selected.activities)
        has_rels = selected is not None and bool(selected.relationships)
        has_baseline_rows = any(e.activities for e in package.baseline_entities)
        has_xer = "primavera_xer" in formats
        has_xml = "primavera_pmxml" in formats
        caps: dict[str, str] = {
            "current_activities": "available" if has_current else "unavailable",
            "current_relationships": "available" if has_rels else "unavailable",
            "current_wbs": "available" if selected and selected.wbs_nodes else "unavailable",
            "current_calendars": "available" if selected and selected.calendars else "unavailable",
            "activity_codes": "available"
            if merged and merged.code_assignments
            else "unavailable",
            "udfs": "available" if merged and merged.udf_values else "unavailable",
            "explicit_total_float": "available" if has_xer else "partially_available" if has_xml else "unavailable",
            "explicit_free_float": "available" if has_xer else "partially_available" if has_xml else "unavailable",
            "source_driving_path": "available" if has_xer else "requires_companion_file",
            "source_critical_flags": "available" if has_xer else "partially_available" if has_xml else "unavailable",
            "cpm_recalculation": "deferred",
            "baseline_assignment": "available" if has_xer or has_baseline_rows else "unavailable",
            "baseline_project_rows": "available" if package.baseline_entities else "requires_companion_file" if has_xer else "unavailable",
            "baseline_activity_rows": "available" if has_baseline_rows else "requires_companion_file" if has_xer else "unavailable",
            "baseline_relationship_rows": "available"
            if any(e.relationships for e in package.baseline_entities)
            else "unavailable",
            "baseline_activity_crosswalk": "available" if has_baseline_rows and has_current else "unavailable",
            "baseline_drift": "available" if has_baseline_rows and has_current else "unavailable",
            "bei": "available" if has_baseline_rows and has_current else "unavailable",
            "missed_tasks": "available" if has_baseline_rows and has_current else "unavailable",
            "resource_assignments": "unavailable",
            "cost_loading": "partially_available" if selected and selected.activities else "unavailable",
            "version_comparison": "available",
            "cost_schedule_correlation": "deferred",
        }
        return caps

    def _persist_package_foundation(
        self,
        *,
        package: ParsedSchedulePackage,
        import_id: str,
        project_key: str,
        version_key: str,
        current_entity: ParsedScheduleEntity | None,
        committed_at: str,
        activity_rows: list[dict[str, Any]],
        conn: sqlite3.Connection,
    ) -> None:
        manifest = self._manifest(package)
        package_row = {
            "package_id": package.package_id,
            "project_key": project_key,
            "import_id": import_id,
            "package_mode": package.package_mode,
            "selected_current_schedule_version_key": version_key,
            "selected_current_project_object_id": current_entity.project_object_id if current_entity else None,
            "selected_current_project_id": current_entity.project_id if current_entity else None,
            "selected_current_project_name": current_entity.project_name if current_entity else None,
            "status": "committed",
            "committed_at": committed_at,
            "manifest_json": json.dumps(manifest, sort_keys=True, default=str),
        }
        file_rows = [
            {
                "package_file_id": f.source_file_id,
                "package_id": package.package_id,
                "import_id": import_id,
                "filename": f.filename,
                "source_format": f.source_format,
                "source_vendor": f.source_vendor,
                "file_role": f.file_role,
                "sha256": f.sha256,
                "byte_size": f.byte_size,
                "parse_status": f.parse_status,
                "parser_name": f.parser_name,
                "parser_version": f.parser_version,
                "detected_project_count": f.detected_project_count,
                "detected_baseline_project_count": f.detected_baseline_project_count,
                "detected_activity_count": f.detected_activity_count,
                "detected_relationship_count": f.detected_relationship_count,
                "coverage_json": json.dumps(f.parser_coverage, sort_keys=True, default=str),
                "warnings_json": json.dumps(f.warnings, sort_keys=True, default=str),
            }
            for f in package.files
        ]
        capability_rows = self._capability_rows(
            package=package,
            schedule_version_key=version_key,
        )
        self._import_repo.insert_schedule_package(
            package_row,
            files=file_rows,
            capabilities=capability_rows,
            conn=conn,
        )
        self._import_repo.insert_package_assembly_evidence(
            lineage_rows=[
                {
                    **row,
                    "import_id": import_id,
                    "project_key": project_key,
                    "schedule_version_key": version_key,
                }
                for row in package.field_family_lineage
            ],
            equivalence_rows=[
                {
                    **row,
                    "import_id": import_id,
                    "project_key": project_key,
                    "schedule_version_key": version_key,
                }
                for row in package.equivalence_facts
            ],
            conn=conn,
        )
        baseline_payload = self._baseline_payload(
            package=package,
            import_id=import_id,
            version_key=version_key,
            current_entity=current_entity,
            current_activity_rows=activity_rows,
        )
        self._import_repo.insert_baseline_evidence(**baseline_payload, conn=conn)

    @staticmethod
    def _capability_rows(
        *,
        package: ParsedSchedulePackage,
        schedule_version_key: str,
    ) -> list[dict[str, Any]]:
        rows = []
        for key, status in package.package_capabilities.items():
            rows.append(
                {
                    "capability_id": f"cap-{package.package_id}-{key}",
                    "package_id": package.package_id,
                    "schedule_version_key": schedule_version_key,
                    "source_format": None,
                    "capability_key": key,
                    "capability_status": status,
                    "source_file_id": None,
                    "basis": "package_manifest",
                    "unavailable_reason": None
                    if status in {"available", "partially_available"}
                    else status,
                    "recommended_action": _recommended_action(key, status),
                    "evidence_json": json.dumps(package.manifest, sort_keys=True, default=str),
                }
            )
        return rows

    def _baseline_payload(
        self,
        *,
        package: ParsedSchedulePackage,
        import_id: str,
        version_key: str,
        current_entity: ParsedScheduleEntity | None,
        current_activity_rows: list[dict[str, Any]],
    ) -> dict[str, list[dict[str, Any]]]:
        projects: list[dict[str, Any]] = []
        activities: list[dict[str, Any]] = []
        relationships: list[dict[str, Any]] = []
        wbs_rows: list[dict[str, Any]] = []
        code_rows: list[dict[str, Any]] = []
        udf_rows: list[dict[str, Any]] = []
        crosswalks: list[dict[str, Any]] = []
        health_facts: list[dict[str, Any]] = []

        current_by_id = {
            str(a.get("activity_id")): a
            for a in current_activity_rows
            if a.get("activity_id")
        }
        for index, baseline in enumerate(package.baseline_entities, start=1):
            baseline_project_key = (
                f"bl-{package.package_id}-{baseline.project_object_id or baseline.project_id or index}"
            )
            projects.append(
                {
                    "baseline_project_key": baseline_project_key,
                    "package_id": package.package_id,
                    "import_id": import_id,
                    "current_schedule_version_key": version_key,
                    "current_project_object_id": current_entity.project_object_id
                    if current_entity
                    else None,
                    "baseline_project_object_id": baseline.project_object_id,
                    "baseline_project_id": baseline.project_id,
                    "baseline_project_name": baseline.project_name,
                    "original_project_object_id": baseline.original_project_object_id,
                    "baseline_type_object_id": baseline.baseline_type_object_id,
                    "baseline_type_name": baseline.baseline_type_name,
                    "baseline_data_date": baseline.data_date,
                    "planned_start": baseline.planned_start,
                    "scheduled_finish": baseline.scheduled_finish,
                    "source_format": baseline.source_format,
                    "source_file_id": baseline.source_file_id,
                    "activity_count": len(baseline.activities),
                    "relationship_count": len(baseline.relationships),
                    "wbs_count": len(baseline.wbs_nodes),
                    "raw_metadata_json": json.dumps(
                        {
                            "project_object_id": baseline.project_object_id,
                            "project_id": baseline.project_id,
                            "project_name": baseline.project_name,
                            "parser_coverage": baseline.parser_coverage,
                        },
                        sort_keys=True,
                        default=str,
                    ),
                }
            )
            for act in baseline.activities:
                activities.append(
                    {
                        "baseline_project_key": baseline_project_key,
                        "package_id": package.package_id,
                        "import_id": import_id,
                        "current_schedule_version_key": version_key,
                        "baseline_project_object_id": baseline.project_object_id,
                        "activity_id": act.get("activity_id"),
                        "source_activity_object_id": act.get("source_activity_object_id"),
                        "activity_name": act.get("activity_name"),
                        "activity_type": act.get("activity_type"),
                        "activity_status": act.get("activity_status"),
                        "wbs_id": act.get("wbs_id"),
                        "wbs_code": act.get("wbs_code"),
                        "wbs_path": act.get("wbs_path"),
                        "calendar_id": act.get("calendar_id"),
                        "planned_start": act.get("planned_start"),
                        "planned_finish": act.get("planned_finish"),
                        "start_date": act.get("start_date"),
                        "finish_date": act.get("finish_date"),
                        "actual_start": act.get("actual_start"),
                        "actual_finish": act.get("actual_finish"),
                        "remaining_early_start": act.get("remaining_early_start"),
                        "remaining_early_finish": act.get("remaining_early_finish"),
                        "remaining_late_start": act.get("remaining_late_start"),
                        "remaining_late_finish": act.get("remaining_late_finish"),
                        "early_start": act.get("early_start"),
                        "early_finish": act.get("early_finish"),
                        "late_start": act.get("late_start"),
                        "late_finish": act.get("late_finish"),
                        "duration_original": _str_or_none(act.get("duration_original")),
                        "duration_remaining": _str_or_none(act.get("duration_remaining")),
                        "duration_actual": _str_or_none(act.get("duration_actual")),
                        "percent_complete": _str_or_none(act.get("percent_complete")),
                        "physical_percent_complete": _str_or_none(act.get("physical_percent_complete")),
                        "duration_percent_complete": _str_or_none(act.get("duration_percent_complete")),
                        "constraint_type": act.get("constraint_type"),
                        "constraint_date": act.get("constraint_date"),
                        "secondary_constraint_type": act.get("secondary_constraint_type"),
                        "secondary_constraint_date": act.get("secondary_constraint_date"),
                        "deadline_date": act.get("deadline_date"),
                        "is_critical": act.get("is_critical"),
                        "is_longest_path": act.get("is_longest_path"),
                        "total_float": _str_or_none(act.get("total_float")),
                        "free_float": _str_or_none(act.get("free_float")),
                        "cost_code": act.get("cost_code"),
                        "cost_loaded_amount": _str_or_none(act.get("cost_loaded_amount")),
                        "cost_loaded_source_type": act.get("cost_loaded_source_type"),
                        "raw_source_fields_json": json.dumps(act, sort_keys=True, default=str),
                        "source_row_hash": act.get("source_row_hash"),
                    }
                )
            for rel in baseline.relationships:
                relationships.append(
                    {
                        "baseline_project_key": baseline_project_key,
                        "package_id": package.package_id,
                        "import_id": import_id,
                        "current_schedule_version_key": version_key,
                        "baseline_project_object_id": baseline.project_object_id,
                        "predecessor_activity_id": rel.get("predecessor_activity_id"),
                        "successor_activity_id": rel.get("successor_activity_id"),
                        "relationship_type": rel.get("relationship_type"),
                        "lag_value": rel.get("lag_value"),
                        "lag_unit": rel.get("lag_unit"),
                        "source_relationship_object_id": rel.get("source_relationship_object_id"),
                        "raw_source_fields_json": json.dumps(rel, sort_keys=True, default=str),
                        "source_row_hash": rel.get("source_row_hash"),
                    }
                )
            wbs_rows.extend(
                [{"baseline_project_key": baseline_project_key, **w} for w in baseline.wbs_nodes]
            )
            code_rows.extend(
                [{"baseline_project_key": baseline_project_key, **c} for c in baseline.code_assignments]
            )
            udf_rows.extend(
                [{"baseline_project_key": baseline_project_key, **u} for u in baseline.udf_values]
            )
            cw = _build_crosswalk(
                version_key=version_key,
                baseline_project_key=baseline_project_key,
                current_by_id=current_by_id,
                baseline_activities=baseline.activities,
            )
            crosswalks.extend(cw)
            health_facts.extend(
                _baseline_health_facts(
                    version_key=version_key,
                    baseline_project_key=baseline_project_key,
                    current_count=len(current_by_id),
                    baseline=baseline,
                    crosswalks=cw,
                )
            )
        return {
            "baseline_projects": projects,
            "baseline_activities": activities,
            "baseline_relationships": relationships,
            "baseline_wbs": wbs_rows,
            "baseline_codes": code_rows,
            "baseline_udfs": udf_rows,
            "crosswalks": crosswalks,
            "health_facts": health_facts,
        }

    def _compute_default_version_diff_best_effort(
        self,
        *,
        project_key: str,
        version_key: str,
        package_id: str | None,
    ) -> int | None:
        try:
            current_match = self._identity_repo.get_match_for_version(version_key)
            if current_match is None:
                self._persist_diff_capability(
                    package_id=package_id,
                    version_key=version_key,
                    status="unavailable",
                    reason="no_identity_match",
                )
                return None
            if (
                str(current_match.get("match_status") or "") != "resolved"
                or int(current_match.get("requires_review") or 0) != 0
            ):
                self._persist_diff_capability(
                    package_id=package_id,
                    version_key=version_key,
                    status="unavailable",
                    reason="identity_requires_review",
                )
                return None
            prior_versions = self._identity_repo.list_prior_resolved_versions(
                schedule_identity_key=str(current_match["schedule_identity_key"]),
                current_schedule_version_key=version_key,
            )
            prior = self._select_default_prior_identity_version(version_key, prior_versions)
            if prior is None:
                self._persist_diff_capability(
                    package_id=package_id,
                    version_key=version_key,
                    status="unavailable",
                    reason="no_prior_identity_version",
                )
                return None
            from_version = str(prior["schedule_version_key"])
            read = ScheduleReadService(db_path=self._db_path)
            from_acts = read.list_activities(from_version, for_diff=True)
            to_acts = read.list_activities(version_key, for_diff=True)
            from_rels = read.list_relationships(from_version)
            to_rels = read.list_relationships(version_key)
            from_wbs = read.list_wbs_nodes(from_version)
            to_wbs = read.list_wbs_nodes(version_key)
            from_calendars = read.list_calendars(from_version)
            to_calendars = read.list_calendars(version_key)
            from_codes = read.list_activity_codes(from_version)
            to_codes = read.list_activity_codes(version_key)
            from_udfs = read.list_udf_values(from_version)
            to_udfs = read.list_udf_values(version_key)
            from .schedule_version_diff import compute_version_diff
            from .schedule_diff_intelligence import build_detail_facts, summarize_detail_facts

            diff = compute_version_diff(
                project_key=project_key,
                from_version=from_version,
                to_version=version_key,
                from_activities=from_acts,
                to_activities=to_acts,
                from_relationships=from_rels,
                to_relationships=to_rels,
            )
            details_cache: list[dict[str, Any]] = []

            def _detail_builder(diff_id: int) -> list[dict[str, Any]]:
                details_cache[:] = build_detail_facts(
                    diff_id=diff_id,
                    project_key=project_key,
                    from_version=from_version,
                    to_version=version_key,
                    schedule_identity_key=str(current_match["schedule_identity_key"]),
                    identity_safe=True,
                    comparison_type="identity_safe_default",
                    from_activities=from_acts,
                    to_activities=to_acts,
                    from_relationships=from_rels,
                    to_relationships=to_rels,
                    from_wbs=from_wbs,
                    to_wbs=to_wbs,
                    from_calendars=from_calendars,
                    to_calendars=to_calendars,
                    from_codes=from_codes,
                    to_codes=to_codes,
                    from_udfs=from_udfs,
                    to_udfs=to_udfs,
                )
                return details_cache

            def _fact_builder(diff_id: int) -> list[dict[str, Any]]:
                return _diff_fact_rows(diff_id, diff) + _diff_detail_summary_fact_rows(
                    diff_id, diff, summarize_detail_facts(details_cache)
                )

            diff_id, _details = self._mapping_repo.insert_version_diff_with_detail_builders(
                diff,
                detail_builder=_detail_builder,
                diff_fact_builder=_fact_builder,
            )
            return diff_id
        except Exception as exc:  # best-effort: valid imports must not roll back
            _logger.warning(
                "default schedule version diff failed project_key=%s version_key=%s",
                project_key,
                version_key,
                exc_info=True,
            )
            self._persist_diff_capability(
                package_id=package_id,
                version_key=version_key,
                status="unavailable",
                reason=type(exc).__name__,
            )
            return None

    @staticmethod
    def _select_default_prior_identity_version(
        current_version_key: str, prior_versions: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        current_date = parse_schedule_version_data_date(current_version_key)
        dated: list[tuple[datetime, dict[str, Any]]] = []
        for item in prior_versions:
            item_date = parse_schedule_version_data_date(
                str(item.get("schedule_version_key") or "")
            )
            if item_date is not None and (current_date is None or item_date < current_date):
                dated.append((item_date, item))
        if dated:
            dated.sort(key=lambda pair: pair[0], reverse=True)
            return dated[0][1]
        if not prior_versions:
            return None
        return sorted(
            prior_versions,
            key=lambda item: str(item.get("import_created_at") or item.get("created_at") or ""),
            reverse=True,
        )[0]

    def _persist_diff_capability(
        self,
        *,
        package_id: str | None,
        version_key: str,
        status: str,
        reason: str,
    ) -> None:
        if not package_id:
            return
        self._import_repo.insert_capabilities(
            [
                {
                    "capability_id": f"cap-{package_id}-default_version_diff",
                    "package_id": package_id,
                    "schedule_version_key": version_key,
                    "capability_key": "default_version_diff",
                    "capability_status": status,
                    "basis": "best_effort_commit_diff",
                    "unavailable_reason": reason,
                    "evidence_json": json.dumps({"reason": reason}, sort_keys=True),
                }
            ],
        )

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
        package = self._parse_package(
            filename=basename,
            data=data,
            column_roles=column_roles,
        )
        if package.selected_current_entity is None:
            raise ScheduleImportError(
                "schedule_current_project_required",
                message="schedule package did not contain a selectable current schedule",
                payload={"warnings": package.warnings},
            )
        bundle = package.merged_current_bundle or package.selected_current_entity.to_bundle()
        selected_file = self._selected_file(package)
        source_type = selected_file.source_type
        source_format = selected_file.source_format
        parser_name = selected_file.parser_name or ""
        parser_version = selected_file.parser_version or ""
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
        idempotent_reimport = bool(
            package.package_mode == "zip_package"
            and existing
            and str(existing.get("import_status") or "") == "committed"
            and str(existing.get("source_file_sha256") or "") == file_sha
        )
        if (
            existing
            and str(existing.get("import_status") or "") == "committed"
            and not confirm_supersede
            and not idempotent_reimport
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

        duplicate_exists = bool(
            existing and str(existing.get("import_status") or "") == "committed"
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
            "confirm_supersede": bool(confirm_supersede),
            "idempotent_reimport": idempotent_reimport,
            "schedule_version_key": version_key,
            "duplicate_exists": duplicate_exists,
            "package": package,
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
            source_project_id=bundle.source_project_id,
            source_project_name=bundle.source_project_name,
            source_project_short_name=bundle.source_project_short_name,
        )
        out = dto.public()
        out.update(self._preview_package_payload(package))
        return out

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

        preview_project_key = str(cached["project_key"])
        if preview_project_key != project_key:
            raise ScheduleImportError(
                "schedule_project_mismatch",
                message="project_key does not match preview",
                payload={
                    "project_key": project_key,
                    "preview_project_key": preview_project_key,
                },
            )

        bundle: ParsedScheduleBundle = cached["bundle"]
        package: ParsedSchedulePackage | None = cached.get("package")
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
        duplicate_exists = bool(
            existing and str(existing.get("import_status") or "") == "committed"
        )
        cached_supersede = bool(cached.get("confirm_supersede"))
        if duplicate_exists:
            idempotent_reimport = bool(cached.get("idempotent_reimport"))
            if not cached_supersede and not idempotent_reimport:
                if confirm_supersede:
                    raise ScheduleImportError(
                        "schedule_supersede_state_mismatch",
                        message="preview was not created with supersede confirmation",
                        payload={
                            "schedule_version_key": version_key,
                            "preview_confirm_supersede": False,
                            "commit_confirm_supersede": True,
                        },
                    )
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
            if not confirm_supersede and not idempotent_reimport:
                raise ScheduleImportError(
                    "schedule_supersede_confirmation_required",
                    message="supersede preview requires explicit commit confirmation",
                    payload={
                        "schedule_version_key": version_key,
                        "preview_confirm_supersede": True,
                        "commit_confirm_supersede": False,
                    },
                )
            superseded_import_id = str(existing.get("import_id"))
        elif confirm_supersede and cached_supersede:
            raise ScheduleImportError(
                "schedule_supersede_state_mismatch",
                message="supersede preview no longer matches committed state",
                payload={
                    "schedule_version_key": version_key,
                    "preview_confirm_supersede": True,
                    "commit_confirm_supersede": True,
                },
            )
        now = datetime.now(timezone.utc).isoformat()
        cost_status = assess_cost_loaded_status(bundle.activities, bundle.cost_loaded_hints)

        record_key = f"svk-{_sha256(f'{project_key}|{schedule_id}|{import_id}')[:32]}"
        import_row = self._build_import_row(
            import_id=import_id,
            project_key=project_key,
            bundle=bundle,
            cached=cached,
            version_key=version_key,
            cost_status=cost_status,
            evidence_package_id=None,
        )
        import_row["import_status"] = "committed"

        activity_rows = self._build_activity_rows(
            bundle=bundle,
            project_key=project_key,
            schedule_id=schedule_id,
            version_key=version_key,
            import_id=import_id,
            schedule_table_id=record_key,
            source_type=cached["source_type"],
            source_format=cached["source_format"],
        )
        self._log_commit_context(
            import_id=import_id,
            project_key=project_key,
            preview_project_key=preview_project_key,
            schedule_id=schedule_id,
            version_key=version_key,
            schedule_table_id=record_key,
            source_type=cached["source_type"],
            source_format=cached["source_format"],
            parser_name=cached["parser_name"],
            parser_version=cached["parser_version"],
            activity_rows=activity_rows,
        )
        identity_evidence = self._identity_repo.build_evidence(
            project_key=project_key,
            schedule_version_key=version_key,
            import_id=import_id,
            source_format=cached["source_format"],
            source_filename=cached["filename"],
            source_project_id=bundle.source_project_id,
            source_project_name=bundle.source_project_name,
            schedule_name=bundle.schedule_name,
            activities=bundle.activities,
            relationships=bundle.relationships,
            wbs_nodes=bundle.wbs_nodes,
        )
        identity_resolution = None

        from hb_assistant.store.connection import get_connection, transaction

        try:
            conn = get_connection(self._db_path)
            try:
                with transaction(conn):
                    if superseded_import_id:
                        self._activity_repo.delete_version_subgraph(
                            schedule_version_key=version_key,
                            import_id=superseded_import_id,
                            conn=conn,
                        )
                        self._import_repo.prepare_schedule_package_supersede(
                            schedule_version_key=version_key,
                            superseded_import_id=superseded_import_id,
                            conn=conn,
                        )
                        self._import_repo.update_import(
                            superseded_import_id,
                            {
                                "import_status": "superseded",
                                "validation_status": "superseded_by_operator",
                            },
                            conn=conn,
                        )
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
                        },
                        conn=conn,
                    )
                    self._import_repo.insert_import(import_row, conn=conn)
                    self._persist_bundle(
                        bundle=bundle,
                        project_key=project_key,
                        schedule_id=schedule_id,
                        version_key=version_key,
                        import_id=import_id,
                        schedule_table_id=record_key,
                        source_type=cached["source_type"],
                        source_format=cached["source_format"],
                        conn=conn,
                        activity_rows=activity_rows,
                    )
                    if package is not None:
                        self._persist_package_foundation(
                            package=package,
                            import_id=import_id,
                            project_key=project_key,
                            version_key=version_key,
                            current_entity=package.selected_current_entity,
                            committed_at=now,
                            activity_rows=activity_rows,
                            conn=conn,
                        )
                    identity_resolution = self._identity_repo.resolve_and_persist(
                        identity_evidence,
                        conn=conn,
                    )
            finally:
                conn.close()
        except (sqlite3.IntegrityError, sqlite3.OperationalError) as exc:
            _logger.warning(
                "schedule import commit persistence failed import_id=%s project_key=%s version_key=%s",
                import_id,
                project_key,
                version_key,
            )
            raise ScheduleImportError(
                "schedule_import_persistence_failed",
                message="Schedule import could not be written to the local database.",
                payload={
                    "source_format": cached["source_format"],
                    "project_key": project_key,
                    "schedule_version_key": version_key,
                    "import_id": import_id,
                },
            ) from exc

        if identity_resolution is not None:
            from hb_assistant.construction.analytics.schedule_trust_service import (
                ScheduleTrustService,
            )

            ScheduleTrustService(db_path=self._db_path).evaluate_import_guardrail(
                project_key=project_key,
                schedule_version_key=version_key,
                import_id=import_id,
                identity_match=identity_resolution.match,
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
        self._import_repo.update_import(import_id, {"evidence_package_id": evidence_id})

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

        default_diff_id = self._compute_default_version_diff_best_effort(
            project_key=project_key,
            version_key=version_key,
            package_id=package.package_id if package else None,
        )
        health_snapshot = ScheduleReadService(db_path=self._db_path).get_health_data(version_key) or {}

        from hb_assistant.construction.analytics.schedule_cpm_recompute_service import (
            ScheduleCpmRecomputeService,
        )

        cpm_result: dict[str, Any] = {
            "cpm_recompute_triggered": False,
            "cpm_recompute_status": "unavailable",
        }
        try:
            cpm_result = ScheduleCpmRecomputeService(db_path=self._db_path).recompute(
                version_key,
                import_id=import_id,
                package_id=package.package_id if package else None,
                trigger_source="import_commit",
            )
        except Exception:
            _logger.exception(
                "schedule import post-commit CPM recompute failed import_id=%s version_key=%s",
                import_id,
                version_key,
            )
            cpm_result = {
                "cpm_recompute_triggered": True,
                "cpm_recompute_status": "failed",
                "failure_reason": "cpm_recompute_exception",
            }

        _PREVIEW_CACHE.pop(import_id, None)
        from .schedule_project_catalog import ScheduleProjectCatalog

        catalog = ScheduleProjectCatalog(db_path=self._db_path)
        cpm_observability = cpm_result.get("cpm_observability") or {}
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
            "supersede_performed": superseded_import_id is not None,
            "package_id": package.package_id if package else None,
            "package_mode": package.package_mode if package else "single_file",
            "capability_summary": package.package_capabilities if package else {},
            "baseline_project_count": len(package.baseline_entities) if package else 0,
            "baseline_activity_count": sum(len(e.activities) for e in package.baseline_entities)
            if package
            else 0,
            "default_diff_id": default_diff_id,
            "schedule_identity_key": identity_resolution.schedule_identity_key
            if identity_resolution
            else None,
            "identity_match": identity_resolution.public_match() if identity_resolution else None,
            "comparison_basis": health_snapshot.get("comparison_basis"),
            "cpm_recompute_triggered": cpm_result.get("cpm_recompute_triggered"),
            "cpm_recompute_status": cpm_result.get("cpm_recompute_status"),
            "cpm_run_id": cpm_result.get("cpm_run_id"),
            "computed_activity_count": cpm_result.get("computed_activity_count"),
            "computed_critical_activity_count": cpm_result.get("computed_critical_activity_count"),
            "computed_near_critical_activity_count": cpm_result.get("computed_near_critical_activity_count"),
            "longest_path_available": cpm_result.get("longest_path_available"),
            "diagnostics_count": cpm_result.get("diagnostics_count"),
            "failure_code": cpm_observability.get("failure_code"),
            "failed_step": cpm_observability.get("failed_step"),
            "failure_message_redacted": cpm_observability.get("failure_message_redacted"),
            "cpm_observability": cpm_observability,
            "canonical_input_activity_count": cpm_result.get("canonical_input_activity_count"),
            "canonical_input_relationship_count": cpm_result.get("canonical_input_relationship_count"),
            "graph_node_count": cpm_result.get("graph_node_count"),
            "graph_edge_count": cpm_result.get("graph_edge_count"),
            "cpm_duration_ms": cpm_result.get("duration_ms"),
        }

    @staticmethod
    def _build_import_row(
        *,
        import_id: str,
        project_key: str,
        bundle: ParsedScheduleBundle,
        cached: dict[str, Any],
        version_key: str,
        cost_status: str,
        evidence_package_id: str | None,
    ) -> dict[str, Any]:
        return {
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
            "evidence_package_id": evidence_package_id,
            "created_by_operator": "operator",
            "source_project_id": bundle.source_project_id,
            "source_project_name": bundle.source_project_name,
            "source_project_short_name": bundle.source_project_short_name,
            "source_project_metadata_json": bundle.source_project_metadata_json,
            "compute_total_float_type": (bundle.schedule_options or {}).get(
                "compute_total_float_type"
            ),
            "critical_activity_path_type": (bundle.schedule_options or {}).get(
                "critical_activity_path_type"
            ),
            "critical_activity_float_threshold": str(
                (bundle.schedule_options or {}).get("critical_activity_float_threshold")
            )
            if (bundle.schedule_options or {}).get("critical_activity_float_threshold") is not None
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
                ScheduleImportService._schedule_options_json_with_analytics(bundle),
                sort_keys=True,
                default=str,
            ),
            "baseline_source": (bundle.schedule_options or {}).get("baseline_source"),
        }

    @staticmethod
    def _schedule_options_json_with_analytics(bundle: ParsedScheduleBundle) -> dict[str, Any]:
        from .schedule_critical_path_analytics import compute_source_critical_path_analytics

        schedule_opts = bundle.schedule_options or {}
        opts = dict(schedule_opts.get("schedule_options_json") or {})
        capabilities = schedule_opts.get("source_capabilities") or {}
        if str(capabilities.get("source_format") or "") == "primavera_xer" and bundle.activities:
            import_meta = {
                "critical_path_type": schedule_opts.get("critical_path_type"),
                "critical_float_threshold": schedule_opts.get("critical_float_threshold"),
            }
            analytics = compute_source_critical_path_analytics(
                import_meta,
                bundle.activities,
                schedule_options=schedule_opts,
            )
            opts["source_critical_path_analytics"] = {
                k: v
                for k, v in analytics.items()
                if k not in {"source_critical_path_evidence_json", "status"}
            }
        return opts

    def _build_activity_rows(
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
    ) -> list[dict[str, Any]]:
        base = {
            "project_key": project_key,
            "schedule_table_id": schedule_table_id,
            "schedule_id": schedule_id,
            "schedule_version_key": version_key,
            "import_id": import_id,
        }
        activities: list[dict[str, Any]] = []
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
        return activities

    @staticmethod
    def _log_commit_context(
        *,
        import_id: str,
        project_key: str,
        preview_project_key: str,
        schedule_id: str,
        version_key: str,
        schedule_table_id: str,
        source_type: str,
        source_format: str,
        parser_name: str,
        parser_version: str,
        activity_rows: list[dict[str, Any]],
    ) -> None:
        sample = [
            {
                "import_id": row.get("import_id"),
                "project_key": row.get("project_key"),
                "schedule_table_id": row.get("schedule_table_id"),
                "schedule_id": row.get("schedule_id"),
                "schedule_version_key": row.get("schedule_version_key"),
                "activity_id": row.get("activity_id"),
            }
            for row in activity_rows[:3]
        ]
        _logger.info(
            "schedule import commit context import_id=%s project_key=%s preview_project_key=%s "
            "schedule_id=%s schedule_version_key=%s schedule_table_id=%s source_type=%s "
            "source_format=%s parser_name=%s parser_version=%s activity_sample=%s",
            import_id,
            project_key,
            preview_project_key,
            schedule_id,
            version_key,
            schedule_table_id,
            source_type,
            source_format,
            parser_name,
            parser_version,
            sample,
        )

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
        conn: sqlite3.Connection | None = None,
        activity_rows: list[dict[str, Any]] | None = None,
    ) -> None:
        base = {
            "project_key": project_key,
            "schedule_table_id": schedule_table_id,
            "schedule_id": schedule_id,
            "schedule_version_key": version_key,
            "import_id": import_id,
        }

        activities = activity_rows or self._build_activity_rows(
            bundle=bundle,
            project_key=project_key,
            schedule_id=schedule_id,
            version_key=version_key,
            import_id=import_id,
            schedule_table_id=schedule_table_id,
            source_type=source_type,
            source_format=source_format,
        )
        self._activity_repo.bulk_upsert_activities(activities, conn=conn)

        rel_cols = {
            "predecessor_activity_id",
            "successor_activity_id",
            "relationship_type",
            "lag_value",
            "lag_unit",
            "source_relationship_object_id",
            "source_row_hash",
        }
        rels = [
            {
                **base,
                **{k: r.get(k) for k in rel_cols},
                "raw_json_redacted": json.dumps(r, default=str),
            }
            for r in bundle.relationships
        ]
        self._activity_repo.bulk_insert_table("procore_ep_schedule_relationships", rels, conn=conn)

        wbs = [{**base, **w} for w in bundle.wbs_nodes]
        self._activity_repo.bulk_insert_table("procore_ep_schedule_wbs_nodes", wbs, conn=conn)

        cals = [{**base, **c, "raw_json_redacted": json.dumps(c, default=str)} for c in bundle.calendars]
        self._activity_repo.bulk_insert_table("procore_ep_schedule_calendars", cals, conn=conn)

        codes = [{**base, **c} for c in bundle.code_assignments]
        self._activity_repo.bulk_insert_table(
            "procore_ep_schedule_activity_code_assignments", codes, conn=conn
        )

        udfs = [{**base, **u} for u in bundle.udf_values]
        self._activity_repo.bulk_insert_table("procore_ep_schedule_udf_values", udfs, conn=conn)

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


def _merge_coverage(entities: list[ParsedScheduleEntity]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "detected_project_count": sum(1 for e in entities if e.role == "current"),
        "detected_baseline_project_count": sum(1 for e in entities if e.role == "baseline"),
        "detected_activity_count": sum(len(e.activities) for e in entities),
        "detected_relationship_count": sum(len(e.relationships) for e in entities),
    }
    for entity in entities:
        for key, value in (entity.parser_coverage or {}).items():
            if key not in out:
                out[key] = value
    return out


def _recommended_action(key: str, status: str) -> str | None:
    if status in {"available", "partially_available", "not_applicable"}:
        return None
    if key.startswith("baseline"):
        return "Upload P6 XML export with baseline projects included."
    if key in {"explicit_total_float", "explicit_free_float", "source_driving_path"}:
        return "Upload companion XER to improve source float and critical-path analytics."
    if key == "cost_schedule_correlation":
        return "Deferred until cost/schedule correlation is implemented."
    return None


def _str_or_none(value: Any) -> str | None:
    return str(value) if value is not None else None


def _norm(value: Any) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def _build_crosswalk(
    *,
    version_key: str,
    baseline_project_key: str,
    current_by_id: dict[str, dict[str, Any]],
    baseline_activities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    current_by_norm_name = {
        (_norm(a.get("activity_name")), _norm(a.get("wbs_code") or a.get("wbs_path"))): a
        for a in current_by_id.values()
        if a.get("activity_name")
    }
    for baseline in baseline_activities:
        baseline_id = str(baseline.get("activity_id") or "")
        current = current_by_id.get(baseline_id)
        method = "exact_activity_id"
        confidence = 1.0
        review_required = False
        if current is None:
            key = (
                _norm(baseline.get("activity_name")),
                _norm(baseline.get("wbs_code") or baseline.get("wbs_path")),
            )
            current = current_by_norm_name.get(key)
            method = "exact_activity_name_and_wbs"
            confidence = 0.90
        if current is None and baseline.get("activity_name"):
            best: tuple[float, dict[str, Any] | None] = (0.0, None)
            for candidate in current_by_id.values():
                ratio = SequenceMatcher(
                    None,
                    _norm(baseline.get("activity_name")),
                    _norm(candidate.get("activity_name")),
                ).ratio()
                if ratio > best[0]:
                    best = (ratio, candidate)
            if best[1] is not None and best[0] >= 0.75:
                current = best[1]
                method = "fuzzy_name"
                confidence = round(best[0], 4)
                review_required = True
        if current is None:
            continue
        rows.append(
            {
                "crosswalk_id": _sha256(f"{version_key}|{baseline_project_key}|{baseline_id}"),
                "current_schedule_version_key": version_key,
                "baseline_project_key": baseline_project_key,
                "current_activity_id": current.get("activity_id"),
                "baseline_activity_id": baseline.get("activity_id"),
                "current_activity_object_id": current.get("source_activity_object_id"),
                "baseline_activity_object_id": baseline.get("source_activity_object_id"),
                "match_method": method,
                "match_confidence": str(confidence),
                "name_similarity": str(confidence) if "name" in method else None,
                "wbs_match": 1
                if _norm(current.get("wbs_code") or current.get("wbs_path"))
                == _norm(baseline.get("wbs_code") or baseline.get("wbs_path"))
                else 0,
                "duration_match": 1
                if _str_or_none(current.get("duration_original"))
                == _str_or_none(baseline.get("duration_original"))
                else 0,
                "date_proximity_score": None,
                "review_required": 1 if review_required else 0,
                "review_status": "review_required" if review_required else "accepted",
                "evidence_json": json.dumps(
                    {
                        "current_name": current.get("activity_name"),
                        "baseline_name": baseline.get("activity_name"),
                    },
                    sort_keys=True,
                    default=str,
                ),
            }
        )
    return rows


def _baseline_health_facts(
    *,
    version_key: str,
    baseline_project_key: str,
    current_count: int,
    baseline: ParsedScheduleEntity,
    crosswalks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    matched = len(crosswalks)
    facts = {
        "baseline_activity_count": (len(baseline.activities), "available"),
        "current_activity_count": (current_count, "available"),
        "matched_activity_count": (matched, "available" if matched else "requires_user_mapping"),
        "unmatched_current_activity_count": (max(current_count - matched, 0), "available"),
        "unmatched_baseline_activity_count": (
            max(len(baseline.activities) - matched, 0),
            "available",
        ),
        "baseline_relationship_count": (len(baseline.relationships), "available"),
        "baseline_drift_status": (
            "measurable_by_crosswalk" if matched else "requires_user_mapping",
            "available" if matched else "requires_user_mapping",
        ),
        "baseline_bei_status": (
            "requires_status_date_and_accepted_crosswalk" if matched else "requires_user_mapping",
            "requires_user_mapping" if not matched else "partially_available",
        ),
        "baseline_missed_tasks_status": (
            "requires_status_date_and_accepted_crosswalk" if matched else "requires_user_mapping",
            "requires_user_mapping" if not matched else "partially_available",
        ),
    }
    rows: list[dict[str, Any]] = []
    for key, (value, status) in facts.items():
        rows.append(
            {
                "fact_id": _sha256(f"{version_key}|{baseline_project_key}|{key}"),
                "current_schedule_version_key": version_key,
                "baseline_project_key": baseline_project_key,
                "metric_key": key,
                "metric_value": str(value),
                "metric_unit": "count" if str(key).endswith("_count") else None,
                "status": status,
                "basis": "baseline_crosswalk" if matched else "baseline_rows_only",
                "evidence_json": json.dumps(
                    {
                        "baseline_project_id": baseline.project_id,
                        "baseline_project_name": baseline.project_name,
                        "matched_activity_count": matched,
                    },
                    sort_keys=True,
                    default=str,
                ),
            }
        )
    return rows


def _diff_fact_rows(diff_id: int, diff: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    metric_keys = [
        "activity_added_count",
        "activity_removed_count",
        "activity_changed_count",
        "finish_drift_mean_days",
        "finish_drift_median_days",
        "finish_drift_max_days",
        "start_drift_mean_days",
        "relationship_added_count",
        "relationship_removed_count",
        "relationship_type_changed_count",
        "lag_changed_count",
        "logic_churn_rate",
        "wbs_churn_count",
        "calendar_churn_count",
        "code_churn_count",
        "constraint_changed_count",
    ]
    for key in metric_keys:
        rows.append(
            {
                "diff_fact_id": _sha256(f"{diff_id}|{key}"),
                "diff_id": diff_id,
                "project_key": diff["project_key"],
                "from_schedule_version_key": diff.get("from_schedule_version_key"),
                "to_schedule_version_key": diff["to_schedule_version_key"],
                "metric_key": key,
                "metric_value": _str_or_none(diff.get(key)),
                "metric_unit": "days" if key.endswith("_days") else "count" if key.endswith("_count") else None,
                "status": "available" if diff.get(key) is not None else "unavailable",
                "basis": "activity_id_aligned",
                "evidence_json": diff.get("summary_json"),
            }
        )
    return rows


def _diff_detail_summary_fact_rows(
    diff_id: int, diff: dict[str, Any], summary: dict[str, Any]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    metric_keys = (
        "total_change_count",
        "date_drift_count",
        "critical_severity_count",
        "major_severity_count",
        "moderate_severity_count",
        "minor_severity_count",
        "informational_count",
        "requires_attention_count",
    )
    for key in metric_keys:
        rows.append(
            {
                "diff_fact_id": _sha256(f"{diff_id}|detail|{key}"),
                "diff_id": diff_id,
                "project_key": diff["project_key"],
                "from_schedule_version_key": diff.get("from_schedule_version_key"),
                "to_schedule_version_key": diff["to_schedule_version_key"],
                "metric_key": key,
                "metric_value": _str_or_none(summary.get(key)),
                "metric_unit": "count",
                "status": "available",
                "basis": "detailed_diff_facts",
                "evidence_json": json.dumps(
                    {"domain_counts": summary.get("domain_counts", {})},
                    sort_keys=True,
                    default=str,
                ),
            }
        )
    return rows


def _safe_json_object(value: Any) -> dict[str, Any]:
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _public_schedule_identity(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {}
    return {
        "schedule_identity_key": row.get("schedule_identity_key"),
        "project_key": row.get("project_key"),
        "identity_status": row.get("identity_status"),
        "canonical_schedule_name": row.get("canonical_schedule_name"),
        "source_system": row.get("source_system"),
        "source_format": row.get("source_format"),
        "latest_schedule_version_key": row.get("latest_schedule_version_key"),
        "evidence_summary": _safe_json_object(row.get("evidence_json")),
    }


def _public_identity_match(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {}
    return {
        "schedule_identity_key": row.get("schedule_identity_key"),
        "schedule_version_key": row.get("schedule_version_key"),
        "import_id": row.get("import_id"),
        "match_type": row.get("match_type"),
        "match_status": row.get("match_status"),
        "match_rule": row.get("match_rule"),
        "confidence_score": row.get("confidence_score"),
        "requires_review": bool(int(row.get("requires_review") or 0)),
        "no_match_reason": row.get("no_match_reason"),
        "candidate_count": row.get("candidate_count"),
        "matched_prior_schedule_version_key": row.get("matched_prior_schedule_version_key"),
        "winning_candidate_schedule_version_key": row.get("winning_candidate_schedule_version_key"),
        "evidence_summary": _safe_json_object(row.get("evidence_json")),
    }


def _public_impact_summary(summary: dict[str, Any] | None) -> dict[str, Any] | None:
    if not summary:
        return None
    row = summary.get("summary")
    if not row:
        return None
    top_wbs = summary.get("top_wbs") or {}
    return {
        "impact_level": row.get("impact_level"),
        "impact_score": row.get("impact_score"),
        "change_count": row.get("change_count"),
        "requires_attention_count": row.get("requires_attention_count"),
        "critical_count": row.get("critical_count"),
        "major_count": row.get("major_count"),
        "critical_or_high_count": summary.get("critical_or_high_count"),
        "max_later_day_delta": row.get("max_later_day_delta"),
        "max_earlier_day_delta": row.get("max_earlier_day_delta"),
        "top_wbs_code": top_wbs.get("wbs_code"),
        "top_wbs_name": top_wbs.get("wbs_name"),
        "top_wbs_impact_level": top_wbs.get("impact_level"),
        "top_wbs_impact_score": top_wbs.get("impact_score"),
        "rollup_count": summary.get("rollup_count"),
    }


class ScheduleReadService:
    """Read-only schedule intelligence queries."""

    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path
        self._activity_repo = ScheduleActivityRepository(db_path=db_path)
        self._identity_repo = ScheduleIdentityRepository(db_path=db_path)
        self._import_repo = ScheduleImportRepository(db_path=db_path)
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
        public = dto.public()
        identity_match = self._identity_repo.get_match_for_version(str(svk))
        if identity_match:
            public.update(
                {
                    "schedule_identity_key": identity_match.get("schedule_identity_key"),
                    "identity_match_type": identity_match.get("match_type"),
                    "identity_match_status": identity_match.get("match_status"),
                    "identity_requires_review": bool(
                        int(identity_match.get("requires_review") or 0)
                    ),
                    "identity_confidence_score": identity_match.get("confidence_score"),
                }
            )
            capability = next(
                (
                    cap
                    for cap in self._import_repo.list_capabilities(str(svk))
                    if cap.get("capability_key") == "default_version_diff"
                ),
                None,
            )
            public["default_prior_available"] = bool(
                capability and capability.get("capability_status") != "unavailable"
            )
            public["default_prior_unavailable_reason"] = (
                capability.get("unavailable_reason") if capability else None
            )
            diff_fact = next(
                (fact for fact in self._import_repo.list_diff_facts(str(svk)) if fact.get("diff_id")),
                None,
            )
            if diff_fact:
                diff_id = int(diff_fact.get("diff_id") or 0)
                public["default_diff_id"] = diff_id
                detail_summary = self._mapping_repo.summarize_diff_detail_facts(diff_id)
                public["default_diff_detail_count"] = detail_summary.get("total_change_count", 0)
                public["default_diff_requires_attention_count"] = detail_summary.get(
                    "requires_attention_count", 0
                )
                impact_summary = self._mapping_repo.summarize_diff_impact_rollups(diff_id)
                if impact_summary.get("summary"):
                    public["default_diff_impact"] = _public_impact_summary(impact_summary)
        return public

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

    def list_wbs_nodes(self, schedule_version_key: str) -> list[dict[str, Any]]:
        self._ensure_schema()
        return self._activity_repo.list_wbs_nodes(schedule_version_key)

    def list_calendars(self, schedule_version_key: str) -> list[dict[str, Any]]:
        self._ensure_schema()
        return self._activity_repo.list_calendars(schedule_version_key)

    def list_activity_codes(self, schedule_version_key: str) -> list[dict[str, Any]]:
        self._ensure_schema()
        return self._activity_repo.list_activity_codes(schedule_version_key)

    def list_udf_values(self, schedule_version_key: str) -> list[dict[str, Any]]:
        self._ensure_schema()
        return self._activity_repo.list_udf_values(schedule_version_key)

    def get_diff_summary(self, project_key: str, diff_id: int) -> dict[str, Any] | None:
        self._ensure_schema()
        diff = self._mapping_repo.get_version_diff(diff_id)
        if not diff or diff.get("project_key") != project_key:
            return None
        counts = self._mapping_repo.summarize_diff_detail_facts(diff_id, project_key=project_key)
        first_detail = self._mapping_repo.list_diff_detail_facts(
            diff_id, project_key=project_key, limit=1, offset=0
        )
        metadata = {
            "diff_id": diff_id,
            "project_key": project_key,
            "from_schedule_version_key": diff.get("from_schedule_version_key"),
            "to_schedule_version_key": diff.get("to_schedule_version_key"),
            "schedule_identity_key": first_detail[0].get("schedule_identity_key")
            if first_detail
            else None,
            "identity_safe": bool(first_detail and int(first_detail[0].get("identity_safe") or 0)),
            "comparison_type": first_detail[0].get("comparison_type") if first_detail else "unknown",
        }
        return {"metadata": metadata, "summary_counts": counts}

    def list_diff_details(
        self,
        project_key: str,
        diff_id: int,
        *,
        change_domain: str | None = None,
        change_type: str | None = None,
        severity: str | None = None,
        requires_attention: bool | None = None,
        wbs_code: str | None = None,
        activity_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any] | None:
        self._ensure_schema()
        summary = self.get_diff_summary(project_key, diff_id)
        if summary is None:
            return None
        rows = self._mapping_repo.list_diff_detail_facts(
            diff_id,
            project_key=project_key,
            change_domain=change_domain,
            change_type=change_type,
            severity=severity,
            requires_attention=requires_attention,
            wbs_code=wbs_code,
            activity_id=activity_id,
            limit=limit,
            offset=offset,
        )
        total = self._mapping_repo.count_diff_detail_facts(diff_id, project_key=project_key)
        return {
            **summary,
            "detail_rows": rows,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total_count": total,
                "returned_count": len(rows),
            },
        }

    def list_diff_impact(
        self,
        project_key: str,
        diff_id: int,
        *,
        rollup_type: str | None = None,
        impact_level: str | None = None,
        requires_attention: bool | None = None,
        wbs_code: str | None = None,
        activity_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any] | None:
        self._ensure_schema()
        summary = self.get_diff_summary(project_key, diff_id)
        if summary is None:
            return None
        rows = self._mapping_repo.list_diff_impact_rollups(
            diff_id,
            project_key=project_key,
            rollup_type=rollup_type,
            impact_level=impact_level,
            requires_attention=requires_attention,
            wbs_code=wbs_code,
            activity_id=activity_id,
            limit=limit,
            offset=offset,
        )
        total = self._mapping_repo.count_diff_impact_rollups(
            diff_id,
            project_key=project_key,
            rollup_type=rollup_type,
            impact_level=impact_level,
            requires_attention=requires_attention,
            wbs_code=wbs_code,
            activity_id=activity_id,
        )
        impact_summary = self._mapping_repo.summarize_diff_impact_rollups(
            diff_id, project_key=project_key
        )
        metadata = dict(summary.get("metadata") or {})
        impact_summary_row = impact_summary.get("summary")
        if impact_summary_row:
            metadata.update(
                {
                    "schedule_identity_key": impact_summary_row.get("schedule_identity_key"),
                    "identity_safe": bool(int(impact_summary_row.get("identity_safe") or 0)),
                    "comparison_type": impact_summary_row.get("comparison_type"),
                }
            )
        return {
            "metadata": metadata,
            "summary": impact_summary_row,
            "top_wbs": impact_summary.get("top_wbs"),
            "availability": {
                "milestone_rollups": "explicit_milestone_detail_facts_only",
                "critical_rollups": "persisted_critical_or_float_detail_facts_only",
            },
            "rollups": rows,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total_count": total,
                "returned_count": len(rows),
            },
        }

    def list_quality(self, schedule_version_key: str) -> list[dict[str, Any]]:
        self._ensure_schema()
        return self._mapping_repo.list_quality_findings(schedule_version_key)

    def get_health_data(self, schedule_version_key: str) -> dict[str, Any] | None:
        self._ensure_schema()
        summary = self.get_summary(schedule_version_key)
        if summary is None:
            return None
        package = self._import_repo.get_package_for_version(schedule_version_key)
        capabilities = self._import_repo.list_capabilities(schedule_version_key)
        baselines = self._import_repo.list_baseline_projects(schedule_version_key)
        baseline_facts = self._import_repo.list_baseline_health_facts(schedule_version_key)
        diff_facts = self._import_repo.list_diff_facts(schedule_version_key)
        package_lineage = self._import_repo.list_package_field_lineage(schedule_version_key)
        package_equivalence = self._import_repo.list_package_equivalence_facts(schedule_version_key)
        identity_match = self._identity_repo.get_match_for_version(schedule_version_key)
        schedule_identity = (
            self._identity_repo.get_identity(str(identity_match["schedule_identity_key"]))
            if identity_match
            else None
        )
        comparison_basis = self._comparison_basis(
            schedule_version_key=schedule_version_key,
            identity_match=identity_match,
            capabilities=capabilities,
            diff_facts=diff_facts,
        )
        run = self._quality_repo.get_latest_run(schedule_version_key) or self._quality_repo.get_pending_run(
            schedule_version_key
        )
        scorecard = self._quality_repo.get_latest_scorecard(schedule_version_key) if run else None
        return {
            "schedule_version_key": schedule_version_key,
            "project_key": summary.get("project_key"),
            "current_schedule": summary,
            "import_package": package or {},
            "capabilities": capabilities,
            "quality_summary": {
                "status": run.get("status") if run else "not_evaluated",
                "evaluation_run_id": run.get("evaluation_run_id") if run else None,
                "scorecard": scorecard or {},
            },
            "default_prior_version": {},
            "default_version_diff": diff_facts[:],
            "available_version_diffs": diff_facts,
            "schedule_identity": _public_schedule_identity(schedule_identity),
            "identity_match": _public_identity_match(identity_match),
            "comparison_basis": comparison_basis,
            "package_lineage": package_lineage,
            "package_equivalence": package_equivalence,
            "baseline_projects": baselines,
            "baseline_health_facts": baseline_facts,
            "top_health_findings": self._mapping_repo.list_quality_findings(schedule_version_key)[:25],
            "deferred_domains": {"cost_schedule_correlation": "deferred"},
        }

    def _comparison_basis(
        self,
        *,
        schedule_version_key: str,
        identity_match: dict[str, Any] | None,
        capabilities: list[dict[str, Any]],
        diff_facts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        capability = next(
            (cap for cap in capabilities if cap.get("capability_key") == "default_version_diff"),
            None,
        )
        unavailable_reason = capability.get("unavailable_reason") if capability else None
        prior_version = None
        if diff_facts:
            prior_version = diff_facts[0].get("from_schedule_version_key")
        current_identity_key = identity_match.get("schedule_identity_key") if identity_match else None
        prior_identity_key = None
        selection_reason = "persisted_default_diff" if prior_version else None
        if identity_match and not prior_version:
            match_resolved = (
                str(identity_match.get("match_status") or "") == "resolved"
                and int(identity_match.get("requires_review") or 0) == 0
                and current_identity_key
            )
            if match_resolved:
                prior_candidates = self._identity_repo.list_prior_resolved_versions(
                    schedule_identity_key=str(current_identity_key),
                    current_schedule_version_key=schedule_version_key,
                )
                prior = ScheduleImportService._select_default_prior_identity_version(
                    schedule_version_key, prior_candidates
                )
                if prior:
                    prior_version = prior.get("schedule_version_key")
                    selection_reason = "identity_safe_prior_eligible"
        if prior_version:
            prior_match = self._identity_repo.get_match_for_version(str(prior_version))
            prior_identity_key = prior_match.get("schedule_identity_key") if prior_match else None
        identity_requires_review = bool(
            identity_match
            and (
                str(identity_match.get("match_status") or "") != "resolved"
                or int(identity_match.get("requires_review") or 0) != 0
            )
        )
        if identity_match is None:
            reason = unavailable_reason or "no_identity_match"
        elif identity_requires_review:
            reason = unavailable_reason or "identity_requires_review"
        elif not prior_version:
            reason = unavailable_reason or "no_prior_identity_version"
        else:
            reason = None
        identity_safe = bool(
            current_identity_key
            and prior_identity_key
            and current_identity_key == prior_identity_key
            and not identity_requires_review
        )
        return {
            "current_schedule_identity_key": current_identity_key,
            "default_prior_schedule_version_key": prior_version,
            "default_prior_schedule_identity_key": prior_identity_key,
            "default_prior_selection_reason": selection_reason if identity_safe else None,
            "default_prior_available": bool(identity_safe),
            "default_prior_unavailable_reason": reason,
            "identity_match_type": identity_match.get("match_type") if identity_match else None,
            "identity_confidence_score": identity_match.get("confidence_score")
            if identity_match
            else None,
            "identity_requires_review": identity_requires_review,
            "identity_safe": identity_safe,
            "detailed_diff_id": int(diff_facts[0].get("diff_id")) if diff_facts else None,
            "detail_summary_counts": self._mapping_repo.summarize_diff_detail_facts(
                int(diff_facts[0].get("diff_id") or 0)
            )
            if diff_facts
            else {},
            "impact_summary": _public_impact_summary(
                self._mapping_repo.summarize_diff_impact_rollups(
                    int(diff_facts[0].get("diff_id") or 0)
                )
            )
            if diff_facts
            else None,
        }
