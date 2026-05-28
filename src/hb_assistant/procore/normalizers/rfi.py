"""RFI + RFI-reply canonical normalization (Phase 04 Prompt 04).

Pure functions over a raw Procore RFI payload. Never persists, never reads
network, never echoes bodies. Replies are stored as separate canonical rows
with category ``rfi_replies`` and ``review_required=True`` per the prompt
stop condition ("RFI replies stored without review routing").

Body excerpts are reduced through :func:`hb_assistant.procore.redaction.redact_body`
so the canonical row never carries raw question or answer text — only the
structural hash summary.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Tuple

NORMALIZATION_SCHEMA_VERSION = 1

_RFI_CANONICAL_FIELD_KEYS = (
    "number",
    "subject",
    "status",
    "assignee_id",
    "due_date",
    "initiated_at",
    "updated_at",
    "created_at",
    "source_url",
)

_RFI_REPLY_CANONICAL_FIELD_KEYS = (
    "id",
    "created_at",
    "updated_at",
    "author_id",
)

# Status strings that flag an RFI for explicit review routing. Match is
# case-insensitive and substring-based so variants like "legal-review-required"
# or "FINANCIAL_HOLD" both trip the flag.
_REVIEW_STATUS_FRAGMENTS = (
    "legal",
    "financial",
    "hold",
    "dispute",
    "review",
    "escalat",  # escalated / escalation
)

# Keywords that, when present in the RFI subject, mark the record as
# review-required even if status looks benign.
_REVIEW_SUBJECT_FRAGMENTS = (
    "claim",
    "change order",
    "delay",
    "back charge",
    "lien",
    "stop work",
)


def _hash_summary(text: Any) -> Optional[Dict[str, Any]]:
    """Return a hash-only structural summary for a body string.

    Never carries the raw text — even short replies get a SHA-256 prefix so the
    stop-condition guarantee (no raw RFI / reply body persisted) is uniform.
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


def _subject_excerpt(subject: Any, *, max_chars: int = 200) -> Optional[str]:
    if not isinstance(subject, str):
        return None
    trimmed = subject.strip()
    if not trimmed:
        return None
    return trimmed[:max_chars]


def _looks_review_required(raw: Dict[str, Any]) -> Tuple[bool, str]:
    status = raw.get("status")
    if isinstance(status, str):
        lowered = status.lower()
        for fragment in _REVIEW_STATUS_FRAGMENTS:
            if fragment in lowered:
                return True, f"status_contains:{fragment}"
    subject = raw.get("subject")
    if isinstance(subject, str):
        lowered = subject.lower()
        for fragment in _REVIEW_SUBJECT_FRAGMENTS:
            if fragment in lowered:
                return True, f"subject_contains:{fragment}"
    if not raw.get("assignee_id"):
        return True, "assignee_missing"
    return False, "default_low_risk"


