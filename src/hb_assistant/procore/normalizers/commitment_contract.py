"""Phase 05 vendor-side contract normalizers.

Pure functions over raw Procore payloads for the commitment / purchase-order
family: commitment contracts + line items + attachments + compliance, and the v1
purchase-order compatibility surface (PO contracts + line items + detail line
items). Never persists, never reads network, never echoes bodies.

Same posture as the owner-side normalizers: amounts / quantities / rates kept
verbatim (decimal-safe); free text (titles / descriptions / compliance + insurance
notes) reduced to a hash-only summary; parties reduced to opaque ids + hashed
refs; organisation / vendor labels kept (not PII); attachment URLs path-only.
Compliance keeps compliance / insurance status + document-status metadata.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .financial import (
    attachment_path,
    extract_currency_config,
    extract_wbs_cost_code,
    hash_summary,
    parse_amount,
    person_hash_summary,
)

NORMALIZATION_SCHEMA_VERSION = 1

_CONTRACT_AMOUNTS = ("grand_total", "retainage_percent")
_PO_AMOUNTS = (
    "grand_total",
    "retainage_percent",
    "total_payments",
    "remaining_balance_outstanding",
)
_LINE_ITEM_AMOUNTS = ("amount", "unit_cost", "quantity", "extended_amount", "total_amount")


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
        amount = parse_amount(raw.get(key))
        if amount is not None:
            out[key] = amount


def _summarize_into(out: Dict[str, Any], raw: Dict[str, Any], keys: Any) -> None:
    # Hash-only (no excerpt) for high-sensitivity financial free text.
    for key in keys:
        summary = hash_summary(raw.get(key))
        if summary is not None:
            out[f"{key}_summary"] = summary


def _parties_into(out: Dict[str, Any], raw: Dict[str, Any], keys: Any) -> None:
    for key in keys:
        person = person_hash_summary(raw.get(key))
        if person is not None:
            out[f"{key}_ref"] = person


def normalize_commitment_contract(
    raw: Dict[str, Any], *, project_key: str, endpoint_id: str, correlation_id: str, fetched_at: str
) -> Dict[str, Any]:
    _require_id(raw, "normalize_commitment_contract")
    cf: Dict[str, Any] = {}
    _keep_scalars(
        raw,
        ("number", "type", "status", "executed", "private", "allow_payments", "updated_at"),
        cf,
    )
    _keep_amounts(raw, _CONTRACT_AMOUNTS, cf)
    cf.update(extract_currency_config(raw))
    _summarize_into(cf, raw, ("title", "description"))
    _parties_into(cf, raw, ("created_by",))
    vendor = raw.get("vendor")
    if isinstance(vendor, dict) and vendor.get("id") is not None:
        cf["vendor_id"] = vendor["id"]
    return _base(
        raw,
        project_key=project_key,
        endpoint_id=endpoint_id,
        category="commitment_contracts",
        correlation_id=correlation_id,
        fetched_at=fetched_at,
        canonical_fields=cf,
        review_required=bool(raw.get("private")),
        routing_reason="commitment_high_sensitivity",
        entity_stable_key=str(raw["id"]),
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


def normalize_commitment_line_item(
    raw: Dict[str, Any], *, project_key: str, endpoint_id: str, correlation_id: str, fetched_at: str
) -> Dict[str, Any]:
    _require_id(raw, "normalize_commitment_line_item")
    return _base(
        raw,
        project_key=project_key,
        endpoint_id=endpoint_id,
        category="commitment_line_items",
        correlation_id=correlation_id,
        fetched_at=fetched_at,
        canonical_fields=_line_item_canonical(raw),
        review_required=False,
        routing_reason="commitment_high_sensitivity",
        entity_stable_key=str(raw["id"]),
    )


def _attachment_canonical(raw: Dict[str, Any]) -> Dict[str, Any]:
    cf: Dict[str, Any] = {}
    filename_summary = hash_summary(raw.get("filename") or raw.get("name"))
    if filename_summary is not None:
        cf["filename_summary"] = filename_summary
    for url_key in ("url", "share_url", "viewable_url"):
        path = attachment_path(raw.get(url_key))
        if path is not None:
            cf[f"{url_key}_path"] = path
    _keep_scalars(raw, ("content_type", "uuid", "created_at"), cf)
    return cf


def normalize_commitment_attachment(
    raw: Dict[str, Any], *, project_key: str, endpoint_id: str, correlation_id: str, fetched_at: str
) -> Dict[str, Any]:
    _require_id(raw, "normalize_commitment_attachment")
    return _base(
        raw,
        project_key=project_key,
        endpoint_id=endpoint_id,
        category="commitment_attachments",
        correlation_id=correlation_id,
        fetched_at=fetched_at,
        canonical_fields=_attachment_canonical(raw),
        review_required=False,
        routing_reason="commitment_attachment",
        entity_stable_key=str(raw["id"]),
    )


def _doc_status_block(docs: Any, kind: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not isinstance(docs, list):
        return out
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        entry: Dict[str, Any] = {"kind": kind}
        for key in ("id", "status", "effective_at", "expires_at"):
            if doc.get(key) is not None:
                entry[key] = doc[key]
        doc_type = doc.get("type") or doc.get("insurance_type")
        if doc_type is not None:
            entry["document_type"] = doc_type
        if doc.get("level") is not None:
            entry["level"] = doc["level"]
        out.append(entry)
    return out


def normalize_commitment_compliance(
    raw: Dict[str, Any], *, project_key: str, endpoint_id: str, correlation_id: str, fetched_at: str
) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise TypeError("normalize_commitment_compliance requires a dict payload")
    cf: Dict[str, Any] = {}
    _keep_scalars(
        raw,
        (
            "compliance_status",
            "derived_compliance_status",
            "insurance_status",
            "derived_insurance_status",
            "updated_at",
        ),
        cf,
    )
    # Notes hashed (hash/vault posture) — never raw.
    _summarize_into(cf, raw, ("compliance_notes", "insurance_notes"))
    compliance_docs = _doc_status_block(raw.get("compliance_documents"), "compliance")
    insurance_docs = _doc_status_block(raw.get("insurance_documents"), "insurance")
    cf["compliance_documents"] = compliance_docs
    cf["insurance_documents"] = insurance_docs
    cf["compliance_document_count"] = len(compliance_docs)
    cf["insurance_document_count"] = len(insurance_docs)
    # The compliance object is anchored to its contract, not a standalone id.
    contract_id = raw.get("contract_id") or raw.get("id")
    return _base(
        raw if "id" in raw else {**raw, "id": contract_id or "compliance"},
        project_key=project_key,
        endpoint_id=endpoint_id,
        category="commitment_compliance",
        correlation_id=correlation_id,
        fetched_at=fetched_at,
        canonical_fields=cf,
        review_required=True,
        routing_reason="commitment_compliance_high_sensitivity",
        entity_stable_key=str(contract_id) if contract_id is not None else "compliance",
    )


def normalize_purchase_order_contract(
    raw: Dict[str, Any], *, project_key: str, endpoint_id: str, correlation_id: str, fetched_at: str
) -> Dict[str, Any]:
    _require_id(raw, "normalize_purchase_order_contract")
    cf: Dict[str, Any] = {}
    _keep_scalars(
        raw,
        (
            "number",
            "status",
            "executed",
            "private",
            "execution_date",
            "delivery_date",
            "contract_date",
            "payment_terms",
            "percentage_paid",
            "updated_at",
        ),
        cf,
    )
    _keep_amounts(raw, _PO_AMOUNTS, cf)
    cf.update(extract_currency_config(raw))
    _summarize_into(cf, raw, ("title", "description", "ship_to_address", "bill_to_address"))
    _parties_into(cf, raw, ("assignee",))
    vendor = raw.get("vendor")
    if isinstance(vendor, dict) and vendor.get("id") is not None:
        cf["vendor_id"] = vendor["id"]
    return _base(
        raw,
        project_key=project_key,
        endpoint_id=endpoint_id,
        category="purchase_order_contracts",
        correlation_id=correlation_id,
        fetched_at=fetched_at,
        canonical_fields=cf,
        review_required=bool(raw.get("private")),
        routing_reason="purchase_order_high_sensitivity",
        entity_stable_key=str(raw["id"]),
    )


def normalize_purchase_order_line_item(
    raw: Dict[str, Any], *, project_key: str, endpoint_id: str, correlation_id: str, fetched_at: str
) -> Dict[str, Any]:
    _require_id(raw, "normalize_purchase_order_line_item")
    return _base(
        raw,
        project_key=project_key,
        endpoint_id=endpoint_id,
        category="purchase_order_line_items",
        correlation_id=correlation_id,
        fetched_at=fetched_at,
        canonical_fields=_line_item_canonical(raw),
        review_required=False,
        routing_reason="purchase_order_high_sensitivity",
        entity_stable_key=str(raw["id"]),
    )


def normalize_purchase_order_detail_line_item(
    raw: Dict[str, Any], *, project_key: str, endpoint_id: str, correlation_id: str, fetched_at: str
) -> Dict[str, Any]:
    _require_id(raw, "normalize_purchase_order_detail_line_item")
    cf: Dict[str, Any] = {}
    _keep_scalars(raw, ("line_item_id", "position", "billed_against", "billed_to_date"), cf)
    _keep_amounts(raw, ("amount",), cf)
    cf.update(extract_currency_config(raw))
    summary = hash_summary(raw.get("description"))
    if summary is not None:
        cf["description_summary"] = summary
    return _base(
        raw,
        project_key=project_key,
        endpoint_id=endpoint_id,
        category="purchase_order_detail_line_items",
        correlation_id=correlation_id,
        fetched_at=fetched_at,
        canonical_fields=cf,
        review_required=False,
        routing_reason="purchase_order_high_sensitivity",
        entity_stable_key=str(raw["id"]),
    )


__all__: List[str] = [
    "NORMALIZATION_SCHEMA_VERSION",
    "normalize_commitment_contract",
    "normalize_commitment_line_item",
    "normalize_commitment_attachment",
    "normalize_commitment_compliance",
    "normalize_purchase_order_contract",
    "normalize_purchase_order_line_item",
    "normalize_purchase_order_detail_line_item",
]
