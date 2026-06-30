"""Provenance enrichment for schedule review workbench cue evidence."""

from __future__ import annotations

from typing import Any

from hb_assistant.store.schedule_activity_repository import ScheduleActivityRepository
from hb_assistant.store.schedule_cpm_import_observability_repository import (
    ScheduleCpmImportObservabilityRepository,
)

_FIELD_LINEAGE_SNIPPET_LIMIT = 8


def _unique_sorted(values: list[str]) -> list[str]:
    return sorted({value for value in values if value})


def _source_file_names(lineage: dict[str, Any] | None) -> list[str]:
    if not lineage:
        return []
    names: list[str] = []
    for row in lineage.get("merged_from_files") or []:
        if isinstance(row, dict):
            name = str(row.get("filename") or row.get("source_file_name") or "").strip()
            if name:
                names.append(name)
    return _unique_sorted(names)


def _source_formats(lineage: dict[str, Any] | None) -> list[str]:
    if not lineage:
        return []
    formats: list[str] = []
    for row in lineage.get("source_object_ids") or []:
        if isinstance(row, dict):
            fmt = str(row.get("source_format") or "").strip()
            if fmt:
                formats.append(fmt)
    for row in lineage.get("merged_from_files") or []:
        if isinstance(row, dict):
            fmt = str(row.get("source_format") or "").strip()
            if fmt:
                formats.append(fmt)
    return _unique_sorted(formats)


def _field_lineage_snippets(lineage: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not lineage:
        return []
    snippets: list[dict[str, Any]] = []
    for row in (lineage.get("field_lineage") or [])[:_FIELD_LINEAGE_SNIPPET_LIMIT]:
        if not isinstance(row, dict):
            continue
        snippets.append(
            {
                "field_name": row.get("field_name") or row.get("canonical_field"),
                "source_format": row.get("source_format"),
                "source_value": row.get("source_value"),
                "canonical_value": row.get("canonical_value") or row.get("merged_value"),
            }
        )
    return snippets


def _evidence_summary(
    *,
    lineage: dict[str, Any] | None,
    observability: dict[str, Any] | None,
    item_type: str,
) -> str:
    files = _source_file_names(lineage)
    formats = _source_formats(lineage)
    parts: list[str] = []
    if files:
        parts.append(f"Canonical activity merged from {', '.join(files)}.")
    elif formats:
        parts.append(f"Canonical activity sourced from {', '.join(formats)}.")
    if observability and observability.get("status"):
        parts.append(f"Latest committed CPM import status: {observability['status']}.")
    if not parts:
        return f"Schedule-control {item_type.replace('_', ' ')} cue from current hub intelligence."
    return " ".join(parts)


class ProjectScheduleReviewEvidenceService:
    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path
        self._activities = ScheduleActivityRepository(db_path=db_path)
        self._cpm_obs = ScheduleCpmImportObservabilityRepository(db_path=db_path)

    def enrich_cues(
        self,
        cues: list[dict[str, Any]],
        *,
        schedule_version_key: str,
    ) -> list[dict[str, Any]]:
        if not cues:
            return cues
        activity_ids = sorted(
            {
                str(cue.get("source_activity_id"))
                for cue in cues
                if cue.get("source_activity_id")
            }
        )
        lineage_by_activity = self._activities.get_activity_merge_lineage_batch(
            schedule_version_key=schedule_version_key,
            activity_ids=activity_ids,
        )
        observability = self._cpm_obs.get_latest_for_schedule_version(schedule_version_key)
        return [
            self._enrich_one(
                cue,
                lineage=lineage_by_activity.get(str(cue.get("source_activity_id") or "")),
                observability=observability,
            )
            for cue in cues
        ]

    def _enrich_one(
        self,
        cue: dict[str, Any],
        *,
        lineage: dict[str, Any] | None,
        observability: dict[str, Any] | None,
    ) -> dict[str, Any]:
        enriched = dict(cue)
        evidence = dict(enriched.get("evidence") or {})
        item_type = str(enriched.get("item_type") or "")
        source_files = _source_file_names(lineage)
        source_formats = _source_formats(lineage)
        field_lineage = _field_lineage_snippets(lineage)
        field_lineage_available = bool(lineage and (lineage.get("field_lineage") or lineage.get("merged_from_files")))
        technical_available = bool(lineage or observability)

        evidence["source_file_names"] = source_files
        evidence["source_formats"] = source_formats
        evidence["field_lineage_available"] = field_lineage_available
        evidence["technical_evidence_available"] = technical_available
        evidence["evidence_summary"] = _evidence_summary(
            lineage=lineage,
            observability=observability,
            item_type=item_type,
        )

        technical: dict[str, Any] = dict(evidence.get("technical_evidence") or {})
        if lineage:
            technical["merged_from_files"] = lineage.get("merged_from_files") or []
            technical["field_lineage"] = field_lineage
            technical["source_object_ids"] = lineage.get("source_object_ids") or []
            technical["source_activity_object_id"] = lineage.get("source_activity_object_id")
            if lineage.get("field_conflicts"):
                technical["field_conflicts"] = lineage.get("field_conflicts")
            if lineage.get("raw_merged"):
                technical["raw_merged"] = lineage.get("raw_merged")
        if observability:
            technical["import_id"] = observability.get("import_id")
            technical["package_id"] = observability.get("package_id")
            technical["cpm_run_id"] = observability.get("cpm_run_id")
            technical["cpm_status"] = observability.get("status")
            technical["cpm_observability"] = {
                key: observability.get(key)
                for key in (
                    "canonical_input_activity_count",
                    "canonical_input_relationship_count",
                    "graph_node_count",
                    "graph_edge_count",
                    "warning_count",
                    "error_count",
                    "failure_code",
                    "trigger_source",
                )
                if observability.get(key) is not None
            }
        if technical:
            evidence["technical_evidence"] = technical

        enriched["evidence"] = evidence
        return enriched
