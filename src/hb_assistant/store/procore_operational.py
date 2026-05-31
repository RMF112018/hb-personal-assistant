"""Phase 06B operational CLI read models — risks roll-up, operator digest, retrieval-readiness
probe, and a no-writeback posture attestation.

All deterministic and **read-only** over local SQLite. ``build_operational_digest`` and
``build_risks`` only re-surface signals/counts the Phase 06B read models already produce;
``build_retrieval_readiness`` and ``build_no_writeback_proof`` are preliminary, contract-stable
commands wired here in Prompt 12 — Prompts 14 (retrieval readiness) and 15 (no-writeback proof)
deepen their logic. No live Procore access, no writeback, no raw payload values, and **no
determinations** (intelligence / review aids only).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from .connection import get_connection

_PHASE = "Phase 06B Prompt 12"

# dimensions that mark a signal as an operational risk even when not high-importance.
_RISK_DIMENSIONS = {"cost_exposure", "schedule_exposure", "safety_quality_compliance", "overdue"}

# the local-only, read-only operator query commands consolidated in Prompt 12.
_QUERY_COMMANDS = (
    "project-health", "stale", "overdue", "risks", "digest",
    "responsible-party-gaps", "relationship-quality",
    "financial exposure", "schedule exposure",
    "retrieval-ready", "no-writeback-proof",
)

# the four code-enforced mailbox read-only layers (see CLAUDE.md runtime guardrails).
_MAILBOX_READ_ONLY_LAYERS = (
    "yaml_scope_policy", "msal_delegated_scope", "python_graph_adapter", "sqlite_check_constraint",
)


def build_risks(
    project_key: str,
    *,
    now_utc: str,
    max_items: int = 25,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Standalone top-risk roll-up over open action signals (high-importance OR risk-dimension)."""
    from .procore_enrichment import get_procore_action_signals
    from .procore_project_health import _dimensions_for

    open_signals = get_procore_action_signals(
        project_key=project_key, signal_status="open", db_path=db_path
    )  # already high-importance-first
    risks: List[Dict[str, Any]] = []
    by_dimension: Dict[str, int] = {}
    high_importance = 0
    for sig in open_signals:
        dims = _dimensions_for(sig.get("signal_type", ""))
        if sig.get("importance") == "high" or (set(dims) & _RISK_DIMENSIONS):
            if sig.get("importance") == "high":
                high_importance += 1
            for d in dims:
                by_dimension[d] = by_dimension.get(d, 0) + 1
            if len(risks) < max_items:
                risks.append({
                    "signal_type": sig.get("signal_type"),
                    "endpoint_id": sig.get("endpoint_id"),
                    "record_key": sig.get("record_key"),
                    "importance": sig.get("importance"),
                    "due_at_utc": sig.get("due_at_utc"),
                    "dimensions": dims,
                    "title_redacted": sig.get("title_redacted"),
                })

    return {
        "command": "hb-assistant procore live risks",
        "ok": True,
        "phase": _PHASE,
        "project_key": project_key,
        "generated_at": now_utc,
        "summary": {
            "total": len(risks),
            "high_importance": high_importance,
            "by_dimension": dict(sorted(by_dimension.items())),
        },
        "risks": risks,
        "risks_truncated": sum(
            1 for s in open_signals
            if s.get("importance") == "high" or (set(_dimensions_for(s.get("signal_type", "")))
                                                 & _RISK_DIMENSIONS)
        ) > len(risks),
        "no_live_call_performed": True,
        "no_raw_values_persisted": True,
        "determinations_made": False,
    }


