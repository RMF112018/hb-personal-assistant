"""Phase 06B overdue / action-queue read model over local SQLite Procore tables.

Deterministic and **read-only**: turns the already-emitted ``procore_action_signals`` (plus
due dates carried on those signals / canonical records and, where present, financial
amount-fact rows) into a single operational queue of overdue and open work across controls,
financials, schedule, safety/quality, and review-required signals. Names / counts / redacted
text and source-links only — no live Procore access, no writeback, no raw payload values, and
**no determinations** (the queue is an intelligence / review aid; it never decides legal,
claims, financial, safety, entitlement, or schedule impact).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .connection import get_connection
from .procore_project_health import _dimensions_for, _parse_iso

# Canonical-record field names that may carry a normalized due date, tried (in order) only
# when the signal itself has no ``due_at_utc``. Anything that does not parse cleanly is left
# as "no due date"; endpoints with no normalizable due date are reported explicitly under
# ``unsupported_due_date_endpoints`` (stop-condition: document unsupported due-date logic).
_DUE_DATE_FIELDS = (
    "due_date", "due_at", "due_at_utc", "due", "deadline",
    "expected_response_at", "expected_delivery_date", "required_on_site_date",
)

_STATUS_OVERDUE = "overdue"
_STATUS_UPCOMING = "upcoming"
_STATUS_NO_DUE = "no_due_date"

_STATUS_RANK = {_STATUS_OVERDUE: 0, _STATUS_UPCOMING: 1, _STATUS_NO_DUE: 2}
_IMPORTANCE_RANK = {"high": 0, "medium": 1, "low": 2}


def _due_status(
    now_dt: Optional[datetime], due_dt: Optional[datetime]
) -> tuple[str, Optional[int]]:
    """Classify a due date relative to ``now`` (no raise on naive/aware mismatch)."""
    if due_dt is None or now_dt is None:
        return _STATUS_NO_DUE, None
    a, b = now_dt, due_dt
    if (a.tzinfo is None) != (b.tzinfo is None):
        a = a.replace(tzinfo=None)
        b = b.replace(tzinfo=None)
    if b < a:
        return _STATUS_OVERDUE, max((a - b).days, 0)
    return _STATUS_UPCOMING, None


def _record_key(
    project_key: str, endpoint_id: str, parent: Optional[str], record_id: Any
) -> str:
    return "|".join([project_key, endpoint_id, parent or "", str(record_id)])


def _canonical_due(canonical_json: Optional[str]) -> Optional[str]:
    """Best-effort: extract one *normalized* due date (ISO) from a canonical record blob.

    Only the normalized ISO form is ever returned — never the raw field value.
    """
    if not canonical_json:
        return None
    try:
        fields = json.loads(canonical_json)
    except (ValueError, TypeError):
        return None
    if not isinstance(fields, dict):
        return None
    for name in _DUE_DATE_FIELDS:
        parsed = _parse_iso(fields.get(name))
        if parsed is not None:
            return parsed.isoformat()
    return None


def build_overdue_queue(
    project_key: str,
    *,
    now_utc: str,
    importance: Optional[str] = None,
    endpoint_id: Optional[str] = None,
    dimension: Optional[str] = None,
    max_items: int = 50,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Build the deterministic overdue / action queue (names / counts / refs only)."""
    from .procore_enrichment import get_procore_action_signals

    conn = get_connection(db_path)
    now_dt = _parse_iso(now_utc)

    # --- record context: review flag + source link + canonical due-date fallback ---
    record_ctx: Dict[str, Dict[str, Any]] = {}
    for r in conn.execute(
        """
        SELECT endpoint_id, parent_procore_id, procore_record_id, review_required,
               source_url_redacted, canonical_json_redacted
          FROM procore_live_records
         WHERE project_key = ?
        """,
        (project_key,),
    ).fetchall():
        rk = _record_key(
            project_key, r["endpoint_id"], r["parent_procore_id"], r["procore_record_id"]
        )
        record_ctx[rk] = {
            "review_required": bool(r["review_required"]),
            "source_url_redacted": r["source_url_redacted"],
            "canonical_due": _canonical_due(r["canonical_json_redacted"]),
        }

    # --- exposure rows (financial amount facts) keyed by record_key: NAMES + COUNT only ---
    exposure: Dict[str, Dict[str, Any]] = {}
    for r in conn.execute(
        "SELECT record_key, amount_name FROM procore_financial_amount_facts WHERE project_key = ?",
        (project_key,),
    ).fetchall():
        slot = exposure.setdefault(r["record_key"], {"names": set(), "count": 0})
        slot["names"].add(r["amount_name"])
        slot["count"] += 1

    # --- open action signals (reuse the enrichment read model; honor optional filters) ---
    signals = get_procore_action_signals(
        project_key=project_key, signal_status="open", endpoint_id=endpoint_id,
        importance=importance, db_path=db_path,
    )

    items: List[Dict[str, Any]] = []
    for sig in signals:
        signal_type = sig.get("signal_type") or ""
        dims = _dimensions_for(signal_type)
        if dimension and dimension not in dims:
            continue
        rk = sig.get("record_key") or ""
        ctx = record_ctx.get(rk, {})
        # due date: the signal's normalized due date first, canonical-record fallback second.
        due_str = sig.get("due_at_utc") or ctx.get("canonical_due")
        status, days_overdue = _due_status(now_dt, _parse_iso(due_str))

        try:
            raw_codes = json.loads(sig.get("reason_codes_json") or "[]")
        except (ValueError, TypeError):
            raw_codes = []
        codes = {str(c) for c in raw_codes} if isinstance(raw_codes, list) else set()
        if status == _STATUS_OVERDUE:
            codes.add("past_due_date")
        if status == _STATUS_NO_DUE and sig.get("importance") == "high":
            codes.add("no_due_date_high_importance")
        if "overdue" in signal_type:
            codes.add("overdue_signal_type")
        review_required = bool(ctx.get("review_required", False))
        if review_required:
            codes.add("review_required_record")

        exp = exposure.get(rk)
        items.append({
            "signal_type": signal_type,
            "endpoint_id": sig.get("endpoint_id"),
            "record_key": rk,
            "due_at_utc": due_str,
            "status": status,
            "days_overdue": days_overdue,
            "importance": sig.get("importance"),
            "owner_entity_key": sig.get("owner_entity_key"),
            "review_required": review_required,
            "reason_codes": sorted(codes),
            "dimensions": dims,
            "title_redacted": sig.get("title_redacted"),
            "source_url_redacted": ctx.get("source_url_redacted"),
            "exposure_present": exp is not None,
            "exposure_amount_names": sorted(exp["names"]) if exp else [],
            "exposure_fact_count": exp["count"] if exp else 0,
        })

    # --- deterministic ordering: overdue first, most overdue, importance, due, key, type ---
    def _sort_key(it: Dict[str, Any]) -> tuple[Any, ...]:
        return (
            _STATUS_RANK.get(it["status"], 3),
            -(it["days_overdue"] or 0),
            _IMPORTANCE_RANK.get(it.get("importance"), 3),
            it["due_at_utc"] or "9999-12-31T23:59:59+00:00",
            it["record_key"],
            it["signal_type"],
        )

    items.sort(key=_sort_key)

    # --- summary over the filtered set ---
    by_dimension: Dict[str, int] = {}
    for it in items:
        for d in it["dimensions"]:
            by_dimension[d] = by_dimension.get(d, 0) + 1
    summary = {
        "total_open": len(items),
        "overdue": sum(1 for it in items if it["status"] == _STATUS_OVERDUE),
        "upcoming": sum(1 for it in items if it["status"] == _STATUS_UPCOMING),
        "no_due_date": sum(1 for it in items if it["status"] == _STATUS_NO_DUE),
        "high_importance": sum(1 for it in items if it.get("importance") == "high"),
        "review_required": sum(1 for it in items if it["review_required"]),
        "by_dimension": dict(sorted(by_dimension.items())),
    }

    # --- endpoints for which no queued item carried a normalizable due date ---
    endpoints_all: set[str] = set()
    endpoints_with_due: set[str] = set()
    for it in items:
        ep = it["endpoint_id"]
        if ep is None:
            continue
        endpoints_all.add(ep)
        if it["due_at_utc"]:
            endpoints_with_due.add(ep)
    unsupported = sorted(endpoints_all - endpoints_with_due)

    queue_truncated = len(items) > max_items
    return {
        "command": "hb-assistant procore live overdue",
        "ok": True,
        "phase": "Phase 06B Prompt 08",
        "project_key": project_key,
        "generated_at": now_utc,
        "filters": {"importance": importance, "endpoint_id": endpoint_id, "dimension": dimension},
        "summary": summary,
        "queue": items[:max_items],
        "queue_truncated": queue_truncated,
        "unsupported_due_date_endpoints": unsupported,
        "no_live_call_performed": True,
        "no_raw_values_persisted": True,
        "determinations_made": False,
    }


__all__ = ["build_overdue_queue"]
