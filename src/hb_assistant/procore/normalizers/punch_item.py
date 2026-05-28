"""Punch item canonical normalization (Phase 04A, Procore /punch_items v1.1).

The punch item LIST endpoint at /rest/v1.1/punch_items returns rows that carry
significant PII (names, emails, company names across ball_in_court, created_by,
closed_by, punch_item_manager, final_approver, assignees, and the per-assignment
login_information block) plus free-text bodies (description, schedule_risk_reason,
assignments[].comment). This normalizer reduces all PII to SHA-256 hash-only
summaries and all free-text bodies to ``*_summary`` hash structures. Structured
risk / financial / status fields are preserved verbatim for operator triage.
Variable-shape ``custom_fields`` keep numeric / boolean / lov_entry values
verbatim; string values are reduced to hash-only summaries.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional

from .rfi import NORMALIZATION_SCHEMA_VERSION

# Top-level whitelist of always-preserved structured fields. Fields outside this
# list are either PII-reduced, hashed, or intentionally omitted.
_PUNCH_ITEM_STRUCTURED_KEYS = (
    "id",
    "name",
    "reference",
    "position",
    "priority",
    "private",
    "status",
    "workflow_status",
    "due_date",
    "created_at",
    "updated_at",
    "closed_at",
    "deleted_at",
    "has_resolved_responses",
    "has_unresolved_responses",
    # Structured risk + financial fields the operator needs for triage.
    "cost_impact",
    "cost_impact_amount",
    "schedule_impact",
    "schedule_impact_days",
    "schedule_risk",
    "schedule_risk_confidence",
    "schedule_risk_probability",
    # Short-label nested objects (id + name; no PII, no free text).
    "location",
    "trade",
    "punch_item_type",
    "cost_code",
)


def _hash_summary(text: Any) -> Optional[Dict[str, Any]]:
    """Hash-only structural summary for a free-text field."""
    if text is None:
        return None
    if not isinstance(text, str):
        text = str(text)
    encoded = text.encode("utf-8", errors="ignore")
    return {
        "type": "string",
        "length": len(text),
        "hash_prefix": hashlib.sha256(encoded).hexdigest()[:12],
    }


def _hash_identifier(value: Any) -> Optional[str]:
    """Return only the SHA-256 hash prefix for a PII string (email, name)."""
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()[:12]


def _person_hash_summary(person: Any) -> Optional[Dict[str, Any]]:
    """Reduce a single person ref to a hash-only summary.

    The person dict carries ``id`` (numeric, opaque Procore identifier — not PII
    by itself), ``name`` (PII), and optionally ``login`` (email, PII) or
    ``company_name`` (semi-PII). The summary keeps the numeric id and hashes
    the name (preferring login when present so the same person hashes
    consistently across endpoints that carry the email).
    """
    if not isinstance(person, dict):
        return None
    hash_input = person.get("login") if isinstance(person.get("login"), str) else person.get("name")
    item: Dict[str, Any] = {"hash_prefix": _hash_identifier(hash_input)}
    person_id = person.get("id")
    if isinstance(person_id, int):
        item["id"] = person_id
    return item


def _people_summary(values: Any) -> Dict[str, Any]:
    """Reduce a people-array or single person ref to a {count, hashed_identifiers} summary."""
    items: List[Dict[str, Any]] = []
    if isinstance(values, list):
        for entry in values:
            summary = _person_hash_summary(entry)
            if summary is not None:
                items.append(summary)
    elif isinstance(values, dict):
        summary = _person_hash_summary(values)
        if summary is not None:
            items.append(summary)
    return {"count": len(items), "hashed_identifiers": items}


def _assignment_summary(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Reduce a single assignment to a PII-safe summary."""
    summary: Dict[str, Any] = {}
    for key in (
        "id",
        "approved",
        "status",
        "notified_at",
        "responded_at",
        "manager_accepted_at",
        "updated_at",
    ):
        value = raw.get(key)
        if value is not None:
            summary[key] = value
    # Hash the login_information ref + the legacy login_information_name field.
    login_info = raw.get("login_information") if isinstance(raw.get("login_information"), dict) else None
    if login_info is not None:
        summary["hashed_login"] = _person_hash_summary(login_info)
    elif raw.get("login_information_name") or raw.get("login_information_id"):
        summary["hashed_login"] = {
            "hash_prefix": _hash_identifier(raw.get("login_information_name")),
            "id": raw.get("login_information_id") if isinstance(raw.get("login_information_id"), int) else None,
        }
    # Comment is free-text -> hash-only.
    comment_summary = _hash_summary(raw.get("comment"))
    if comment_summary is not None:
        summary["comment_summary"] = comment_summary
    # vendor is a short-label structured object (id + name); preserve verbatim.
    vendor = raw.get("vendor")
    if isinstance(vendor, dict):
        summary["vendor"] = vendor
    # attachments: count only.
    attachments = raw.get("attachments")
    summary["attachments_count"] = len(attachments) if isinstance(attachments, list) else 0
    return summary


