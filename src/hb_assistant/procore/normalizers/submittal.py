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

import hashlib
from typing import Any, Dict, List, Optional, Tuple

from .rfi import NORMALIZATION_SCHEMA_VERSION

_SUBMITTAL_CANONICAL_FIELD_KEYS = (
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


def _hash_summary(text: Any) -> Optional[Dict[str, Any]]:
    """Return a hash-only structural summary for a body string.

    Never carries the raw text — even short comments get a SHA-256 prefix so
    the stop-condition guarantee (no raw submittal/response body persisted) is
    uniform regardless of length.
    """
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

    canonical_fields: Dict[str, Any] = {}
    source_url = _source_url(raw)
    if source_url is not None:
        canonical_fields["source_url"] = source_url
    for key in _SUBMITTAL_CANONICAL_FIELD_KEYS:
        if key == "source_url":
            continue
        if key in raw and raw[key] is not None:
            canonical_fields[key] = raw[key]

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
    :func:`_hash_summary` to a structural hash; the canonical record never
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
    body_summary = _hash_summary(body) if body is not None else None

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
    description_summary = _hash_summary(description) if description is not None else None

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
