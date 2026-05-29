"""Phase 05 owner-side contract normalizers.

Pure functions over raw Procore payloads for the owner family: prime contracts,
prime-contract line items + attachments, prime change orders + CO line items, and
payment applications. Never persists, never reads network, never echoes bodies.

Each returns the canonical record shape consumed by the live-sync upsert into
``procore_live_records`` (the financial-table projection is a separate store-layer
step). Amounts / quantities / rates are preserved verbatim as decimal-safe strings
(``parse_amount``); free text (titles / descriptions / review notes) is reduced to a
hash-only summary; parties are reduced to opaque ids + hashed refs; attachment URLs
are path-only. Payment-application financial amounts are read from the nested
``g702`` AIA-form object.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .financial import (
    attachment_path,
    extract_currency_config,
    extract_wbs_cost_code,
    hash_summary,
    parse_amount,
    person_hash_summary,
)

NORMALIZATION_SCHEMA_VERSION = 1

# Amount / quantity / rate fields kept verbatim (decimal-safe) per record type.
_CONTRACT_AMOUNTS = (
    "grand_total",
    "original_contract_amount",
    "approved_change_orders",
    "pending_revised_contract_amount",
    "revised_contract_amount",
    "retainage_percent",
)
_CHANGE_ORDER_AMOUNTS = ("grand_total", "schedule_impact_amount")
_LINE_ITEM_AMOUNTS = ("amount", "unit_cost", "quantity", "extended_amount")
_G702_AMOUNTS = (
    "original_contract_sum",
    "net_change_by_change_orders",
    "contract_sum_to_date",
    "total_completed_and_stored_to_date",
    "less_previous_certificates_for_payment",
    "current_payment_due",
    "total_retainage",
    "completed_work_retainage_amount",
    "stored_materials_retainage_amount",
    "total_earned_less_retainage",
    "balance_to_finish_including_retainage",
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
    entity_stable_key: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "source_project_key": project_key,
        "endpoint_id": endpoint_id,
        "entity_stable_key": entity_stable_key or str(raw["id"]),
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


def _keep_amounts(raw: Dict[str, Any], keys: Any, out: Dict[str, Any]) -> None:
    for key in keys:
        amount = parse_amount(raw.get(key))
        if amount is not None:
            out[key] = amount


def _keep_scalars(raw: Dict[str, Any], keys: Any, out: Dict[str, Any]) -> None:
    for key in keys:
        value = raw.get(key)
        if value is not None:
            out[key] = value


def _summarize_into(out: Dict[str, Any], raw: Dict[str, Any], keys: Any) -> None:
    # Hash-only (no excerpt) for high-sensitivity financial free text — the raw
    # body and any preview never persist.
    for key in keys:
        summary = hash_summary(raw.get(key))
        if summary is not None:
            out[f"{key}_summary"] = summary


def normalize_prime_contract(
    raw: Dict[str, Any], *, project_key: str, endpoint_id: str, correlation_id: str, fetched_at: str
) -> Dict[str, Any]:
    _require_id(raw, "normalize_prime_contract")
    cf: Dict[str, Any] = {}
    _keep_scalars(
        raw,
        (
            "number",
            "status",
            "executed",
            "private",
            "accounting_method",
            "contract_date",
            "execution_date",
            "contract_start_date",
            "contract_estimated_completion_date",
            "actual_completion_date",
            "updated_at",
        ),
        cf,
    )
    _keep_amounts(raw, _CONTRACT_AMOUNTS, cf)
    cf.update(extract_currency_config(raw))
    _summarize_into(cf, raw, ("title", "description", "inclusions", "exclusions"))
    for party_key in ("architect", "contractor", "vendor", "created_by"):
        person = person_hash_summary(raw.get(party_key))
        if person is not None:
            cf[f"{party_key}_ref"] = person
    cf["attachments_count"] = len(raw.get("attachments") or [])
    review = bool(raw.get("private"))
    return _base(
        raw,
        project_key=project_key,
        endpoint_id=endpoint_id,
        category="prime_contracts",
        correlation_id=correlation_id,
        fetched_at=fetched_at,
        canonical_fields=cf,
        review_required=review,
        routing_reason="prime_contract_private" if review else "owner_contract_high_sensitivity",
    )


def _line_item_canonical(raw: Dict[str, Any]) -> Dict[str, Any]:
    cf: Dict[str, Any] = {}
    _keep_scalars(raw, ("position", "uom", "extended_type", "updated_at"), cf)
    _keep_amounts(raw, _LINE_ITEM_AMOUNTS, cf)
    cf.update(extract_wbs_cost_code(raw))
    summary = hash_summary(raw.get("description"))
    if summary is not None:
        cf["description_summary"] = summary
    return cf


def normalize_prime_contract_line_item(
    raw: Dict[str, Any], *, project_key: str, endpoint_id: str, correlation_id: str, fetched_at: str
) -> Dict[str, Any]:
    _require_id(raw, "normalize_prime_contract_line_item")
    return _base(
        raw,
        project_key=project_key,
        endpoint_id=endpoint_id,
        category="prime_contract_line_items",
        correlation_id=correlation_id,
        fetched_at=fetched_at,
        canonical_fields=_line_item_canonical(raw),
        review_required=False,
        routing_reason="owner_contract_high_sensitivity",
    )


def normalize_prime_contract_attachment(
    raw: Dict[str, Any], *, project_key: str, endpoint_id: str, correlation_id: str, fetched_at: str
) -> Dict[str, Any]:
    _require_id(raw, "normalize_prime_contract_attachment")
    cf: Dict[str, Any] = {}
    filename_summary = hash_summary(raw.get("filename") or raw.get("name"))
    if filename_summary is not None:
        cf["filename_summary"] = filename_summary
    for url_key in ("url", "share_url", "viewable_url"):
        path = attachment_path(raw.get(url_key))
        if path is not None:
            cf[f"{url_key}_path"] = path
    _keep_scalars(raw, ("content_type", "created_at"), cf)
    return _base(
        raw,
        project_key=project_key,
        endpoint_id=endpoint_id,
        category="prime_contract_attachments",
        correlation_id=correlation_id,
        fetched_at=fetched_at,
        canonical_fields=cf,
        review_required=False,
        routing_reason="owner_contract_attachment",
    )


def normalize_prime_change_order(
    raw: Dict[str, Any], *, project_key: str, endpoint_id: str, correlation_id: str, fetched_at: str
) -> Dict[str, Any]:
    _require_id(raw, "normalize_prime_change_order")
    cf: Dict[str, Any] = {}
    _keep_scalars(
        raw,
        (
            "number",
            "contract_id",
            "status",
            "executed",
            "paid",
            "private",
            "field_change",
            "signature_required",
            "type",
            "due_date",
            "invoiced_date",
            "paid_date",
            "reviewed_at",
            "updated_at",
        ),
        cf,
    )
    _keep_amounts(raw, _CHANGE_ORDER_AMOUNTS, cf)
    cf.update(extract_currency_config(raw))
    _summarize_into(cf, raw, ("title", "description", "review_notes"))
    for party_key in ("created_by", "received_from", "designated_reviewer", "reviewed_by"):
        person = person_hash_summary(raw.get(party_key))
        if person is not None:
            cf[f"{party_key}_ref"] = person
    return _base(
        raw,
        project_key=project_key,
        endpoint_id=endpoint_id,
        category="prime_change_orders",
        correlation_id=correlation_id,
        fetched_at=fetched_at,
        canonical_fields=cf,
        review_required=True,
        routing_reason="owner_change_order_high_sensitivity",
    )


def normalize_prime_change_order_line_item(
    raw: Dict[str, Any], *, project_key: str, endpoint_id: str, correlation_id: str, fetched_at: str
) -> Dict[str, Any]:
    _require_id(raw, "normalize_prime_change_order_line_item")
    return _base(
        raw,
        project_key=project_key,
        endpoint_id=endpoint_id,
        category="prime_change_order_line_items",
        correlation_id=correlation_id,
        fetched_at=fetched_at,
        canonical_fields=_line_item_canonical(raw),
        review_required=False,
        routing_reason="owner_change_order_high_sensitivity",
    )


def _g702(raw: Dict[str, Any]) -> Dict[str, Any]:
    g = raw.get("g702")
    return g if isinstance(g, dict) else {}


def normalize_payment_application(
    raw: Dict[str, Any], *, project_key: str, endpoint_id: str, correlation_id: str, fetched_at: str
) -> Dict[str, Any]:
    _require_id(raw, "normalize_payment_application")
    cf: Dict[str, Any] = {}
    _keep_scalars(
        raw,
        (
            "number",
            "invoice_number",
            "status",
            "period_id",
            "billing_date",
            "period_start",
            "period_end",
            "percent_complete",
            "total_amount_paid",
            "updated_at",
        ),
        cf,
    )
    # total_amount_paid may be a money string — keep decimal-safe.
    paid = parse_amount(raw.get("total_amount_paid"))
    if paid is not None:
        cf["total_amount_paid"] = paid
    g702 = _g702(raw)
    g702_fields: Dict[str, Any] = {}
    for key in _G702_AMOUNTS:
        amount = parse_amount(g702.get(key))
        if amount is not None:
            g702_fields[key] = amount
    if g702_fields:
        cf["g702"] = g702_fields
    contract = raw.get("contract")
    if isinstance(contract, dict) and contract.get("id") is not None:
        cf["contract_id"] = contract["id"]
    status = str(raw.get("status") or "").strip().lower()
    return _base(
        raw,
        project_key=project_key,
        endpoint_id=endpoint_id,
        category="payment_applications",
        correlation_id=correlation_id,
        fetched_at=fetched_at,
        canonical_fields=cf,
        review_required=status != "paid",
        routing_reason="payment_application_high_sensitivity",
    )


__all__: List[str] = [
    "NORMALIZATION_SCHEMA_VERSION",
    "normalize_prime_contract",
    "normalize_prime_contract_line_item",
    "normalize_prime_contract_attachment",
    "normalize_prime_change_order",
    "normalize_prime_change_order_line_item",
    "normalize_payment_application",
]
