"""Inspections + Inspection-Items canonical normalization (Phase 04A,
Procore /rest/v1.0/projects/{project_id}/checklist/lists and
/rest/v1.0/checklist/lists/{list_id}/items).

The inspections list endpoint carries significant PII — inspectors,
distribution_members, signature_requests (with signatory + captured_by),
created_by, closed_by, point_of_contact, responsible_contractor — plus
free-text fields (``description``, optional long ``name``), attachments
with URLs + filenames, custom_fields, and inspection counts. This
normalizer hashes every PII person ref via the shared
``person_hash_summary`` helper, reduces every free-text field via
``hash_summary``, and strips raw filenames + redacts attachment URLs to
path-only form.

The inspection-items endpoint carries per-item observations[],
comments[].body, histories[].body, item_response.payload.text_value, plus
responder PII. All of these reduce to ``*_summary`` blocks; the canonical
record never carries raw text. Default ``review_required=True`` because
every inspection-item row carries some free-text/PII surface.

Structured non-PII data (location, inspection_type, trade,
specification_section, drawing_ids, default_response_phrasing, response_set
metadata) is preserved verbatim so operator triage tooling can show counts,
types, and references without re-fetching.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from .hashing import hash_summary, person_hash_summary
from .rfi import NORMALIZATION_SCHEMA_VERSION

# ---------------------------------------------------------------------------
# Inspections (parent / checklist lists)
# ---------------------------------------------------------------------------

_INSPECTION_STRUCTURED_KEYS = (
    "id",
    "name",
    "number",
    "status",
    "list_template_id",
    "list_template_name",
    "inspection_date",
    "due_at",
    "closed_at",
    "created_at",
    "updated_at",
    "deleted",
    "private",
    "overdue",
    "conforming_item_count",
    "deficient_item_count",
    "not_applicable_item_count",
    "neutral_item_count",
    "inspected_item_count",
    "observations_count",
    "closed_observations_count",
    "item_count",
    "template_id",
    "managed_equipment_id",
)

# Status fragments that escalate review_required (case-insensitive substring).
_INSPECTION_STATUS_REVIEW_FRAGMENTS = (
    "open",
    "in progress",
    "in_progress",
    "incomplete",
    "rejected",
)

# inspection_type.name fragments that flag a safety-class inspection. When any
# of these match, review_required=True AND safety_route=True.
_INSPECTION_TYPE_SAFETY_FRAGMENTS = (
    "safety",
    "incident",
    "injury",
    "near miss",
    "near-miss",
    "near_miss",
    "osha",
    "ppe",
    "fall protection",
    "fall",
)


def _redact_url_to_path(value: Any) -> Optional[str]:
    """Strip scheme + host + query from a URL, returning the path only."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = urlparse(value)
    except ValueError:
        return None
    path = parsed.path or ""
    if not path:
        return None
    return path


def _attachment_summary(att: Any) -> Optional[Dict[str, Any]]:
    """Reduce a single attachment to ``{id, filename_summary, url_path, ...}``."""
    if not isinstance(att, dict):
        return None
    out: Dict[str, Any] = {}
    if isinstance(att.get("id"), int):
        out["id"] = att["id"]
    filename_summary = hash_summary(att.get("filename"))
    if filename_summary is not None:
        out["filename_summary"] = filename_summary
    url_path = _redact_url_to_path(att.get("url"))
    if url_path is not None:
        out["url_path"] = url_path
    thumb_path = _redact_url_to_path(att.get("thumbnail_url"))
    if thumb_path is not None:
        out["thumbnail_url_path"] = thumb_path
    for key in ("content_type", "viewable_document_id"):
        value = att.get(key)
        if value is not None:
            out[key] = value
    return out


def _attachments_summary(values: Any) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    if isinstance(values, list):
        for entry in values:
            summary = _attachment_summary(entry)
            if summary is not None:
                items.append(summary)
    return {"count": len(items), "items": items}


def _signature_request_summary(req: Any) -> Optional[Dict[str, Any]]:
    """Reduce a signature_request entry to PII-safe summary."""
    if not isinstance(req, dict):
        return None
    out: Dict[str, Any] = {}
    if isinstance(req.get("id"), int):
        out["id"] = req["id"]
    signatory = req.get("signatory")
    if signatory is not None:
        out["hashed_signatory"] = person_hash_summary(signatory)
    signature = req.get("signature")
    if isinstance(signature, dict):
        sig_out: Dict[str, Any] = {}
        if isinstance(signature.get("id"), int):
            sig_out["id"] = signature["id"]
        if signature.get("captured_at"):
            sig_out["captured_at"] = signature["captured_at"]
        captured_by = signature.get("captured_by")
        if captured_by is not None:
            sig_out["hashed_captured_by"] = person_hash_summary(captured_by)
        attachment = signature.get("attachment")
        if isinstance(attachment, dict):
            att_summary = _attachment_summary(attachment)
            if att_summary is not None:
                sig_out["attachment_summary"] = att_summary
        out["signature"] = sig_out
    return out


