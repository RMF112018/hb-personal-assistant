"""Daily log section-aware canonical normalization (Phase 04 Prompt 08).

Procore's daily log endpoint returns one daily log per project per date,
each carrying multiple parallel sub-collections (counts, weather, manpower,
DCR, delivery, notes, accident, injury, delay, safety violations). This
normalizer demultiplexes a payload into per-section canonical rows guided
by the selection scope at ``resources/config/procore_daily_log_selection.seed.yaml``.

Three buckets:
- **selected_sections** persist as canonical rows with a configurable
  ``canonical_fields`` whitelist and ``review_required=False``.
- **review_only_sections** persist with ``review_required=True`` and a
  ``daily_log_review_only_section`` routing reason; body text is reduced
  to a SHA-256 hash-only summary.
- **routed_to_review_sections** persist with ``review_required=True`` AND
  ``safety_route=True``; body text is reduced to a SHA-256 hash-only
  summary. Accident / injury / delay / safety section text never enters
  normal rows by construction (the routing decision is structural, not
  content-derived).

Unlike the RFI / submittal / observation / meeting normalizers, this module
returns a ``dict[str, list[dict]]`` keyed by section category rather than
a tuple — the multi-section demultiplexing doesn't fit a tuple cleanly.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from hb_assistant.procore.daily_log_selection import (
    DailyLogSection,
    ProcoreDailyLogSelection,
)

from .hashing import hash_summary
from .rfi import NORMALIZATION_SCHEMA_VERSION

# Common timestamp / id keys that EVERY persisted section row carries even
# in the review-only / routed-to-review buckets where the canonical
# whitelist is intentionally minimal.
_MINIMAL_CANONICAL_KEYS = ("id", "log_date", "created_at", "updated_at")

# Body-text keys probed for hash summarization. The first present key wins.
_BODY_TEXT_KEYS = (
    "description",
    "narrative",
    "body",
    "note",
    "comment",
    "details",
)


def _extract_body(raw: Dict[str, Any]) -> Optional[str]:
    for key in _BODY_TEXT_KEYS:
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _bucket_treatment(
    section: DailyLogSection,
    *,
    bucket: str,
) -> Dict[str, Any]:
    """Return the per-bucket review/routing flags applied to every section
    row in that bucket.
    """
    if bucket == "selected":
        return {
            "review_required": False,
            "routing_reason": "default_low_risk",
            "safety_route": False,
        }
    if bucket == "review_only":
        return {
            "review_required": True,
            "routing_reason": "daily_log_review_only_section",
            "safety_route": False,
        }
    # routed_to_review
    return {
        "review_required": True,
        "routing_reason": f"daily_log_routed_to_review:{section.id}",
        "safety_route": True,
    }


def normalize_daily_log_section_item(
    raw: Dict[str, Any],
    *,
    section: DailyLogSection,
    bucket: str,
    parent_daily_log_stable_key: str,
    project_key: str,
    endpoint_id: str,
    correlation_id: str,
    fetched_at: str,
) -> Dict[str, Any]:
    """Normalize a single item from inside a daily log section array.

    ``bucket`` is one of ``"selected"``, ``"review_only"``,
    ``"routed_to_review"`` and drives the canonical-fields whitelist plus
    the review / routing flags.
    """
    if not isinstance(raw, dict):
        raise TypeError("normalize_daily_log_section_item requires a dict payload")
    if "id" not in raw or raw["id"] in (None, ""):
        raise ValueError("normalize_daily_log_section_item requires raw['id']")

    canonical_fields: Dict[str, Any] = {}
    if bucket == "selected":
        for key in section.canonical_field_keys:
            if key in raw and raw[key] is not None:
                canonical_fields[key] = raw[key]
    else:
        # review_only + routed_to_review carry only minimal id+timestamps.
        for key in _MINIMAL_CANONICAL_KEYS:
            if key in raw and raw[key] is not None:
                canonical_fields[key] = raw[key]

    # parent_daily_log_stable_key is always preserved so a section row can be
    # joined back to its parent daily log.
    canonical_fields["parent_daily_log_stable_key"] = parent_daily_log_stable_key

    treatment = _bucket_treatment(section, bucket=bucket)
    record: Dict[str, Any] = {
        "source_project_key": project_key,
        "endpoint_id": endpoint_id,
        "entity_stable_key": f"{section.id}-{parent_daily_log_stable_key}-{raw['id']}",
        "parent_daily_log_stable_key": parent_daily_log_stable_key,
        "category": section.category,
        "section_id": section.id,
        "bucket": bucket,
        "review_required": treatment["review_required"],
        "routing_reason": treatment["routing_reason"],
        "safety_route": treatment["safety_route"],
        "canonical_fields": canonical_fields,
        "fetched_at": fetched_at,
        "correlation_id": correlation_id,
        "redaction_applied": True,
        "normalization_schema_version": NORMALIZATION_SCHEMA_VERSION,
    }

    if bucket in ("review_only", "routed_to_review"):
        body = _extract_body(raw)
        body_summary = hash_summary(body)
        if body_summary is not None:
            record["body_summary"] = body_summary

    return record


def normalize_daily_log_payload_block(
    raw_items: List[Dict[str, Any]],
    *,
    selection_scope: ProcoreDailyLogSelection,
    project_key: str,
    endpoint_id: str,
    correlation_id: str,
    fetched_at: str,
) -> Dict[str, List[Dict[str, Any]]]:
    """Demultiplex daily log items into per-section canonical record lists.

    Returns a dict keyed by ``section.category``. Sections missing from the
    raw payload are simply absent from the output dict. Section arrays that
    are not lists (or are empty) yield zero records and produce no entry.
    """
    out: Dict[str, List[Dict[str, Any]]] = {}
    if not raw_items:
        return out

    buckets = (
        ("selected", selection_scope.selected_sections),
        ("review_only", selection_scope.review_only_sections),
        ("routed_to_review", selection_scope.routed_to_review_sections),
    )

    for raw_log in raw_items:
        if not isinstance(raw_log, dict):
            continue
        parent_id = raw_log.get("id")
        if parent_id in (None, ""):
            continue
        parent_key = str(parent_id)
        for bucket_name, sections in buckets:
            for section in sections:
                items = raw_log.get(section.payload_key)
                if not isinstance(items, list):
                    continue
                for raw_item in items:
                    if not isinstance(raw_item, dict):
                        continue
                    if "id" not in raw_item or raw_item["id"] in (None, ""):
                        continue
                    record = normalize_daily_log_section_item(
                        raw_item,
                        section=section,
                        bucket=bucket_name,
                        parent_daily_log_stable_key=parent_key,
                        project_key=project_key,
                        endpoint_id=endpoint_id,
                        correlation_id=correlation_id,
                        fetched_at=fetched_at,
                    )
                    out.setdefault(section.category, []).append(record)
    return out


__all__ = [
    "NORMALIZATION_SCHEMA_VERSION",
    "normalize_daily_log_payload_block",
    "normalize_daily_log_section_item",
]
