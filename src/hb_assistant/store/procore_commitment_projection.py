"""Phase 05 vendor-side financial projections.

Projects commitment contracts + line items + attachments + compliance, and the v1
purchase-order compatibility surface (PO contracts + line items + detail line
items) into the V8 financial tables, with amount facts, relationship edges,
compliance-document rows, and vendor-side signals.

Commitment-vs-PO de-duplication: PO contracts are a compatibility/backfill
surface. The dedup is **data-driven** — a PO is treated as a duplicate only when a
commitment contract with the same ``(project_key, contract_id)`` already exists
(i.e. v2 ``commitment_contracts`` covered it). In that case the PO row is still
stored (queryable) but its amount facts are NOT emitted, so committed cost is
never double-counted. This self-corrects regardless of whether v2 covers POs in a
given tenant; live coverage determination is deferred to operator smoke (Prompt 10).

Self-contained store module — no ``hb_assistant.procore`` import. Amounts are
decimal-safe TEXT; free text / compliance notes are hash-only or omitted;
attachment URLs are path-only.
"""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from .connection import get_connection
from .procore_enrichment import emit_action_signal, emit_record_edge, extract_attachment_refs
from .procore_financial_projection import (
    bool_to_int,
    coerce_amount,
    emit_amount_facts,
    link_record_entities,
    record_key,
)
from .procore_financials import (
    upsert_financial_compliance_document,
    upsert_financial_contract,
    upsert_financial_line_item,
)

COMMITMENT_ENDPOINTS = frozenset(
    {
        "commitment-contracts",
        "commitment-line-items",
        "commitment-attachments",
        "commitment-compliance",
        "purchase-order-contracts",
        "purchase-order-line-items",
        "purchase-order-detail-line-items",
    }
)

_PO_PROCESSING = {
    "draft", "pending", "under_review", "approved_pending_signature",
    "processing", "in_review", "submitted",
}
_PO_TERMINAL = {"closed", "completed", "cancelled", "canceled", "void", "paid"}
_COMPLIANT = {"compliant", "approved", "active", "valid"}


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
    cost = raw.get("cost_code")
    if isinstance(cost, dict) and cost.get("id") is not None:
        out["cost_code_id"] = str(cost["id"])
    elif raw.get("cost_code_id") is not None:
        out["cost_code_id"] = str(raw["cost_code_id"])
    if raw.get("tax_code_id") is not None:
        out["tax_code_id"] = str(raw["tax_code_id"])
    return out


def _emit_facts(
    *, project_key: str, rk: str, endpoint_id: str, table: str, fields: Mapping[str, Any],
    amount_keys: Any, now_utc: str, currency_iso_code: Optional[str], db_path: Optional[Path],
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
            project_key=project_key, record_key=rk, endpoint_id=endpoint_id, facts=facts,
            created_at_utc=now_utc, currency_iso_code=currency_iso_code, db_path=db_path,
        )


def _note_hash(value: Any) -> Optional[str]:
    """Hash-only summary string for a notes column (no raw text / no excerpt)."""
    if value is None:
        return None
    text = value if isinstance(value, str) else str(value)
    if not text:
        return None
    return f"h:{hashlib.sha256(text.encode('utf-8', errors='ignore')).hexdigest()[:16]}:{len(text)}"


def _days_until(date_str: Any, now_utc: str) -> Optional[int]:
    try:
        target = date.fromisoformat(str(date_str)[:10])
        today = date.fromisoformat(str(now_utc)[:10])
    except (ValueError, TypeError):
        return None
    return (target - today).days


def _commitment_exists(project_key: str, contract_id: str, db_path: Optional[Path]) -> bool:
    conn = get_connection(db_path)
    row = conn.execute(
        "SELECT 1 FROM procore_financial_contracts "
        "WHERE project_key = ? AND contract_id = ? AND contract_family = 'commitment' LIMIT 1",
        (project_key, str(contract_id)),
    ).fetchone()
    return row is not None


def _is_compliant(primary: Any, derived: Any) -> bool:
    for value in (primary, derived):
        if isinstance(value, str) and value.strip().lower() in _COMPLIANT:
            return True
    return False


