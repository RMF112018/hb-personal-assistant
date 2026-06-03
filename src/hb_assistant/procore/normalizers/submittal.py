"""Submittal + submittal-response + submittal-package canonical normalization
(Phase 04 Prompt 05).

Pure functions over a raw Procore submittal payload. Never persists, never
reads network, never echoes bodies. Responses and packages are stored as
separate canonical rows (categories ``submittal_responses`` /
``submittal_packages``) with ``review_required=True`` per the prompt stop
condition ("response comments stored raw" is structurally impossible — the
canonical record never carries the comment text, only a SHA-256 prefix).

Mirrors :mod:`hb_assistant.procore.normalizers.rfi`. The hash-only helper is
duplicated here rather than extracted into a shared module so this prompt
remains surgically scoped to submittals.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .hashing import hash_identifier, hash_summary
from .rfi import NORMALIZATION_SCHEMA_VERSION

_SUBMITTAL_CANONICAL_FIELD_KEYS = (
    "id",
    "number",
    "title",
    "status",
    "type",
    "specification_section",
    "assignee_id",
    "ball_in_court_id",
    "due_date",
    "initiated_at",
    "created_at",
    "updated_at",
    "source_url",
)

_SUBMITTAL_FULL_RESPONSE_FIELD_KEYS = (
    "id",
    "actual_delivery_date",
    "bic_due_date",
    "confirmed_delivery_date",
    "closed_at",
    "cost_code_id",
    "current_step_approvers",
    "current_step_returned_date",
    "current_step_sent_date",
    "custom_textarea_1",
    "custom_textfield_1",
    "description",
    "design_team_review_time",
    "distribution_member_ids",
    "due_date",
    "internal_review_time",
    "issue_date",
    "lead_time",
    "location_id",
    "number",
    "private",
    "received_date",
    "received_from_id",
    "required_on_site_date",
    "responsible_contractor_id",
    "revision",
    "scheduled_task_key",
    "scheduled_task_id",
    "specification_section_id",
    "status_id",
    "sub_job_id",
    "submit_by",
    "submittal_manager_id",
    "submittal_package_id",
    "title",
    "type",
    "workflow_step",
)

_SUBMITTAL_FREE_TEXT_FIELD_KEYS = {
    "custom_textarea_1",
    "custom_textfield_1",
    "description",
}

_SUBMITTAL_RESPONSE_CANONICAL_FIELD_KEYS = (
    "id",
    "created_at",
    "updated_at",
    "author_id",
    "response_status",
)

_SUBMITTAL_PACKAGE_CANONICAL_FIELD_KEYS = (
    "id",
    "number",
    "title",
    "status",
    "created_at",
    "updated_at",
)

# Status-string fragments that trip the review-routing heuristic. Substring +
# case-insensitive. The submittal list extends the generic RFI fragments with
# submittal-specific workflow states (rejected / revise & resubmit / void).
_REVIEW_STATUS_FRAGMENTS = (
    "legal",
    "financial",
    "hold",
    "dispute",
    "review",
    "escalat",
    "rejected",
    "revise",
    "resubmit",
    "void",
)

# Subject keywords that, when present in the submittal title, mark the record
# review-required even if status looks benign.
_REVIEW_SUBJECT_FRAGMENTS = (
    "claim",
    "change order",
    "contract amendment",
    "delay",
    "back charge",
    "lien",
    "stop work",
)


def _title_excerpt(title: Any, *, max_chars: int = 200) -> Optional[str]:
    if not isinstance(title, str):
        return None
    trimmed = title.strip()
    if not trimmed:
        return None
    return trimmed[:max_chars]


def _source_url(raw: Dict[str, Any]) -> Optional[str]:
    for key in ("html_url", "url", "source_url"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _redact_person_ref(raw: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    out: Dict[str, Any] = {}
    if raw.get("id") is not None:
        out["id"] = raw["id"]
    name_hash = hash_identifier(raw.get("name"))
    if name_hash is not None:
        out["name_hash_prefix"] = name_hash
    return out or None


def _redact_current_step_approvers(raw: Any) -> list[Dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    approvers: list[Dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        out: Dict[str, Any] = {}
        for key in ("id", "response_required"):
            if item.get(key) is not None:
                out[key] = item[key]
        user = _redact_person_ref(item.get("user"))
        if user is not None:
            out["user"] = user
        approvers.append(out)
    return approvers


def _redact_custom_field_payload(raw: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    data_type = raw.get("data_type")
    value = raw.get("value")
    out: Dict[str, Any] = {"data_type": data_type}
    if value is None:
        return out
    if data_type in {"decimal", "boolean", "lov_entry", "lov_entries"}:
        out["value"] = value
    else:
        summary = hash_summary(value)
        if summary is not None:
            out["value_summary"] = summary
    return out


def _capture_submittal_response_fields(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Capture the documented submittal response shape with redaction.

    The field set mirrors Procore's detail response. Scalar IDs, dates,
    numbers, booleans and workflow metrics are preserved. Free-text fields and
    string custom-field values are represented as hash summaries to preserve
    the field without storing raw body text.
    """
    canonical_fields: Dict[str, Any] = {}
    source_url = _source_url(raw)
    if source_url is not None:
        canonical_fields["source_url"] = source_url

    for key in _SUBMITTAL_FULL_RESPONSE_FIELD_KEYS:
        if key not in raw or raw[key] is None:
            continue
        value = raw[key]
        if key in _SUBMITTAL_FREE_TEXT_FIELD_KEYS:
            summary = hash_summary(value)
            if summary is not None:
                canonical_fields[key] = summary
            continue
        if key == "current_step_approvers":
            canonical_fields[key] = _redact_current_step_approvers(value)
            continue
        canonical_fields[key] = value

    for key, value in raw.items():
        if not key.startswith("custom_field_"):
            continue
        redacted = _redact_custom_field_payload(value)
        if redacted is not None:
            canonical_fields[key] = redacted

    # Backward-compatible aliases used by older fixtures/projections.
    for key in _SUBMITTAL_CANONICAL_FIELD_KEYS:
        if key == "source_url" or key in canonical_fields:
            continue
        if key in raw and raw[key] is not None:
            canonical_fields[key] = raw[key]
    return canonical_fields


