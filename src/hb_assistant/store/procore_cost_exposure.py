"""Phase 06B cost / financial exposure read model over local SQLite Procore tables.

Deterministic and **read-only**: classifies the already-emitted open ``procore_action_signals``
into operator-facing *exposure types* (pending change, unapproved change, budget movement,
invoice/retainage risk, RFQ/quote pending, compliance risk) and adds an ``amount_changed`` lens
straight from ``procore_financial_budget_changes``. Each item is enriched with decimal-safe
amount facts (``procore_financial_amount_facts``) and a source link. Amounts pass through as
verbatim TEXT strings — never parsed to float, never summed. This is an advisory / review aid:
it makes **no** legal, claims, financial, safety, entitlement, schedule, liability, or
contractual determination. No live Procore access, no writeback, no raw payload values.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from .connection import get_connection

# signal_type -> exposure type. Only cost/financial signal types are mapped; any signal whose
# type is absent here is not an exposure item and is skipped. Kept as an explicit table (not a
# keyword guess) so the classification is auditable.
_EXPOSURE_SIGNAL_MAP: Dict[str, str] = {
    # pending change (change events not yet resolved + their ROM/schedule exposure)
    "change_event_pending": "pending_change",
    "change_event_rom_cost_exposure": "pending_change",
    "change_event_schedule_impact": "pending_change",
    # unapproved / unexecuted change & commitments
    "commitment_unexecuted": "unapproved_change",
    "commitment_change_order_unexecuted": "unapproved_change",
    "commitment_change_order_unpaid": "unapproved_change",
    "contract_unexecuted": "unapproved_change",
    # budget movement
    "budget_change_posted": "budget_movement",
    "budget_modification_posted": "budget_movement",
    "budget_variance_negative": "budget_movement",
    "budget_forecast_exceeds_budget": "budget_movement",
    "budget_actual_exceeds_budget": "budget_movement",
    # invoice / retainage risk
    "invoice_approved_not_paid": "invoice_retainage_risk",
    "invoice_payment_due": "invoice_retainage_risk",
    "invoice_retainage_held": "invoice_retainage_risk",
    "invoice_pending_approval": "invoice_retainage_risk",
    "billing_period_due_soon": "invoice_retainage_risk",
    # RFQ / quote pending
    "rfq_estimated_cost_exposure": "rfq_quote_pending",
    "rfq_estimated_schedule_impact": "rfq_quote_pending",
    "rfq_under_review": "rfq_quote_pending",
    "rfq_overdue": "rfq_quote_pending",
    "rfq_no_intent_to_quote": "rfq_quote_pending",
    # compliance risk
    "commitment_compliance_document_expiring": "compliance_risk",
    "commitment_non_compliant": "compliance_risk",
    "commitment_insurance_not_compliant": "compliance_risk",
}

# exposure types that always warrant a human look regardless of signal importance.
_HIGH_SENSITIVITY_TYPES = frozenset(
    {"compliance_risk", "unapproved_change", "invoice_retainage_risk"}
)

# canonical type order (all keyed in the summary, 0 when absent) — "amount_changed" last.
_EXPOSURE_TYPES = (
    "pending_change",
    "unapproved_change",
    "budget_movement",
    "invoice_retainage_risk",
    "rfq_quote_pending",
    "compliance_risk",
    "amount_changed",
)

_IMPORTANCE_RANK = {"high": 0, "medium": 1, "low": 2}


def _record_ctx(conn: Any, project_key: str) -> Dict[str, Dict[str, Any]]:
    """record_key -> {review_required, source_url_redacted} (best-effort live-record join)."""
    ctx: Dict[str, Dict[str, Any]] = {}
    for r in conn.execute(
        """
        SELECT project_key, endpoint_id, parent_procore_id, procore_record_id,
               review_required, source_url_redacted
          FROM procore_live_records
         WHERE project_key = ?
        """,
        (project_key,),
    ).fetchall():
        rk = "|".join([
            r["project_key"], r["endpoint_id"], r["parent_procore_id"] or "",
            r["procore_record_id"],
        ])
        ctx[rk] = {
            "review_required": bool(r["review_required"]),
            "source_url_redacted": r["source_url_redacted"],
        }
    return ctx


def build_cost_exposure(
    project_key: str,
    *,
    now_utc: str,
    exposure_type: Optional[str] = None,
    importance: Optional[str] = None,
    max_items: int = 100,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Build the deterministic cost-exposure report (counts + per-item decimal-safe amounts)."""
    from .procore_enrichment import get_procore_action_signals
    from .procore_financials import read_financial_amount_facts, read_financial_budget_changes

    conn = get_connection(db_path)
    record_ctx = _record_ctx(conn, project_key)

    # record_key -> [amount facts] (amount_value kept verbatim as decimal-safe TEXT).
    amounts_by_record: Dict[str, List[Dict[str, Any]]] = {}
    currencies: set[str] = set()
    for fact in read_financial_amount_facts(project_key=project_key, db_path=db_path):
        entry = {
            "amount_name": fact.get("amount_name"),
            "amount_value": fact.get("amount_value"),
            "currency_iso_code": fact.get("currency_iso_code"),
        }
        amounts_by_record.setdefault(fact.get("record_key") or "", []).append(entry)
        if fact.get("currency_iso_code"):
            currencies.add(fact["currency_iso_code"])

    items: List[Dict[str, Any]] = []

    # --- signal-driven exposure items ---
    for sig in get_procore_action_signals(
        project_key=project_key, signal_status="open", importance=importance, db_path=db_path
    ):
        signal_type = sig.get("signal_type") or ""
        etype = _EXPOSURE_SIGNAL_MAP.get(signal_type)
        if etype is None:
            continue
        rk = sig.get("record_key") or ""
        ctx = record_ctx.get(rk, {})
        sig_importance = sig.get("importance") or "medium"
        review_required = bool(ctx.get("review_required", False))
        codes: List[str] = []
        high_sensitivity = sig_importance == "high" or etype in _HIGH_SENSITIVITY_TYPES
        if high_sensitivity:
            review_required = True
            codes.append("review_required_high_sensitivity")
        items.append({
            "exposure_type": etype,
            "source": "action_signal",
            "signal_type": signal_type,
            "endpoint_id": sig.get("endpoint_id"),
            "record_key": rk,
            "importance": sig_importance,
            "review_required": review_required,
            "due_at_utc": sig.get("due_at_utc"),
            "title_redacted": sig.get("title_redacted"),
            "reason_codes": codes,
            "source_url_redacted": ctx.get("source_url_redacted"),
            "amounts": amounts_by_record.get(rk, []),
        })

    # --- amount_changed lens straight from budget changes (from/to/adjustment TEXT) ---
    if importance in (None, "medium"):
        for bc in read_financial_budget_changes(project_key=project_key, db_path=db_path):
            adj, frm, to = bc.get("adjustment_amount"), bc.get("from_amount"), bc.get("to_amount")
            if adj is None and (frm is None or to is None):
                continue
            rk = bc.get("budget_change_key") or ""
            ctx = record_ctx.get(rk, {})
            amt: List[Dict[str, Any]] = []
            for name, value in (("adjustment_amount", adj), ("from_amount", frm), ("to_amount", to)):
                if value is not None:
                    amt.append({"amount_name": name, "amount_value": value,
                                "currency_iso_code": None})
            items.append({
                "exposure_type": "amount_changed",
                "source": "budget_change",
                "signal_type": None,
                "endpoint_id": bc.get("budget_change_kind"),
                "record_key": rk,
                "importance": "medium",
                "review_required": bool(ctx.get("review_required", False)),
                "due_at_utc": None,
                "title_redacted": bc.get("number"),
                "reason_codes": ["budget_amount_movement"],
                "source_url_redacted": ctx.get("source_url_redacted"),
                "amounts": amt,
            })

    # --- optional post-classification type filter ---
    if exposure_type is not None:
        items = [it for it in items if it["exposure_type"] == exposure_type]

    # --- deterministic ordering ---
    items.sort(key=lambda it: (
        _IMPORTANCE_RANK.get(it.get("importance"), 3),
        it["exposure_type"],
        it["record_key"],
        it.get("signal_type") or it["source"],
    ))

    by_type = {t: 0 for t in _EXPOSURE_TYPES}
    by_importance = {"high": 0, "medium": 0, "low": 0}
    review_required_count = 0
    for it in items:
        by_type[it["exposure_type"]] = by_type.get(it["exposure_type"], 0) + 1
        by_importance[it["importance"]] = by_importance.get(it["importance"], 0) + 1
        if it["review_required"]:
            review_required_count += 1

    return {
        "command": "hb-assistant procore live financial exposure",
        "ok": True,
        "phase": "Phase 06B Prompt 09",
        "project_key": project_key,
        "generated_at": now_utc,
        "filters": {"exposure_type": exposure_type, "importance": importance},
        "summary": {
            "total": len(items),
            "review_required": review_required_count,
            "by_type": by_type,
            "by_importance": by_importance,
            "currencies": sorted(currencies),
        },
        "exposure": items[:max_items],
        "exposure_truncated": len(items) > max_items,
        "amounts_are_strings": True,
        "no_live_call_performed": True,
        "no_raw_values_persisted": True,
        "determinations_made": False,
    }


__all__ = ["build_cost_exposure"]