def _source_url(raw: Dict[str, Any]) -> Optional[str]:
    for key in ("html_url", "url", "source_url"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def normalize_rfi(
    raw: Dict[str, Any],
    *,
    project_key: str,
    endpoint_id: str,
    correlation_id: str,
    fetched_at: str,
) -> Dict[str, Any]:
    """Return a canonical RFI record from a raw Procore RFI payload.

    Body fields are never carried through. ``redacted_excerpt`` is derived
    from the subject only (truncated to 200 chars). ``review_required`` is
    derived from status/subject heuristics and an assignee presence check.
    """

    if not isinstance(raw, dict):
        raise TypeError("normalize_rfi requires a dict payload")
    if "id" not in raw or raw["id"] in (None, ""):
        raise ValueError("normalize_rfi requires raw['id']")

    canonical_fields: Dict[str, Any] = {}
    source_url = _source_url(raw)
    if source_url is not None:
        canonical_fields["source_url"] = source_url
    for key in _RFI_CANONICAL_FIELD_KEYS:
        if key == "source_url":
            continue
        if key in raw and raw[key] is not None:
            canonical_fields[key] = raw[key]

    review_required, routing_reason = _looks_review_required(raw)
    excerpt = _subject_excerpt(raw.get("subject"))
    replies_list = raw.get("replies") if isinstance(raw.get("replies"), list) else []

    record: Dict[str, Any] = {
        "source_project_key": project_key,
        "endpoint_id": endpoint_id,
        "entity_stable_key": str(raw["id"]),
        "category": "rfis",
        "review_required": review_required,
        "routing_reason": routing_reason,
        "canonical_fields": canonical_fields,
        "replies_count": len(replies_list),
        "fetched_at": fetched_at,
        "correlation_id": correlation_id,
        "redaction_applied": True,
        "normalization_schema_version": NORMALIZATION_SCHEMA_VERSION,
    }
    if excerpt is not None:
        record["redacted_excerpt"] = excerpt
    return record


def normalize_rfi_reply(
    raw: Dict[str, Any],
    *,
    parent_rfi_stable_key: str,
    project_key: str,
    endpoint_id: str,
    correlation_id: str,
    fetched_at: str,
) -> Dict[str, Any]:
    """Return a canonical RFI-reply record.

    All replies are flagged ``review_required=True`` (stop-condition: replies
    must never be stored without review routing). The reply body is reduced
    through :func:`redact_body` to a structural hash; the canonical record
    never carries reply text.
    """

    if not isinstance(raw, dict):
        raise TypeError("normalize_rfi_reply requires a dict payload")
    if "id" not in raw or raw["id"] in (None, ""):
        raise ValueError("normalize_rfi_reply requires raw['id']")

    canonical_fields: Dict[str, Any] = {}
    for key in _RFI_REPLY_CANONICAL_FIELD_KEYS:
        if key in raw and raw[key] is not None:
            canonical_fields[key] = raw[key]

    body = raw.get("body") if "body" in raw else raw.get("comment")
    body_summary = _hash_summary(body) if body is not None else None

    record: Dict[str, Any] = {
        "source_project_key": project_key,
        "endpoint_id": endpoint_id,
        "entity_stable_key": f"reply-{parent_rfi_stable_key}-{raw['id']}",
        "parent_rfi_stable_key": parent_rfi_stable_key,
        "category": "rfi_replies",
        "review_required": True,
        "routing_reason": "rfi_reply_default_review_required",
        "canonical_fields": canonical_fields,
        "fetched_at": fetched_at,
        "correlation_id": correlation_id,
        "redaction_applied": True,
        "normalization_schema_version": NORMALIZATION_SCHEMA_VERSION,
    }
    if body_summary is not None:
        record["body_summary"] = body_summary
    return record


def normalize_rfi_payload_block(
    raw_items: List[Dict[str, Any]],
    *,
    project_key: str,
    endpoint_id: str,
    correlation_id: str,
    fetched_at: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Normalize an entire RFI list response into (rfis, replies) record lists."""

    rfis: List[Dict[str, Any]] = []
    replies: List[Dict[str, Any]] = []
    for raw in raw_items or []:
        rfi_record = normalize_rfi(
            raw,
            project_key=project_key,
            endpoint_id=endpoint_id,
            correlation_id=correlation_id,
            fetched_at=fetched_at,
        )
        rfis.append(rfi_record)
        for raw_reply in raw.get("replies") or []:
            if not isinstance(raw_reply, dict):
                continue
            replies.append(
                normalize_rfi_reply(
                    raw_reply,
                    parent_rfi_stable_key=rfi_record["entity_stable_key"],
                    project_key=project_key,
                    endpoint_id=endpoint_id,
                    correlation_id=correlation_id,
                    fetched_at=fetched_at,
                )
            )
    return rfis, replies


__all__ = [
    "NORMALIZATION_SCHEMA_VERSION",
    "normalize_rfi",
    "normalize_rfi_reply",
    "normalize_rfi_payload_block",
]