def _looks_review_required(raw: Dict[str, Any]) -> Tuple[bool, str]:
    status = raw.get("status")
    if isinstance(status, str):
        lowered = status.lower()
        for fragment in _REVIEW_STATUS_FRAGMENTS:
            if fragment in lowered:
                return True, f"status_contains:{fragment}"
    title = raw.get("title") if isinstance(raw.get("title"), str) else raw.get("subject")
    if isinstance(title, str):
        lowered = title.lower()
        for fragment in _REVIEW_SUBJECT_FRAGMENTS:
            if fragment in lowered:
                return True, f"subject_contains:{fragment}"
    if not raw.get("assignee_id") and not raw.get("ball_in_court_id"):
        return True, "assignee_missing"
    return False, "default_low_risk"


def normalize_submittal(
    raw: Dict[str, Any],
    *,
    project_key: str,
    endpoint_id: str,
    correlation_id: str,
    fetched_at: str,
) -> Dict[str, Any]:
    """Return a canonical submittal record from a raw Procore submittal payload.

    Body fields are never carried through. ``redacted_excerpt`` is derived
    from the title only (truncated to 200 chars). ``review_required`` is
    derived from status / subject heuristics and an assignee-or-ball-in-court
    presence check.
    """

    if not isinstance(raw, dict):
        raise TypeError("normalize_submittal requires a dict payload")
    if "id" not in raw or raw["id"] in (None, ""):
        raise ValueError("normalize_submittal requires raw['id']")

    canonical_fields = _capture_submittal_response_fields(raw)

    review_required, routing_reason = _looks_review_required(raw)
    excerpt = _title_excerpt(raw.get("title") or raw.get("subject"))
    responses_list = raw.get("responses") if isinstance(raw.get("responses"), list) else []
    packages_list = raw.get("packages") if isinstance(raw.get("packages"), list) else []

    record: Dict[str, Any] = {
        "source_project_key": project_key,
        "endpoint_id": endpoint_id,
        "entity_stable_key": str(raw["id"]),
        "category": "submittals",
        "review_required": review_required,
        "routing_reason": routing_reason,
        "canonical_fields": canonical_fields,
        "responses_count": len(responses_list),
        "packages_count": len(packages_list),
        "fetched_at": fetched_at,
        "correlation_id": correlation_id,
        "redaction_applied": True,
        "normalization_schema_version": NORMALIZATION_SCHEMA_VERSION,
    }
    if excerpt is not None:
        record["redacted_excerpt"] = excerpt
    return record