def _project_commitment_contract(
    raw: Mapping[str, Any], *, project_key: str, sync_run_id: Optional[str], now_utc: str,
    db_path: Optional[Path],
) -> Dict[str, Any]:
    cid = str(raw["id"])
    rk = record_key(project_key, "commitment-contracts", None, cid)
    currency = _currency(raw)
    fields = _drop_none(
        {
            "number": raw.get("number"),
            "contract_type": raw.get("type"),
            "title_redacted": raw.get("title"),
            "status": raw.get("status"),
            "executed": bool_to_int(raw.get("executed")),
            "private": bool_to_int(raw.get("private")),
            "grand_total": coerce_amount(raw.get("grand_total")),
            "retainage_percent": coerce_amount(raw.get("retainage_percent")),
            "updated_at_utc": raw.get("updated_at"),
            "last_sync_run_id": sync_run_id,
            **currency,
        }
    )
    upsert_financial_contract(
        record_key=rk, project_key=project_key, endpoint_id="commitment-contracts",
        contract_id=cid, contract_family="commitment", fields=fields, db_path=db_path,
    )
    _emit_facts(
        project_key=project_key, rk=rk, endpoint_id="commitment-contracts",
        table="procore_financial_contracts", fields=fields,
        amount_keys=("grand_total", "retainage_percent"), now_utc=now_utc,
        currency_iso_code=currency.get("currency_iso_code"), db_path=db_path,
    )
    link_record_entities(
        project_key=project_key, record_key=rk, endpoint_id="commitment-contracts",
        people={"created_by": raw.get("created_by")}, companies={"vendor": raw.get("vendor")},
        now_utc=now_utc, db_path=db_path,
    )
    if raw.get("attachments"):
        extract_attachment_refs(
            raw.get("attachments"), project_key=project_key, source_record_key=rk,
            source_endpoint_id="commitment-contracts", sensitivity="high", now_utc=now_utc,
            db_path=db_path,
        )
    signals: List[str] = []
    if not raw.get("executed"):
        emit_action_signal(
            project_key=project_key, record_key=rk, endpoint_id="commitment-contracts",
            signal_type="commitment_unexecuted", importance="high", now_utc=now_utc, db_path=db_path,
        )
        signals.append("commitment_unexecuted")
    return {"projected": True, "record_key": rk, "signals": signals}


