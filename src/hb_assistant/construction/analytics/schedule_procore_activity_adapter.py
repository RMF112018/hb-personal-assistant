"""Project Procore schedule activity JSON into V62 canonical tables."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from hb_assistant.procore.normalizers.hashing import hash_summary
from hb_assistant.store.schedule_activity_repository import ScheduleActivityRepository
from hb_assistant.store.schedule_import_repository import ScheduleImportRepository


def _sha256(payload: str) -> str:
    return hashlib.sha256(payload.encode()).hexdigest()


def _schedule_version_key(project_key: str, schedule_id: str, data_date: str | None) -> str:
    dd = data_date or "unknown"
    return f"{project_key}|{schedule_id}|{dd}"


def _redacted_fragment(raw: dict[str, Any]) -> str:
    allowed = (
        "activity_id",
        "activity_name",
        "start_date",
        "finish_date",
        "duration",
        "duration_unit",
        "percent_complete",
        "is_critical",
        "total_float",
        "schedule_id",
        "calendar_id",
        "constraint_type",
        "category_data",
        "resource_data",
    )
    out = {k: raw[k] for k in allowed if k in raw}
    notes_hash = hash_summary(raw.get("notes"))
    if notes_hash:
        out["notes_summary"] = notes_hash
    return json.dumps(out, sort_keys=True, default=str)


def project_procore_activity(
    raw: dict[str, Any],
    *,
    project_key: str,
    db_path: str,
    parent_schedule_id: str | None = None,
    raw_payload_id: str | None = None,
    sync_run_id: str | None = None,
) -> dict[str, Any]:
    """Upsert one Procore activity into procore_ep_schedule_activities."""
    activity_id = str(raw.get("activity_id") or "")
    schedule_id = str(raw.get("schedule_id") or parent_schedule_id or "")
    if not activity_id or not schedule_id:
        return {"status": "skipped", "reason": "missing_ids"}

    act_repo = ScheduleActivityRepository(db_path=db_path)
    imp_repo = ScheduleImportRepository(db_path=db_path)

    schedule_table_id = act_repo.find_schedule_table_id(
        project_key=project_key, schedule_id=schedule_id
    )
    created_version = schedule_table_id is None
    data_date = None
    if schedule_table_id is None:
        now = datetime.now(timezone.utc).isoformat()
        record_key = f"procore-{_sha256(f'{project_key}|{schedule_id}|procore_api')[:32]}"
        act_repo.upsert_schedule_version_row(
            {
                "record_key": record_key,
                "raw_payload_id": raw_payload_id,
                "endpoint_key": "schedules",
                "endpoint_family": "schedules",
                "project_key": project_key,
                "project_id": str(raw.get("project_id") or ""),
                "record_id": schedule_id,
                "schedule_id": schedule_id,
                "schedule_name": None,
                "data_date": None,
                "start_date": raw.get("start_date"),
                "source_quality": "procore_api",
                "is_current": 0,
                "created_utc": now,
                "updated_utc": now,
                "external_writeback_performed": 0,
                "raw_payload_emitted_to_read_model": 0,
                "raw_payload_emitted_to_evidence": 0,
            }
        )
        schedule_table_id = record_key

    if schedule_table_id:
        from hb_assistant.store.connection import get_connection

        conn = get_connection(db_path)
        cur = conn.execute(
            "SELECT data_date FROM procore_ep_schedules WHERE record_key=?",
            (schedule_table_id,),
        )
        row = cur.fetchone()
        conn.close()
        if row:
            data_date = row[0]

    version_key = _schedule_version_key(project_key, schedule_id, data_date)
    import_id = f"procore-{sync_run_id or uuid.uuid4().hex[:8]}"

    existing = imp_repo.get_import(import_id)
    if existing is None:
        imp_repo.insert_import(
            {
                "import_id": import_id,
                "project_key": project_key,
                "procore_project_id": str(raw.get("project_id") or ""),
                "source_type": "procore_api",
                "source_format": "procore_json",
                "source_filename_redacted": "procore_api",
                "source_file_sha256": _sha256(import_id),
                "source_payload_sha256": _sha256(json.dumps(raw, sort_keys=True, default=str)),
                "parser_name": "schedule_procore_activity_adapter",
                "parser_version": "1.0.0",
                "import_status": "committed",
                "validation_status": "ok",
                "activity_count": 1,
                "relationship_count": 0,
                "wbs_count": 0,
                "calendar_count": 0,
                "code_count": 0,
                "udf_count": 0,
                "cost_loaded_status": "not_cost_loaded",
                "schedule_version_key": version_key,
                "created_by_operator": "procore_sync",
            }
        )

    fragment = _redacted_fragment(raw)
    row = {
        "project_key": project_key,
        "procore_project_id": str(raw.get("project_id") or ""),
        "schedule_table_id": schedule_table_id,
        "schedule_id": schedule_id,
        "schedule_version_key": version_key,
        "import_id": import_id,
        "source_type": "procore_api",
        "source_format": "procore_json",
        "activity_id": activity_id,
        "source_activity_object_id": activity_id,
        "parent_activity_id": str(raw.get("parent_id") or "") or None,
        "activity_name": raw.get("activity_name"),
        "start_date": raw.get("start_date"),
        "finish_date": raw.get("finish_date"),
        "duration_original": str(raw.get("duration")) if raw.get("duration") is not None else None,
        "duration_unit": raw.get("duration_unit"),
        "percent_complete": str(raw.get("percent_complete"))
        if raw.get("percent_complete") is not None
        else None,
        "calendar_id": str(raw.get("calendar_id") or "") or None,
        "constraint_type": raw.get("constraint_type"),
        "constraint_date": raw.get("constraint_date"),
        "deadline_date": raw.get("deadline_date"),
        "deadline_variance": str(raw.get("deadline_variance"))
        if raw.get("deadline_variance") is not None
        else None,
        "total_float": str(raw.get("total_float")) if raw.get("total_float") is not None else None,
        "is_critical": 1 if raw.get("is_critical") else 0,
        "assigned_company_name_redacted": raw.get("assigned_company"),
        "crew_size": str(raw.get("crew_size")) if raw.get("crew_size") is not None else None,
        "notes_summary_hash": (hash_summary(raw.get("notes")) or {}).get("hash_prefix"),
        "raw_json_redacted": fragment,
        "raw_source_fields_json": fragment,
        "source_row_hash": _sha256(fragment),
    }
    act_repo.bulk_upsert_activities([row])
    if created_version:
        from hb_assistant.construction.analytics.schedule_quality_service import (
            ScheduleQualityService,
        )
        from hb_assistant.construction.analytics.schedule_quality_worker import poll_and_process

        svc = ScheduleQualityService(db_path=db_path)
        svc.queue_after_procore_update(
            project_key=project_key,
            schedule_version_key=version_key,
            schedule_table_id=schedule_table_id,
            import_id=import_id,
            sync_watermark=sync_run_id or import_id,
        )
        poll_and_process(db_path=db_path, limit=1)
    return {"status": "upserted", "activity_id": activity_id, "schedule_version_key": version_key}