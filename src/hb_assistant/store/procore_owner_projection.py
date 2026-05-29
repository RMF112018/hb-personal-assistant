"""Phase 05 owner-side financial projections.

Projects prime contracts, their line items + attachments, prime change orders +
CO line items, and payment applications (raw payloads) into the V8 financial
tables, emits amount facts (contract totals, approved COs, grand totals, payment
due, retainage, balance to finish), relationship edges (contract -> architect /
contractor / vendor / created_by / attachments / change orders / payment
applications), and owner-side action signals.

Amounts are coerced decimal-safe (``coerce_amount`` — never float-lossy) and
stored verbatim as TEXT; free text / titles / notes are reduced by the repository
boundary (``title_redacted`` excerpt-masked, ``description_summary_json`` ->
hash+len+excerpt) and attachment URLs are path-only. Self-contained store module —
no ``hb_assistant.procore`` import.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from .procore_enrichment import emit_action_signal, emit_record_edge, extract_attachment_refs
from .procore_financial_projection import (
    bool_to_int,
    coerce_amount,
    emit_amount_facts,
    is_positive_amount,
    link_record_entities,
    record_key,
)
from .procore_financials import (
    upsert_financial_change_order,
    upsert_financial_change_order_line_item,
    upsert_financial_contract,
    upsert_financial_line_item,
    upsert_financial_payment_application,
)

OWNER_ENDPOINTS = frozenset(
    {
        "prime-contracts",
        "prime-contract-line-items",
        "prime-contract-attachments",
        "prime-change-orders",
        "prime-change-order-line-items",
        "payment-applications",
    }
)

_CLOSED_PAID = {"paid", "closed"}
_CO_BILLABLE = {"approved", "executed", "closed"}


def _drop_none(fields: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in fields.items() if v is not None}


def _currency(raw: Mapping[str, Any]) -> Dict[str, Any]:
    cc = raw.get("currency_configuration")
    src: Mapping[str, Any] = cc if isinstance(cc, dict) else raw
    out: Dict[str, Any] = {}
    iso = src.get("currency_iso_code") or raw.get("currency_iso_code")
    if isinstance(iso, str) and iso:
        out["currency_iso_code"] = iso
    base = src.get("base_currency_iso_code")
    if isinstance(base, str) and base:
        out["base_currency_iso_code"] = base
    rate = coerce_amount(src.get("currency_exchange_rate"))
    if rate is not None:
        out["currency_exchange_rate"] = rate
    return out


def _wbs(raw: Mapping[str, Any], *, include_description: bool) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    wbs = raw.get("wbs_code")
    if isinstance(wbs, dict):
        if wbs.get("id") is not None:
            out["wbs_code_id"] = str(wbs["id"])
        if isinstance(wbs.get("flat_code"), str) and wbs["flat_code"]:
            out["wbs_flat_code"] = wbs["flat_code"]
        if include_description and isinstance(wbs.get("description"), str) and wbs["description"]:
            out["wbs_description_redacted"] = wbs["description"]
    elif raw.get("wbs_code_id") is not None:
        out["wbs_code_id"] = str(raw["wbs_code_id"])
    for code_key, scalar in (("cost_code_id", "cost_code_id"), ("line_item_type_id", "line_item_type_id")):
        if raw.get(scalar) is not None:
            out[code_key] = str(raw[scalar])
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
    db_path: Optional[Path],
) -> None:
    facts: List[Dict[str, Any]] = []
    for key in amount_keys:
        value = fields.get(key)
        if value is None:
            continue
        facts.append(
            {"amount_name": key, "amount_value": value, "source_field_path": f"{table}.{key}"}
        )
    if facts:
        emit_amount_facts(
            project_key=project_key,
            record_key=rk,
            endpoint_id=endpoint_id,
            facts=facts,
            created_at_utc=now_utc,
            currency_iso_code=currency_iso_code,
            db_path=db_path,
        )


def _project_prime_contract(
    raw: Mapping[str, Any], *, project_key: str, sync_run_id: Optional[str], now_utc: str, db_path: Optional[Path]
) -> Dict[str, Any]:
    cid = str(raw["id"])
    rk = record_key(project_key, "prime-contracts", None, cid)
    currency = _currency(raw)
    fields = _drop_none(
        {
            "number": raw.get("number"),
            "title_redacted": raw.get("title"),
            "status": raw.get("status"),
            "executed": bool_to_int(raw.get("executed")),
            "private": bool_to_int(raw.get("private")),
            "accounting_method": raw.get("accounting_method"),
            "grand_total": coerce_amount(raw.get("grand_total")),
            "original_contract_sum": coerce_amount(raw.get("original_contract_amount")),
            "revised_contract_sum": coerce_amount(
                raw.get("revised_contract_amount") or raw.get("pending_revised_contract_amount")
            ),
            "approved_change_orders_amount": coerce_amount(raw.get("approved_change_orders")),
            "retainage_percent": coerce_amount(raw.get("retainage_percent")),
            "contract_date": raw.get("contract_date"),
            "start_date": raw.get("contract_start_date"),
            "completion_date": raw.get("contract_estimated_completion_date"),
            "updated_at_utc": raw.get("updated_at"),
            "last_sync_run_id": sync_run_id,
            **currency,
        }
    )
    upsert_financial_contract(
        record_key=rk, project_key=project_key, endpoint_id="prime-contracts",
        contract_id=cid, contract_family="owner", fields=fields, db_path=db_path,
    )
    _emit_facts(
        project_key=project_key, rk=rk, endpoint_id="prime-contracts",
        table="procore_financial_contracts", fields=fields,
        amount_keys=("grand_total", "original_contract_sum", "revised_contract_sum",
                     "approved_change_orders_amount", "retainage_percent"),
        now_utc=now_utc, currency_iso_code=currency.get("currency_iso_code"), db_path=db_path,
    )
    link_record_entities(
        project_key=project_key, record_key=rk, endpoint_id="prime-contracts",
        people={"architect": raw.get("architect"), "created_by": raw.get("created_by")},
        companies={"contractor": raw.get("contractor"), "vendor": raw.get("vendor")},
        now_utc=now_utc, db_path=db_path,
    )
    extract_attachment_refs(
        raw.get("attachments"), project_key=project_key, source_record_key=rk,
        source_endpoint_id="prime-contracts", sensitivity="high", now_utc=now_utc, db_path=db_path,
    )
    signals: List[str] = []
    if not raw.get("executed"):
        emit_action_signal(project_key=project_key, record_key=rk, endpoint_id="prime-contracts",
                           signal_type="prime_contract_unexecuted", importance="high",
                           now_utc=now_utc, db_path=db_path)
        signals.append("prime_contract_unexecuted")
    if raw.get("private"):
        emit_action_signal(project_key=project_key, record_key=rk, endpoint_id="prime-contracts",
                           signal_type="prime_contract_private", importance="low",
                           now_utc=now_utc, db_path=db_path)
        signals.append("prime_contract_private")
    return {"projected": True, "record_key": rk, "signals": signals}


def _project_line_item(
    raw: Mapping[str, Any], *, endpoint_id: str, parent_endpoint: str, line_item_kind: str,
    parent_procore_id: Optional[str], project_key: str, now_utc: str, db_path: Optional[Path]
) -> Dict[str, Any]:
    lid = str(raw["id"])
    parent = parent_procore_id or (
        str(raw.get("prime_contract_id") or raw.get("contract_id"))
        if (raw.get("prime_contract_id") or raw.get("contract_id")) is not None
        else None
    )
    parent_rk = record_key(project_key, parent_endpoint, None, parent) if parent else ""
    li_key = record_key(project_key, endpoint_id, parent, lid)
    # Financial line-item rows carry structured facts only; the description's
    # hash-only summary lives in procore_live_records via the normalizer.
    fields = _drop_none(
        {
            "amount": coerce_amount(raw.get("amount")),
            "unit_cost": coerce_amount(raw.get("unit_cost")),
            "quantity": coerce_amount(raw.get("quantity")),
            "uom": raw.get("uom"),
            "position": raw.get("position"),
            **_wbs(raw, include_description=True),
            **_currency(raw),
        }
    )
    upsert_financial_line_item(
        line_item_key=li_key, project_key=project_key, parent_record_key=parent_rk,
        endpoint_id=endpoint_id, line_item_id=lid, line_item_kind=line_item_kind,
        fields=fields, db_path=db_path,
    )
    _emit_facts(
        project_key=project_key, rk=li_key, endpoint_id=endpoint_id,
        table="procore_financial_line_items", fields=fields, amount_keys=("amount",),
        now_utc=now_utc, currency_iso_code=_currency(raw).get("currency_iso_code"), db_path=db_path,
    )
    return {"projected": True, "record_key": li_key, "signals": []}


def _project_attachment(
    raw: Mapping[str, Any], *, parent_procore_id: Optional[str], project_key: str, now_utc: str,
    db_path: Optional[Path]
) -> Dict[str, Any]:
    parent_rk = (
        record_key(project_key, "prime-contracts", None, parent_procore_id)
        if parent_procore_id else ""
    )
    keys = extract_attachment_refs(
        [raw], project_key=project_key, source_record_key=parent_rk,
        source_endpoint_id="prime-contract-attachments", sensitivity="high",
        now_utc=now_utc, db_path=db_path,
    )
    return {"projected": bool(keys), "record_key": parent_rk, "signals": []}


def _project_prime_change_order(
    raw: Mapping[str, Any], *, project_key: str, sync_run_id: Optional[str], now_utc: str,
    db_path: Optional[Path]
) -> Dict[str, Any]:
    coid = str(raw["id"])
    co_rk = record_key(project_key, "prime-change-orders", None, coid)
    contract_id = raw.get("contract_id")
    contract_rk = (
        record_key(project_key, "prime-contracts", None, str(contract_id))
        if contract_id is not None else None
    )
    currency = _currency(raw)
    fields = _drop_none(
        {
            "contract_record_key": contract_rk,
            "contract_id": str(contract_id) if contract_id is not None else None,
            "number": raw.get("number"),
            "title_redacted": raw.get("title"),
            "status": raw.get("status"),
            "executed": bool_to_int(raw.get("executed")),
            "paid": bool_to_int(raw.get("paid")),
            "private": bool_to_int(raw.get("private")),
            "field_change": bool_to_int(raw.get("field_change")),
            "signature_required": bool_to_int(raw.get("signature_required")),
            "grand_total": coerce_amount(raw.get("grand_total")),
            "schedule_impact_amount": coerce_amount(raw.get("schedule_impact_amount")),
            "due_date": raw.get("due_date"),
            "invoiced_date": raw.get("invoiced_date"),
            "paid_date": raw.get("paid_date"),
            "reviewed_at_utc": raw.get("reviewed_at"),
            "updated_at_utc": raw.get("updated_at"),
        }
    )
    upsert_financial_change_order(
        record_key=co_rk, project_key=project_key, endpoint_id="prime-change-orders",
        change_order_id=coid, change_order_family="prime", fields=fields, db_path=db_path,
    )
    _emit_facts(
        project_key=project_key, rk=co_rk, endpoint_id="prime-change-orders",
        table="procore_financial_change_orders", fields=fields,
        amount_keys=("grand_total", "schedule_impact_amount"),
        now_utc=now_utc, currency_iso_code=currency.get("currency_iso_code"), db_path=db_path,
    )
    link_record_entities(
        project_key=project_key, record_key=co_rk, endpoint_id="prime-change-orders",
        people={
            "created_by": raw.get("created_by"), "received_from": raw.get("received_from"),
            "designated_reviewer": raw.get("designated_reviewer"), "reviewed_by": raw.get("reviewed_by"),
        },
        now_utc=now_utc, db_path=db_path,
    )
    if contract_rk:
        emit_record_edge(
            project_key=project_key, from_record_key=co_rk, edge_type="change_order_of",
            source_endpoint_id="prime-change-orders", to_record_key=contract_rk,
            now_utc=now_utc, db_path=db_path,
        )
    signals: List[str] = []

    def _sig(signal_type: str, importance: str) -> None:
        emit_action_signal(project_key=project_key, record_key=co_rk, endpoint_id="prime-change-orders",
                           signal_type=signal_type, importance=importance, now_utc=now_utc, db_path=db_path)
        signals.append(signal_type)

    status = str(raw.get("status") or "").strip().lower()
    if not raw.get("executed") and raw.get("signature_required"):
        _sig("prime_change_order_unexecuted", "high")
    if not raw.get("paid") and (raw.get("invoiced_date") or status in _CO_BILLABLE):
        _sig("prime_change_order_unpaid", "high")
    if is_positive_amount(raw.get("schedule_impact_amount")):
        _sig("prime_change_order_schedule_impact", "medium")
    return {"projected": True, "record_key": co_rk, "signals": signals}


def _project_co_line_item(
    raw: Mapping[str, Any], *, parent_procore_id: Optional[str], project_key: str, now_utc: str,
    db_path: Optional[Path]
) -> Dict[str, Any]:
    lid = str(raw["id"])
    parent = parent_procore_id or (
        str(raw.get("change_order_id")) if raw.get("change_order_id") is not None else None
    )
    co_rk = record_key(project_key, "prime-change-orders", None, parent) if parent else ""
    li_key = record_key(project_key, "prime-change-order-line-items", parent, lid)
    fields = _drop_none(
        {
            "amount": coerce_amount(raw.get("amount")),
            "unit_cost": coerce_amount(raw.get("unit_cost")),
            "quantity": coerce_amount(raw.get("quantity")),
            "uom": raw.get("uom"),
            "position": raw.get("position"),
            **_wbs(raw, include_description=False),
            **_currency(raw),
        }
    )
    upsert_financial_change_order_line_item(
        line_item_key=li_key, project_key=project_key, change_order_record_key=co_rk,
        endpoint_id="prime-change-order-line-items", line_item_id=lid, change_order_family="prime",
        fields=fields, db_path=db_path,
    )
    _emit_facts(
        project_key=project_key, rk=li_key, endpoint_id="prime-change-order-line-items",
        table="procore_financial_change_order_line_items", fields=fields, amount_keys=("amount",),
        now_utc=now_utc, currency_iso_code=_currency(raw).get("currency_iso_code"), db_path=db_path,
    )
    return {"projected": True, "record_key": li_key, "signals": []}


def _project_payment_application(
    raw: Mapping[str, Any], *, project_key: str, now_utc: str, db_path: Optional[Path]
) -> Dict[str, Any]:
    pid = str(raw["id"])
    pa_rk = record_key(project_key, "payment-applications", None, pid)
    g702 = raw.get("g702") if isinstance(raw.get("g702"), dict) else {}
    contract = raw.get("contract")
    contract_id = (
        contract.get("id") if isinstance(contract, dict) else raw.get("prime_contract_id")
    )
    contract_rk = (
        record_key(project_key, "prime-contracts", None, str(contract_id))
        if contract_id is not None else None
    )
    fields = _drop_none(
        {
            "contract_record_key": contract_rk,
            "prime_contract_id": str(contract_id) if contract_id is not None else None,
            "billing_period_id": str(raw["period_id"]) if raw.get("period_id") is not None else None,
            "invoice_number": str(raw["invoice_number"]) if raw.get("invoice_number") is not None else None,
            "number": str(raw["number"]) if raw.get("number") is not None else None,
            "status": raw.get("status"),
            "billing_date": raw.get("billing_date"),
            "period_start": raw.get("period_start"),
            "period_end": raw.get("period_end"),
            "percent_complete": coerce_amount(raw.get("percent_complete")),
            "current_payment_due": coerce_amount(g702.get("current_payment_due")),
            "total_amount_paid": coerce_amount(raw.get("total_amount_paid")),
            "total_retainage": coerce_amount(g702.get("total_retainage")),
            "balance_to_finish_including_retainage": coerce_amount(
                g702.get("balance_to_finish_including_retainage")
            ),
            "contract_sum_to_date": coerce_amount(g702.get("contract_sum_to_date")),
            "updated_at_utc": raw.get("updated_at"),
        }
    )
    upsert_financial_payment_application(
        record_key=pa_rk, project_key=project_key, endpoint_id="payment-applications",
        payment_application_id=pid, fields=fields, db_path=db_path,
    )
    _emit_facts(
        project_key=project_key, rk=pa_rk, endpoint_id="payment-applications",
        table="procore_financial_payment_applications", fields=fields,
        amount_keys=("current_payment_due", "total_retainage",
                     "balance_to_finish_including_retainage", "total_amount_paid"),
        now_utc=now_utc, currency_iso_code=None, db_path=db_path,
    )
    if contract_rk:
        emit_record_edge(
            project_key=project_key, from_record_key=pa_rk, edge_type="payment_application_of",
            source_endpoint_id="payment-applications", to_record_key=contract_rk,
            now_utc=now_utc, db_path=db_path,
        )
    signals: List[str] = []
    status = str(raw.get("status") or "").strip().lower()
    if status not in _CLOSED_PAID:
        emit_action_signal(project_key=project_key, record_key=pa_rk, endpoint_id="payment-applications",
                           signal_type="payment_application_pending_or_unpaid", importance="medium",
                           now_utc=now_utc, db_path=db_path)
        signals.append("payment_application_pending_or_unpaid")
    if is_positive_amount(g702.get("total_retainage")):
        emit_action_signal(project_key=project_key, record_key=pa_rk, endpoint_id="payment-applications",
                           signal_type="payment_application_retainage_held", importance="medium",
                           now_utc=now_utc, db_path=db_path)
        signals.append("payment_application_retainage_held")
    return {"projected": True, "record_key": pa_rk, "signals": signals}


def project_owner_contract_family(
    endpoint_id: str,
    raw: Mapping[str, Any],
    *,
    project_key: str,
    sync_run_id: Optional[str] = None,
    now_utc: str,
    db_path: Optional[Path] = None,
    parent_procore_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Dispatch a raw owner-family payload to its financial projection."""
    if not isinstance(raw, dict) or raw.get("id") in (None, ""):
        return {"projected": False}
    if endpoint_id == "prime-contracts":
        return _project_prime_contract(
            raw, project_key=project_key, sync_run_id=sync_run_id, now_utc=now_utc, db_path=db_path
        )
    if endpoint_id == "prime-contract-line-items":
        return _project_line_item(
            raw, endpoint_id="prime-contract-line-items", parent_endpoint="prime-contracts",
            line_item_kind="prime_contract", parent_procore_id=parent_procore_id,
            project_key=project_key, now_utc=now_utc, db_path=db_path,
        )
    if endpoint_id == "prime-contract-attachments":
        return _project_attachment(
            raw, parent_procore_id=parent_procore_id, project_key=project_key,
            now_utc=now_utc, db_path=db_path,
        )
    if endpoint_id == "prime-change-orders":
        return _project_prime_change_order(
            raw, project_key=project_key, sync_run_id=sync_run_id, now_utc=now_utc, db_path=db_path
        )
    if endpoint_id == "prime-change-order-line-items":
        return _project_co_line_item(
            raw, parent_procore_id=parent_procore_id, project_key=project_key,
            now_utc=now_utc, db_path=db_path,
        )
    if endpoint_id == "payment-applications":
        return _project_payment_application(
            raw, project_key=project_key, now_utc=now_utc, db_path=db_path
        )
    return {"projected": False}


__all__ = ["OWNER_ENDPOINTS", "project_owner_contract_family"]
