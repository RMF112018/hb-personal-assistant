"""Phase 05 budget projections.

Projects budget views + detail rows and budget change history / change line items /
modifications into the V8 budget tables (`procore_financial_budget_views` /
`_budget_rows` / `_budget_changes`), with structured column-value JSON, amount facts
(queryable by view / row / column / WBS), relationship edges, and budget signals.
budget-detail-columns has no table — it links to its parent view via an edge (column
names live in the normalized live record). ``budget-details`` is a non-routable
sentinel and is intentionally NOT handled here.

Stays column-name-agnostic: the variable per-tenant columns are not assumed; row
amount facts are emitted for recognised named amount fields, and the full structured
value set is preserved verbatim in ``column_values_json_redacted`` (curated to exclude
free text — budget cells are non-PII amounts/codes). Self-contained store module.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from .procore_enrichment import emit_action_signal, emit_record_edge
from .procore_financial_projection import (
    coerce_amount,
    emit_amount_facts,
    record_key,
)
from .procore_financials import (
    upsert_financial_budget_change,
    upsert_financial_budget_row,
    upsert_financial_budget_view,
)

BUDGET_ENDPOINTS = frozenset(
    {
        "budget-views",
        "budget-detail-columns",
        "budget-detail-rows",
        "budget-change-history",
        "budget-change-line-items",
        "budget-modifications",
    }
)

# Named row amount fields recognised for facts + the structured column JSON.
_ROW_AMOUNTS = (
    "original_budget_amount",
    "revised_budget",
    "approved_change_orders",
    "pending_budget_changes",
    "projected_budget",
    "committed_costs",
    "direct_costs",
    "projected_costs",
    "actual_cost",
    "forecast_to_complete",
    "estimated_cost_at_completion",
    "projected_over_under",
    "variance",
    "over_under",
)
_BUDGET_BASES = ("revised_budget", "original_budget_amount")
_ACTUAL_BASES = ("actual_cost", "projected_costs", "committed_costs", "direct_costs")
_VARIANCE_FIELDS = ("projected_over_under", "variance", "over_under")
_POSTED_STATUSES = {"posted", "approved", "closed", "complete", "completed"}


def _drop_none(fields: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in fields.items() if v is not None}


def _decimal(value: Any) -> Optional[Decimal]:
    coerced = coerce_amount(value)
    if coerced is None:
        return None
    try:
        return Decimal(coerced)
    except (InvalidOperation, ValueError):
        return None


def _first_present(raw: Mapping[str, Any], keys: Any) -> Optional[Decimal]:
    for key in keys:
        d = _decimal(raw.get(key))
        if d is not None:
            return d
    return None


def _currency_iso(raw: Mapping[str, Any]) -> Optional[str]:
    cc = raw.get("currency_configuration")
    src: Mapping[str, Any] = cc if isinstance(cc, dict) else raw
    iso = src.get("currency_iso_code") or raw.get("currency_iso_code")
    return iso if isinstance(iso, str) and iso else None


def _row_codes(raw: Mapping[str, Any]) -> Dict[str, Optional[str]]:
    wbs = raw.get("wbs_code")
    wbs_id = None
    wbs_flat = None
    if isinstance(wbs, dict):
        wbs_id = str(wbs["id"]) if wbs.get("id") is not None else None
        wbs_flat = wbs.get("flat_code") if isinstance(wbs.get("flat_code"), str) else None
    if wbs_id is None and raw.get("wbs_code_id") is not None:
        wbs_id = str(raw["wbs_code_id"])
    cost = raw.get("cost_code")
    cost_id = None
    if isinstance(cost, dict) and cost.get("id") is not None:
        cost_id = str(cost["id"])
    elif raw.get("cost_code_id") is not None:
        cost_id = str(raw["cost_code_id"])
    return {"wbs_code_id": wbs_id, "wbs_flat_code": wbs_flat, "cost_code_id": cost_id}


def _emit_facts(
    *,
    project_key: str,
    rk: str,
    endpoint_id: str,
    facts: List[Dict[str, Any]],
    now_utc: str,
    currency_iso_code: Optional[str],
    wbs_code_id: Optional[str] = None,
    cost_code_id: Optional[str] = None,
    db_path: Optional[Path],
) -> None:
    enriched = [
        {**f, "wbs_code_id": wbs_code_id, "cost_code_id": cost_code_id} for f in facts
    ]
    if enriched:
        emit_amount_facts(
            project_key=project_key, record_key=rk, endpoint_id=endpoint_id, facts=enriched,
            created_at_utc=now_utc, currency_iso_code=currency_iso_code, db_path=db_path,
        )


def _hash(*parts: Any) -> str:
    return hashlib.sha256(
        "|".join("" if p is None else str(p) for p in parts).encode("utf-8")
    ).hexdigest()[:16]


def _project_budget_view(
    raw: Mapping[str, Any], *, project_key: str, now_utc: str, db_path: Optional[Path]
) -> Dict[str, Any]:
    vid = str(raw["id"])
    view_key = record_key(project_key, "budget-views", None, vid)
    fields = _drop_none(
        {
            "name_redacted": raw.get("name"),
            "description_summary_json": raw.get("description"),
            "updated_at_utc": raw.get("updated_at"),
        }
    )
    upsert_financial_budget_view(
        budget_view_key=view_key, project_key=project_key, budget_view_id=vid,
        fields=fields, db_path=db_path,
    )
    return {"projected": True, "record_key": view_key, "signals": []}


def _project_budget_detail_column(
    raw: Mapping[str, Any], *, parent_procore_id: Optional[str], project_key: str, now_utc: str,
    db_path: Optional[Path],
) -> Dict[str, Any]:
    col_id = str(raw["id"])
    view_id = parent_procore_id or (
        str(raw.get("budget_view_id")) if raw.get("budget_view_id") is not None else None
    )
    col_rk = record_key(project_key, "budget-detail-columns", view_id, col_id)
    if view_id is not None:
        emit_record_edge(
            project_key=project_key, from_record_key=col_rk, edge_type="column_of",
            source_endpoint_id="budget-detail-columns",
            to_record_key=record_key(project_key, "budget-views", None, view_id),
            now_utc=now_utc, db_path=db_path,
        )
    return {"projected": True, "record_key": col_rk, "signals": []}


def _project_budget_detail_row(
    raw: Mapping[str, Any], *, parent_procore_id: Optional[str], project_key: str, now_utc: str,
    db_path: Optional[Path],
) -> Dict[str, Any]:
    rid = str(raw["id"])
    view_id = parent_procore_id or (
        str(raw.get("budget_view_id")) if raw.get("budget_view_id") is not None else None
    )
    view_key = record_key(project_key, "budget-views", None, view_id) if view_id else None
    row_key = record_key(project_key, "budget-detail-rows", view_id, rid)
    codes = _row_codes(raw)

    # Curated structured column values (amounts/codes only; no free text).
    column_values: Dict[str, Any] = {}
    for key in _ROW_AMOUNTS:
        amount = coerce_amount(raw.get(key))
        if amount is not None:
            column_values[key] = amount
    forecast = raw.get("budget_forecast")
    forecast_amount = None
    if isinstance(forecast, dict):
        forecast_amount = coerce_amount(forecast.get("amount"))
        for sub in ("amount", "automatic_amount", "manual_amount"):
            amt = coerce_amount(forecast.get(sub))
            if amt is not None:
                column_values[f"budget_forecast.{sub}"] = amt

    fields = _drop_none(
        {
            "budget_view_key": view_key,
            "wbs_code_id": codes["wbs_code_id"],
            "wbs_flat_code": codes["wbs_flat_code"],
            "cost_code_id": codes["cost_code_id"],
            "column_values_json_redacted": json.dumps(column_values, sort_keys=True)
            if column_values else None,
        }
    )
    upsert_financial_budget_row(
        budget_row_key=row_key, project_key=project_key, endpoint_id="budget-detail-rows",
        row_id=rid, fields=fields, db_path=db_path,
    )
    facts = [
        {"amount_name": name, "amount_value": value,
         "source_field_path": f"budget_detail_rows.{name}"}
        for name, value in column_values.items()
    ]
    _emit_facts(
        project_key=project_key, rk=row_key, endpoint_id="budget-detail-rows", facts=facts,
        now_utc=now_utc, currency_iso_code=_currency_iso(raw),
        wbs_code_id=codes["wbs_code_id"], cost_code_id=codes["cost_code_id"], db_path=db_path,
    )

    signals: List[str] = []

    def _sig(signal_type: str) -> None:
        emit_action_signal(project_key=project_key, record_key=row_key,
                           endpoint_id="budget-detail-rows", signal_type=signal_type,
                           importance="high", now_utc=now_utc, db_path=db_path)
        signals.append(signal_type)

    budget = _first_present(raw, _BUDGET_BASES)
    forecast_dec = _decimal(forecast_amount) if forecast_amount is not None else _decimal(
        raw.get("projected_budget")
    )
    actual = _first_present(raw, _ACTUAL_BASES)
    variance = _first_present(raw, _VARIANCE_FIELDS)
    if budget is not None and forecast_dec is not None and forecast_dec > budget:
        _sig("budget_forecast_exceeds_budget")
    if budget is not None and actual is not None and actual > budget:
        _sig("budget_actual_exceeds_budget")
    if variance is not None:
        if variance < 0:
            _sig("budget_variance_negative")
    elif budget is not None and forecast_dec is not None and (budget - forecast_dec) < 0:
        _sig("budget_variance_negative")
    return {"projected": True, "record_key": row_key, "signals": signals}


def _project_budget_change(
    raw: Mapping[str, Any], *, endpoint_id: str, kind: str, parent_procore_id: Optional[str],
    project_key: str, now_utc: str, db_path: Optional[Path],
) -> Dict[str, Any]:
    signals: List[str] = []
    if kind == "change_history":
        change_id = str(raw["id"]) if raw.get("id") not in (None, "") else _hash(
            raw.get("budget_code"), raw.get("column"), raw.get("created_at"),
            raw.get("old_value"), raw.get("new_value"),
        )
        rk = record_key(project_key, endpoint_id, None, change_id)
        old_value = coerce_amount(raw.get("old_value"))
        new_value = coerce_amount(raw.get("new_value"))
        delta = None
        od, nd = _decimal(raw.get("old_value")), _decimal(raw.get("new_value"))
        if od is not None and nd is not None:
            delta = str(nd - od)
        fields = _drop_none(
            {
                "wbs_flat_code": raw.get("budget_code"),
                "from_amount": old_value,
                "to_amount": new_value,
                "adjustment_amount": delta,
                "title_redacted": raw.get("description"),
                "approved_at_utc": raw.get("created_at"),
                "updated_at_utc": raw.get("created_at"),
            }
        )
        upsert_financial_budget_change(
            budget_change_key=rk, project_key=project_key, endpoint_id=endpoint_id,
            budget_change_kind=kind, budget_change_id=change_id, fields=fields, db_path=db_path,
        )
        column = raw.get("column") or "value"
        facts = [
            {"amount_name": name, "amount_value": value,
             "source_field_path": f"budget_change_history.{column}.{name}"}
            for name, value in (("from_amount", old_value), ("to_amount", new_value))
            if value is not None
        ]
        _emit_facts(project_key=project_key, rk=rk, endpoint_id=endpoint_id, facts=facts,
                    now_utc=now_utc, currency_iso_code=_currency_iso(raw), db_path=db_path)
        emit_action_signal(project_key=project_key, record_key=rk, endpoint_id=endpoint_id,
                           signal_type="budget_change_posted", importance="medium",
                           now_utc=now_utc, db_path=db_path)
        signals.append("budget_change_posted")
        return {"projected": True, "record_key": rk, "signals": signals}

    if kind == "line_item":
        liid = str(raw["id"])
        parent_change = parent_procore_id or (
            str(raw.get("budget_change_id")) if raw.get("budget_change_id") is not None else None
        )
        rk = record_key(project_key, endpoint_id, parent_change, liid)
        parent_change_key = (
            record_key(project_key, "budget-change-history", None, parent_change)
            if parent_change else None
        )
        amount = coerce_amount(raw.get("amount"))
        status = raw.get("budget_change_status")
        fields = _drop_none(
            {
                "parent_change_key": parent_change_key,
                "number": str(raw["budget_change_number"]) if raw.get("budget_change_number") is not None else None,
                "status": status,
                "title_redacted": raw.get("budget_change_name"),
                "wbs_code_id": str(raw["wbs_code_id"]) if raw.get("wbs_code_id") is not None else None,
                "adjustment_amount": amount,
            }
        )
        upsert_financial_budget_change(
            budget_change_key=rk, project_key=project_key, endpoint_id=endpoint_id,
            budget_change_kind=kind, budget_change_id=liid, fields=fields, db_path=db_path,
        )
        if amount is not None:
            _emit_facts(project_key=project_key, rk=rk, endpoint_id=endpoint_id,
                        facts=[{"amount_name": "amount", "amount_value": amount,
                                "source_field_path": "budget_change_line_items.amount"}],
                        now_utc=now_utc, currency_iso_code=_currency_iso(raw),
                        wbs_code_id=fields.get("wbs_code_id"), db_path=db_path)
        if parent_change_key:
            emit_record_edge(project_key=project_key, from_record_key=rk,
                             edge_type="change_line_item_of", source_endpoint_id=endpoint_id,
                             to_record_key=parent_change_key, now_utc=now_utc, db_path=db_path)
        if isinstance(status, str) and status.strip().lower() in _POSTED_STATUSES:
            emit_action_signal(project_key=project_key, record_key=rk, endpoint_id=endpoint_id,
                               signal_type="budget_change_posted", importance="medium",
                               now_utc=now_utc, db_path=db_path)
            signals.append("budget_change_posted")
        return {"projected": True, "record_key": rk, "signals": signals}

    # kind == "modification"
    mid = str(raw["id"])
    rk = record_key(project_key, endpoint_id, None, mid)
    transfer = coerce_amount(raw.get("transfer_amount"))
    fields = _drop_none(
        {
            "adjustment_amount": transfer,
            "approved_at_utc": raw.get("created_at"),
            "updated_at_utc": raw.get("updated_at"),
        }
    )
    upsert_financial_budget_change(
        budget_change_key=rk, project_key=project_key, endpoint_id=endpoint_id,
        budget_change_kind=kind, budget_change_id=mid, fields=fields, db_path=db_path,
    )
    if transfer is not None:
        _emit_facts(project_key=project_key, rk=rk, endpoint_id=endpoint_id,
                    facts=[{"amount_name": "transfer_amount", "amount_value": transfer,
                            "source_field_path": "budget_modifications.transfer_amount"}],
                    now_utc=now_utc, currency_iso_code=_currency_iso(raw), db_path=db_path)
    for field, edge in (("from_budget_line_item_id", "modifies_budget_row"),
                        ("to_budget_line_item_id", "modifies_budget_row")):
        if raw.get(field) is not None:
            emit_record_edge(
                project_key=project_key, from_record_key=rk, edge_type=edge,
                source_endpoint_id=endpoint_id,
                to_record_key=record_key(project_key, "budget-detail-rows", None, str(raw[field])),
                now_utc=now_utc, db_path=db_path,
            )
    emit_action_signal(project_key=project_key, record_key=rk, endpoint_id=endpoint_id,
                       signal_type="budget_modification_posted", importance="medium",
                       now_utc=now_utc, db_path=db_path)
    signals.append("budget_modification_posted")
    return {"projected": True, "record_key": rk, "signals": signals}


def project_budget_family(
    endpoint_id: str,
    raw: Mapping[str, Any],
    *,
    project_key: str,
    sync_run_id: Optional[str] = None,
    now_utc: str,
    db_path: Optional[Path] = None,
    parent_procore_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Dispatch a raw budget payload to its projection. ``budget-details`` (the
    non-routable sentinel) is not handled and never reaches here."""
    if not isinstance(raw, dict):
        return {"projected": False}
    if endpoint_id == "budget-change-history":
        return _project_budget_change(
            raw, endpoint_id=endpoint_id, kind="change_history",
            parent_procore_id=parent_procore_id, project_key=project_key, now_utc=now_utc,
            db_path=db_path,
        )
    if raw.get("id") in (None, ""):
        return {"projected": False}
    if endpoint_id == "budget-views":
        return _project_budget_view(raw, project_key=project_key, now_utc=now_utc, db_path=db_path)
    if endpoint_id == "budget-detail-columns":
        return _project_budget_detail_column(
            raw, parent_procore_id=parent_procore_id, project_key=project_key,
            now_utc=now_utc, db_path=db_path,
        )
    if endpoint_id == "budget-detail-rows":
        return _project_budget_detail_row(
            raw, parent_procore_id=parent_procore_id, project_key=project_key,
            now_utc=now_utc, db_path=db_path,
        )
    if endpoint_id == "budget-change-line-items":
        return _project_budget_change(
            raw, endpoint_id=endpoint_id, kind="line_item",
            parent_procore_id=parent_procore_id, project_key=project_key, now_utc=now_utc,
            db_path=db_path,
        )
    if endpoint_id == "budget-modifications":
        return _project_budget_change(
            raw, endpoint_id=endpoint_id, kind="modification",
            parent_procore_id=parent_procore_id, project_key=project_key, now_utc=now_utc,
            db_path=db_path,
        )
    return {"projected": False}


__all__ = ["BUDGET_ENDPOINTS", "project_budget_family"]
