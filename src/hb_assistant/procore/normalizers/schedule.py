"""Schedule + activity canonical normalization (Phase 04A, Procore v2.0).

Two Procore v2.0 company-scoped endpoints:
- ``/rest/v2.0/companies/{company_id}/projects/{project_id}/schedules`` — list
  of schedules per project. Mostly structured fields (ids, timestamps,
  schedule_type, is_active).
- ``/rest/v2.0/companies/{company_id}/projects/{project_id}/schedules/{schedule_id}/activities``
  — list of activities per schedule. Mostly structured scheduling data with
  one free-text body field (``notes``) and nested structured arrays
  (``category_data``, ``resource_data``).

Both endpoints wrap their response in a ``"data"`` envelope handled by the
shared ``http_client.paginate`` body unwrap. The normalizers below operate
on the already-unwrapped per-item dict.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .hashing import hash_summary
from .rfi import NORMALIZATION_SCHEMA_VERSION

_SCHEDULE_STRUCTURED_KEYS = (
    "schedule_id",
    "project_id",
    "company_id",
    "schedule_name",
    "schedule_type",
    "is_active",
    "data_date",
    "start_date",
    "calendar_id",
    "parent_schedule_id",
    "created_at",
    "created_by",
    "updated_at",
    "updated_by",
    "deleted_at",
    "deleted_by",
)


_ACTIVITY_STRUCTURED_KEYS = (
    "activity_id",
    "activity_name",
    "start_date",
    "finish_date",
    "duration",
    "duration_unit",
    "duration_display_unit",
    "percent_complete",
    "parent_id",
    "ordered_parent_index",
    "constraint_type",
    "constraint_date",
    "assigned_company",
    "crew_size",
    "calendar_id",
    "deadline_date",
    "deadline_variance",
    "is_critical",
    "is_actual_start",
    "is_actual_finish",
    "total_float",
    "schedule_id",
    "project_id",
    "company_id",
    "created_at",
    "created_by",
    "updated_at",
    "updated_by",
)


def normalize_schedule(
    raw: Dict[str, Any],
    *,
    project_key: str,
    endpoint_id: str,
    correlation_id: str,
    fetched_at: str,
) -> Dict[str, Any]:
    """Return a canonical schedule record from a v2.0 schedules list entry."""

    if not isinstance(raw, dict):
        raise TypeError("normalize_schedule requires a dict payload")
    schedule_id = raw.get("schedule_id")
    if schedule_id is None or schedule_id == "":
        raise ValueError("normalize_schedule requires raw['schedule_id']")

    canonical_fields: Dict[str, Any] = {}
    for key in _SCHEDULE_STRUCTURED_KEYS:
        if key in raw and raw[key] is not None:
            canonical_fields[key] = raw[key]

    record: Dict[str, Any] = {
        "source_project_key": project_key,
        "endpoint_id": endpoint_id,
        "entity_stable_key": str(schedule_id),
        "category": "schedules",
        "review_required": False,
        "routing_reason": "schedules_structured_medium_sensitivity",
        "canonical_fields": canonical_fields,
        "fetched_at": fetched_at,
        "correlation_id": correlation_id,
        "redaction_applied": True,
        "normalization_schema_version": NORMALIZATION_SCHEMA_VERSION,
    }
    return record


def _preserved_array(value: Any) -> List[Dict[str, Any]]:
    """Pass-through filter for arrays of short-label structured dicts."""
    if not isinstance(value, list):
        return []
    return [entry for entry in value if isinstance(entry, dict)]


def normalize_activity(
    raw: Dict[str, Any],
    *,
    project_key: str,
    endpoint_id: str,
    correlation_id: str,
    fetched_at: str,
    parent_procore_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Return a canonical activity record.

    ``parent_procore_id`` carries the parent schedule_id when the orchestrator
    is iterating from a schedules list (the N+1 dispatch path). It is surfaced
    in canonical_fields as ``parent_schedule_id`` for backward-compat lineage
    even when the raw payload already includes a ``schedule_id`` field.
    """

    if not isinstance(raw, dict):
        raise TypeError("normalize_activity requires a dict payload")
    activity_id = raw.get("activity_id")
    if activity_id is None or activity_id == "":
        raise ValueError("normalize_activity requires raw['activity_id']")

    canonical_fields: Dict[str, Any] = {}
    for key in _ACTIVITY_STRUCTURED_KEYS:
        if key in raw and raw[key] is not None:
            canonical_fields[key] = raw[key]

    # Free-text notes -> hash-only summary.
    notes_summary = hash_summary(raw.get("notes"))
    if notes_summary is not None:
        canonical_fields["notes_summary"] = notes_summary

    # Nested short-label structured arrays preserved verbatim.
    canonical_fields["category_data"] = _preserved_array(raw.get("category_data"))
    canonical_fields["resource_data"] = _preserved_array(raw.get("resource_data"))

    # Parent schedule lineage (when supplied by the orchestrator).
    if parent_procore_id is not None and canonical_fields.get("parent_schedule_id") is None:
        canonical_fields["parent_schedule_id"] = parent_procore_id

    record: Dict[str, Any] = {
        "source_project_key": project_key,
        "endpoint_id": endpoint_id,
        "entity_stable_key": str(activity_id),
        "category": "schedule_activities",
        "review_required": False,
        "routing_reason": "schedule_activity_structured_medium_sensitivity",
        "canonical_fields": canonical_fields,
        "fetched_at": fetched_at,
        "correlation_id": correlation_id,
        "redaction_applied": True,
        "normalization_schema_version": NORMALIZATION_SCHEMA_VERSION,
    }
    return record


__all__ = [
    "NORMALIZATION_SCHEMA_VERSION",
    "normalize_schedule",
    "normalize_activity",
]