def _signature_requests_summary(values: Any) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    if isinstance(values, list):
        for entry in values:
            summary = _signature_request_summary(entry)
            if summary is not None:
                items.append(summary)
    return {"count": len(items), "items": items}


def _people_summary(values: Any) -> Dict[str, Any]:
    """Reduce a people-array or single person ref to ``{count, hashed_identifiers}``.

    Mirrors the punch_item._people_summary shape so cross-endpoint operator
    tooling can read both surfaces with the same expectations.
    """
    items: List[Dict[str, Any]] = []
    if isinstance(values, list):
        for entry in values:
            summary = person_hash_summary(entry)
            if summary is not None:
                items.append(summary)
    elif isinstance(values, dict):
        summary = person_hash_summary(values)
        if summary is not None:
            items.append(summary)
    return {"count": len(items), "hashed_identifiers": items}


def _custom_fields_summary(raw_custom_fields: Any) -> Dict[str, Any]:
    """Reduce custom_fields per the same policy as punch_item: numeric /
    boolean / lov_entry values preserved verbatim; string values hashed."""
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
            summary = hash_summary(value)
            if summary is not None:
                entry["value_summary"] = summary
        elif data_type in {"decimal", "boolean", "lov_entry", "lov_entries"}:
            if value is not None:
                entry["value"] = value
        else:
            if value is not None:
                summary = hash_summary(str(value))
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


def _inspection_review_decision(raw: Dict[str, Any]) -> tuple[bool, str, bool]:
    """Return ``(review_required, routing_reason, safety_route)`` per the
    inspection heuristic. Mirrors observation._safety_route_decision shape."""
    # 1. Safety inspection_type wins outright.
    inspection_type = raw.get("inspection_type")
    if isinstance(inspection_type, dict):
        type_name = inspection_type.get("name")
        if isinstance(type_name, str):
            lowered = type_name.lower()
            for fragment in _INSPECTION_TYPE_SAFETY_FRAGMENTS:
                if fragment in lowered:
                    return True, f"inspection_type_contains:{fragment}", True
    # 2. Overdue.
    if bool(raw.get("overdue")):
        return True, "overdue", False
    # 3. Non-Closed status fragment.
    status = raw.get("status")
    if isinstance(status, str):
        lowered = status.lower()
        for fragment in _INSPECTION_STATUS_REVIEW_FRAGMENTS:
            if fragment in lowered:
                return True, f"status_contains:{fragment}", False
    # 4. Default low risk.
    return False, "default_low_risk", False