def _project_line_item(
    raw: Mapping[str, Any], *, endpoint_id: str, parent_endpoint: str, line_item_kind: str,
    parent_field: str, parent_procore_id: Optional[str], project_key: str, now_utc: str,
    db_path: Optional[Path],
) -> Dict[str, Any]:
    lid = str(raw["id"])
    parent = parent_procore_id or (
        str(raw.get(parent_field)) if raw.get(parent_field) is not None else None
    )
    parent_rk = record_key(project_key, parent_endpoint, None, parent) if parent else ""
    li_key = record_key(project_key, endpoint_id, parent, lid)
    fields = _drop_none(
        {
            "amount": coerce_amount(raw.get("amount") or raw.get("total_amount")),
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
    db_path: Optional[Path],
) -> Dict[str, Any]:
    parent_rk = (
        record_key(project_key, "commitment-contracts", None, parent_procore_id)
        if parent_procore_id else ""
    )
    keys = extract_attachment_refs(
        [raw], project_key=project_key, source_record_key=parent_rk,
        source_endpoint_id="commitment-attachments", sensitivity="high", now_utc=now_utc,
        db_path=db_path,
    )
    return {"projected": bool(keys), "record_key": parent_rk, "signals": []}


def _project_compliance(
    raw: Mapping[str, Any], *, parent_procore_id: Optional[str], project_key: str, now_utc: str,
    db_path: Optional[Path],
) -> Dict[str, Any]:
    contract_id = parent_procore_id or raw.get("contract_id") or raw.get("id")
    if contract_id is None:
        return {"projected": False}
    contract_rk = record_key(project_key, "commitment-contracts", None, str(contract_id))
    signals: List[str] = []

    def _project_docs(docs: Any, kind: str) -> None:
        if not isinstance(docs, list):
            return
        for doc in docs:
            if not isinstance(doc, dict) or doc.get("id") in (None, ""):
                continue
            doc_id = str(doc["id"])
            comp_key = record_key(project_key, "commitment-compliance", str(contract_id), doc_id)
            attachments = doc.get("attachments")
            first_url = None
            if isinstance(attachments, list):
                first_url = next(
                    (a.get("url") for a in attachments if isinstance(a, dict) and a.get("url")),
                    None,
                )
            status = doc.get("status")
            fields = _drop_none(
                {
                    "contract_record_key": contract_rk,
                    "document_type": doc.get("type") or doc.get("insurance_type") or kind,
                    "status": status,
                    "compliant": bool_to_int(
                        isinstance(status, str) and status.strip().lower() in _COMPLIANT
                    ),
                    "effective_date": doc.get("effective_at"),
                    "expiration_date": doc.get("expires_at"),
                    "attachment_path_redacted": first_url,  # repo reduces to path-only
                    "notes_summary_redacted": _note_hash(doc.get("notes")),
                    "updated_at_utc": raw.get("updated_at"),
                }
            )
            upsert_financial_compliance_document(
                compliance_key=comp_key, project_key=project_key, endpoint_id="commitment-compliance",
                compliance_id=doc_id, fields=fields, db_path=db_path,
            )
            if isinstance(status, str) and status.strip().lower() == "expired":
                continue
            days = _days_until(doc.get("expires_at"), now_utc)
            if days is not None and days <= 30:
                emit_action_signal(
                    project_key=project_key, record_key=contract_rk,
                    endpoint_id="commitment-compliance",
                    signal_type="commitment_compliance_document_expiring", importance="high",
                    now_utc=now_utc, db_path=db_path,
                )
                signals.append("commitment_compliance_document_expiring")

    _project_docs(raw.get("compliance_documents"), "compliance")
    _project_docs(raw.get("insurance_documents"), "insurance")

    if raw.get("compliance_status") is not None and not _is_compliant(
        raw.get("compliance_status"), raw.get("derived_compliance_status")
    ):
        emit_action_signal(
            project_key=project_key, record_key=contract_rk, endpoint_id="commitment-compliance",
            signal_type="commitment_non_compliant", importance="high", now_utc=now_utc, db_path=db_path,
        )
        signals.append("commitment_non_compliant")
    if raw.get("insurance_status") is not None and not _is_compliant(
        raw.get("insurance_status"), raw.get("derived_insurance_status")
    ):
        emit_action_signal(
            project_key=project_key, record_key=contract_rk, endpoint_id="commitment-compliance",
            signal_type="commitment_insurance_not_compliant", importance="high", now_utc=now_utc,
            db_path=db_path,
        )
        signals.append("commitment_insurance_not_compliant")
    return {"projected": True, "record_key": contract_rk, "signals": signals}


def _project_purchase_order(
    raw: Mapping[str, Any], *, project_key: str, sync_run_id: Optional[str], now_utc: str,
    db_path: Optional[Path],
) -> Dict[str, Any]:
    poid = str(raw["id"])
    po_rk = record_key(project_key, "purchase-order-contracts", None, poid)
    duplicate = _commitment_exists(project_key, poid, db_path)
    currency = _currency(raw)
    fields = _drop_none(
        {
            "number": raw.get("number"),
            "title_redacted": raw.get("title"),
            "status": raw.get("status"),
            "executed": bool_to_int(raw.get("executed")),
            "private": bool_to_int(raw.get("private")),
            "grand_total": coerce_amount(raw.get("grand_total")),
            "retainage_percent": coerce_amount(raw.get("retainage_percent")),
            "contract_date": raw.get("contract_date"),
            "updated_at_utc": raw.get("updated_at"),
            "last_sync_run_id": sync_run_id,
            **currency,
        }
    )
    upsert_financial_contract(
        record_key=po_rk, project_key=project_key, endpoint_id="purchase-order-contracts",
        contract_id=poid, contract_family="purchase_order", fields=fields, db_path=db_path,
    )
    # Compatibility/backfill: skip amount facts when a commitment already covers
    # this contract id (v2 coverage) so committed cost is never double-counted.
    if not duplicate:
        _emit_facts(
            project_key=project_key, rk=po_rk, endpoint_id="purchase-order-contracts",
            table="procore_financial_contracts", fields=fields,
            amount_keys=("grand_total", "retainage_percent"), now_utc=now_utc,
            currency_iso_code=currency.get("currency_iso_code"), db_path=db_path,
        )
    link_record_entities(
        project_key=project_key, record_key=po_rk, endpoint_id="purchase-order-contracts",
        people={"assignee": raw.get("assignee")}, companies={"vendor": raw.get("vendor")},
        now_utc=now_utc, db_path=db_path,
    )
    signals: List[str] = []
    status = str(raw.get("status") or "").strip().lower()
    if status in _PO_PROCESSING:
        emit_action_signal(
            project_key=project_key, record_key=po_rk, endpoint_id="purchase-order-contracts",
            signal_type="purchase_order_processing", importance="medium", now_utc=now_utc, db_path=db_path,
        )
        signals.append("purchase_order_processing")
    days = _days_until(raw.get("delivery_date"), now_utc)
    if days is not None and days <= 14 and status not in _PO_TERMINAL:
        emit_action_signal(
            project_key=project_key, record_key=po_rk, endpoint_id="purchase-order-contracts",
            signal_type="purchase_order_delivery_due", importance="medium", now_utc=now_utc, db_path=db_path,
        )
        signals.append("purchase_order_delivery_due")
    return {
        "projected": True, "record_key": po_rk, "signals": signals,
        "duplicate_of_commitment": duplicate,
    }


def project_commitment_family(
    endpoint_id: str,
    raw: Mapping[str, Any],
    *,
    project_key: str,
    sync_run_id: Optional[str] = None,
    now_utc: str,
    db_path: Optional[Path] = None,
    parent_procore_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Dispatch a raw commitment / purchase-order payload to its projection."""
    if not isinstance(raw, dict):
        return {"projected": False}
    if endpoint_id == "commitment-compliance":
        return _project_compliance(
            raw, parent_procore_id=parent_procore_id, project_key=project_key,
            now_utc=now_utc, db_path=db_path,
        )
    if raw.get("id") in (None, ""):
        return {"projected": False}
    if endpoint_id == "commitment-contracts":
        return _project_commitment_contract(
            raw, project_key=project_key, sync_run_id=sync_run_id, now_utc=now_utc, db_path=db_path
        )
    if endpoint_id == "commitment-line-items":
        return _project_line_item(
            raw, endpoint_id="commitment-line-items", parent_endpoint="commitment-contracts",
            line_item_kind="commitment", parent_field="commitment_contract_id",
            parent_procore_id=parent_procore_id, project_key=project_key, now_utc=now_utc, db_path=db_path,
        )
    if endpoint_id == "commitment-attachments":
        return _project_attachment(
            raw, parent_procore_id=parent_procore_id, project_key=project_key, now_utc=now_utc, db_path=db_path
        )
    if endpoint_id == "purchase-order-contracts":
        return _project_purchase_order(
            raw, project_key=project_key, sync_run_id=sync_run_id, now_utc=now_utc, db_path=db_path
        )
    if endpoint_id == "purchase-order-line-items":
        return _project_line_item(
            raw, endpoint_id="purchase-order-line-items", parent_endpoint="purchase-order-contracts",
            line_item_kind="purchase_order", parent_field="purchase_order_contract_id",
            parent_procore_id=parent_procore_id, project_key=project_key, now_utc=now_utc, db_path=db_path,
        )
    if endpoint_id == "purchase-order-detail-line-items":
        return _project_line_item(
            raw, endpoint_id="purchase-order-detail-line-items",
            parent_endpoint="purchase-order-line-items", line_item_kind="purchase_order_detail",
            parent_field="line_item_id", parent_procore_id=parent_procore_id,
            project_key=project_key, now_utc=now_utc, db_path=db_path,
        )
    return {"projected": False}


__all__ = ["COMMITMENT_ENDPOINTS", "project_commitment_family"]
