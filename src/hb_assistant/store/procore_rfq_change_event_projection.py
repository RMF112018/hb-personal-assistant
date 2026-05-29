"""Phase 05 RFQ / change-event projections.

Projects RFQs and change events into the V8 ``procore_financial_rfqs`` /
``procore_financial_change_events`` tables, and links their informal pricing/change
workflow (RFQ responses & quotes, change-event comments) to the formal change records
via amount facts, relationship edges, and action signals. Responses / quotes /
comments have **no dedicated table** (none in the package schema) — their hashed +
excerpted text is carried only in the normalized live record; here they contribute
quote cost/schedule amount facts, edges, and the comment-added signal.

Amounts are coerced decimal-safe (``coerce_amount`` — never float-lossy) and stored
verbatim as TEXT; titles / descriptions / comments are reduced upstream by the
normalizers (hash + masked excerpt). Self-contained store module — no
``hb_assistant.procore`` import.
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
from .procore_financials import upsert_financial_change_event, upsert_financial_rfq

RFQ_ENDPOINTS = frozenset(
    {
        "rfqs",
        "rfq-responses",
        "rfq-quotes",
        "change-events",
        "change-event-comments",
    }
)

_RFQ_REVIEW = {"open", "pending", "under_review", "in_review", "sent", "submitted", "draft"}
_RFQ_TERMINAL = {"awarded", "closed", "void", "voided", "canceled", "cancelled", "rejected"}
_CHANGE_EVENT_TERMINAL = {"approved", "rejected", "closed", "void", "voided", "canceled", "cancelled"}


def _drop_none(fields: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in fields.items() if v is not None}


def _currency_iso(raw: Mapping[str, Any]) -> Optional[str]:
    cc = raw.get("currency_configuration")
    src: Mapping[str, Any] = cc if isinstance(cc, dict) else raw
    iso = src.get("currency_iso_code") or raw.get("currency_iso_code")
    return iso if isinstance(iso, str) and iso else None


def _cost_code_id(raw: Mapping[str, Any]) -> Optional[str]:
    cost = raw.get("cost_code")
    if isinstance(cost, dict) and cost.get("id") is not None:
        return str(cost["id"])
    if raw.get("cost_code_id") is not None:
        return str(raw["cost_code_id"])
    return None


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


def _ref_ids(value: Any) -> List[str]:
    """Extract id(s) from a dict / list-of-dicts / scalar reference field."""
    ids: List[str] = []
    if isinstance(value, dict):
        if value.get("id") is not None:
            ids.append(str(value["id"]))
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, dict) and item.get("id") is not None:
                ids.append(str(item["id"]))
            elif item is not None and not isinstance(item, (dict, list)):
                ids.append(str(item))
    return ids


def _project_rfq(
    raw: Mapping[str, Any], *, project_key: str, sync_run_id: Optional[str], now_utc: str,
    db_path: Optional[Path],
) -> Dict[str, Any]:
    rid = str(raw["id"])
    rfq_rk = record_key(project_key, "rfqs", None, rid)
    commitment_id = raw.get("commitment_contract_id")
    cost_code_id = _cost_code_id(raw)
    fields = _drop_none(
        {
            "commitment_contract_id": str(commitment_id) if commitment_id is not None else None,
            "number": raw.get("number"),
            "title_redacted": raw.get("title"),
            "status": raw.get("status"),
            "private": bool_to_int(raw.get("private")),
            "due_date": raw.get("due_date"),
            "estimated_amount": coerce_amount(raw.get("estimated_amount")),
            "estimated_schedule_impact": coerce_amount(raw.get("estimated_schedule_impact")),
            "estimated_status": raw.get("estimated_status"),
            "intent_to_quote": bool_to_int(raw.get("intent_to_quote")),
            "original_quote": coerce_amount(raw.get("original_quote")),
            "updated_at_utc": raw.get("updated_at"),
        }
    )
    upsert_financial_rfq(
        record_key=rfq_rk, project_key=project_key, endpoint_id="rfqs", rfq_id=rid,
        fields=fields, db_path=db_path,
    )
    _emit_facts(
        project_key=project_key, rk=rfq_rk, endpoint_id="rfqs", table="procore_financial_rfqs",
        fields=fields, amount_keys=("estimated_amount", "original_quote", "estimated_schedule_impact"),
        now_utc=now_utc, currency_iso_code=_currency_iso(raw), cost_code_id=cost_code_id, db_path=db_path,
    )
    link_record_entities(
        project_key=project_key, record_key=rfq_rk, endpoint_id="rfqs",
        people={"created_by": raw.get("created_by"), "assigned": raw.get("assigned")},
        now_utc=now_utc, db_path=db_path,
    )
    if commitment_id is not None:
        emit_record_edge(
            project_key=project_key, from_record_key=rfq_rk, edge_type="rfq_of_commitment",
            source_endpoint_id="rfqs",
            to_record_key=record_key(project_key, "commitment-contracts", None, str(commitment_id)),
            now_utc=now_utc, db_path=db_path,
        )
    change_event = raw.get("change_event")
    if isinstance(change_event, dict) and change_event.get("id") is not None:
        emit_record_edge(
            project_key=project_key, from_record_key=rfq_rk, edge_type="rfq_change_event",
            source_endpoint_id="rfqs",
            to_record_key=record_key(project_key, "change-events", None, str(change_event["id"])),
            now_utc=now_utc, db_path=db_path,
        )
    # PCO / COR / CCO links: prime-family -> prime-change-orders namespace,
    # commitment-family -> commitment-change-orders namespace (documented mapping).
    for field, namespace in (
        ("potential_change_orders", "prime-change-orders"),
        ("change_order_packages", "prime-change-orders"),
        ("commitment_potential_change_orders", "commitment-change-orders"),
        ("commitment_change_order_packages", "commitment-change-orders"),
    ):
        for coid in _ref_ids(raw.get(field)):
            emit_record_edge(
                project_key=project_key, from_record_key=rfq_rk, edge_type="rfq_change_order",
                source_endpoint_id="rfqs",
                to_record_key=record_key(project_key, namespace, None, coid),
                now_utc=now_utc, db_path=db_path,
            )
    signals: List[str] = []

    def _sig(signal_type: str, importance: str) -> None:
        emit_action_signal(project_key=project_key, record_key=rfq_rk, endpoint_id="rfqs",
                           signal_type=signal_type, importance=importance, now_utc=now_utc, db_path=db_path)
        signals.append(signal_type)

    status = str(raw.get("status") or "").strip().lower()
    days = _days_until(raw.get("due_date"), now_utc)
    if days is not None and days < 0 and status not in _RFQ_TERMINAL:
        _sig("rfq_overdue", "high")
    if status in _RFQ_REVIEW:
        _sig("rfq_under_review", "medium")
    if raw.get("intent_to_quote") is False:
        _sig("rfq_no_intent_to_quote", "low")
    if is_positive_amount(raw.get("estimated_schedule_impact")):
        _sig("rfq_estimated_schedule_impact", "medium")
    if is_positive_amount(raw.get("estimated_amount")):
        _sig("rfq_estimated_cost_exposure", "medium")
    return {"projected": True, "record_key": rfq_rk, "signals": signals}


def _project_change_event(
    raw: Mapping[str, Any], *, project_key: str, sync_run_id: Optional[str], now_utc: str,
    db_path: Optional[Path],
) -> Dict[str, Any]:
    ceid = str(raw["id"])
    ce_rk = record_key(project_key, "change-events", None, ceid)
    cost_code_id = _cost_code_id(raw)
    fields = _drop_none(
        {
            "number": raw.get("number"),
            "title_redacted": raw.get("title"),
            "status": raw.get("status"),
            "scope": raw.get("scope"),
            "estimated_cost": coerce_amount(raw.get("estimated_cost")),
            "estimated_revenue": coerce_amount(raw.get("estimated_revenue")),
            "schedule_impact_amount": coerce_amount(raw.get("schedule_impact_amount")),
            "owner_cost_amount": coerce_amount(raw.get("owner_cost_amount")),
            "commitment_cost_amount": coerce_amount(raw.get("commitment_cost_amount")),
            "updated_at_utc": raw.get("updated_at"),
        }
    )
    upsert_financial_change_event(
        record_key=ce_rk, project_key=project_key, endpoint_id="change-events",
        change_event_id=ceid, fields=fields, db_path=db_path,
    )
    _emit_facts(
        project_key=project_key, rk=ce_rk, endpoint_id="change-events",
        table="procore_financial_change_events", fields=fields,
        amount_keys=("estimated_cost", "estimated_revenue", "owner_cost_amount",
                     "commitment_cost_amount", "schedule_impact_amount"),
        now_utc=now_utc, currency_iso_code=_currency_iso(raw), cost_code_id=cost_code_id, db_path=db_path,
    )
    link_record_entities(
        project_key=project_key, record_key=ce_rk, endpoint_id="change-events",
        people={"created_by": raw.get("created_by")}, now_utc=now_utc, db_path=db_path,
    )
    signals: List[str] = []

    def _sig(signal_type: str, importance: str) -> None:
        emit_action_signal(project_key=project_key, record_key=ce_rk, endpoint_id="change-events",
                           signal_type=signal_type, importance=importance, now_utc=now_utc, db_path=db_path)
        signals.append(signal_type)

    status = str(raw.get("status") or "").strip().lower()
    if status and status not in _CHANGE_EVENT_TERMINAL:
        _sig("change_event_pending", "medium")
    if is_positive_amount(raw.get("estimated_cost")):
        _sig("change_event_rom_cost_exposure", "high")
    if is_positive_amount(raw.get("schedule_impact_amount")):
        _sig("change_event_schedule_impact", "medium")
    return {"projected": True, "record_key": ce_rk, "signals": signals}


def _project_rfq_quote(
    raw: Mapping[str, Any], *, parent_procore_id: Optional[str], project_key: str, now_utc: str,
    db_path: Optional[Path],
) -> Dict[str, Any]:
    qid = str(raw["id"])
    rfq_id = parent_procore_id or (
        str(raw.get("request_for_quote_id")) if raw.get("request_for_quote_id") is not None else None
    )
    quote_rk = record_key(project_key, "rfq-quotes", rfq_id, qid)
    fields = _drop_none(
        {"cost": coerce_amount(raw.get("cost")), "schedule_impact": coerce_amount(raw.get("schedule_impact"))}
    )
    _emit_facts(
        project_key=project_key, rk=quote_rk, endpoint_id="rfq-quotes", table="rfq_quotes",
        fields=fields, amount_keys=("cost", "schedule_impact"), now_utc=now_utc,
        currency_iso_code=_currency_iso(raw), db_path=db_path,
    )
    if rfq_id is not None:
        emit_record_edge(
            project_key=project_key, from_record_key=quote_rk, edge_type="quote_of",
            source_endpoint_id="rfq-quotes",
            to_record_key=record_key(project_key, "rfqs", None, rfq_id),
            now_utc=now_utc, db_path=db_path,
        )
    link_record_entities(
        project_key=project_key, record_key=quote_rk, endpoint_id="rfq-quotes",
        people={"created_by": raw.get("created_by")}, now_utc=now_utc, db_path=db_path,
    )
    return {"projected": True, "record_key": quote_rk, "signals": []}


def _project_rfq_response(
    raw: Mapping[str, Any], *, parent_procore_id: Optional[str], project_key: str, now_utc: str,
    db_path: Optional[Path],
) -> Dict[str, Any]:
    resp_id = str(raw["id"])
    rfq_id = parent_procore_id or (
        str(raw.get("request_for_quote_id")) if raw.get("request_for_quote_id") is not None else None
    )
    resp_rk = record_key(project_key, "rfq-responses", rfq_id, resp_id)
    if rfq_id is not None:
        emit_record_edge(
            project_key=project_key, from_record_key=resp_rk, edge_type="response_of",
            source_endpoint_id="rfq-responses",
            to_record_key=record_key(project_key, "rfqs", None, rfq_id),
            now_utc=now_utc, db_path=db_path,
        )
    link_record_entities(
        project_key=project_key, record_key=resp_rk, endpoint_id="rfq-responses",
        people={"created_by": raw.get("created_by")}, now_utc=now_utc, db_path=db_path,
    )
    return {"projected": True, "record_key": resp_rk, "signals": []}


def _project_change_event_comment(
    raw: Mapping[str, Any], *, parent_procore_id: Optional[str], project_key: str, now_utc: str,
    db_path: Optional[Path],
) -> Dict[str, Any]:
    cid = str(raw["id"])
    ce_id = parent_procore_id or (
        str(raw.get("change_event_id")) if raw.get("change_event_id") is not None else None
    )
    comment_rk = record_key(project_key, "change-event-comments", ce_id, cid)
    signals: List[str] = []
    if ce_id is not None:
        emit_record_edge(
            project_key=project_key, from_record_key=comment_rk, edge_type="comment_of",
            source_endpoint_id="change-event-comments",
            to_record_key=record_key(project_key, "change-events", None, ce_id),
            now_utc=now_utc, db_path=db_path,
        )
    link_record_entities(
        project_key=project_key, record_key=comment_rk, endpoint_id="change-event-comments",
        people={"creator": raw.get("creator")}, now_utc=now_utc, db_path=db_path,
    )
    emit_action_signal(
        project_key=project_key, record_key=comment_rk, endpoint_id="change-event-comments",
        signal_type="change_event_comment_added", importance="low", now_utc=now_utc, db_path=db_path,
    )
    signals.append("change_event_comment_added")
    return {"projected": True, "record_key": comment_rk, "signals": signals}


def project_rfq_change_event_family(
    endpoint_id: str,
    raw: Mapping[str, Any],
    *,
    project_key: str,
    sync_run_id: Optional[str] = None,
    now_utc: str,
    db_path: Optional[Path] = None,
    parent_procore_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Dispatch a raw RFQ / change-event payload to its projection."""
    if not isinstance(raw, dict) or raw.get("id") in (None, ""):
        return {"projected": False}
    if endpoint_id == "rfqs":
        return _project_rfq(
            raw, project_key=project_key, sync_run_id=sync_run_id, now_utc=now_utc, db_path=db_path
        )
    if endpoint_id == "change-events":
        return _project_change_event(
            raw, project_key=project_key, sync_run_id=sync_run_id, now_utc=now_utc, db_path=db_path
        )
    if endpoint_id == "rfq-quotes":
        return _project_rfq_quote(
            raw, parent_procore_id=parent_procore_id, project_key=project_key,
            now_utc=now_utc, db_path=db_path,
        )
    if endpoint_id == "rfq-responses":
        return _project_rfq_response(
            raw, parent_procore_id=parent_procore_id, project_key=project_key,
            now_utc=now_utc, db_path=db_path,
        )
    if endpoint_id == "change-event-comments":
        return _project_change_event_comment(
            raw, parent_procore_id=parent_procore_id, project_key=project_key,
            now_utc=now_utc, db_path=db_path,
        )
    return {"projected": False}


__all__ = ["RFQ_ENDPOINTS", "project_rfq_change_event_family"]