def normalize_inspection(
    raw: Dict[str, Any],
    *,
    project_key: str,
    endpoint_id: str,
    correlation_id: str,
    fetched_at: str,
) -> Dict[str, Any]:
    """Return a canonical inspection record (PII hashed, free-text summarized).

    Mirrors the structural shape of normalize_punch_item. The optional rich
    nested objects (location, inspection_type, trade, specification_section,
    default_response_phrasing) are kept verbatim — they carry no PII and the
    operator needs them for triage. People-ref + signature + attachment
    fields are reduced; description is hashed.
    """
    if not isinstance(raw, dict):
        raise TypeError("normalize_inspection requires a dict payload")
    if "id" not in raw or raw["id"] in (None, ""):
        raise ValueError("normalize_inspection requires raw['id']")

    canonical_fields: Dict[str, Any] = {}
    for key in _INSPECTION_STRUCTURED_KEYS:
        if key in raw and raw[key] is not None:
            canonical_fields[key] = raw[key]

    # Free-text bodies -> hash-only summaries.
    description_summary = hash_summary(raw.get("description"))
    if description_summary is not None:
        canonical_fields["description_summary"] = description_summary

    # Structured rich nested objects: preserve verbatim (no PII inside).
    for key in (
        "location",
        "inspection_type",
        "trade",
        "specification_section",
        "default_response_phrasing",
    ):
        value = raw.get(key)
        if isinstance(value, dict):
            canonical_fields[key] = value

    # Numeric reference arrays: preserve verbatim.
    for key in ("drawing_ids", "current_drawing_revision_ids"):
        value = raw.get(key)
        if isinstance(value, list):
            canonical_fields[key] = value

    # PII people refs -> hashed summaries.
    canonical_fields["created_by_summary"] = _people_summary(raw.get("created_by"))
    canonical_fields["closed_by_summary"] = _people_summary(raw.get("closed_by"))
    canonical_fields["point_of_contact_summary"] = _people_summary(
        raw.get("point_of_contact")
    )
    canonical_fields["responsible_contractor_summary"] = _people_summary(
        raw.get("responsible_contractor")
    )
    canonical_fields["inspectors_summary"] = _people_summary(raw.get("inspectors"))
    canonical_fields["distribution_members_summary"] = _people_summary(
        raw.get("distribution_members")
    )

    # Signatures + attachments -> hashed summaries.
    canonical_fields["signature_requests_summary"] = _signature_requests_summary(
        raw.get("signature_requests")
    )
    canonical_fields["attachments_summary"] = _attachments_summary(
        raw.get("attachments")
    )

    # Custom fields -> structured/hashed per data_type.
    canonical_fields["custom_fields_summary"] = _custom_fields_summary(
        raw.get("custom_fields")
    )

    review_required, routing_reason, safety_route = _inspection_review_decision(raw)

    record: Dict[str, Any] = {
        "source_project_key": project_key,
        "endpoint_id": endpoint_id,
        "entity_stable_key": str(raw["id"]),
        "category": "inspections",
        "review_required": review_required,
        "routing_reason": routing_reason,
        "safety_route": safety_route,
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


# ---------------------------------------------------------------------------
# Inspection Items (child / per-list items)
# ---------------------------------------------------------------------------

_INSPECTION_ITEM_STRUCTURED_KEYS = (
    "id",
    "name",
    "status",
    "responded_with",
    "origin_id",
    "section_id",
    "position",
    "response_set_id",
    "template_item_id",
    "response_type_id",
    "updated_at",
)


def _observation_summary(obs: Any) -> Optional[Dict[str, Any]]:
    """Reduce an embedded observation ref under an inspection item to PII-safe
    summary. The full observation rows live as their own endpoint; here we
    keep only the minimal cross-reference shape so operators can join."""
    if not isinstance(obs, dict):
        return None
    out: Dict[str, Any] = {}
    for key in ("id", "number", "status", "created_at"):
        value = obs.get(key)
        if value is not None:
            out[key] = value
    obs_type = obs.get("type")
    if isinstance(obs_type, dict):
        out["type"] = obs_type
    title_summary = hash_summary(obs.get("title"))
    if title_summary is not None:
        out["title_summary"] = title_summary
    for person_key in ("assignee", "created_by"):
        person = obs.get(person_key)
        if person is not None:
            out[f"hashed_{person_key}"] = person_hash_summary(person)
    return out


def _observations_summary(values: Any) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    if isinstance(values, list):
        for entry in values:
            summary = _observation_summary(entry)
            if summary is not None:
                items.append(summary)
    return {"count": len(items), "items": items}


def _comment_summary(comment: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(comment, dict):
        return None
    out: Dict[str, Any] = {}
    if isinstance(comment.get("id"), int):
        out["id"] = comment["id"]
    if comment.get("created_at"):
        out["created_at"] = comment["created_at"]
    body_summary = hash_summary(comment.get("body"))
    if body_summary is not None:
        out["body_summary"] = body_summary
    created_by = comment.get("created_by")
    if created_by is not None:
        out["hashed_created_by"] = person_hash_summary(created_by)
    return out


def _comments_summary(values: Any) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    if isinstance(values, list):
        for entry in values:
            summary = _comment_summary(entry)
            if summary is not None:
                items.append(summary)
    return {"count": len(items), "items": items}


def _history_summary(hist: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(hist, dict):
        return None
    out: Dict[str, Any] = {}
    for key in ("id", "status", "responded_with", "created_at"):
        value = hist.get(key)
        if value is not None:
            out[key] = value
    body_summary = hash_summary(hist.get("body"))
    if body_summary is not None:
        out["body_summary"] = body_summary
    created_by = hist.get("created_by")
    if created_by is not None:
        out["hashed_created_by"] = person_hash_summary(created_by)
    return out


def _histories_summary(values: Any) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    if isinstance(values, list):
        for entry in values:
            summary = _history_summary(entry)
            if summary is not None:
                items.append(summary)
    return {"count": len(items), "items": items}


def _attachment_history_summary(att_hist: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(att_hist, dict):
        return None
    out: Dict[str, Any] = {}
    for key in ("id", "created_at"):
        value = att_hist.get(key)
        if value is not None:
            out[key] = value
    attachment = att_hist.get("attachment")
    if isinstance(attachment, dict):
        att_summary = _attachment_summary(attachment)
        if att_summary is not None:
            out["attachment_summary"] = att_summary
    created_by = att_hist.get("created_by")
    if created_by is not None:
        out["hashed_created_by"] = person_hash_summary(created_by)
    return out


def _attachment_histories_summary(values: Any) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    if isinstance(values, list):
        for entry in values:
            summary = _attachment_history_summary(entry)
            if summary is not None:
                items.append(summary)
    return {"count": len(items), "items": items}


def _item_response_summary(item_response: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(item_response, dict):
        return None
    out: Dict[str, Any] = {}
    for key in ("item_id", "status", "responded_at"):
        value = item_response.get(key)
        if value is not None:
            out[key] = value
    item_type = item_response.get("item_type")
    if isinstance(item_type, dict):
        out["item_type"] = item_type
    responder = item_response.get("responder")
    if responder is not None:
        out["hashed_responder"] = person_hash_summary(responder)
    payload = item_response.get("payload")
    if isinstance(payload, dict):
        payload_out: Dict[str, Any] = {}
        # Non-text payload fields stay structurally visible.
        for key in ("number_value", "date_value", "response_option"):
            value = payload.get(key)
            if value is not None:
                payload_out[key] = value
        text_summary = hash_summary(payload.get("text_value"))
        if text_summary is not None:
            payload_out["text_value_summary"] = text_summary
        out["payload"] = payload_out
    return out


def normalize_inspection_item(
    raw: Dict[str, Any],
    *,
    project_key: str,
    endpoint_id: str,
    correlation_id: str,
    fetched_at: str,
    parent_list_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Return a canonical inspection-item record.

    Default ``review_required=True``: every inspection-item row carries some
    free-text or PII surface (comments, histories, observations, responder).
    Operators consume these as cross-reference rows under a parent
    ``inspections`` row, joined via ``parent_procore_id`` = the list id.

    ``parent_list_id`` falls back to ``raw["list_id"]`` so the orchestrator's
    standard normalizer call signature works — the inspection-items dispatch
    sets ``list_id`` on every raw payload before normalization (mirrors the
    activities pattern's ``schedule_id`` setdefault).
    """
    if not isinstance(raw, dict):
        raise TypeError("normalize_inspection_item requires a dict payload")
    if "id" not in raw or raw["id"] in (None, ""):
        raise ValueError("normalize_inspection_item requires raw['id']")

    if parent_list_id is None:
        parent_list_id = raw.get("list_id")
    if parent_list_id is None or parent_list_id == "":
        raise ValueError(
            "normalize_inspection_item requires parent_list_id (kwarg or raw['list_id'])"
        )

    canonical_fields: Dict[str, Any] = {}
    for key in _INSPECTION_ITEM_STRUCTURED_KEYS:
        if key in raw and raw[key] is not None:
            canonical_fields[key] = raw[key]

    # parent_list_id preserved for joinability.
    canonical_fields["parent_list_id"] = str(parent_list_id)

    # Free-text details -> hashed summary.
    details_summary = hash_summary(raw.get("details"))
    if details_summary is not None:
        canonical_fields["details_summary"] = details_summary

    # Structured short-label refs preserved verbatim.
    for key in ("response", "type"):
        value = raw.get(key)
        if isinstance(value, dict):
            canonical_fields[key] = value
    response_set = raw.get("response_set")
    if isinstance(response_set, dict):
        # Drop nested responses[].name only if necessary; the Procore
        # example carries response_set.responses[] as short labels (no PII).
        canonical_fields["response_set"] = response_set

    # Nested arrays with PII/free-text -> hashed summaries.
    canonical_fields["observations_summary"] = _observations_summary(
        raw.get("observations")
    )
    canonical_fields["comments_summary"] = _comments_summary(raw.get("comments"))
    canonical_fields["histories_summary"] = _histories_summary(raw.get("histories"))
    canonical_fields["attachment_histories_summary"] = _attachment_histories_summary(
        raw.get("attachment_histories")
    )
    canonical_fields["attachments_summary"] = _attachments_summary(
        raw.get("attachments")
    )

    item_response_summary = _item_response_summary(raw.get("item_response"))
    if item_response_summary is not None:
        canonical_fields["item_response_summary"] = item_response_summary

    record: Dict[str, Any] = {
        "source_project_key": project_key,
        "endpoint_id": endpoint_id,
        "entity_stable_key": str(raw["id"]),
        "parent_inspection_stable_key": str(parent_list_id),
        "category": "inspection_items",
        "review_required": True,
        "routing_reason": "inspection_item_default_review_required",
        "safety_route": False,
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
    "normalize_inspection",
    "normalize_inspection_item",
]
