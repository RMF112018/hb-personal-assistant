"""Package-level assembly for companion schedule files."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from .schedule_file_parser import (
    ParsedScheduleBundle,
    ParsedScheduleEntity,
    ParsedSchedulePackage,
    ScheduleImportError,
)


def assemble_schedule_package(package: ParsedSchedulePackage) -> ParsedSchedulePackage:
    """Attach a content-backed current bundle to a parsed package.

    XER remains authoritative for current schedule rows. Compatible XML current
    candidates can contribute companion-only activity codes and UDFs, while XML
    baseline entities remain in the existing baseline evidence path.
    """

    currents = [e for e in package.schedule_entities if e.role == "current" and e.activities]
    primary = package.selected_current_entity or _select_primary(currents)
    if primary is None:
        package.assembly_mode = "no_current"
        return package

    companions = [e for e in currents if e is not primary]
    facts = [_equivalence_fact(package.package_id, primary, candidate) for candidate in companions]
    incompatible = [f for f in facts if not f["is_equivalent"]]
    package.equivalence_facts = facts
    package.equivalence_report = {
        "status": "compatible" if not incompatible else "incompatible",
        "primary_source_file_id": primary.source_file_id,
        "primary_source_format": primary.source_format,
        "candidate_count": len(currents),
        "companion_count": len(companions),
        "equivalent_companion_count": len(companions) - len(incompatible),
        "incompatible_candidate_count": len(incompatible),
    }

    if incompatible:
        block_reason = _block_reason(incompatible)
        package.equivalence_report["incompatible_candidates"] = [
            {
                "source_file_id": f["candidate_source_file_id"],
                "source_format": f["candidate_source_format"],
                "equivalence_status": f["equivalence_status"],
                "block_reason": f["block_reason"],
                "activity_overlap_ratio": f["activity_overlap_ratio"],
                "relationship_overlap_ratio": f["relationship_overlap_ratio"],
                "data_date_match": f["data_date_match"],
                "primary_normalized_data_date": f["primary_normalized_data_date"],
                "candidate_normalized_data_date": f["candidate_normalized_data_date"],
            }
            for f in incompatible
        ]
        package.equivalence_report["block_reason"] = block_reason
        raise ScheduleImportError(
            "schedule_package_multiple_current_candidates",
            message=_block_message(block_reason),
            payload={
                "candidates": [_candidate_payload(e) for e in currents],
                "equivalence_report": package.equivalence_report,
                "equivalence_facts": package.equivalence_facts,
                "block_reason": block_reason,
            },
        )

    merged = _merge_current_bundle(primary, companions, package=package)
    package.selected_current_entity = primary
    package.primary_current_entity = primary
    package.companion_current_entities = companions
    package.merged_current_bundle = merged
    package.assembly_mode = "unified_companion_package" if companions else "single_source"
    package.field_family_lineage = _lineage_rows(package, primary, companions, merged)
    package.merge_warnings = _merge_warnings(primary, companions, merged)
    if package.merge_warnings:
        package.warnings.extend(package.merge_warnings)
    return package


def _select_primary(currents: list[ParsedScheduleEntity]) -> ParsedScheduleEntity | None:
    if not currents:
        return None
    xer = [e for e in currents if e.source_format == "primavera_xer"]
    if xer:
        return max(xer, key=lambda e: (len(e.activities), e.data_date or ""))
    return max(currents, key=lambda e: (len(e.activities), e.data_date or ""))


def _normal(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())


def _date(value: str | None) -> str | None:
    text = str(value or "").strip()
    return text[:10] if len(text) >= 10 else text or None


def _activity_ids(entity: ParsedScheduleEntity) -> set[str]:
    return {_normal(a.get("activity_id")) for a in entity.activities if _normal(a.get("activity_id"))}


def _relationship_keys(entity: ParsedScheduleEntity) -> set[tuple[str, str, str, str, str]]:
    keys: set[tuple[str, str, str, str, str]] = set()
    for rel in entity.relationships:
        pred = _normal(rel.get("predecessor_activity_id"))
        succ = _normal(rel.get("successor_activity_id"))
        if not pred or not succ:
            continue
        keys.add(
            (
                pred,
                succ,
                _relationship_type_key(rel.get("relationship_type")),
                _normal(rel.get("lag_value") or "0"),
                _normal(rel.get("lag_unit") or ""),
            )
        )
    return keys


def _ratio(left: set[Any], right: set[Any]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / max(min(len(left), len(right)), 1)


def _compatible_name(left: ParsedScheduleEntity, right: ParsedScheduleEntity) -> bool:
    left_name = _normal(left.project_name) or _normal(left.project_id)
    right_name = _normal(right.project_name) or _normal(right.project_id)
    if not left_name or not right_name:
        return True
    return left_name == right_name or left_name in right_name or right_name in left_name


def _block_reason(incompatible: list[dict[str, Any]]) -> str:
    reasons = {str(f.get("block_reason") or "") for f in incompatible}
    if "different_normalized_data_date" in reasons:
        return "different_normalized_data_date"
    if "low_activity_overlap" in reasons:
        return "low_activity_overlap"
    return "conflicting_current_snapshots"


def _block_message(reason: str) -> str:
    if reason == "different_normalized_data_date":
        return (
            "zip package contains multiple current schedule snapshots with different "
            "normalized data dates; remove extra current schedules and retry"
        )
    if reason == "low_activity_overlap":
        return (
            "zip package contains multiple current schedule snapshots with low activity-ID "
            "overlap; remove unrelated current schedules and retry"
        )
    return (
        "zip package contains multiple conflicting current schedule snapshots; "
        "remove extra current schedules and retry"
    )


def _equivalence_fact(
    package_id: str,
    primary: ParsedScheduleEntity,
    candidate: ParsedScheduleEntity,
) -> dict[str, Any]:
    primary_ids = _activity_ids(primary)
    candidate_ids = _activity_ids(candidate)
    primary_rels = _relationship_keys(primary)
    candidate_rels = _relationship_keys(candidate)
    activity_overlap = _ratio(primary_ids, candidate_ids)
    relationship_overlap = _ratio(primary_rels, candidate_rels)
    primary_data_date = _date(primary.data_date)
    candidate_data_date = _date(candidate.data_date)
    data_date_match = bool(primary_data_date and primary_data_date == candidate_data_date)
    planned_start_match = bool(
        _date(primary.planned_start) and _date(primary.planned_start) == _date(candidate.planned_start)
    )
    scheduled_finish_match = bool(
        _date(primary.scheduled_finish)
        and _date(primary.scheduled_finish) == _date(candidate.scheduled_finish)
    )
    project_identity_compatible = _compatible_name(primary, candidate)
    high_activity_overlap = activity_overlap >= 0.98
    relationship_support = bool(primary_rels and candidate_rels and relationship_overlap >= 0.95)
    dates_conflict = bool(primary_data_date and candidate_data_date and primary_data_date != candidate_data_date)
    same_snapshot_by_activity_date = high_activity_overlap and data_date_match
    same_snapshot_by_activity_logic = (
        high_activity_overlap
        and relationship_support
        and (project_identity_compatible or planned_start_match or scheduled_finish_match)
    )
    is_equivalent = bool(not dates_conflict and (same_snapshot_by_activity_date or same_snapshot_by_activity_logic))
    if not high_activity_overlap:
        block_reason = "low_activity_overlap"
    elif dates_conflict:
        block_reason = "different_normalized_data_date"
    else:
        block_reason = "conflicting_current_snapshots"
    status = "equivalent_companion" if is_equivalent else "non_equivalent_current"
    evidence = {
        "activity_overlap_count": len(primary_ids & candidate_ids),
        "primary_activity_count": len(primary_ids),
        "candidate_activity_count": len(candidate_ids),
        "relationship_overlap_count": len(primary_rels & candidate_rels),
        "primary_relationship_count": len(primary_rels),
        "candidate_relationship_count": len(candidate_rels),
        "basis": "activity_overlap_with_same_normalized_data_date_or_relationship_support",
        "block_reason": None if is_equivalent else block_reason,
    }
    fact_key = "|".join(
        [
            package_id,
            str(primary.source_file_id or "primary"),
            str(candidate.source_file_id or "candidate"),
            f"{activity_overlap:.6f}",
            f"{relationship_overlap:.6f}",
        ]
    )
    return {
        "equivalence_id": f"peq-{hashlib.sha256(fact_key.encode()).hexdigest()[:24]}",
        "package_id": package_id,
        "primary_source_file_id": primary.source_file_id,
        "candidate_source_file_id": candidate.source_file_id,
        "primary_source_format": primary.source_format,
        "candidate_source_format": candidate.source_format,
        "primary_project_id": primary.project_id,
        "candidate_project_id": candidate.project_id,
        "primary_project_name": primary.project_name,
        "candidate_project_name": candidate.project_name,
        "primary_data_date": primary.data_date,
        "candidate_data_date": candidate.data_date,
        "primary_normalized_data_date": primary_data_date,
        "candidate_normalized_data_date": candidate_data_date,
        "activity_overlap_ratio": f"{activity_overlap:.6f}",
        "relationship_overlap_ratio": f"{relationship_overlap:.6f}",
        "data_date_match": 1 if data_date_match else 0,
        "planned_start_match": 1 if planned_start_match else 0,
        "scheduled_finish_match": 1 if scheduled_finish_match else 0,
        "project_identity_compatible": 1 if project_identity_compatible else 0,
        "equivalence_status": status,
        "is_equivalent": 1 if is_equivalent else 0,
        "block_reason": None if is_equivalent else block_reason,
        "evidence_json": json.dumps(evidence, sort_keys=True),
    }


def _merge_current_bundle(
    primary: ParsedScheduleEntity,
    companions: list[ParsedScheduleEntity],
    *,
    package: ParsedSchedulePackage | None = None,
) -> ParsedScheduleBundle:
    bundle = primary.to_bundle()
    bundle.schedule_options = dict(bundle.schedule_options or {})
    bundle.schedule_options["assembly_mode"] = "unified_companion_package" if companions else "single_source"
    bundle.schedule_options["primary_source_format"] = primary.source_format
    bundle.schedule_options["companion_source_formats"] = sorted(
        {e.source_format for e in companions if e.source_format}
    )
    source_meta = _source_metadata(package)
    bundle.activities = _merge_activity_rows(primary, companions, source_meta=source_meta)
    bundle.relationships = _merge_relationship_rows(primary, companions, source_meta=source_meta)
    bundle.code_assignments = _merge_canonical_collection(
        primary,
        companions,
        attr="code_assignments",
        keys=("activity_id", "code_type", "code_value"),
        source_meta=source_meta,
    )
    bundle.udf_values = _merge_canonical_collection(
        primary,
        companions,
        attr="udf_values",
        keys=("activity_id", "udf_type_name", "udf_value"),
        source_meta=source_meta,
    )
    return bundle


def _source_metadata(package: ParsedSchedulePackage | None) -> dict[str, dict[str, Any]]:
    if package is None:
        return {}
    return {
        str(file.source_file_id): {
            "source_file_id": file.source_file_id,
            "filename": file.filename,
            "source_format": file.source_format,
            "parser_name": file.parser_name,
            "parser_version": file.parser_version,
        }
        for file in package.files
    }


def _entity_meta(
    entity: ParsedScheduleEntity,
    source_meta: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    meta = source_meta.get(str(entity.source_file_id), {})
    return {
        "source_file_id": entity.source_file_id,
        "filename": meta.get("filename"),
        "source_format": entity.source_format,
        "parser_name": meta.get("parser_name"),
        "parser_version": meta.get("parser_version"),
    }


def _has_value(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def _canonical_activity_id(row: dict[str, Any]) -> str:
    return _normal(row.get("activity_id"))


def _merge_activity_rows(
    primary: ParsedScheduleEntity,
    companions: list[ParsedScheduleEntity],
    *,
    source_meta: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    source_order = [primary, *companions]
    for entity in source_order:
        meta = _entity_meta(entity, source_meta)
        for row in entity.activities:
            key = _canonical_activity_id(row)
            if not key:
                continue
            if key not in merged:
                merged[key] = dict(row)
                order.append(key)
            _merge_activity_into(
                merged[key],
                row,
                source_meta=meta,
            )
    out = [merged[key] for key in order]
    for row in out:
        row["source_row_hash"] = _row_hash({k: row[k] for k in row if k != "source_row_hash"})
    return out


def _merge_activity_into(
    target: dict[str, Any],
    incoming: dict[str, Any],
    *,
    source_meta: dict[str, Any],
) -> None:
    lineage = _json_list(target.get("field_lineage_json"))
    conflicts = _json_list(target.get("field_conflicts_json"))
    object_ids = _json_list(target.get("source_object_ids_json"))
    merged_sources = _json_list(target.get("merged_from_files_json"))
    source_object_id = incoming.get("source_activity_object_id")
    if _has_value(source_object_id):
        entry = {**source_meta, "source_activity_object_id": source_object_id}
        if entry not in object_ids:
            object_ids.append(entry)
    file_entry = {k: source_meta.get(k) for k in ("source_file_id", "filename", "source_format", "parser_name", "parser_version")}
    if file_entry not in merged_sources:
        merged_sources.append(file_entry)
    skip = {
        "source_row_hash",
        "field_lineage_json",
        "field_conflicts_json",
        "source_object_ids_json",
        "merged_from_files_json",
        "raw_merged_json",
    }
    for field, value in incoming.items():
        if field in skip:
            continue
        existing = target.get(field)
        selected = existing
        strategy = "kept_existing"
        if not _has_value(existing) and _has_value(value):
            target[field] = value
            selected = value
            strategy = "filled_empty"
        elif _has_value(existing) and _has_value(value):
            if str(existing) == str(value):
                strategy = "confirmed_equal"
            else:
                strategy = "conflict_kept_existing"
                conflicts.append(
                    {
                        "field": field,
                        "selected_value": existing,
                        "conflicting_value": value,
                        "source": source_meta,
                    }
                )
        elif _has_value(existing):
            strategy = "ignored_empty"
        lineage.append(
            {
                "field": field,
                "source": source_meta,
                "source_object_id": source_object_id,
                "value": value,
                "selected_value": selected,
                "strategy": strategy,
            }
        )
    target["field_lineage_json"] = json.dumps(lineage, sort_keys=True, default=str)
    target["field_conflicts_json"] = json.dumps(conflicts, sort_keys=True, default=str)
    target["source_object_ids_json"] = json.dumps(object_ids, sort_keys=True, default=str)
    target["merged_from_files_json"] = json.dumps(merged_sources, sort_keys=True, default=str)
    target["raw_merged_json"] = json.dumps(
        {
            "merged_from_files": merged_sources,
            "source_object_ids": object_ids,
            "field_conflicts": conflicts,
        },
        sort_keys=True,
        default=str,
    )


def _json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return list(value)
    if not value:
        return []
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


def _relationship_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        _normal(row.get("predecessor_activity_id")),
        _normal(row.get("successor_activity_id")),
        _relationship_type_key(row.get("relationship_type")),
        _normal(row.get("lag_value") or "0"),
    )


def _relationship_type_key(value: Any) -> str:
    raw = str(value or "FS").strip().lower()
    return {
        "finish to start": "fs",
        "finish-to-start": "fs",
        "fs": "fs",
        "finish to finish": "ff",
        "finish-to-finish": "ff",
        "ff": "ff",
        "start to start": "ss",
        "start-to-start": "ss",
        "ss": "ss",
        "start to finish": "sf",
        "start-to-finish": "sf",
        "sf": "sf",
    }.get(raw, _normal(raw))


def _merge_relationship_rows(
    primary: ParsedScheduleEntity,
    companions: list[ParsedScheduleEntity],
    *,
    source_meta: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    by_key: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for entity in [primary, *companions]:
        meta = _entity_meta(entity, source_meta)
        for row in entity.relationships:
            key = _relationship_key(row)
            if not key[0] or not key[1]:
                continue
            if key not in by_key:
                merged = dict(row)
                merged["merged_from_files_json"] = json.dumps([meta], sort_keys=True, default=str)
                if _has_value(row.get("source_relationship_object_id")):
                    merged["source_relationship_object_ids_json"] = json.dumps(
                        [{**meta, "source_relationship_object_id": row.get("source_relationship_object_id")}],
                        sort_keys=True,
                        default=str,
                    )
                by_key[key] = merged
                out.append(merged)
                continue
            merged = by_key[key]
            files = _json_list(merged.get("merged_from_files_json"))
            if meta not in files:
                files.append(meta)
            merged["merged_from_files_json"] = json.dumps(files, sort_keys=True, default=str)
            if _has_value(row.get("source_relationship_object_id")):
                ids = _json_list(merged.get("source_relationship_object_ids_json"))
                entry = {**meta, "source_relationship_object_id": row.get("source_relationship_object_id")}
                if entry not in ids:
                    ids.append(entry)
                merged["source_relationship_object_ids_json"] = json.dumps(ids, sort_keys=True, default=str)
    for row in out:
        row["source_row_hash"] = _row_hash({k: row[k] for k in row if k != "source_row_hash"})
    return out


def _merge_canonical_collection(
    primary: ParsedScheduleEntity,
    companions: list[ParsedScheduleEntity],
    *,
    attr: str,
    keys: tuple[str, ...],
    source_meta: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    primary_rows = [dict(r) for r in getattr(primary, attr)]
    companion_rows = [dict(r) for e in companions for r in getattr(e, attr)]
    # Real equivalent XER/XML exports can encode the same code/UDF dimensions with
    # different display labels. If both sources cover the same current activities and
    # have the same row count, keep one canonical set and persist companion evidence
    # through package field lineage instead of doubling analytical rows.
    if (
        companions
        and primary_rows
        and sum(len(getattr(e, attr)) for e in companions) == len(primary_rows)
        and all(_activity_ids(e) == _activity_ids(primary) for e in companions)
    ):
        return primary_rows
    return _merge_rows(primary_rows, companion_rows, keys=keys)


def _merge_rows(
    primary_rows: list[dict[str, Any]],
    companion_rows: list[dict[str, Any]],
    *,
    keys: tuple[str, ...],
) -> list[dict[str, Any]]:
    out = [dict(r) for r in primary_rows]
    seen = {_row_key(r, keys) for r in out}
    for row in companion_rows:
        key = _row_key(row, keys)
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(row))
    return out


def _row_key(row: dict[str, Any], keys: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(_normal(row.get(k)) for k in keys)


def _row_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def _source_file(package: ParsedSchedulePackage, source_file_id: str | None) -> str | None:
    for file in package.files:
        if file.source_file_id == source_file_id:
            return file.filename
    return None


def _lineage_rows(
    package: ParsedSchedulePackage,
    primary: ParsedScheduleEntity,
    companions: list[ParsedScheduleEntity],
    merged: ParsedScheduleBundle,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(
        field_family: str,
        source_entity: ParsedScheduleEntity | None,
        *,
        precedence_rank: int,
        merge_strategy: str,
        records_contributed: int,
        records_skipped: int = 0,
        basis: str,
    ) -> None:
        file_id = source_entity.source_file_id if source_entity else None
        lineage_key = "|".join(
            [package.package_id, field_family, str(precedence_rank), str(file_id or "none")]
        )
        rows.append(
            {
                "lineage_id": f"pln-{hashlib.sha256(lineage_key.encode()).hexdigest()[:24]}",
                "package_id": package.package_id,
                "source_file_id": file_id,
                "source_filename_redacted": _source_file(package, file_id),
                "source_format": source_entity.source_format if source_entity else None,
                "field_family": field_family,
                "precedence_rank": precedence_rank,
                "merge_strategy": merge_strategy,
                "records_contributed": records_contributed,
                "records_skipped": records_skipped,
                "basis": basis,
                "evidence_json": json.dumps(
                    {
                        "source_file_id": file_id,
                        "field_family": field_family,
                        "merge_strategy": merge_strategy,
                        "records_contributed": records_contributed,
                        "records_skipped": records_skipped,
                    },
                    sort_keys=True,
                ),
            }
        )

    add("current_activities", primary, precedence_rank=1, merge_strategy="primary_authoritative", records_contributed=len(primary.activities), basis="selected_primary_current")
    add("current_relationships", primary, precedence_rank=1, merge_strategy="primary_authoritative", records_contributed=len(primary.relationships), basis="selected_primary_current")
    add("current_wbs", primary, precedence_rank=1, merge_strategy="primary_authoritative", records_contributed=len(primary.wbs_nodes), basis="selected_primary_current")
    add("current_calendars", primary, precedence_rank=1, merge_strategy="primary_authoritative", records_contributed=len(primary.calendars), basis="selected_primary_current")
    add("current_float", primary, precedence_rank=1, merge_strategy="primary_authoritative", records_contributed=len(primary.activities), basis="xer_authoritative_when_present")
    add("source_critical", primary, precedence_rank=1, merge_strategy="primary_authoritative", records_contributed=len(primary.activities), basis="xer_authoritative_when_present")
    add("source_options", primary, precedence_rank=1, merge_strategy="primary_authoritative", records_contributed=len(primary.source_options), basis="xer_authoritative_when_present")
    add("activity_codes", primary, precedence_rank=1, merge_strategy="merge_without_overwrite", records_contributed=len(primary.code_assignments), basis="primary_plus_companion_only")
    add("current_udfs", primary, precedence_rank=1, merge_strategy="merge_without_overwrite", records_contributed=len(primary.udf_values), basis="primary_plus_companion_only")

    for rank, companion in enumerate(companions, start=2):
        add(
            "activity_codes",
            companion,
            precedence_rank=rank,
            merge_strategy="companion_additive",
            records_contributed=max(len(merged.code_assignments) - len(primary.code_assignments), 0),
            basis="compatible_current_companion",
        )
        add(
            "current_udfs",
            companion,
            precedence_rank=rank,
            merge_strategy="companion_additive",
            records_contributed=max(len(merged.udf_values) - len(primary.udf_values), 0),
            basis="compatible_current_companion",
        )

    for rank, baseline in enumerate(package.baseline_entities, start=1):
        add("baseline_activities", baseline, precedence_rank=rank, merge_strategy="baseline_evidence", records_contributed=len(baseline.activities), basis="xml_baseline_entity")
        add("baseline_relationships", baseline, precedence_rank=rank, merge_strategy="baseline_evidence", records_contributed=len(baseline.relationships), basis="xml_baseline_entity")
        add("baseline_wbs", baseline, precedence_rank=rank, merge_strategy="baseline_evidence", records_contributed=len(baseline.wbs_nodes), basis="xml_baseline_entity")
        add("baseline_udfs", baseline, precedence_rank=rank, merge_strategy="baseline_evidence", records_contributed=len(baseline.udf_values), basis="xml_baseline_entity")

    return rows


def _merge_warnings(
    primary: ParsedScheduleEntity,
    companions: list[ParsedScheduleEntity],
    merged: ParsedScheduleBundle,
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    companion_udfs = sum(len(e.udf_values) for e in companions)
    if companion_udfs and len(merged.udf_values) == len(primary.udf_values):
        warnings.append(
            {
                "code": "companion_udfs_all_duplicates",
                "message": "compatible companion UDF rows were duplicates of primary current rows",
            }
        )
    return warnings


def _candidate_payload(entity: ParsedScheduleEntity) -> dict[str, Any]:
    return {
        "source_file_id": entity.source_file_id,
        "project_id": entity.project_id,
        "project_name": entity.project_name,
        "data_date": entity.data_date,
        "source_format": entity.source_format,
        "activity_count": len(entity.activities),
        "relationship_count": len(entity.relationships),
    }