def normalize_submittal_response(
    raw: Dict[str, Any],
    *,
    parent_procore_id: str,
    project_key: str,
    endpoint_id: str,
    correlation_id: str,
    fetched_at: str,
) -> Dict[str, Any]:
    """Return a canonical submittal-response record.

    All responses are flagged ``review_required=True`` (stop-condition: response
    comments must never be stored raw). The comment body is reduced through
    :func:`hash_summary` to a structural hash; the canonical record never
    carries comment text.
    """

    if not isinstance(raw, dict):
        raise TypeError("normalize_submittal_response requires a dict payload")
    if "id" not in raw or raw["id"] in (None, ""):
        raise ValueError("normalize_submittal_response requires raw['id']")

    canonical_fields: Dict[str, Any] = {}
    for key in _SUBMITTAL_RESPONSE_CANONICAL_FIELD_KEYS:
        if key in raw and raw[key] is not None:
            canonical_fields[key] = raw[key]

    body = raw.get("comment") if "comment" in raw else raw.get("body")
    body_summary = hash_summary(body) if body is not None else None

    record: Dict[str, Any] = {
        "source_project_key": project_key,
        "endpoint_id": endpoint_id,
        "entity_stable_key": f"response-{parent_procore_id}-{raw['id']}",
        "parent_submittal_stable_key": parent_procore_id,
        "category": "submittal_responses",
        "review_required": True,
        "routing_reason": "submittal_response_default_review_required",
        "canonical_fields": canonical_fields,
        "fetched_at": fetched_at,
        "correlation_id": correlation_id,
        "redaction_applied": True,
        "normalization_schema_version": NORMALIZATION_SCHEMA_VERSION,
    }
    if body_summary is not None:
        record["body_summary"] = body_summary
    return record


def normalize_submittal_package(
    raw: Dict[str, Any],
    *,
    parent_procore_id: str,
    project_key: str,
    endpoint_id: str,
    correlation_id: str,
    fetched_at: str,
) -> Dict[str, Any]:
    """Return a canonical submittal-package record.

    Packages are always flagged ``review_required=True``: a package endpoint
    has not been promoted to a verified live endpoint, so the dry-run posture
    routes every package row for human review regardless of contents.
    """

    if not isinstance(raw, dict):
        raise TypeError("normalize_submittal_package requires a dict payload")
    if "id" not in raw or raw["id"] in (None, ""):
        raise ValueError("normalize_submittal_package requires raw['id']")

    canonical_fields: Dict[str, Any] = {}
    for key in _SUBMITTAL_PACKAGE_CANONICAL_FIELD_KEYS:
        if key in raw and raw[key] is not None:
            canonical_fields[key] = raw[key]

    description = raw.get("description")
    description_summary = hash_summary(description) if description is not None else None

    record: Dict[str, Any] = {
        "source_project_key": project_key,
        "endpoint_id": endpoint_id,
        "entity_stable_key": f"package-{parent_procore_id}-{raw['id']}",
        "parent_submittal_stable_key": parent_procore_id,
        "category": "submittal_packages",
        "review_required": True,
        "routing_reason": "submittal_package_default_review_required",
        "canonical_fields": canonical_fields,
        "fetched_at": fetched_at,
        "correlation_id": correlation_id,
        "redaction_applied": True,
        "normalization_schema_version": NORMALIZATION_SCHEMA_VERSION,
    }
    if description_summary is not None:
        record["description_summary"] = description_summary
    return record


def normalize_submittal_payload_block(
    raw_items: List[Dict[str, Any]],
    *,
    project_key: str,
    endpoint_id: str,
    correlation_id: str,
    fetched_at: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Normalize an entire submittal list response into
    ``(submittals, responses, packages)`` record lists.
    """

    submittals: List[Dict[str, Any]] = []
    responses: List[Dict[str, Any]] = []
    packages: List[Dict[str, Any]] = []
    for raw in raw_items or []:
        submittal_record = normalize_submittal(
            raw,
            project_key=project_key,
            endpoint_id=endpoint_id,
            correlation_id=correlation_id,
            fetched_at=fetched_at,
        )
        submittals.append(submittal_record)
        for raw_response in raw.get("responses") or []:
            if not isinstance(raw_response, dict):
                continue
            responses.append(
                normalize_submittal_response(
                    raw_response,
                    parent_procore_id=submittal_record["entity_stable_key"],
                    project_key=project_key,
                    endpoint_id=endpoint_id,
                    correlation_id=correlation_id,
                    fetched_at=fetched_at,
                )
            )
        for raw_package in raw.get("packages") or []:
            if not isinstance(raw_package, dict):
                continue
            packages.append(
                normalize_submittal_package(
                    raw_package,
                    parent_procore_id=submittal_record["entity_stable_key"],
                    project_key=project_key,
                    endpoint_id=endpoint_id,
                    correlation_id=correlation_id,
                    fetched_at=fetched_at,
                )
            )
    return submittals, responses, packages


__all__ = [
    "NORMALIZATION_SCHEMA_VERSION",
    "normalize_submittal",
    "normalize_submittal_response",
    "normalize_submittal_package",
    "normalize_submittal_payload_block",
]
