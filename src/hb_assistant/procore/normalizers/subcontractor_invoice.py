"""Phase 05 subcontractor-billing normalizers.

Pure functions over raw Procore payloads for the billing surface: billing periods,
subcontractor invoices (requisitions), and their three child item families
(contract / contract-detail / change-order items). Never persists, never reads
network, never echoes bodies.

Same posture as the owner / commitment normalizers: amounts / quantities / rates
kept verbatim (decimal-safe); free text (item description / comment) reduced to a
hash-only summary; parties (creator) hashed; vendor / company labels kept; the
``summary_text`` AIA cover-sheet block (subcontractor street / city / state / zip /
name) is **never carried** — address / contact content does not persist.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .financial import (
    extract_currency_config,
    extract_wbs_cost_code,
    hash_summary,
    parse_amount,
    person_hash_summary,
)

NORMALIZATION_SCHEMA_VERSION = 1

# Amounts kept verbatim (decimal-safe) per record type.
_INVOICE_SUMMARY_AMOUNTS = (
    "original_contract_sum",
    "contract_sum_to_date",
    "current_payment_due",
    "total_completed_and_stored_to_date",
    "total_retainage",
    "total_earned_less_retainage",
    "balance_to_finish_including_retainage",
)
_ITEM_AMOUNTS = (
    "scheduled_quantity",
    "scheduled_unit_price",
    "scheduled_value",
    "work_completed_this_period",
    "work_completed_from_previous_application",
    "materials_presently_stored",
    "total_completed_and_stored_to_date",
    "subcontractor_claimed_amount",
    "work_completed_retainage_retained_this_period",
    "materials_stored_retainage_currently_retained",
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
        amount = parse_amount(raw.get(key))
        if amount is not None:
            out[key] = amount


def normalize_billing_period(
    raw: Dict[str, Any], *, project_key: str, endpoint_id: str, correlation_id: str, fetched_at: str
) -> Dict[str, Any]:
    _require_id(raw, "normalize_billing_period")
    cf: Dict[str, Any] = {}
    _keep_scalars(
        raw,
        ("status", "start_date", "end_date", "due_date", "position", "updated_at"),
        cf,
    )
    return _base(
        raw,
        project_key=project_key,
        endpoint_id=endpoint_id,
        category="billing_periods",
        correlation_id=correlation_id,
        fetched_at=fetched_at,
        canonical_fields=cf,
        review_required=False,
        routing_reason="billing_period_anchor",
        entity_stable_key=str(raw["id"]),
    )


def normalize_subcontractor_invoice(
    raw: Dict[str, Any], *, project_key: str, endpoint_id: str, correlation_id: str, fetched_at: str
) -> Dict[str, Any]:
    _require_id(raw, "normalize_subcontractor_invoice")
    cf: Dict[str, Any] = {}
    _keep_scalars(
        raw,
        (
            "number",
            "invoice_number",
            "invoice_type",
            "status",
            "final",
            "billing_date",
            "requisition_start",
            "requisition_end",
            "period_id",
            "previous_requisition_id",
            "commitment_id",
            "commitment_type",
            "vendor_id",
            "percent_complete",
            "payment_date",
            "submitted_at",
            "erp_status",
            "updated_at",
        ),
        cf,
    )
    cf.update(extract_currency_config(raw))
    # Vendor / contract names are organisation labels (not PII) — kept verbatim.
    for label_key in ("vendor_name", "contract_name"):
        value = raw.get(label_key)
        if isinstance(value, str) and value:
            cf[label_key] = value
    # Creator party is hashed (PII never persists).
    person = person_hash_summary(raw.get("created_by"))
    if person is not None:
        cf["created_by_ref"] = person
    # Aggregate amount facts from the AIA summary block (decimal-safe).
    summary = raw.get("summary")
    if isinstance(summary, dict):
        summary_amounts: Dict[str, Any] = {}
        _keep_amounts(summary, _INVOICE_SUMMARY_AMOUNTS, summary_amounts)
        if summary_amounts:
            cf["summary"] = summary_amounts
    claimed = parse_amount(raw.get("total_claimed_amount"))
    if claimed is not None:
        cf["total_claimed_amount"] = claimed
    # NOTE: ``summary_text`` (subcontractor street/city/state/zip/name, GC text) is
    # address / contact content and is intentionally NOT carried.
    return _base(
        raw,
        project_key=project_key,
        endpoint_id=endpoint_id,
        category="subcontractor_invoices",
        correlation_id=correlation_id,
        fetched_at=fetched_at,
        canonical_fields=cf,
        review_required=True,
        routing_reason="subcontractor_invoice_high_sensitivity",
        entity_stable_key=str(raw["id"]),
    )


def _invoice_item_canonical(raw: Dict[str, Any]) -> Dict[str, Any]:
    cf: Dict[str, Any] = {}
    _keep_scalars(
        raw,
        (
            "position",
            "status",
            "item_type",
            "line_item_id",
            "cost_code_id",
            "detail_line_item_id",
            "change_order_package_id",
            "commitment_line_item_id",
        ),
        cf,
    )
    _keep_amounts(raw, _ITEM_AMOUNTS, cf)
    cf.update(extract_wbs_cost_code(raw))
    cf.update(extract_currency_config(raw))
    # Free text (work description / comment) is hash-only — never raw (it can carry
    # addresses / contact content).
    for text_key in ("description_of_work", "comment"):
        summary = hash_summary(raw.get(text_key))
        if summary is not None:
            cf[f"{text_key}_summary"] = summary
    return cf


def _normalize_invoice_item(
    raw: Dict[str, Any],
    *,
    project_key: str,
    endpoint_id: str,
    correlation_id: str,
    fetched_at: str,
    category: str,
    fn: str,
) -> Dict[str, Any]:
    _require_id(raw, fn)
    return _base(
        raw,
        project_key=project_key,
        endpoint_id=endpoint_id,
        category=category,
        correlation_id=correlation_id,
        fetched_at=fetched_at,
        canonical_fields=_invoice_item_canonical(raw),
        review_required=False,
        routing_reason="subcontractor_invoice_high_sensitivity",
        entity_stable_key=str(raw["id"]),
    )


def normalize_subcontractor_invoice_contract_item(
    raw: Dict[str, Any], *, project_key: str, endpoint_id: str, correlation_id: str, fetched_at: str
) -> Dict[str, Any]:
    return _normalize_invoice_item(
        raw,
        project_key=project_key,
        endpoint_id=endpoint_id,
        correlation_id=correlation_id,
        fetched_at=fetched_at,
        category="subcontractor_invoice_contract_items",
        fn="normalize_subcontractor_invoice_contract_item",
    )


def normalize_subcontractor_invoice_contract_detail_item(
    raw: Dict[str, Any], *, project_key: str, endpoint_id: str, correlation_id: str, fetched_at: str
) -> Dict[str, Any]:
    return _normalize_invoice_item(
        raw,
        project_key=project_key,
        endpoint_id=endpoint_id,
        correlation_id=correlation_id,
        fetched_at=fetched_at,
        category="subcontractor_invoice_contract_detail_items",
        fn="normalize_subcontractor_invoice_contract_detail_item",
    )


def normalize_subcontractor_invoice_change_order_item(
    raw: Dict[str, Any], *, project_key: str, endpoint_id: str, correlation_id: str, fetched_at: str
) -> Dict[str, Any]:
    return _normalize_invoice_item(
        raw,
        project_key=project_key,
        endpoint_id=endpoint_id,
        correlation_id=correlation_id,
        fetched_at=fetched_at,
        category="subcontractor_invoice_change_order_items",
        fn="normalize_subcontractor_invoice_change_order_item",
    )


__all__: List[str] = [
    "NORMALIZATION_SCHEMA_VERSION",
    "normalize_billing_period",
    "normalize_subcontractor_invoice",
    "normalize_subcontractor_invoice_contract_item",
    "normalize_subcontractor_invoice_contract_detail_item",
    "normalize_subcontractor_invoice_change_order_item",
]
