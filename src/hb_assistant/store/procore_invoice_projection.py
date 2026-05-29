"""Phase 05 subcontractor-billing projections.

Projects billing periods, subcontractor invoices (requisitions), and their three
child item families (contract / contract-detail / change-order items) into the V9
billing tables + the V8 ``procore_financial_invoice_items`` table, with amount
facts (period- and commitment-aggregatable), relationship edges (invoice ->
commitment / billing period / previous invoice / vendor / creator), and
billing/invoice action signals.

Amounts are coerced decimal-safe (``coerce_amount`` — never float-lossy) and stored
verbatim as TEXT; item free text is reduced by the repository boundary
(``description_summary_json`` -> hash+len+excerpt); the subcontractor-invoice
``summary_text`` address / contact block is never projected. Self-contained store
module — no ``hb_assistant.procore`` import.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from .procore_enrichment import emit_action_signal, emit_record_edge
from .procore_financial_projection import (
    bool_to_int,
    coerce_amount,
    emit_amount_facts,
    is_positive_amount,
    link_record_entities,
    record_key,
)
from .procore_financials import (
    upsert_financial_billing_period,
    upsert_financial_invoice_item,
    upsert_financial_subcontractor_invoice,
)

INVOICE_ENDPOINTS = frozenset(
    {
        "billing-periods",
        "subcontractor-invoices",
        "subcontractor-invoice-contract-items",
        "subcontractor-invoice-contract-detail-items",
        "subcontractor-invoice-change-order-items",
    }
)

_BILLING_OPEN = {"open", "draft", "active"}
_BILLING_CLOSED = {"closed", "completed", "paid"}
_INVOICE_PENDING = {
    "draft", "under_review", "pending", "submitted", "revise_and_resubmit", "in_review",
}
_INVOICE_PAID = {"paid"}
_DUE_SOON_DAYS = 7


def _drop_none(fields: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in fields.items() if v is not None}


def _currency_iso(raw: Mapping[str, Any]) -> Optional[str]:
    cc = raw.get("currency_configuration")
    src: Mapping[str, Any] = cc if isinstance(cc, dict) else raw
    iso = src.get("currency_iso_code") or raw.get("currency_iso_code")
    return iso if isinstance(iso, str) and iso else None


def _wbs_full(raw: Mapping[str, Any]) -> Dict[str, Optional[str]]:
    """WBS / cost-code identifiers (for amount facts; flat code for item columns)."""
    out: Dict[str, Optional[str]] = {"wbs_code_id": None, "wbs_flat_code": None, "cost_code_id": None}
    wbs = raw.get("wbs_code")
    if isinstance(wbs, dict):
        if wbs.get("id") is not None:
            out["wbs_code_id"] = str(wbs["id"])
        if isinstance(wbs.get("flat_code"), str) and wbs["flat_code"]:
            out["wbs_flat_code"] = wbs["flat_code"]
    cost = raw.get("cost_code")
    if isinstance(cost, dict) and cost.get("id") is not None:
        out["cost_code_id"] = str(cost["id"])
    elif raw.get("cost_code_id") is not None:
        out["cost_code_id"] = str(raw["cost_code_id"])
    return out


def _emit_facts(
    *,
    project_key: str,
    rk: str,
    endpoint_id: str,
    table: str,
    fields: Mapping[str, Any],
    amount_keys: Any,
    now_utc: str,
    currency_iso_code: Optional[str],
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
    wbs_code_id: Optional[str] = None,
    cost_code_id: Optional[str] = None,
    db_path: Optional[Path],
) -> None:
    facts: List[Dict[str, Any]] = []
    for key in amount_keys:
        value = fields.get(key)
        if value is None:
            continue
        facts.append(
            {
                "amount_name": key,
                "amount_value": value,
                "source_field_path": f"{table}.{key}",
                "period_start": period_start,
                "period_end": period_end,
                "wbs_code_id": wbs_code_id,
                "cost_code_id": cost_code_id,
            }
        )
    if facts:
        emit_amount_facts(
            project_key=project_key, record_key=rk, endpoint_id=endpoint_id, facts=facts,
            created_at_utc=now_utc, currency_iso_code=currency_iso_code, db_path=db_path,
        )


def _days_until(date_str: Any, now_utc: str) -> Optional[int]:
    try:
        target = date.fromisoformat(str(date_str)[:10])
        today = date.fromisoformat(str(now_utc)[:10])
    except (ValueError, TypeError):
        return None
    return (target - today).days


def _vendor_ref(raw: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    if raw.get("vendor_id") is None:
        return None
    return {"id": raw.get("vendor_id"), "name": raw.get("vendor_name")}


def _project_billing_period(
    raw: Mapping[str, Any], *, project_key: str, now_utc: str, db_path: Optional[Path]
) -> Dict[str, Any]:
    pid = str(raw["id"])
    bp_key = record_key(project_key, "billing-periods", None, pid)
    fields = _drop_none(
        {
            "status": raw.get("status"),
            "start_date": raw.get("start_date"),
            "end_date": raw.get("end_date"),
            "due_date": raw.get("due_date"),
            "position": raw.get("position"),
            "updated_at_utc": raw.get("updated_at"),
        }
    )
    upsert_financial_billing_period(
        billing_period_key=bp_key, project_key=project_key, endpoint_id="billing-periods",
        billing_period_id=pid, fields=fields, db_path=db_path,
    )
    signals: List[str] = []
    status = str(raw.get("status") or "").strip().lower()
    if status in _BILLING_OPEN:
        emit_action_signal(
            project_key=project_key, record_key=bp_key, endpoint_id="billing-periods",
            signal_type="billing_period_open", importance="low", now_utc=now_utc, db_path=db_path,
        )
        signals.append("billing_period_open")
    days = _days_until(raw.get("due_date"), now_utc)
    if days is not None and days <= _DUE_SOON_DAYS and status not in _BILLING_CLOSED:
        emit_action_signal(
            project_key=project_key, record_key=bp_key, endpoint_id="billing-periods",
            signal_type="billing_period_due_soon", importance="medium", now_utc=now_utc, db_path=db_path,
        )
        signals.append("billing_period_due_soon")
    return {"projected": True, "record_key": bp_key, "signals": signals}


def _project_subcontractor_invoice(
    raw: Mapping[str, Any], *, project_key: str, sync_run_id: Optional[str], now_utc: str,
    db_path: Optional[Path],
) -> Dict[str, Any]:
    iid = str(raw["id"])
    inv_rk = record_key(project_key, "subcontractor-invoices", None, iid)
    commitment_id = raw.get("commitment_id")
    commitment_rk = (
        record_key(project_key, "commitment-contracts", None, str(commitment_id))
        if commitment_id is not None else None
    )
    period_id = raw.get("period_id")
    billing_period_key = (
        record_key(project_key, "billing-periods", None, str(period_id))
        if period_id is not None else None
    )
    prev_id = raw.get("previous_requisition_id")
    # Link entities first so the vendor entity key can be stored on the row.
    linked = link_record_entities(
        project_key=project_key, record_key=inv_rk, endpoint_id="subcontractor-invoices",
        people={"created_by": raw.get("created_by")},
        companies={"vendor": _vendor_ref(raw)},
        now_utc=now_utc, db_path=db_path,
    )
    vendor_keys = linked.get("vendor") or []
    summary = raw.get("summary") if isinstance(raw.get("summary"), dict) else {}
    fields = _drop_none(
        {
            "commitment_record_key": commitment_rk,
            "commitment_id": str(commitment_id) if commitment_id is not None else None,
            "billing_period_key": billing_period_key,
            "billing_period_id": str(period_id) if period_id is not None else None,
            "previous_invoice_id": str(prev_id) if prev_id is not None else None,
            "vendor_id": str(raw["vendor_id"]) if raw.get("vendor_id") is not None else None,
            "vendor_entity_key": vendor_keys[0] if vendor_keys else None,
            "invoice_number": str(raw["invoice_number"]) if raw.get("invoice_number") is not None else None,
            "number": str(raw["number"]) if raw.get("number") is not None else None,
            "invoice_type": raw.get("invoice_type"),
            "status": raw.get("status"),
            "final": bool_to_int(raw.get("final")),
            "billing_date": raw.get("billing_date"),
            "period_start": raw.get("requisition_start"),
            "period_end": raw.get("requisition_end"),
            "percent_complete": coerce_amount(raw.get("percent_complete")),
            "payment_date": raw.get("payment_date"),
            "submitted_at": raw.get("submitted_at"),
            "erp_status": raw.get("erp_status"),
            "current_payment_due": coerce_amount(summary.get("current_payment_due")),
            "total_claimed_amount": coerce_amount(raw.get("total_claimed_amount")),
            "original_contract_sum": coerce_amount(summary.get("original_contract_sum")),
            "contract_sum_to_date": coerce_amount(summary.get("contract_sum_to_date")),
            "total_completed_and_stored_to_date": coerce_amount(
                summary.get("total_completed_and_stored_to_date")
            ),
            "total_retainage": coerce_amount(summary.get("total_retainage")),
            "total_earned_less_retainage": coerce_amount(summary.get("total_earned_less_retainage")),
            "balance_to_finish_including_retainage": coerce_amount(
                summary.get("balance_to_finish_including_retainage")
            ),
            "updated_at_utc": raw.get("updated_at"),
        }
    )
    upsert_financial_subcontractor_invoice(
        record_key=inv_rk, project_key=project_key, endpoint_id="subcontractor-invoices",
        invoice_id=iid, fields=fields, db_path=db_path,
    )
    _emit_facts(
        project_key=project_key, rk=inv_rk, endpoint_id="subcontractor-invoices",
        table="procore_financial_subcontractor_invoices", fields=fields,
        amount_keys=(
            "current_payment_due", "total_claimed_amount", "total_retainage",
            "total_completed_and_stored_to_date", "contract_sum_to_date",
        ),
        now_utc=now_utc, currency_iso_code=_currency_iso(raw),
        period_start=raw.get("requisition_start"), period_end=raw.get("requisition_end"),
        db_path=db_path,
    )
    if commitment_rk:
        emit_record_edge(
            project_key=project_key, from_record_key=inv_rk, edge_type="invoice_of",
            source_endpoint_id="subcontractor-invoices", to_record_key=commitment_rk,
            now_utc=now_utc, db_path=db_path,
        )
    if billing_period_key:
        emit_record_edge(
            project_key=project_key, from_record_key=inv_rk, edge_type="billed_in_period",
            source_endpoint_id="subcontractor-invoices", to_record_key=billing_period_key,
            now_utc=now_utc, db_path=db_path,
        )
    if prev_id is not None:
        emit_record_edge(
            project_key=project_key, from_record_key=inv_rk, edge_type="supersedes",
            source_endpoint_id="subcontractor-invoices",
            to_record_key=record_key(project_key, "subcontractor-invoices", None, str(prev_id)),
            now_utc=now_utc, db_path=db_path,
        )
    signals: List[str] = []

    def _sig(signal_type: str, importance: str) -> None:
        emit_action_signal(project_key=project_key, record_key=inv_rk,
                           endpoint_id="subcontractor-invoices", signal_type=signal_type,
                           importance=importance, now_utc=now_utc, db_path=db_path)
        signals.append(signal_type)

    status = str(raw.get("status") or "").strip().lower()
    paid = status in _INVOICE_PAID or raw.get("payment_date") not in (None, "")
    if status in _INVOICE_PENDING:
        _sig("invoice_pending_approval", "medium")
    if status == "approved" and not paid:
        _sig("invoice_approved_not_paid", "high")
    if raw.get("final"):
        _sig("invoice_final", "low")
    if is_positive_amount(summary.get("total_retainage")):
        _sig("invoice_retainage_held", "medium")
    if is_positive_amount(summary.get("current_payment_due")):
        _sig("invoice_payment_due", "high")
    return {"projected": True, "record_key": inv_rk, "signals": signals}


def _project_invoice_item(
    raw: Mapping[str, Any], *, endpoint_id: str, parent_procore_id: Optional[str],
    project_key: str, now_utc: str, db_path: Optional[Path],
) -> Dict[str, Any]:
    lid = str(raw["id"])
    parent = parent_procore_id or (
        str(raw.get("requisition_id")) if raw.get("requisition_id") is not None else None
    )
    inv_rk = record_key(project_key, "subcontractor-invoices", None, parent) if parent else ""
    li_key = record_key(project_key, endpoint_id, parent, lid)
    wbs = _wbs_full(raw)
    retainage = coerce_amount(raw.get("work_completed_retainage_retained_this_period"))
    fields = _drop_none(
        {
            "invoice_record_key": inv_rk or None,
            "requisition_id": parent,
            "item_type": raw.get("item_type"),
            "line_item_id": str(raw["line_item_id"]) if raw.get("line_item_id") is not None else None,
            "cost_code_id": wbs["cost_code_id"],
            "wbs_flat_code": wbs["wbs_flat_code"],
            "description_summary_json": raw.get("description_of_work"),  # repo -> hash+len+excerpt
            "scheduled_value": coerce_amount(raw.get("scheduled_value")),
            "work_completed_this_period": coerce_amount(raw.get("work_completed_this_period")),
            "materials_presently_stored": coerce_amount(raw.get("materials_presently_stored")),
            "total_completed_and_stored_to_date": coerce_amount(
                raw.get("total_completed_and_stored_to_date")
            ),
            "retainage_held": retainage,
            "subcontractor_claimed_amount": coerce_amount(raw.get("subcontractor_claimed_amount")),
            "status": raw.get("status"),
            "position": raw.get("position"),
        }
    )
    upsert_financial_invoice_item(
        invoice_item_key=li_key, project_key=project_key, endpoint_id=endpoint_id,
        item_id=lid, fields=fields, db_path=db_path,
    )
    _emit_facts(
        project_key=project_key, rk=li_key, endpoint_id=endpoint_id,
        table="procore_financial_invoice_items", fields=fields,
        amount_keys=(
            "scheduled_value", "work_completed_this_period", "materials_presently_stored",
            "total_completed_and_stored_to_date", "subcontractor_claimed_amount", "retainage_held",
        ),
        now_utc=now_utc, currency_iso_code=_currency_iso(raw),
        wbs_code_id=wbs["wbs_code_id"], cost_code_id=wbs["cost_code_id"], db_path=db_path,
    )
    if inv_rk and is_positive_amount(raw.get("materials_presently_stored")):
        emit_action_signal(
            project_key=project_key, record_key=inv_rk, endpoint_id=endpoint_id,
            signal_type="invoice_materials_stored", importance="low", now_utc=now_utc, db_path=db_path,
        )
        return {"projected": True, "record_key": li_key, "signals": ["invoice_materials_stored"]}
    return {"projected": True, "record_key": li_key, "signals": []}


_ITEM_ENDPOINTS = frozenset(
    {
        "subcontractor-invoice-contract-items",
        "subcontractor-invoice-contract-detail-items",
        "subcontractor-invoice-change-order-items",
    }
)


def project_invoice_family(
    endpoint_id: str,
    raw: Mapping[str, Any],
    *,
    project_key: str,
    sync_run_id: Optional[str] = None,
    now_utc: str,
    db_path: Optional[Path] = None,
    parent_procore_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Dispatch a raw billing / subcontractor-invoice payload to its projection."""
    if not isinstance(raw, dict) or raw.get("id") in (None, ""):
        return {"projected": False}
    if endpoint_id == "billing-periods":
        return _project_billing_period(
            raw, project_key=project_key, now_utc=now_utc, db_path=db_path
        )
    if endpoint_id == "subcontractor-invoices":
        return _project_subcontractor_invoice(
            raw, project_key=project_key, sync_run_id=sync_run_id, now_utc=now_utc, db_path=db_path
        )
    if endpoint_id in _ITEM_ENDPOINTS:
        return _project_invoice_item(
            raw, endpoint_id=endpoint_id, parent_procore_id=parent_procore_id,
            project_key=project_key, now_utc=now_utc, db_path=db_path,
        )
    return {"projected": False}


__all__ = ["INVOICE_ENDPOINTS", "project_invoice_family"]