def _assignments_summary(values: Any) -> Dict[str, Any]:
    """Reduce the assignments[] array to a per-assignment summary list."""
    items: List[Dict[str, Any]] = []
    if isinstance(values, list):
        for entry in values:
            if isinstance(entry, dict):
                items.append(_assignment_summary(entry))
    return {"count": len(items), "items": items}


def _custom_fields_summary(raw_custom_fields: Any) -> Dict[str, Any]:
    """Reduce custom_fields per the operator policy.

    - data_type == "string" -> value reduced to a hash-only summary.
    - data_type in {"decimal", "boolean", "lov_entry", "lov_entries"} ->
      value preserved verbatim (these are not free-form text and the
      operator needs them for triage).
    - Unknown types -> hash the str() of the value (defensive).

    Returns a dict keyed on the same custom_field_<uuid> identifier as the
    source, so operators can locate specific fields across rows.
    """
    if not isinstance(raw_custom_fields, dict):
        return {"count": 0, "fields": {}}
    fields: Dict[str, Any] = {}
    for key, payload in raw_custom_fields.items():
        if not isinstance(payload, dict):
            continue
        data_type = payload.get("data_type")
        value = payload.get("value")
        entry: Dict[str, Any] = {"data_type": data_type}
        if data_type == "string":
            summary = _hash_summary(value)
            if summary is not None:
                entry["value_summary"] = summary
        elif data_type in {"decimal", "boolean", "lov_entry", "lov_entries"}:
            if value is not None:
                entry["value"] = value
        else:
            # Defensive: unknown data_type -> hash the str() of value.
            if value is not None:
                summary = _hash_summary(str(value))
                if summary is not None:
                    entry["value_summary"] = summary
        fields[key] = entry
    return {"count": len(fields), "fields": fields}


def _title_excerpt(value: Any, *, max_chars: int = 200) -> Optional[str]:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    return trimmed[:max_chars]


def normalize_punch_item(
    raw: Dict[str, Any],
    *,
    project_key: str,
    endpoint_id: str,
    correlation_id: str,
    fetched_at: str,
) -> Dict[str, Any]:
    """Return a canonical punch-item record with PII hashed and bodies summarized."""

    if not isinstance(raw, dict):
        raise TypeError("normalize_punch_item requires a dict payload")
    if "id" not in raw or raw["id"] in (None, ""):
        raise ValueError("normalize_punch_item requires raw['id']")

    canonical_fields: Dict[str, Any] = {}
    for key in _PUNCH_ITEM_STRUCTURED_KEYS:
        if key in raw and raw[key] is not None:
            canonical_fields[key] = raw[key]

    # Free-text bodies -> hash-only summaries.
    description_summary = _hash_summary(raw.get("description"))
    if description_summary is not None:
        canonical_fields["description_summary"] = description_summary
    schedule_risk_summary = _hash_summary(raw.get("schedule_risk_reason"))
    if schedule_risk_summary is not None:
        canonical_fields["schedule_risk_reason_summary"] = schedule_risk_summary

    # PII people refs -> hashed summaries.
    canonical_fields["ball_in_court_summary"] = _people_summary(raw.get("ball_in_court"))
    canonical_fields["created_by_summary"] = _people_summary(raw.get("created_by"))
    canonical_fields["closed_by_summary"] = _people_summary(raw.get("closed_by"))
    canonical_fields["punch_item_manager_summary"] = _people_summary(raw.get("punch_item_manager"))
    canonical_fields["final_approver_summary"] = _people_summary(raw.get("final_approver"))
    canonical_fields["assignees_summary"] = _people_summary(raw.get("assignees"))

    # Assignments -> per-assignment PII-safe summary list.
    canonical_fields["assignments_summary"] = _assignments_summary(raw.get("assignments"))

    # Custom fields -> structured/hashed per data_type.
    canonical_fields["custom_fields_summary"] = _custom_fields_summary(raw.get("custom_fields"))

    record: Dict[str, Any] = {
        "source_project_key": project_key,
        "endpoint_id": endpoint_id,
        "entity_stable_key": str(raw["id"]),
        "category": "punch_items",
        "review_required": True,  # PII bearing
        "routing_reason": "punch_item_default_review_required_pii_bearing",
        "canonical_fields": canonical_fields,
        "fetched_at": fetched_at,
        "correlation_id": correlation_id,
        "redaction_applied": True,
        "normalization_schema_version": NORMALIZATION_SCHEMA_VERSION,
    }
    excerpt = _title_excerpt(raw.get("name"))
    if excerpt is not None:
        record["redacted_excerpt"] = excerpt
    return record


__all__ = [
    "NORMALIZATION_SCHEMA_VERSION",
    "normalize_punch_item",
]
