"""Meeting + meeting-topic canonical normalization (Phase 04 Prompt 07).

Meetings and meeting-topics are **two separate Procore endpoints**
(``/projects/{project_id}/meetings`` and
``/projects/{project_id}/meetings/{meeting_id}/topics``) — unlike RFI replies,
submittal responses, or observation comments, topics are NOT nested children
of a meeting payload. Each entity therefore has its own normalizer and its
own dispatch entry; the apply path persists them independently.

Meeting parents are metadata-only (title / time / location); the body /
description / action-items text on topics is reduced to SHA-256 hash-only
summaries — raw text is never persisted. The topic-level safety heuristic
extends the observation pattern with the prompt-specific claim / delay /
cost / safety / incident / injury / corrective fragment set.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Tuple

from .rfi import NORMALIZATION_SCHEMA_VERSION

_MEETING_CANONICAL_FIELD_KEYS = (
    "number",
    "title",
    "status",
    "start_time",
    "end_time",
    "location",
    "organizer_id",
    "project_id",
    "source_url",
    "created_at",
    "updated_at",
)

_MEETING_TOPIC_CANONICAL_FIELD_KEYS = (
    "id",
    "title",
    "status",
    "sequence_number",
    "assignee_id",
    "due_date",
    "parent_meeting_id",
    "source_url",
    "created_at",
    "updated_at",
)

# Generic review fragments shared with prior normalizers.
_GENERIC_REVIEW_STATUS_FRAGMENTS = (
    "legal",
    "financial",
    "hold",
    "dispute",
    "review",
    "escalat",
)
_GENERIC_REVIEW_SUBJECT_FRAGMENTS = (
    "claim",
    "change order",
    "delay",
    "back charge",
    "lien",
    "stop work",
)

# Topic-only safety fragments (Phase 04 Prompt 07 prompt-specific keywords).
_TOPIC_SAFETY_STATUS_FRAGMENTS = (
    "claim",
    "delay",
    "cost",
    "safety",
    "incident",
    "injury",
    "corrective",
    "near-miss",
    "near_miss",
    "unsafe",
    "violation",
)
_TOPIC_SAFETY_SUBJECT_FRAGMENTS = (
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


def _hash_summary(text: Any) -> Optional[Dict[str, Any]]:
    """Return a hash-only structural summary for a body string.

    Never carries the raw text — any topic description / action-items text
    becomes a SHA-256 prefix so the stop-condition guarantee ("raw minutes /
    topic notes persisted") is structurally unsatisfiable.
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


def _action_items_text(raw: Dict[str, Any]) -> Optional[str]:
    """Flatten ``action_items`` (string or list) into a single scannable string."""
    value = raw.get("action_items")
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = [str(v) for v in value if v is not None]
        return "\n".join(parts) if parts else None
    return str(value)


def _meeting_review_decision(raw: Dict[str, Any]) -> Tuple[bool, str]:
    """Meeting-parent review heuristic — metadata-only (status + title)."""
    status = raw.get("status")
    if isinstance(status, str):
        lowered = status.lower()
        for fragment in _GENERIC_REVIEW_STATUS_FRAGMENTS:
            if fragment in lowered:
                return True, f"status_contains:{fragment}"
    title = raw.get("title") if isinstance(raw.get("title"), str) else raw.get("subject")
    if isinstance(title, str):
        lowered = title.lower()
        for fragment in _GENERIC_REVIEW_SUBJECT_FRAGMENTS:
            if fragment in lowered:
                return True, f"subject_contains:{fragment}"
    return False, "default_low_risk"


def _topic_review_decision(raw: Dict[str, Any]) -> Tuple[bool, str, bool]:
    """Meeting-topic review heuristic with body + action-items scan.

    Returns ``(review_required, routing_reason, safety_route)``.
    """
    # Status / type fields — generic + safety fragments combined.
    status_fragments = tuple(set(_GENERIC_REVIEW_STATUS_FRAGMENTS + _TOPIC_SAFETY_STATUS_FRAGMENTS))
    for field_name in ("status", "type"):
        value = raw.get(field_name)
        if not isinstance(value, str):
            continue
        lowered = value.lower()
        for fragment in status_fragments:
            if fragment in lowered:
                safety = fragment in _TOPIC_SAFETY_STATUS_FRAGMENTS
                return True, f"{field_name}_contains:{fragment}", safety

    # Title scan.
    subject_fragments = tuple(set(_GENERIC_REVIEW_SUBJECT_FRAGMENTS + _TOPIC_SAFETY_SUBJECT_FRAGMENTS))
    title = raw.get("title") if isinstance(raw.get("title"), str) else raw.get("subject")
    if isinstance(title, str):
        lowered = title.lower()
        for fragment in subject_fragments:
            if fragment in lowered:
                safety = fragment in _TOPIC_SAFETY_SUBJECT_FRAGMENTS
                return True, f"subject_contains:{fragment}", safety

    # Body / description scan.
    description = (
        raw.get("description")
        if isinstance(raw.get("description"), str)
        else raw.get("body")
    )
    if isinstance(description, str):
        lowered = description.lower()
        for fragment in subject_fragments:
            if fragment in lowered:
                safety = fragment in _TOPIC_SAFETY_SUBJECT_FRAGMENTS
                return True, f"body_contains:{fragment}", safety

    # Action-items scan (string or list).
    flattened_actions = _action_items_text(raw)
    if isinstance(flattened_actions, str):
        lowered = flattened_actions.lower()
        for fragment in subject_fragments:
            if fragment in lowered:
                safety = fragment in _TOPIC_SAFETY_SUBJECT_FRAGMENTS
                return True, f"action_items_contains:{fragment}", safety

    if not raw.get("assignee_id"):
        return True, "assignee_missing", False
    return False, "default_low_risk", False


def normalize_meeting(
    raw: Dict[str, Any],
    *,
    project_key: str,
    endpoint_id: str,
    correlation_id: str,
    fetched_at: str,
) -> Dict[str, Any]:
    """Return a canonical meeting record (metadata-only — no body carried)."""

    if not isinstance(raw, dict):
        raise TypeError("normalize_meeting requires a dict payload")
    if "id" not in raw or raw["id"] in (None, ""):
        raise ValueError("normalize_meeting requires raw['id']")

    canonical_fields: Dict[str, Any] = {}
    source_url = _source_url(raw)
    if source_url is not None:
        canonical_fields["source_url"] = source_url
    for key in _MEETING_CANONICAL_FIELD_KEYS:
        if key == "source_url":
            continue
        if key in raw and raw[key] is not None:
            canonical_fields[key] = raw[key]

    review_required, routing_reason = _meeting_review_decision(raw)
    excerpt = _title_excerpt(raw.get("title") or raw.get("subject"))

    record: Dict[str, Any] = {
        "source_project_key": project_key,
        "endpoint_id": endpoint_id,
        "entity_stable_key": str(raw["id"]),
        "category": "meetings",
        "review_required": review_required,
        "routing_reason": routing_reason,
        "canonical_fields": canonical_fields,
        "fetched_at": fetched_at,
        "correlation_id": correlation_id,
        "redaction_applied": True,
        "normalization_schema_version": NORMALIZATION_SCHEMA_VERSION,
    }
    if excerpt is not None:
        record["redacted_excerpt"] = excerpt
    return record


def normalize_meeting_topic(
    raw: Dict[str, Any],
    *,
    project_key: str,
    endpoint_id: str,
    correlation_id: str,
    fetched_at: str,
    parent_meeting_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Return a canonical meeting-topic record.

    Description / body / action_items text are reduced to hash-only
    summaries; review routing fires on claim / delay / cost / safety /
    incident / injury / corrective keywords anywhere in the scanned fields.
    """

    if not isinstance(raw, dict):
        raise TypeError("normalize_meeting_topic requires a dict payload")
    if "id" not in raw or raw["id"] in (None, ""):
        raise ValueError("normalize_meeting_topic requires raw['id']")

    canonical_fields: Dict[str, Any] = {}
    source_url = _source_url(raw)
    if source_url is not None:
        canonical_fields["source_url"] = source_url
    for key in _MEETING_TOPIC_CANONICAL_FIELD_KEYS:
        if key == "source_url":
            continue
        if key in raw and raw[key] is not None:
            canonical_fields[key] = raw[key]
    # Defensive: if the caller supplied a parent_meeting_id and the raw payload
    # didn't carry one, surface it in canonical_fields so the apply row links
    # back to the parent meeting.
    if (
        parent_meeting_id is not None
        and canonical_fields.get("parent_meeting_id") is None
    ):
        canonical_fields["parent_meeting_id"] = parent_meeting_id

    review_required, routing_reason, safety_route = _topic_review_decision(raw)
    excerpt = _title_excerpt(raw.get("title") or raw.get("subject"))

    description = (
        raw.get("description")
        if "description" in raw
        else raw.get("body")
    )
    description_summary = _hash_summary(description) if description is not None else None
    flattened_actions = _action_items_text(raw)
    action_items_summary = (
        _hash_summary(flattened_actions) if flattened_actions is not None else None
    )

    record: Dict[str, Any] = {
        "source_project_key": project_key,
        "endpoint_id": endpoint_id,
        "entity_stable_key": str(raw["id"]),
        "category": "meeting_topics",
        "review_required": review_required,
        "routing_reason": routing_reason,
        "safety_route": safety_route,
        "canonical_fields": canonical_fields,
        "fetched_at": fetched_at,
        "correlation_id": correlation_id,
        "redaction_applied": True,
        "normalization_schema_version": NORMALIZATION_SCHEMA_VERSION,
    }
    if excerpt is not None:
        record["redacted_excerpt"] = excerpt
    if description_summary is not None:
        record["description_summary"] = description_summary
    if action_items_summary is not None:
        record["action_items_summary"] = action_items_summary
    return record


def normalize_meeting_payload_block(
    raw_items: List[Dict[str, Any]],
    *,
    project_key: str,
    endpoint_id: str,
    correlation_id: str,
    fetched_at: str,
) -> Tuple[List[Dict[str, Any]]]:
    """Normalize an entire meeting list response into a one-tuple of meeting records."""

    meetings: List[Dict[str, Any]] = []
    for raw in raw_items or []:
        meetings.append(
            normalize_meeting(
                raw,
                project_key=project_key,
                endpoint_id=endpoint_id,
                correlation_id=correlation_id,
                fetched_at=fetched_at,
            )
        )
    return (meetings,)


def normalize_meeting_topic_payload_block(
    raw_items: List[Dict[str, Any]],
    *,
    project_key: str,
    endpoint_id: str,
    correlation_id: str,
    fetched_at: str,
    parent_meeting_id: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]]]:
    """Normalize an entire meeting-topic list response into a one-tuple of topic records."""

    topics: List[Dict[str, Any]] = []
    for raw in raw_items or []:
        topics.append(
            normalize_meeting_topic(
                raw,
                project_key=project_key,
                endpoint_id=endpoint_id,
                correlation_id=correlation_id,
                fetched_at=fetched_at,
                parent_meeting_id=parent_meeting_id,
            )
        )
    return (topics,)


__all__ = [
    "NORMALIZATION_SCHEMA_VERSION",
    "normalize_meeting",
    "normalize_meeting_topic",
    "normalize_meeting_payload_block",
    "normalize_meeting_topic_payload_block",
]