def build_operational_digest(
    project_key: str,
    *,
    now_utc: str,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Compact operator digest — headline numbers composed from the Phase 06B read models."""
    from .procore_action_queue import build_overdue_queue
    from .procore_cost_exposure import build_cost_exposure
    from .procore_project_health import build_project_health
    from .procore_relationship_quality import (
        build_relationship_quality,
        build_responsible_party_gaps,
    )
    from .procore_schedule_exposure import build_schedule_exposure

    health = build_project_health(project_key, now_utc=now_utc, db_path=db_path)
    overdue = build_overdue_queue(project_key, now_utc=now_utc, db_path=db_path)
    cost = build_cost_exposure(project_key, now_utc=now_utc, db_path=db_path)
    schedule = build_schedule_exposure(project_key, now_utc=now_utc, db_path=db_path)
    gaps = build_responsible_party_gaps(project_key, now_utc=now_utc, db_path=db_path)
    rel = build_relationship_quality(project_key, now_utc=now_utc, db_path=db_path)

    hc = health["counts"]
    return {
        "command": "hb-assistant procore live digest",
        "ok": True,
        "phase": _PHASE,
        "project_key": project_key,
        "generated_at": now_utc,
        "health_status": health["health_status"],
        "status_reason": health["status_reason"],
        "headline": {
            "total_records": hc["total_records"],
            "open_signals": hc["open_signals"],
            "high_importance_signals": hc["high_importance_signals"],
            "review_required_records": hc["review_required_records"],
            "stale_endpoints": health["score_components"]["freshness"]["stale_endpoints"],
            "overdue": overdue["summary"]["overdue"],
            "upcoming": overdue["summary"]["upcoming"],
            "cost_exposure": cost["summary"]["total"],
            "schedule_exposure": schedule["summary"]["total"],
            "responsibility_partial_gaps": gaps["summary"]["partial_gap_relationships"],
            "orphan_records": rel["summary"]["orphan_records"],
            "duplicate_warnings": rel["summary"]["duplicate_warnings"],
        },
        "sources": {
            "project_health": health["phase"],
            "overdue": overdue["phase"],
            "cost_exposure": cost["phase"],
            "schedule_exposure": schedule["phase"],
            "responsible_party_gaps": gaps["phase"],
            "relationship_quality": rel["phase"],
        },
        "no_live_call_performed": True,
        "no_raw_values_persisted": True,
        "determinations_made": False,
    }


def build_retrieval_readiness(
    project_key: str,
    *,
    now_utc: str,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Preliminary, read-only retrieval-corpus probe (Prompt 14 hardens embedding readiness)."""
    conn = get_connection(db_path)

    def _count(sql: str) -> int:
        return int(conn.execute(sql, (project_key,)).fetchone()[0])

    text_total = _count(
        "SELECT COUNT(*) FROM procore_text_intelligence WHERE project_key = ?"
    )
    text_with_actions = _count(
        "SELECT COUNT(*) FROM procore_text_intelligence WHERE project_key = ? "
        "AND action_candidates_json IS NOT NULL AND action_candidates_json != ''"
    )
    records = _count("SELECT COUNT(*) FROM procore_live_records WHERE project_key = ?")
    open_signals = _count(
        "SELECT COUNT(*) FROM procore_action_signals WHERE project_key = ? AND signal_status = 'open'"
    )

    reasons: List[str] = []
    if text_total == 0:
        reasons.append("no_text_intelligence_rows")
    if records == 0:
        reasons.append("no_live_records")
    ready = text_total > 0 and records > 0

    return {
        "command": "hb-assistant procore live retrieval-ready",
        "ok": True,
        "phase": _PHASE,
        "project_key": project_key,
        "generated_at": now_utc,
        "retrieval_ready": ready,
        "reasons": reasons,
        "corpus": {
            "text_intelligence_rows": text_total,
            "text_intelligence_with_action_candidates": text_with_actions,
            "live_records": records,
            "open_action_signals": open_signals,
        },
        "note": "Preliminary readiness probe (Phase 06B Prompt 12). Prompt 14 hardens embedding "
                "readiness over content_embeddings.",
        "no_live_call_performed": True,
        "no_raw_values_persisted": True,
        "determinations_made": False,
    }


def build_no_writeback_proof(
    project_key: Optional[str] = None,
    *,
    now_utc: str,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Preliminary, read-only no-writeback posture attestation (Prompt 15 produces the formal proof)."""
    return {
        "command": "hb-assistant procore live no-writeback-proof",
        "ok": True,
        "phase": _PHASE,
        "project_key": project_key,
        "generated_at": now_utc,
        "checks": {
            "no_m365_writeback": True,
            "no_procore_writeback": True,
            "query_commands_local_sqlite_only": True,
            "no_raw_bodies_persisted": True,
            "mailbox_read_only_layers": list(_MAILBOX_READ_ONLY_LAYERS),
        },
        "query_commands": list(_QUERY_COMMANDS),
        "note": "Preliminary posture attestation (Phase 06B Prompt 12). Prompt 15 produces the "
                "formal no-writeback proof bundle.",
        "no_live_call_performed": True,
        "no_raw_values_persisted": True,
        "determinations_made": False,
    }


__all__ = [
    "build_risks",
    "build_operational_digest",
    "build_retrieval_readiness",
    "build_no_writeback_proof",
]
