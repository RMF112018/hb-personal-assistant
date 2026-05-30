"""Phase 06B project-health read model over local SQLite Procore tables.

Deterministic and **read-only**: aggregates freshness, open work, review-required items,
cost / schedule / safety-quality-compliance signal COUNTS, and relationship-quality
indicators into a names/counts-only health report. No live Procore access, no writeback,
no raw payload values, and **no determinations** — every dimension is a count of
pre-existing signals/flags, surfaced as an intelligence/review aid. Review-required and
high-risk facts are always listed explicitly (never hidden behind a single score).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .connection import get_connection

# signal_type -> health dimension (substring keywords). A signal may match multiple
# lenses; counts are per-dimension and are never summed into one opaque number.
_DIMENSION_KEYWORDS: Dict[str, tuple[str, ...]] = {
    "cost_exposure": (
        "cost_impact", "cost_exposure", "budget_variance_negative", "budget_actual_exceeds",
        "budget_forecast_exceeds", "retainage_held", "payment_due", "unpaid",
        "payment_application_pending",
    ),
    "schedule_exposure": (
        "schedule_impact", "activity_critical", "activity_zero_float", "activity_constrained",
        "activity_deadline_variance", "delivery_due",
    ),
    "safety_quality_compliance": (
        "safety", "deficient", "non_conforming", "_failed", "non_compliant",
        "insurance_not_compliant", "compliance_document_expiring",
    ),
    "overdue": ("overdue",),
}

_RESPONSIBILITY_EDGE_TYPES = ("responsible_contractor", "assignee", "ball_in_court")
_STATUS_NO_DATA = "no_data"
_STATUS_REVIEW = "review_recommended"
_STATUS_MONITOR = "monitor"
_STATUS_CURRENT = "current"


def _open(db_path: Optional[Path]) -> sqlite3.Connection:
    return get_connection(db_path)


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _age_days(now: Optional[datetime], then: Optional[datetime]) -> Optional[int]:
    if now is None or then is None:
        return None
    return (now - then).days


def _dimensions_for(signal_type: str) -> List[str]:
    return [dim for dim, kws in _DIMENSION_KEYWORDS.items() if any(k in signal_type for k in kws)]


def build_project_health(
    project_key: str,
    *,
    now_utc: str,
    stale_days: int = 7,
    db_path: Optional[Path] = None,
    max_items: int = 25,
) -> Dict[str, Any]:
    """Build the deterministic project-health report (names / counts / refs only)."""
    conn = _open(db_path)
    now_dt = _parse_iso(now_utc)

    # --- open action signals (reuse the enrichment read model) ---
    from .procore_enrichment import get_procore_action_signals

    open_signals = get_procore_action_signals(
        project_key=project_key, signal_status="open", db_path=db_path
    )
    high_importance = [s for s in open_signals if s.get("importance") == "high"]

    breakdown: Dict[str, Dict[str, int]] = {dim: {} for dim in _DIMENSION_KEYWORDS}
    dim_counts: Dict[str, int] = {dim: 0 for dim in _DIMENSION_KEYWORDS}
    for sig in open_signals:
        for dim in _dimensions_for(sig.get("signal_type", "")):
            dim_counts[dim] += 1
            st = sig["signal_type"]
            breakdown[dim][st] = breakdown[dim].get(st, 0) + 1

    # --- review-required records (explicit, never hidden; names/refs only) ---
    rr_total = conn.execute(
        "SELECT COUNT(*) FROM procore_live_records WHERE project_key = ? AND review_required = 1",
        (project_key,),
    ).fetchone()[0]
    review_required_items = [
        {
            "endpoint_id": r["endpoint_id"],
            "procore_record_id": r["procore_record_id"],
            "sensitive_reason": r["sensitive_reason"],
            "source_url_redacted": r["source_url_redacted"],
        }
        for r in conn.execute(
            """
            SELECT endpoint_id, procore_record_id, sensitive_reason, source_url_redacted
              FROM procore_live_records
             WHERE project_key = ? AND review_required = 1
             ORDER BY endpoint_id, procore_record_id
             LIMIT ?
            """,
            (project_key, max_items),
        ).fetchall()
    ]

    # --- counts ---
    total_records = conn.execute(
        "SELECT COUNT(*) FROM procore_live_records WHERE project_key = ?", (project_key,)
    ).fetchone()[0]
    endpoints_with_data = conn.execute(
        "SELECT COUNT(DISTINCT endpoint_id) FROM procore_live_records WHERE project_key = ?",
        (project_key,),
    ).fetchone()[0]
    amount_fact_count = conn.execute(
        "SELECT COUNT(*) FROM procore_financial_amount_facts WHERE project_key = ?", (project_key,)
    ).fetchone()[0]

    # --- freshness / stale endpoints (from watermarks) ---
    watermarks = conn.execute(
        """
        SELECT endpoint_id, last_success_at_utc
          FROM procore_live_sync_watermarks
         WHERE project_key = ?
         ORDER BY endpoint_id
        """,
        (project_key,),
    ).fetchall()
    stale_endpoints: List[Dict[str, Any]] = []
    for w in watermarks:
        age = _age_days(now_dt, _parse_iso(w["last_success_at_utc"]))
        if w["last_success_at_utc"] is None:
            stale_endpoints.append(
                {"endpoint_id": w["endpoint_id"], "last_success_at_utc": None,
                 "age_days": None, "state": "never_synced"}
            )
        elif age is not None and age > stale_days:
            stale_endpoints.append(
                {"endpoint_id": w["endpoint_id"], "last_success_at_utc": w["last_success_at_utc"],
                 "age_days": age, "state": "stale"}
            )

    # --- relationship quality ---
    record_key_expr = (
        "(lr.project_key || '|' || lr.endpoint_id || '|' || lr.parent_procore_id "
        "|| '|' || lr.procore_record_id)"
    )
    placeholders = ", ".join("?" for _ in _RESPONSIBILITY_EDGE_TYPES)
    missing_resp = conn.execute(
        f"""
        SELECT COUNT(*) FROM procore_live_records lr
         WHERE lr.project_key = ?
           AND NOT EXISTS (
             SELECT 1 FROM procore_record_edges e
              WHERE e.project_key = lr.project_key
                AND e.from_record_key = {record_key_expr}
                AND e.edge_type IN ({placeholders})
           )
        """,
        (project_key, *_RESPONSIBILITY_EDGE_TYPES),
    ).fetchone()[0]
    distinct_responsible = conn.execute(
        """
        SELECT COUNT(DISTINCT to_entity_key) FROM procore_record_edges
         WHERE project_key = ? AND edge_type = 'responsible_contractor'
           AND to_entity_key IS NOT NULL
        """,
        (project_key,),
    ).fetchone()[0]

    # --- top risks (explicit; high importance OR exposure/overdue/safety lens) ---
    exposure_dims = {"cost_exposure", "schedule_exposure", "safety_quality_compliance", "overdue"}
    top_risks: List[Dict[str, Any]] = []
    for sig in open_signals:  # already ordered high-importance-first by the read model
        dims = _dimensions_for(sig.get("signal_type", ""))
        if sig.get("importance") == "high" or (set(dims) & exposure_dims):
            top_risks.append(
                {
                    "signal_type": sig.get("signal_type"),
                    "endpoint_id": sig.get("endpoint_id"),
                    "record_key": sig.get("record_key"),
                    "importance": sig.get("importance"),
                    "due_at_utc": sig.get("due_at_utc"),
                    "dimensions": dims,
                    "title_redacted": sig.get("title_redacted"),
                }
            )
        if len(top_risks) >= max_items:
            break

    # --- deterministic triage status (a label, not a determination) ---
    triggers: List[str] = []
    if rr_total > 0:
        triggers.append("review_required_records")
    if high_importance:
        triggers.append("high_importance_signals")
    if dim_counts["safety_quality_compliance"] > 0:
        triggers.append("safety_quality_compliance_signals")
    if dim_counts["overdue"] > 0:
        triggers.append("overdue_signals")
    if stale_endpoints:
        triggers.append("stale_endpoints")

    if total_records == 0 and not open_signals:
        health_status = _STATUS_NO_DATA
    elif triggers:
        health_status = _STATUS_REVIEW
    elif open_signals:
        health_status = _STATUS_MONITOR
    else:
        health_status = _STATUS_CURRENT

    return {
        "command": "hb-assistant procore live project-health",
        "ok": True,
        "phase": "Phase 06B Prompt 06",
        "project_key": project_key,
        "generated_at": now_utc,
        "health_status": health_status,
        "status_reason": triggers or ["no_triggers"],
        "score_components": {
            "freshness": {
                "endpoints_with_data": endpoints_with_data,
                "endpoints_synced": len(watermarks),
                "stale_endpoints": len(stale_endpoints),
                "stale_threshold_days": stale_days,
            },
            "open_work": {"open_signals": len(open_signals), "high_importance": len(high_importance)},
            "review_required": {"records": rr_total},
            "cost_exposure": {"open_signals": dim_counts["cost_exposure"]},
            "schedule_exposure": {"open_signals": dim_counts["schedule_exposure"]},
            "safety_quality_compliance": {"open_signals": dim_counts["safety_quality_compliance"]},
            "overdue": {"open_signals": dim_counts["overdue"]},
            "relationship_quality": {
                "records_missing_responsibility_edge": missing_resp,
                "distinct_responsible_parties": distinct_responsible,
            },
        },
        "counts": {
            "total_records": total_records,
            "review_required_records": rr_total,
            "open_signals": len(open_signals),
            "high_importance_signals": len(high_importance),
            "endpoints_with_data": endpoints_with_data,
            "financial_amount_facts": amount_fact_count,
        },
        "dimension_signal_breakdown": breakdown,
        "top_risks": top_risks,
        "stale_endpoints": stale_endpoints,
        "review_required_items": review_required_items,
        "review_required_items_truncated": rr_total > len(review_required_items),
        "evidence_references": {
            "review_required_sources": [
                i["source_url_redacted"] for i in review_required_items if i["source_url_redacted"]
            ],
        },
        "no_raw_values_persisted": True,
        "no_live_call_performed": True,
        "determinations_made": False,
    }


__all__ = ["build_project_health"]
