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


def _fact(
    *, fact_type: str, source_table: str, source_key: str, endpoint_id: Optional[str],
    attributes: Dict[str, Any], source_link: str, procore_record_id: Optional[str] = None,
) -> Dict[str, Any]:
    """One retrieval-safe fact. Attributes carry only redacted scalars — never raw free text."""
    return {
        "fact_type": fact_type,
        "source_table": source_table,
        "source_key": source_key,
        "endpoint_id": endpoint_id,
        "procore_record_id": procore_record_id,
        "attributes": attributes,
        "source_link": source_link,
    }


def _record_facts(conn: Any, project_key: str) -> tuple[List[Dict[str, Any]], int]:
    """Facts from the redacted scalar columns of procore_live_records.

    ``review_required = 1`` rows are blocked (counted, never emitted); ``canonical_json_redacted``
    free text is never read.
    """
    from .procore_action_queue import _record_key

    facts: List[Dict[str, Any]] = []
    blocked = 0
    for r in conn.execute(
        """
        SELECT endpoint_id, parent_procore_id, procore_record_id, procore_record_number,
               title_redacted, status, updated_at_utc, source_url_redacted, review_required
          FROM procore_live_records
         WHERE project_key = ?
        """,
        (project_key,),
    ).fetchall():
        if bool(r["review_required"]):
            blocked += 1
            continue
        rk = _record_key(
            project_key, r["endpoint_id"], r["parent_procore_id"], r["procore_record_id"]
        )
        facts.append(_fact(
            fact_type="record", source_table="procore_live_records", source_key=rk,
            endpoint_id=r["endpoint_id"], procore_record_id=r["procore_record_id"],
            attributes={
                "number": r["procore_record_number"], "title": r["title_redacted"],
                "status": r["status"], "updated_at": r["updated_at_utc"],
            },
            source_link=r["source_url_redacted"] or f"procore_live_records:{rk}",
        ))
    return facts, blocked


def build_retrieval_readiness(
    project_key: str,
    *,
    now_utc: str,
    max_samples: int = 10,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Retrieval fact manifest (Phase 06B Prompt 14) — retrieval-safe, source-linked Procore facts.

    Read-only. Each fact carries only already-redacted scalar attributes (never raw free text, raw
    payload bodies, or change values) and a source link to its table/key/record. Also reports the
    embedding-corpus readiness probe (carried over from Prompt 12) and blocked-fact reason counts.
    """
    from .procore_cost_exposure import build_cost_exposure
    from .procore_enrichment import get_procore_action_signals
    from .procore_financials import read_financial_amount_facts
    from .procore_history import get_procore_changes
    from .procore_schedule_exposure import build_schedule_exposure

    conn = get_connection(db_path)

    def _count(sql: str) -> int:
        return int(conn.execute(sql, (project_key,)).fetchone()[0])

    # --- corpus readiness probe (preserved from Prompt 12) ---
    text_total = _count("SELECT COUNT(*) FROM procore_text_intelligence WHERE project_key = ?")
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

    # --- fact families (redacted scalars + source links only) ---
    facts, review_blocked = _record_facts(conn, project_key)

    for s in get_procore_action_signals(
        project_key=project_key, signal_status="open", db_path=db_path
    ):
        rk = s.get("record_key") or ""
        facts.append(_fact(
            fact_type="action_signal", source_table="procore_action_signals", source_key=rk,
            endpoint_id=s.get("endpoint_id"),
            attributes={
                "signal_type": s.get("signal_type"), "importance": s.get("importance"),
                "status": s.get("signal_status"), "due_at_utc": s.get("due_at_utc"),
                "title": s.get("title_redacted"),
            },
            source_link=f"procore_action_signals:{rk}",
        ))

    for c in get_procore_changes(project_key=project_key, db_path=db_path):
        # metadata only — old_value_redacted / new_value_redacted / hashes deliberately excluded.
        ceid = c.get("change_event_id") or ""
        facts.append(_fact(
            fact_type="timeline_event", source_table="procore_live_record_change_events",
            source_key=ceid, endpoint_id=c.get("endpoint_id"),
            procore_record_id=c.get("procore_record_id"),
            attributes={
                "detected_at_utc": c.get("detected_at_utc"), "field_path": c.get("field_path"),
                "change_type": c.get("change_type"), "change_category": c.get("change_category"),
                "importance": c.get("importance"),
            },
            source_link=f"procore_live_record_change_events:{ceid}",
        ))

    for src_cmd, items in (
        ("cost_exposure",
         build_cost_exposure(project_key, now_utc=now_utc, db_path=db_path)["exposure"]),
        ("schedule_exposure",
         build_schedule_exposure(project_key, now_utc=now_utc, db_path=db_path)["exposure"]),
    ):
        for it in items:
            rk = it.get("record_key") or ""
            facts.append(_fact(
                fact_type="exposure", source_table=f"read_model:{src_cmd}", source_key=rk,
                endpoint_id=it.get("endpoint_id"),
                attributes={  # no amounts inline (carried as dedicated amount facts)
                    "exposure": it.get("exposure_type") or it.get("exposure_category"),
                    "importance": it.get("importance"), "due_at_utc": it.get("due_at_utc"),
                    "reason_codes": it.get("reason_codes"),
                },
                source_link=it.get("source_url_redacted") or f"{src_cmd}:{rk}",
            ))

    for a in read_financial_amount_facts(project_key=project_key, db_path=db_path):
        rk = a.get("record_key") or ""
        facts.append(_fact(
            fact_type="amount", source_table="procore_financial_amount_facts", source_key=rk,
            endpoint_id=a.get("endpoint_id"),
            attributes={  # amount_value is decimal-safe TEXT (never float-coerced)
                "amount_name": a.get("amount_name"), "amount_value": a.get("amount_value"),
                "currency_iso_code": a.get("currency_iso_code"),
            },
            source_link=f"procore_financial_amount_facts:{rk}",
        ))

    # --- deterministic ordering + tallies ---
    facts.sort(key=lambda f: (f["fact_type"], f["endpoint_id"] or "", f["source_key"]))
    by_fact_type = {t: 0 for t in
                    ("record", "action_signal", "timeline_event", "exposure", "amount")}
    by_endpoint: Dict[str, int] = {}
    no_source_link = 0
    for f in facts:
        by_fact_type[f["fact_type"]] = by_fact_type.get(f["fact_type"], 0) + 1
        ep = f["endpoint_id"] or "unknown"
        by_endpoint[ep] = by_endpoint.get(ep, 0) + 1
        if not f["source_link"]:
            no_source_link += 1

    manifest = {
        "total_facts": len(facts),
        "by_fact_type": by_fact_type,
        "by_endpoint": dict(sorted(by_endpoint.items())),
        "review_required_blocked": review_blocked,
        "blocked_by_reason": {
            "review_required": review_blocked,
            "free_text_field": 0,
            "no_source_link": no_source_link,
        },
        "samples": facts[:max_samples],
        "samples_truncated": len(facts) > max_samples,
    }

    return {
        "command": "hb-assistant procore live retrieval-ready",
        "ok": True,
        "phase": "Phase 06B Prompt 14",
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
        "manifest": manifest,
        "note": "Retrieval fact manifest (Phase 06B Prompt 14) — redacted scalar facts only; raw "
                "free text, payload bodies, and change values are never embedded. Source-linked to "
                "table/key/record. `retrieval_ready` reflects embedding-corpus readiness.",
        "no_live_call_performed": True,
        "no_raw_values_persisted": True,
        "determinations_made": False,
    }


__all__ = [
    "build_risks",
    "build_operational_digest",
    "build_retrieval_readiness",
]
