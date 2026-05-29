"""Phase 05 RFQ / change-event normalizers.

Pure functions over raw Procore payloads for the change-management pricing surface:
RFQs (request for quotes) + their responses & quotes, and change events + their
comments. Never persists, never reads network, never echoes bodies.

Same posture as the owner / commitment normalizers: amounts / quantities / rates kept
verbatim (decimal-safe); WBS / cost-code identifiers + labels kept; parties (creator /
assignee) hashed. RFQ descriptions, quote descriptions, response comments and
change-event comments are reduced to a hash + length + **PII-masked excerpt**
(``summarize_text``) — the raw body never persists.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .financial import (
    extract_currency_config,
    extract_wbs_cost_code,
    person_hash_summary,
    summarize_text,
)
from .financial import parse_amount as _parse_amount

NORMALIZATION_SCHEMA_VERSION = 1

_RFQ_AMOUNTS = ("estimated_amount", "original_quote")
_CHANGE_EVENT_AMOUNTS = (
    "estimated_cost",
    "estimated_revenue",
    "owner_cost_amount",
    "commitment_cost_amount",
)


def _base(
    raw: Dict[str, Any],
    *,
    project_key: str,
    endpoint_id: str,
    category: str,
    correlation_id: str,
    fetched_at: str,
    canonical_fields: Dict[str, Any],
    review_required: bool,
    routing_reason: str,
    entity_stable_key: str,
) -> Dict[str, Any]:
    return {
        "source_project_key": project_key,
        "endpoint_id": endpoint_id,
        "entity_stable_key": entity_stable_key,
        "category": category,
        "review_required": review_required,
        "routing_reason": routing_reason,
        "canonical_fields": canonical_fields,
        "fetched_at": fetched_at,
        "correlation_id": correlation_id,
        "redaction_applied": True,
        "normalization_schema_version": NORMALIZATION_SCHEMA_VERSION,
    }


def _require_id(raw: Any, fn: str) -> None:
    if not isinstance(raw, dict):
        raise TypeError(f"{fn} requires a dict payload")
    if raw.get("id") in (None, ""):
        raise ValueError(f"{fn} requires raw['id']")


def _keep_scalars(raw: Dict[str, Any], keys: Any, out: Dict[str, Any]) -> None:
    for key in keys:
        value = raw.get(key)
        if value is not None:
            out[key] = value


def _keep_amounts(raw: Dict[str, Any], keys: Any, out: Dict[str, Any]) -> None:
    for key in keys:
        amount = _parse_amount(raw.get(key))
        if amount is not None:
            out[key] = amount


def _summarize_into(out: Dict[str, Any], raw: Dict[str, Any], keys: Any) -> None:
    # Hash + length + PII-masked excerpt for change-management free text.
    for key in keys:
        summary = summarize_text(raw.get(key))
        if summary is not None:
            out[f"{key}_summary"] = summary


def _parties_into(out: Dict[str, Any], raw: Dict[str, Any], keys: Any) -> None:
    for key in keys:
        person = person_hash_summary(raw.get(key))
        if person is not None:
            out[f"{key}_ref"] = person


def normalize_rfq(
    raw: Dict[str, Any], *, project_key: str, endpoint_id: str, correlation_id: str, fetched_at: str
) -> Dict[str, Any]:
    _require_id(raw, "normalize_rfq")
    cf: Dict[str, Any] = {}
    _keep_scalars(
        raw,
        (
            "number",
            "status",
            "estimated_status",
            "due_date",
            "intent_to_quote",
            "private",
            "commitment_contract_id",
            "updated_at",
        ),
        cf,
    )
    _keep_amounts(raw, _RFQ_AMOUNTS, cf)
    impact = _parse_amount(raw.get("estimated_schedule_impact"))
    if impact is not None:
        cf["estimated_schedule_impact"] = impact
    cf.update(extract_currency_config(raw))
    cf.update(extract_wbs_cost_code(raw))
    _summarize_into(cf, raw, ("title", "description"))
    _parties_into(cf, raw, ("created_by", "assigned"))
    change_event = raw.get("change_event")
    if isinstance(change_event, dict) and change_event.get("id") is not None:
        cf["change_event_id"] = str(change_event["id"])
    return _base(
        raw,
        project_key=project_key,
        endpoint_id=endpoint_id,
        category="rfqs",
        correlation_id=correlation_id,
        fetched_at=fetched_at,
        canonical_fields=cf,
        review_required=bool(raw.get("private")),
        routing_reason="rfq_high_sensitivity",
        entity_stable_key=str(raw["id"]),
    )


def normalize_rfq_response(
    raw: Dict[str, Any], *, project_key: str, endpoint_id: str, correlation_id: str, fetched_at: str
) -> Dict[str, Any]:
    _require_id(raw, "normalize_rfq_response")
    cf: Dict[str, Any] = {}
    _keep_scalars(raw, ("request_for_quote_id", "created_at", "updated_at"), cf)
    _summarize_into(cf, raw, ("comment",))
    _parties_into(cf, raw, ("created_by",))
    attachments = raw.get("attachments")
    if isinstance(attachments, list):
        cf["attachments_count"] = len(attachments)
    return _base(
        raw,
        project_key=project_key,
        endpoint_id=endpoint_id,
        category="rfq_responses",
        correlation_id=correlation_id,
        fetched_at=fetched_at,
        canonical_fields=cf,
        review_required=False,
        routing_reason="rfq_high_sensitivity",
        entity_stable_key=str(raw["id"]),
    )


def normalize_rfq_quote(
    raw: Dict[str, Any], *, project_key: str, endpoint_id: str, correlation_id: str, fetched_at: str
) -> Dict[str, Any]:
    _require_id(raw, "normalize_rfq_quote")
    cf: Dict[str, Any] = {}
    _keep_scalars(
        raw,
        ("request_for_quote_id", "commitment_quote_number", "created_at", "updated_at"),
        cf,
    )
    _keep_amounts(raw, ("cost",), cf)
    impact = _parse_amount(raw.get("schedule_impact"))
    if impact is not None:
        cf["schedule_impact"] = impact
    cf.update(extract_currency_config(raw))
    _summarize_into(cf, raw, ("description",))
    _parties_into(cf, raw, ("created_by",))
    return _base(
        raw,
        project_key=project_key,
        endpoint_id=endpoint_id,
        category="rfq_quotes",
        correlation_id=correlation_id,
        fetched_at=fetched_at,
        canonical_fields=cf,
        review_required=False,
        routing_reason="rfq_high_sensitivity",
        entity_stable_key=str(raw["id"]),
    )


def normalize_change_event(
    raw: Dict[str, Any], *, project_key: str, endpoint_id: str, correlation_id: str, fetched_at: str
) -> Dict[str, Any]:
    _require_id(raw, "normalize_change_event")
    cf: Dict[str, Any] = {}
    _keep_scalars(raw, ("number", "status", "scope", "updated_at"), cf)
    _keep_amounts(raw, _CHANGE_EVENT_AMOUNTS, cf)
    impact = _parse_amount(raw.get("schedule_impact_amount"))
    if impact is not None:
        cf["schedule_impact_amount"] = impact
    cf.update(extract_currency_config(raw))
    cf.update(extract_wbs_cost_code(raw))
    _summarize_into(cf, raw, ("title",))
    _parties_into(cf, raw, ("created_by",))
    return _base(
        raw,
        project_key=project_key,
        endpoint_id=endpoint_id,
        category="change_events",
        correlation_id=correlation_id,
        fetched_at=fetched_at,
        canonical_fields=cf,
        review_required=True,
        routing_reason="change_event_high_sensitivity",
        entity_stable_key=str(raw["id"]),
    )


def normalize_change_event_comment(
    raw: Dict[str, Any], *, project_key: str, endpoint_id: str, correlation_id: str, fetched_at: str
) -> Dict[str, Any]:
    _require_id(raw, "normalize_change_event_comment")
    cf: Dict[str, Any] = {}
    _keep_scalars(raw, ("created_at",), cf)
    _summarize_into(cf, raw, ("body",))
    _parties_into(cf, raw, ("creator",))
    return _base(
        raw,
        project_key=project_key,
        endpoint_id=endpoint_id,
        category="change_event_comments",
        correlation_id=correlation_id,
        fetched_at=fetched_at,
        canonical_fields=cf,
        review_required=False,
        routing_reason="change_event_high_sensitivity",
        entity_stable_key=str(raw["id"]),
    )


__all__: List[str] = [
    "NORMALIZATION_SCHEMA_VERSION",
    "normalize_rfq",
    "normalize_rfq_response",
    "normalize_rfq_quote",
    "normalize_change_event",
    "normalize_change_event_comment",
]
