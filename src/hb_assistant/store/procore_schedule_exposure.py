"""Phase 06B schedule exposure read model over local SQLite Procore tables.

Deterministic and **read-only**: classifies the already-emitted open ``procore_action_signals``
from the schedule-bearing domains (RFIs, submittals, schedule activities, meetings, punch,
observations, inspections) into operator-facing *exposure categories* via an explicit
``_SCHEDULE_EXPOSURE_SIGNAL_MAP`` literal table. Each item carries reason codes, the source
endpoint / record key, a normalized due date + overdue status, and a review flag — names / counts
/ redacted text / source-links only. No live Procore access, no writeback, no raw payload values.

This is an intelligence / review aid: it makes **no** delay, entitlement, responsibility, claims,
liability, or schedule-impact determination. It surfaces that a signal *exists*; it never asserts
who caused a delay, how many days are owed, or that a deadline was breached.

Repo-truth note: the package brief lists "daily logs" in the join set, but no daily-log projection
emits action signals in this repo. Rather than fabricate, ``daily_log_delay`` is declared in the
canonical category set (always 0) and reported under ``unsupported_categories`` — mirroring the
overdue model's ``unsupported_due_date_endpoints`` stop-condition surface.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .connection import get_connection
from .procore_action_queue import (
    _IMPORTANCE_RANK,
    _STATUS_NO_DUE,
    _STATUS_OVERDUE,
    _STATUS_RANK,
    _canonical_due,
    _due_status,
    _record_key,
)
from .procore_project_health import _dimensions_for, _parse_iso

# signal_type -> schedule-exposure category. Only schedule-bearing signal types are mapped; any
# signal whose type is absent here is not a schedule-exposure item and is skipped. Kept as an
# explicit, auditable table (not a keyword guess) — the classification of *what* a signal is must
# never depend on free-text parsing.
_SCHEDULE_EXPOSURE_SIGNAL_MAP: Dict[str, str] = {
    # overdue RFIs / submittals
    "rfi_overdue": "overdue_rfi",
    "submittal_overdue": "overdue_submittal",
    # low-float / critical-path schedule activities
    "activity_critical": "critical_or_low_float_activity",
    "activity_zero_float": "critical_or_low_float_activity",
    "activity_constrained": "critical_or_low_float_activity",
    "activity_deadline_variance": "critical_or_low_float_activity",
    # meeting action topics
    "meeting_topic_open_high_priority": "meeting_action_topic",
    # inspections / punch / observations blocking completion
    "inspection_overdue": "inspection_punch_blocking",
    "inspection_has_deficient_items": "inspection_punch_blocking",
    "inspection_has_unanswered_items": "inspection_punch_blocking",
    "inspection_open_safety": "inspection_punch_blocking",
    "punch_overdue": "inspection_punch_blocking",
    "punch_due_tomorrow": "inspection_punch_blocking",
    "punch_assignment_waiting": "inspection_punch_blocking",
    "punch_unresolved_response": "inspection_punch_blocking",
    "observation_open_safety": "inspection_punch_blocking",
    "observation_high_priority": "inspection_punch_blocking",
    # explicit schedule-impact / near-deadline flags carried on other records
    "rfi_schedule_impact_flagged": "schedule_impact_flag",
    "submittal_required_on_site_date_near": "schedule_impact_flag",
    "purchase_order_delivery_due": "schedule_impact_flag",
    "observation_due_soon": "schedule_impact_flag",
}

# categories that always warrant a human look regardless of signal importance.
_HIGH_SENSITIVITY_CATEGORIES = frozenset(
    {"overdue_rfi", "overdue_submittal", "critical_or_low_float_activity", "inspection_punch_blocking"}
)

# canonical category order (all keyed in the summary, 0 when absent). ``daily_log_delay`` is always
# 0 — there is no daily-log signal source — and is echoed under ``unsupported_categories``.
_SCHEDULE_CATEGORIES = (
    "overdue_rfi",
    "overdue_submittal",
    "critical_or_low_float_activity",
    "meeting_action_topic",
    "inspection_punch_blocking",
    "schedule_impact_flag",
    "daily_log_delay",
)

# categories with no signal source in the current projection set (stop-condition surface).
_UNSUPPORTED_CATEGORIES = (
    {"category": "daily_log_delay",
     "reason": "no daily_log action signals emitted by current projections"},
)


def _record_ctx(conn: Any, project_key: str) -> Dict[str, Dict[str, Any]]:
    """record_key -> {review_required, source_url_redacted, canonical_due} (live-record join)."""
    ctx: Dict[str, Dict[str, Any]] = {}
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
        ctx[rk] = {
            "review_required": bool(r["review_required"]),
            "source_url_redacted": r["source_url_redacted"],
            "canonical_due": _canonical_due(r["canonical_json_redacted"]),
        }
    return ctx


def build_schedule_exposure(
    project_key: str,
    *,
    now_utc: str,
    exposure_category: Optional[str] = None,
    importance: Optional[str] = None,
    max_items: int = 50,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Build the deterministic schedule-exposure report (names / counts / refs only)."""
    from .procore_enrichment import get_procore_action_signals

    conn = get_connection(db_path)
    now_dt = _parse_iso(now_utc)
    record_ctx = _record_ctx(conn, project_key)

    items: List[Dict[str, Any]] = []
    for sig in get_procore_action_signals(
        project_key=project_key, signal_status="open", importance=importance, db_path=db_path
    ):
        signal_type = sig.get("signal_type") or ""
        category = _SCHEDULE_EXPOSURE_SIGNAL_MAP.get(signal_type)
        if category is None:
            continue
        rk = sig.get("record_key") or ""
        ctx = record_ctx.get(rk, {})
        sig_importance = sig.get("importance") or "medium"

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
        if status == _STATUS_NO_DUE and sig_importance == "high":
            codes.add("no_due_date_high_importance")
        if "overdue" in signal_type:
            codes.add("overdue_signal_type")

        review_required = bool(ctx.get("review_required", False))
        if review_required:
            codes.add("review_required_record")
        if sig_importance == "high" or category in _HIGH_SENSITIVITY_CATEGORIES:
            review_required = True
            codes.add("review_required_high_sensitivity")

        items.append({
            "exposure_category": category,
            "signal_type": signal_type,
            "endpoint_id": sig.get("endpoint_id"),
            "record_key": rk,
            "due_at_utc": due_str,
            "status": status,
            "days_overdue": days_overdue,
            "importance": sig_importance,
            "owner_entity_key": sig.get("owner_entity_key"),
            "review_required": review_required,
            "reason_codes": sorted(codes),
            "dimensions": _dimensions_for(signal_type),
            "title_redacted": sig.get("title_redacted"),
            "source_url_redacted": ctx.get("source_url_redacted"),
        })

    # --- optional post-classification category filter ---
    if exposure_category is not None:
        items = [it for it in items if it["exposure_category"] == exposure_category]

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

    by_category = {c: 0 for c in _SCHEDULE_CATEGORIES}
    by_importance = {"high": 0, "medium": 0, "low": 0}
    review_required_count = 0
    overdue_count = 0
    for it in items:
        by_category[it["exposure_category"]] = by_category.get(it["exposure_category"], 0) + 1
        by_importance[it["importance"]] = by_importance.get(it["importance"], 0) + 1
        if it["review_required"]:
            review_required_count += 1
        if it["status"] == _STATUS_OVERDUE:
            overdue_count += 1

    return {
        "command": "hb-assistant procore live schedule exposure",
        "ok": True,
        "phase": "Phase 06B Prompt 10",
        "project_key": project_key,
        "generated_at": now_utc,
        "filters": {"exposure_category": exposure_category, "importance": importance},
        "summary": {
            "total": len(items),
            "review_required": review_required_count,
            "overdue": overdue_count,
            "by_category": by_category,
            "by_importance": by_importance,
        },
        "exposure": items[:max_items],
        "exposure_truncated": len(items) > max_items,
        "unsupported_categories": [dict(c) for c in _UNSUPPORTED_CATEGORIES],
        "no_live_call_performed": True,
        "no_raw_values_persisted": True,
        "determinations_made": False,
    }


__all__ = ["build_schedule_exposure"]
