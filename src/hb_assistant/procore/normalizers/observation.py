"""Observation + observation-comment canonical normalization (Phase 04 Prompt 06).

Pure functions over a raw Procore observation payload. Never persists, never
reads network, never echoes bodies. Comments are stored as separate canonical
rows (``category="observation_comments"``) with ``review_required=True``.
Observations themselves are flagged ``review_required=True`` when the safety
heuristic fires on status / type / subject / description text — body text is
never carried; only a SHA-256 hash-only summary survives.

Mirrors :mod:`hb_assistant.procore.normalizers.submittal`. Safety routing is
encoded as keyword scans over status, type, subject (title), and body text;
the wider scan is the key difference from RFI / submittal, where the body is
not consulted.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .hashing import hash_summary
from .rfi import NORMALIZATION_SCHEMA_VERSION

_OBSERVATION_CANONICAL_FIELD_KEYS = (
    "number",
    "title",
    "status",
    "type",
    "subtype",
    "assignee_id",
    "created_by_id",
    "observed_at",
    "due_date",
    "closed_at",
    "created_at",
    "updated_at",
    "source_url",
    "severity",
    "priority",
)

_OBSERVATION_COMMENT_CANONICAL_FIELD_KEYS = (
    "id",
    "created_at",
    "updated_at",
    "author_id",
)

# Status / type fragments that trip the safety review-routing heuristic.
# Substring + case-insensitive.
_REVIEW_STATUS_FRAGMENTS = (
    "legal",
    "financial",
    "hold",
    "dispute",
    "review",
    "escalat",
    # Safety-specific:
    "safety",
    "incident",
    "injury",
    "near-miss",
    "near_miss",
    "corrective",
    "unsafe",
    "violation",
)

# Title / subject keywords that mark the record review-required.
_REVIEW_SUBJECT_FRAGMENTS = (
    "claim",
    "change order",
    "delay",
    "back charge",
    "lien",
    "stop work",
    # Safety-specific:
    "injury",
    "incident",
    "near miss",
    "near-miss",
    "corrective action",
    "unsafe",
    "violation",
    "ppe",
    "fall",
    "first aid",
)

# Description / body keywords. Same fragments as the subject scan plus a few
# observation-specific ones. The body scan is the key escalation over the
# RFI / submittal normalizers, which never inspect body text.
_REVIEW_BODY_FRAGMENTS = _REVIEW_SUBJECT_FRAGMENTS + (
    "personnel",
    "notice",
    "claim",
    "hospital",
    "emergency",
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


def _safety_route_decision(raw: Dict[str, Any]) -> Tuple[bool, str, bool]:
    """Return (review_required, routing_reason, safety_route).

    ``safety_route`` is True only when the trigger is a safety-specific
    fragment (status / subject / body). Generic review fragments (legal,
    financial, etc.) still trigger ``review_required=True`` but with
    ``safety_route=False``.
    """
    safety_status_fragments = (
        "safety",
        "incident",
        "injury",
        "near-miss",
        "near_miss",
        "corrective",
        "unsafe",
        "violation",
    )
    safety_subject_fragments = (
        "injury",
        "incident",
        "near miss",
        "near-miss",
        "corrective action",
        "unsafe",
        "violation",
        "ppe",
        "fall",
        "first aid",
    )

    # Status check (covers status + type fields).
    for field_name in ("status", "type", "subtype"):
        value = raw.get(field_name)
        if not isinstance(value, str):
            continue
        lowered = value.lower()
        for fragment in _REVIEW_STATUS_FRAGMENTS:
            if fragment in lowered:
                is_safety = fragment in safety_status_fragments
                return True, f"{field_name}_contains:{fragment}", is_safety

    # Subject (title) check.
    title = raw.get("title") if isinstance(raw.get("title"), str) else raw.get("subject")
    if isinstance(title, str):
        lowered = title.lower()
        for fragment in _REVIEW_SUBJECT_FRAGMENTS:
            if fragment in lowered:
                is_safety = fragment in safety_subject_fragments
                return True, f"subject_contains:{fragment}", is_safety

    # Body (description) check — unique to observations.
    description = (
        raw.get("description")
        if isinstance(raw.get("description"), str)
        else raw.get("body")
    )
    if isinstance(description, str):
        lowered = description.lower()
        for fragment in _REVIEW_BODY_FRAGMENTS:
            if fragment in lowered:
                # The body scan is treated as a safety signal whenever the
                # matched fragment is in the safety subject set.
                is_safety = fragment in safety_subject_fragments or fragment in (
                    "personnel",
                    "hospital",
                    "emergency",
                )
                return True, f"body_contains:{fragment}", is_safety

    # No fragment matched. Fall back to assignee-missing escalation.
    if not raw.get("assignee_id"):
        return True, "assignee_missing", False
    return False, "default_low_risk", False


def normalize_observation(
    raw: Dict[str, Any],
    *,
    project_key: str,
    endpoint_id: str,
    correlation_id: str,
    fetched_at: str,
) -> Dict[str, Any]:
    """Return a canonical observation record from a raw Procore payload.

    Description / body fields are never carried — only ``description_summary``
    (hash-only) survives. ``redacted_excerpt`` is derived from the title only,
    truncated to 200 chars. ``review_required`` and ``safety_route`` are
    derived from a four-field heuristic (status / type / subject / body).
    """

    if not isinstance(raw, dict):
        raise TypeError("normalize_observation requires a dict payload")
    if "id" not in raw or raw["id"] in (None, ""):
        raise ValueError("normalize_observation requires raw['id']")

    canonical_fields: Dict[str, Any] = {}
    source_url = _source_url(raw)
    if source_url is not None:
        canonical_fields["source_url"] = source_url
    for key in _OBSERVATION_CANONICAL_FIELD_KEYS:
        if key == "source_url":
            continue
        if key in raw and raw[key] is not None:
            canonical_fields[key] = raw[key]

    review_required, routing_reason, safety_route = _safety_route_decision(raw)
    excerpt = _title_excerpt(raw.get("title") or raw.get("subject"))
    description = (
        raw.get("description")
        if "description" in raw
        else raw.get("body")
    )
    description_summary = hash_summary(description) if description is not None else None
    comments_list = raw.get("comments") if isinstance(raw.get("comments"), list) else []

    record: Dict[str, Any] = {
        "source_project_key": project_key,
        "endpoint_id": endpoint_id,
        "entity_stable_key": str(raw["id"]),
        "category": "observations",
        "review_required": review_required,
        "routing_reason": routing_reason,
        "safety_route": safety_route,
        "canonical_fields": canonical_fields,
        "comments_count": len(comments_list),
        "fetched_at": fetched_at,
        "correlation_id": correlation_id,
        "redaction_applied": True,
        "normalization_schema_version": NORMALIZATION_SCHEMA_VERSION,
    }
    if excerpt is not None:
        record["redacted_excerpt"] = excerpt
    if description_summary is not None:
        record["description_summary"] = description_summary
    return record


def normalize_observation_comment(
    raw: Dict[str, Any],
    *,
    parent_observation_stable_key: str,
    project_key: str,
    endpoint_id: str,
    correlation_id: str,
    fetched_at: str,
) -> Dict[str, Any]:
    """Return a canonical observation-comment record.

    All comments are flagged ``review_required=True``. The comment body is
    reduced through :func:`hash_summary` to a structural hash; the canonical
    record never carries comment text.
    """

    if not isinstance(raw, dict):
        raise TypeError("normalize_observation_comment requires a dict payload")
    if "id" not in raw or raw["id"] in (None, ""):
        raise ValueError("normalize_observation_comment requires raw['id']")

    canonical_fields: Dict[str, Any] = {}
    for key in _OBSERVATION_COMMENT_CANONICAL_FIELD_KEYS:
        if key in raw and raw[key] is not None:
            canonical_fields[key] = raw[key]

    body = raw.get("comment") if "comment" in raw else raw.get("body")
    body_summary = hash_summary(body) if body is not None else None

    record: Dict[str, Any] = {
        "source_project_key": project_key,
        "endpoint_id": endpoint_id,
        "entity_stable_key": f"comment-{parent_observation_stable_key}-{raw['id']}",
        "parent_observation_stable_key": parent_observation_stable_key,
        "category": "observation_comments",
        "review_required": True,
        "routing_reason": "observation_comment_default_review_required",
        "canonical_fields": canonical_fields,
        "fetched_at": fetched_at,
        "correlation_id": correlation_id,
        "redaction_applied": True,
        "normalization_schema_version": NORMALIZATION_SCHEMA_VERSION,
    }
    if body_summary is not None:
        record["body_summary"] = body_summary
    return record


def normalize_observation_payload_block(
    raw_items: List[Dict[str, Any]],
    *,
    project_key: str,
    endpoint_id: str,
    correlation_id: str,
    fetched_at: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Normalize an entire observation list response into
    ``(observations, comments)`` record lists.
    """

    observations: List[Dict[str, Any]] = []
    comments: List[Dict[str, Any]] = []
    for raw in raw_items or []:
        observation_record = normalize_observation(
            raw,
            project_key=project_key,
            endpoint_id=endpoint_id,
            correlation_id=correlation_id,
            fetched_at=fetched_at,
        )
        observations.append(observation_record)
        for raw_comment in raw.get("comments") or []:
            if not isinstance(raw_comment, dict):
                continue
            comments.append(
                normalize_observation_comment(
                    raw_comment,
                    parent_observation_stable_key=observation_record["entity_stable_key"],
                    project_key=project_key,
                    endpoint_id=endpoint_id,
                    correlation_id=correlation_id,
                    fetched_at=fetched_at,
                )
            )
    return observations, comments


__all__ = [
    "NORMALIZATION_SCHEMA_VERSION",
    "normalize_observation",
    "normalize_observation_comment",
    "normalize_observation_payload_block",
]
